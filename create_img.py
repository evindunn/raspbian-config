#!/usr/bin/env python3

import sys
from uuid import uuid4

from pychroot import Chroot
from lib.debootstrap import debootstrap
from lib.system import *
from lib.network import *
from lib.disk import (
    dd,
    losetup_create,
    losetup_delete,
    create_partition_table,
    create_partition,
    format_partition,
    mount_device,
    unmount_device,
    get_partition_uuid
)

LOG_FMT_MSG = "[%(asctime)s][%(levelname)s] %(message)s"
LOG_FMT_DATE = "%H:%M:%S %Y-%m-%d"

PKG_KERNEL = "linux-image-arm64"
PKG_INCLUDES = [
    "aptitude",
    "dbus",
    "dialog",
    "dosfstools",
    "firmware-brcm80211",
    "firmware-realtek",
    "iproute2",
    "locales",
    "parted",
    "python-apt",       # For ansible
    "python",           # For ansible
    "python-selinux",   # For ansible
    "raspi3-firmware",
    "rng-tools5",
    "systemd",
    "systemd-sysv",
    "ssh",
    "vim",
    "wireless-tools",
    "wpasupplicant"
]

FILE_IMG_DEFAULT = "debian-stable-arm64.img"
PATH_MOUNT = "/mnt"
FILE_STATUS = ".status"
FILE_RESIZE_PART = "/usr/local/bin/expand-root-partition"

SCRIPT_RESIZE_ROOTFS = """
#/bin/bash

parted -s /dev/mmcblk0p2 resizepart 1 100%
resize2fs /dev/mmcblk0p2
""".strip()


def main():
    logging.basicConfig(
        format=LOG_FMT_MSG,
        datefmt=LOG_FMT_DATE,
        level="INFO"
    )

    if os.path.exists(FILE_IMG_DEFAULT):
        os.remove(FILE_IMG_DEFAULT)

    # Create image file
    logging.info("Creating {}...".format(FILE_IMG_DEFAULT))
    if not dd("/dev/zero", FILE_IMG_DEFAULT, "1M", 2048):
        logging.error("Failed to create {}. Exiting.".format(FILE_IMG_DEFAULT))
        return 1

    # Create a loop device from the image file
    logging.info("Creating a loop device from {}...".format(FILE_IMG_DEFAULT))
    loop_device = losetup_create(FILE_IMG_DEFAULT)
    if loop_device is None:
        logging.error("Failed to create a loop device from {}. Exiting.".format(FILE_IMG_DEFAULT))
        return 1

    # Create partition table
    logging.info("Creating partition table on {}...".format(loop_device))
    if not create_partition_table(loop_device):
        logging.error("Failed to create partition table on {}. Exiting.".format(loop_device))
        losetup_delete(loop_device)
        return 1

    # Create boot partition
    logging.info("Creating boot partition {}...".format(loop_device))
    if not create_partition(loop_device, "fat32", "0%", "256M"):
        logging.error("Failed to create boot partition on {}. Exiting.".format(loop_device))
        losetup_delete(loop_device)
        return 1

    # Create root partition
    logging.info("Creating root partition {}...".format(loop_device))
    if not create_partition(loop_device, "ext4", "256M", "100%"):
        logging.error("Failed to create root partition on {}. Exiting.".format(loop_device))
        losetup_delete(loop_device)
        return 1

    # Format boot partition
    logging.info("Formatting boot partition...")
    if not format_partition("{}p1".format(loop_device), "vfat"):
        logging.error("Failed to format boot partition on {}. Exiting.".format(loop_device))
        losetup_delete(loop_device)
        return 1

    # Format root partition
    logging.info("Formatting root partition...")
    if not format_partition("{}p2".format(loop_device), "ext4"):
        logging.error("Failed to format root partition on {}. Exiting.".format(loop_device))
        losetup_delete(loop_device)
        return 1

    # Get partition uuids
    boot_partition_uuid = get_partition_uuid("{}p1".format(loop_device))
    root_partition_uuid = get_partition_uuid("{}p2".format(loop_device))

    if boot_partition_uuid is None or root_partition_uuid is None:
        logging.error("Failed to retrieve partition UUIDs. Exiting.".format(loop_device))
        losetup_delete(loop_device)
        return 1

    # Mount the root partition
    logging.info("Mounting root partition on {}...".format(PATH_MOUNT))
    if not mount_device("UUID={}".format(root_partition_uuid), PATH_MOUNT):
        logging.error("Failed to mount root partition. Exiting.")
        losetup_delete(loop_device)
        return 1

    # Mount the boot partition
    boot_mount_path = os.path.join(PATH_MOUNT, "boot", "firmware")
    logging.info("Mounting boot partition on {}...".format(boot_mount_path))
    os.makedirs(boot_mount_path, mode=0o755, exist_ok=True)
    if not mount_device("UUID={}".format(boot_partition_uuid), boot_mount_path):
        logging.error("Failed to mount boot partition. Exiting.")
        unmount_device("UUID={}".format(root_partition_uuid))
        losetup_delete(loop_device)
        return 1

    # Debootstrap
    logging.info("Creating minimal debootstrap system at {}...".format(PATH_MOUNT))
    if not debootstrap(PATH_MOUNT, extra_pks=PKG_INCLUDES, repo="http://localhost:8080/debian"):
        logging.error("debootstrap failed for {}. Exiting.".format(PATH_MOUNT))
        unmount_device("UUID={}".format(boot_partition_uuid))
        unmount_device("UUID={}".format(root_partition_uuid))
        losetup_delete(loop_device)
        return 1

    # System configuration
    # TODO: Script keeps going if configuration fails, because cant pass variables btwn main script & chroot context
    logging.info("Configuring system...")
    with Chroot(PATH_MOUNT):
        success = True

        # Configure apt to use cache
        if success and not configure_apt("http://localhost:8080/debian"):
            logging.error("Failed to configure apt")
            success = False

        # Install kernel
        if success and not install_kernel():
            logging.error("Failed to install kernel".format(PATH_MOUNT))
            success = False

        # Write fstab
        if success and not write_fstab(boot_partition_uuid, root_partition_uuid):
            logging.error("Failed to write {}/etc/fstab".format(PATH_MOUNT))
            success = False

        # Change root password
        if success and not change_rootpw("toor"):
            logging.error("Failed to change root password")
            success = False

        # Configure locale
        if success and not configure_locale("en_US.UTF-8"):
            logging.error("Locale configuration failed")
            success = False

        # Configure keyboard
        if success and not configure_keyboard("us"):
            logging.error("Keyboard configuration failed")
            success = False

        # Configure vim
        if success and not configure_vim():
            logging.error("Vim configuration failed")
            success = False

        # Configure networking
        if success and not configure_networking():
            logging.error("Network configuration failed")
            success = False

        # Configure hostname
        if success and not configure_hostname("raspberrypi"):
            logging.error("Hostname configuration failed")
            success = False

        # Configure ssh
        if success and not configure_sshd():
            logging.error("SSHD configuration failed")
            success = False

        # Configure apt to use official repo
        if success and not configure_apt():
            logging.error("Failed to configure apt")
            success = False

        # Write a convenience script for resizing the root fs
        if success and not write_file(FILE_RESIZE_PART, SCRIPT_RESIZE_ROOTFS):
            success = False

        if not success:
            logging.error("System configuration failed.")

    # Unmount the boot partition
    logging.info("Umounting boot partition...")
    if not unmount_device("UUID={}".format(boot_partition_uuid)):
        logging.error("Failed to unmount boot partition. Exiting.")
        unmount_device("UUID={}".format(root_partition_uuid))
        return 1

    # Unmount the root partition
    logging.info("Umounting root partition...")
    if not unmount_device("UUID={}".format(root_partition_uuid)):
        logging.error("Failed to unmount root partition. Exiting")
        return 1

    # Delete image loop device
    logging.info("Deleting loop device at {}".format(loop_device))
    if not losetup_delete(loop_device):
        logging.info("Failed to remove loop device {}. Exiting.".format(loop_device))
        return 1

    logging.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

