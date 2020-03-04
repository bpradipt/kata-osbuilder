#!/bin/bash

# This script builds the kata appliance initrd and image. It is invoked
# at RPM install %post time and via kata-osbuilder-generate.service

set -o errexit
set -o nounset
set -o pipefail

[ -n "${DEBUG:-}" ] && set -o xtrace

readonly IMAGE_TOPDIR="/var/cache/kata-containers"
readonly KERNEL_SYMLINK="${IMAGE_TOPDIR}/vmlinuz.container"
readonly KVERSION=`uname -r`
readonly SCRIPTNAME="$0"

readonly DRACUT_OVERLAY=`mktemp --directory -t kata-dracut-overlay-XXXXXX`
readonly DRACUT_ROOTFS=`mktemp --directory -t kata-dracut-rootfs-XXXXXX`
readonly DRACUT_IMAGES=`mktemp --directory -t kata-dracut-images-XXXXXX`
trap exit_handler EXIT

readonly GENERATED_IMAGE="${DRACUT_IMAGES}/kata-containers.img"
readonly GENERATED_INITRD="${DRACUT_IMAGES}/kata-containers-initrd.img"


KERNEL_PATH=""
COMMAND=""


die()
{
    echo "ERROR: ${SCRIPTNAME}: $*" >&2
    exit 1
}


info()
{
    echo "${SCRIPTNAME}: $*"
}


exit_handler()
{
    rm -rf "${DRACUT_OVERLAY}" "${DRACUT_ROOTFS}" "${DRACUT_IMAGES}"
}


parse_args()
{
    COMMAND="${1:-}"
    [ -z "$COMMAND" ] && COMMAND="check"
    [ "$COMMAND" != "check" ] && [ "$COMMAND" != "regenerate" ] && die "Unknown command=$COMMAND"
    return 0
}


find_host_kernel_path()
{
    local vmname
    for vmname in vmlinuz vmlinux; do
        local trypath="/lib/modules/$KVERSION/$vmname"
        if [ -e "$trypath" ] ; then
            KERNEL_PATH="$trypath"
            break
        fi
    done

    [ -z "$KERNEL_PATH" ] && die "Didn't find kernel path for version=$KVERSION"

    if [ "regenerate" != "$COMMAND" ]; then
        local linked_kernel=$(readlink -n "${KERNEL_SYMLINK}" || :)
        if [ "${KERNEL_PATH}" = "${linked_kernel}" ] ; then
            info "symlink=${KERNEL_SYMLINK} already points to host kernel=${KERNEL_PATH}"
            info "Nothing to generate. Exiting."
            exit 0
        fi
    fi
}


move_images()
{
    # Move images into place
    local image_osbuilder_dir="${IMAGE_TOPDIR}/osbuilder-images"
    local image_dir="${image_osbuilder_dir}/$KVERSION"
    local initrd_dest_path="${image_dir}/fedora-kata-${KVERSION}.initrd"
    local image_dest_path="${image_dir}/fedora-kata-${KVERSION}.img"

    # This blows away the entire osbuilder-images/ dir, deleting any
    # previously cached content
    rm -rf "${image_osbuilder_dir}"
    mkdir -p "${image_dir}"

    ln -sf ${KERNEL_PATH} ${KERNEL_SYMLINK}

    mv ${GENERATED_INITRD} ${initrd_dest_path}
    ln -sf ${initrd_dest_path} ${IMAGE_TOPDIR}/kata-containers-initrd.img

    mv ${GENERATED_IMAGE} ${image_dest_path}
    ln -sf ${image_dest_path} ${IMAGE_TOPDIR}/kata-containers.img
}


main()
{
    [ "$(id -u)" -eq 0 ] || die "$0: must be run as root"

    parse_args $*
    find_host_kernel_path

    cd /usr/libexec/kata-containers/osbuilder

    export AGENT_SOURCE_BIN="/usr/libexec/kata-containers/osbuilder/agent/kata-agent"
    local osbuilder_version="fedora-osbuilder-version-unknown"
    local dracut_conf_dir="./dracut/dracut.conf.d"
    local dracut_kmodules=`source ${dracut_conf_dir}/10-drivers.conf; echo "$drivers"`

    # Build the dracut overlay fs
    ./rootfs-builder/rootfs.sh -o ${osbuilder_version} -r ${DRACUT_OVERLAY}
    mkdir -p ${DRACUT_OVERLAY}/etc/modules-load.d
    echo ${dracut_kmodules} | tr " " "\n" > ${DRACUT_OVERLAY}/etc/modules-load.d/kata-modules.conf

    # Build the initrd
    dracut  \
        --no-compress \
        --conf /dev/null \
        --confdir ${dracut_conf_dir} \
        --include ${DRACUT_OVERLAY} \
        / ${GENERATED_INITRD} ${KVERSION}

    # Extract initrd filesystem for image build
    cat ${GENERATED_INITRD} | \
        cpio --extract --preserve-modification-time --make-directories --directory=${DRACUT_ROOTFS}

    # Build the FS image
    ./image-builder/image_builder.sh -o ${GENERATED_IMAGE} ${DRACUT_ROOTFS}

    # This is a workaround till issue[0] is fixed, released and packaged.
    # [0]: https://github.com/kata-containers/osbuilder/issues/394
    rm image-builder/nsdax

    move_images
}


main $*
