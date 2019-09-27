#!/usr/bin/env python3

import os
import logging
import sys

from lib.common import run_cmd
from lib.disk import dd, losetup_create, losetup_delete, create_partition_table, create_partition

LOG_FMT_MSG = "[%(asctime)s][%(levelname)s] %(message)s"
LOG_FMT_DATE = "%H:%M:%S %Y-%m-%d"

PKG_KERNEL = "linux-image-arm64"
PKG_INCLUDES = [
    "dbus",
    "dialog",
    "dosfstools",
    "firmware-brcm80211",
    "firmware-realtek",
    "haveged",
    "iproute2",
    "locales",
    "parted",
    "python",   # For ansible
    "raspi3-firmware",
    "systemd",
    "systemd-sysv",
    "ssh",
    "vim",
    "wireless-tools",
    "wpasupplicant"
]

FILE_IMG_DEFAULT = "debian-stable-arm64.img"
CHROOT_LOCATION = "/mnt"
STATUS_FILENAME = ".status"


def main():
    logging.basicConfig(
        format=LOG_FMT_MSG,
        datefmt=LOG_FMT_DATE,
        level="INFO"
    )

    # TODO: Remove, for testing only
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

    # Delete image loop device
    logging.info("Deleting loop device at {}".format(loop_device))
    if not losetup_delete(loop_device):
        logging.info("Failed to remove loop device {}. Exiting.".format(loop_device))
        return 1

    logging.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

