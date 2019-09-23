#!/usr/bin/env python3

import logging
import os
import subprocess as sp
import sys

ANSI_BLUE = "\u001b[34;1m"
ANSI_RED = "\u001b[32m"
ANSI_RESET = "\u001b[0m"

CMD_IMGFILE_CREATE = "dd status=progress if=/dev/zero of={} iflag=fullblock " \
                     "bs=1M count={}"

CMD_LOOP_DEV_CREATE = "losetup -f -P --show {}"
CMD_LOOP_DEV_DELETE = "losetup -d {}"
CMD_LOOP_DEV_FORMAT = """
    #!/bin/bash
    set -e
    
    parted -s {disk} mklabel msdos
    parted -s -a optimal {disk} mkpart primary fat32 0% 256M
    parted -s -a optimal {disk} mkpart primary ext4 256M 100%
    
    mkfs.vfat /dev/{part_1_name}
    mkfs.ext4 /dev/{part_2_name}
"""

CMD_MNT = "mount {} {} {}"
CMD_UMNT = "umount {}"

LOG_FMT_MSG = "[%(asctime)s][%(levelname)s] %(message)s"
LOG_FMT_DATE = "%H:%M:%S %Y-%m-%d"

MSG_IMGFILE_CREATED = "Created image file '{}' of size {} MB"


def create_imgfile(name, size):
    """
    Creates an empty *.img file using dd
    :param name: Name of the file
    :param size: size of the file
    :return: Whether the process was successful
    """
    completed_process = sp.run(
        CMD_IMGFILE_CREATE.format(name, size),
        shell=True,
        stdout=sp.DEVNULL,
        stderr=sp.PIPE
    )
    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        return False

    logging.info(MSG_IMGFILE_CREATED.format(name, size))
    return True


def img_file_to_loop_dev(name):
    """
    Mounts an image file as a loop device
    :param name: File name to mount as a loop device
    :return: The name of the loop device created or None on error
    """
    completed_process = sp.run(
        CMD_LOOP_DEV_CREATE.format(name),
        shell=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE
    )
    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        return None
    return completed_process.stdout.decode("utf-8").strip()


def format_loop_dev(loop_dev):
    """
    Formats the given loop device with
        - 256M fat32 partition
        - 256M -> 100% ext4 partition
    :param loop_dev: The device to format
    :return: Whether the operation was successful
    """
    part_prefix = loop_dev.split("/")[-1]
    part_1_name = "{}p1".format(part_prefix)
    part_2_name = "{}p2".format(part_prefix)
    completed_process = sp.run(
        CMD_LOOP_DEV_FORMAT.format(
            disk=loop_dev,
            part_1_name=part_1_name,
            part_2_name=part_2_name
        ),
        shell=True,
        stdout=sp.DEVNULL,
        stderr=sp.PIPE
    )
    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        return False
    return True


def mount_device(dev_path, mnt_path, opts=""):
    """
    Runs 'mount {opts} {dev_path} {mnt_path}'
    :param dev_path: Path to block device to mount
    :param mnt_path: Path to mount block device on
    :param opts: Mount options
    :return: Whether the operation was successful
    """
    completed_process = sp.run(
        CMD_MNT.format(
            opts,
            dev_path,
            mnt_path
        ),
        shell=True,
        stdout=sp.DEVNULL,
        stderr=sp.PIPE
    )
    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        return False
    return True


def unmount_device(dev_or_mount_path):
    """
    :param dev_or_mount_path: Filesystem or block device path to unmount
    :return: Whether the operation was successful
    """
    completed_process = sp.run(
        CMD_UMNT.format(dev_or_mount_path),
        shell=True,
        stdout=sp.DEVNULL,
        stderr=sp.PIPE
    )
    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        return False
    return True


def delete_loop_dev(loop_dev):
    """
    Unmounts a loop device
    :param loop_dev: Loop device path
    :return: Whether the operation was successful
    """
    completed_process = sp.run(
        CMD_LOOP_DEV_DELETE.format(loop_dev),
        shell=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE
    )
    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        return False
    return True


def main():
    logging.basicConfig(
        format=LOG_FMT_MSG,
        datefmt=LOG_FMT_DATE,
        level="DEBUG"
    )

    img_file = "test.img"

    # Create *.img file
    if not create_imgfile(img_file, 1024):
        return 1

    loop_dev = img_file_to_loop_dev(img_file)
    boot_partition = "{}p1".format(loop_dev)
    root_partition = "{}p2".format(loop_dev)
    if loop_dev is None:
        return 1

    logging.info(
        "Created loop device at {} for {}".format(loop_dev, img_file)
    )

    logging.info("Formatting {}...".format(loop_dev))
    if not format_loop_dev(loop_dev):
        return 1

    logging.info("Mounting {} on /mnt...".format(root_partition))
    if not mount_device(root_partition, "/mnt", "-i -o exec,dev"):
        return 1

    try:
        os.makedirs("/mnt/boot/firmware", mode=0o755)
    except OSError as e:
        logging.error(e)
        return 1

    logging.info("Mounting {} on /mnt/boot/firmware...".format(boot_partition))
    if not mount_device(boot_partition, "/mnt", "-i -o exec,dev"):
        return 1

    # Clean up
    logging.info("Unmounting {}...".format(boot_partition))
    if not unmount_device(boot_partition):
        return 1
    logging.info("Unmounting {}...".format(root_partition))
    if not unmount_device(root_partition):
        return 1

    logging.info("Deleting loop device {}...".format(loop_dev))
    if not delete_loop_dev(loop_dev):
        return 1

    logging.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

