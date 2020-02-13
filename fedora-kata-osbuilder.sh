#!/bin/bash

# This script builds the kata appliance initrd and image. It is invoked
# at RPM install %post time and via kata-osbuilder-generate.service

set -e

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || die "$0: must be run as root"


IMAGE_TOPDIR="/var/cache/kata-containers"
KVERSION=`uname -r`
IMAGE_DIR="${IMAGE_TOPDIR}/osbuilder-images/$KVERSION"
KERNEL_PATH=""
for VMNAME in vmlinuz vmlinux; do
    TRYPATH="/lib/modules/$KVERSION/$VMNAME"
    if [ -e "$TRYPATH" ] ; then
        KERNEL_PATH="$TRYPATH"
        break
    fi
done

[ -z "$KERNEL_PATH" ] && die "$0: Didn't find kernel path for version=$KVERSION"


cd /usr/libexec/kata-containers/osbuilder

DRACUT_OVERLAY=`mktemp --directory -t kata-dracut-overlay-XXXXXX`
DRACUT_ROOTFS=`mktemp --directory -t kata-dracut-rootfs-XXXXXX`
DRACUT_IMAGES=`mktemp --directory -t kata-dracut-images-XXXXXX`
trap "{ rm -rf ${DRACUT_OVERLAY} ${DRACUT_ROOTFS} ${DRACUT_IMAGES}; }" EXIT


export AGENT_SOURCE_BIN="/usr/libexec/kata-containers/osbuilder/agent/kata-agent"
TARGET_IMAGE="${DRACUT_IMAGES}/kata-containers.img" \
TARGET_INITRD="${DRACUT_IMAGES}/kata-containers-initrd.img" \
OSBUILDER_VERSION="fedora-osbuilder-version-unknown"
DRACUT_CONF_DIR="./dracut/dracut.conf.d"
DRACUT_KMODULES=`source ${DRACUT_CONF_DIR}/10-drivers.conf; echo "$drivers"`
DRACUT_OPTIONS="--no-compress --conf /dev/null --confdir ./dracut/dracut.conf.d"

# Build the dracut overlay fs
./rootfs-builder/rootfs.sh -o ${OSBUILDER_VERSION} -r ${DRACUT_OVERLAY}
mkdir -p ${DRACUT_OVERLAY}/etc/modules-load.d
echo ${DRACUT_KMODULES} | tr " " "\n" > ${DRACUT_OVERLAY}/etc/modules-load.d/kata-modules.conf

# Build the initrd
dracut ${DRACUT_OPTIONS} \
    --include ${DRACUT_OVERLAY} \
    / ${TARGET_INITRD} ${KVERSION}

# Extract initrd filesystem for image build
cat ${TARGET_INITRD} | \
    cpio --extract --preserve-modification-time --make-directories --directory=${DRACUT_ROOTFS}

# Build the FS image
./image-builder/image_builder.sh -o ${TARGET_IMAGE} ${DRACUT_ROOTFS}

# This is a workaround till issue[0] is fixed, released and packaged.
# [0]: https://github.com/kata-containers/osbuilder/issues/394
rm image-builder/nsdax

# Move images into place
cd /var/cache/kata-containers
# This is dangerous, but not sure what else to do...
rm vmlinu* kata-*.img fedora-kata*.img fedora-kata*.initrd || true

INITRD_NAME="fedora-kata-${KVERSION}.initrd"
IMAGE_NAME="fedora-kata-${KVERSION}.img"

ln -sf ${KERNEL_PATH} vmlinuz.container

mv ${TARGET_INITRD} ${INITRD_NAME}
ln -sf ${INITRD_NAME} kata-containers-initrd.img

mv ${TARGET_IMAGE} ${IMAGE_NAME}
ln -sf ${IMAGE_NAME} kata-containers.img
