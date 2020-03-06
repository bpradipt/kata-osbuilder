#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

[ -n "${DEBUG:-}" ] && set -o xtrace

readonly IMAGE_TOPDIR="/var/cache/kata-containers"
readonly KERNEL_SYMLINK="${IMAGE_TOPDIR}/vmlinuz.container"
readonly SCRIPTNAME="$0"

readonly DRACUT_ROOTFS=`mktemp --directory -t kata-dracut-rootfs-XXXXXX`
readonly DRACUT_IMAGES=`mktemp --directory -t kata-dracut-images-XXXXXX`
trap exit_handler EXIT

readonly GENERATED_IMAGE="${DRACUT_IMAGES}/kata-containers.img"
readonly GENERATED_INITRD="${DRACUT_IMAGES}/kata-containers-initrd.img"


KVERSION=`uname -r`
KERNEL_PATH=""
COMMAND=""
OSBUILDER_DIR="/usr/libexec/kata-containers/osbuilder"

# rpm %check sets this to run the script without overwriting host
# content, and not requiring root
TEST_MODE="${TEST_MODE:-}"


die()
{
    error "$*"
    exit 1
}


error()
{
    echo "ERROR: ${SCRIPTNAME}: $*" >&2
}


info()
{
    echo "${SCRIPTNAME}: $*"
}


exit_handler()
{
    rm -rf "${DRACUT_ROOTFS}" "${DRACUT_IMAGES}"
}


usage()
{
    cat <<EOT

Usage: ${SCRIPTNAME} [options]

This script builds the kata appliance initrd and image and adds
stable symlink paths in ${IMAGE_TOPDIR}

This script is called at kata-osbuilder at RPM install %post time and
via kata-osbuilder-generate.service

Options:
  -h            Show this help message

  -c            Check if an initrd is already generated for the current
                kernel, and if so, simply exit

  -k            Manually specify kernel version to use. Default comes
                from uname. Default: ${KVERSION}

  -o DIRNAME    Use the passed directory for osbuilder code. Point
                To a git checkout if you want to use upstream osbuilder.
                Default: ${OSBUILDER_DIR}

EOT

    exit $1
}


parse_args()
{
    while getopts "chk:o:" opt
    do
        case $opt in
            c) COMMAND="check" ;;
            h) usage 0 ;;
            o) OSBUILDER_DIR="${OPTARG}" ;;
            k) KVERSION="${OPTARG}" ;;
            *) usage 1 ;;
        esac
    done
    shift $(($OPTIND - 1))

    if [ -n "$*" ]; then
        error "Unhandled options: '$*'"
        usage 1
    fi
}


find_host_kernel_path()
{
    local modpath="/lib/modules/$KVERSION/"
    [ ! -e "$modpath" ] && die "version=$KVERSION path=$modpath does not exist"

    local vmname
    for vmname in vmlinuz vmlinux; do
        local trypath="$modpath/$vmname"
        if [ -e "$trypath" ] ; then
            KERNEL_PATH="$trypath"
            break
        fi
    done

    [ -z "$KERNEL_PATH" ] && die "Didn't find vmlinu* path in $modpath"

    if [ "$COMMAND" = "check" ]; then
        local linked_kernel=$(readlink -n "${KERNEL_SYMLINK}" || :)
        if [ "${KERNEL_PATH}" = "${linked_kernel}" ] ; then
            info "symlink=${KERNEL_SYMLINK} already points to host kernel=${KERNEL_PATH}"
            info "Nothing to generate. Exiting."
            exit 0
        fi
    fi
}


generate_modules_load_conf()
{
    # Write the modules-load file from all driver .ko.* files in the initrd
    local loadfile="${DRACUT_ROOTFS}/etc/modules-load.d/kata-modules.conf"
    mkdir -p $(dirname $loadfile)

    local modpath
    for modpath in `find ${DRACUT_ROOTFS} -path \*lib/modules/\*\.ko\*`; do
        local name=$(echo $(basename ${modpath}) | cut -d '.' -f 1)
        echo "${name}" >> $loadfile
    done
}


generate_rootfs()
{
    # To generate the rootfs, we build an initrd with dracut, extract
    # the initrd content, and then discard the initrd. We then rebuild
    # the initrd using the osbuilder native scripts.
    #
    # This is a bit wasteful, but it's the easiest way to work around
    # obuilder script inflexibility for now, which expect that some rootfs.sh
    # code is called on a fully populated distro root.

    local agent_dir="/usr/libexec/kata-containers/osbuilder/agent"
    if [ -n "${TEST_MODE}" ] ; then
        agent_dir="${OSBUILDER_DIR}/agent"
        nsdax_bin="${OSBUILDER_DIR}/nsdax"
    fi

    local agent_source_bin="${agent_dir}/usr/bin/kata-agent"
    local osbuilder_version="fedora-osbuilder-version-unknown"
    local dracut_conf_dir="./dracut/dracut.conf.d"
    local tmp_initrd=`mktemp --tmpdir=${DRACUT_IMAGES}`
    unlink "$tmp_initrd"

    # Build the initrd
    echo -e "+ Building dracut initrd"
    dracut  \
        --confdir "${dracut_conf_dir}" \
        --no-compress \
        --conf /dev/null \
        ${tmp_initrd} ${KVERSION}

    # Extract the generated rootfs
    echo "+ Extracting dracut initrd rootfs"
    cat ${tmp_initrd} | \
        cpio --extract --preserve-modification-time --make-directories --directory=${DRACUT_ROOTFS}

    # Using the busybox dracut module sets /sbin/init -> busybox
    # We don't want that. Reset it to systemd
    ln -sf ../lib/systemd/systemd ${DRACUT_ROOTFS}/usr/sbin/init

    echo "+ Copying agent directory tree into place"
    cp -ar ${agent_dir}/* ${DRACUT_ROOTFS}

    # Make kata specific adjustments to our rootfs
    echo "Calling osbuilder rootfs.sh on extracted rootfs"
    AGENT_SOURCE_BIN="${agent_source_bin}" \
        ./rootfs-builder/rootfs.sh \
        -o ${osbuilder_version} \
        -r ${DRACUT_ROOTFS}

    # Generate modules-load.d file
    generate_modules_load_conf
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
    parse_args $*

    if [ -z "${TEST_MODE}" ]; then
        [ "$(id -u)" -eq 0 ] || die "$0: must be run as root"
    fi

    find_host_kernel_path

    cd "${OSBUILDER_DIR}"

    # Generate the rootfs using dracut
    generate_rootfs

    if [ -n "${TEST_MODE}" ]; then
        echo "+ Exiting TEST_MODE successfully"
        return
    fi

    # Build the initrd
    echo "+ Calling osbuilder initrd_builder.sh"
    ./initrd-builder/initrd_builder.sh -o ${GENERATED_INITRD} ${DRACUT_ROOTFS}

    # Build the FS image
    local nsdax_bin="/usr/libexec/kata-containers/osbuilder/nsdax"
    echo "+ Calling osbuilder image_builder.sh"
    NSDAX_BIN="${nsdax_bin}" \
        ./image-builder/image_builder.sh \
        -o ${GENERATED_IMAGE} ${DRACUT_ROOTFS}

    move_images
}


main $*
