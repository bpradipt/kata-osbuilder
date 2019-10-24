#!/bin/bash

# This script builds the kata appliance initrd and image. It is invoked
# at RPM install %post time.

set -e
set -x

cd /usr/libexec/kata-containers/osbuilder

KVERSION=`uname -r`
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

# Move images into place
cd /usr/share/kata-containers
# This is dangerous, but not sure what else to do...
rm vmlinu* kata-*.img fedora-kata*.img fedora-kata*.initrd || true

KERNEL_NAME="vmlinuz-${KVERSION}"
INITRD_NAME="fedora-kata-${KVERSION}.initrd"
IMAGE_NAME="fedora-kata-${KVERSION}.img"

cp /boot/${KERNEL_NAME} .
ln -sf ${KERNEL_NAME} vmlinuz.container

mv ${TARGET_INITRD} ${INITRD_NAME}
ln -sf ${INITRD_NAME} kata-containers-initrd.img

mv ${TARGET_IMAGE} ${IMAGE_NAME}
ln -sf ${IMAGE_NAME} kata-containers.img
