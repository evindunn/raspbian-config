import json
import logging
from .common import run_cmd

CMD_DD = "dd if={} of={}"
CMD_DD_COUNT = "dd if={} of={} iflag=fullblock bs={} count={}"

CMD_PART_TBL_CREATE = "parted -s {} mklabel msdos"
CMD_PART_UUID = "lsblk {} -n -o UUID"

CMD_LOOP_DEV_CREATE = "udisksctl loop-setup -f {}"
CMD_LOOP_DEV_DELETE = "udisksctl loop-delete -b {}"
CMD_LOOP_DEV_LIST = "losetup -l -J"

CMD_PARTITION_LOOP_DEV = """
    #!/bin/bash
    set -e

    parted -s -a optimal {0} mkpart primary fat32 0% 256M
    parted -s -a optimal {0} mkpart primary ext4 256M 100%
"""

CMD_MNT = "udisksctl mount -b {}"
CMD_UMNT = "udisksctl unmount -b {}"

SUPPORTED_FSTYPES = ["vfat", "ext4"]


def create_partition_table(block_dev):
    """
    Creates an msdos partition table on the given block_dev
    :param block_dev: Block device to partition
    :return: Whether the operation was successful
    """
    return run_cmd(CMD_PART_TBL_CREATE.format(block_dev))


def dd(input_file, output_file, block_bytes=512, block_count=0):
    """
    Wrapper for the system 'dd' command
    :param input_file: Copy source file
    :param output_file: Copy destination file
    :param block_bytes: Size of blocks to copy
    :param block_count: Number of blocks to copy
    :return: Whether the operation was successful
    """
    if block_count > 0:
        command = CMD_DD_COUNT.format(input_file, output_file, block_bytes, block_count)
    else:
        command = CMD_DD.format(input_file, output_file)
    return run_cmd(command)


def mount_device(dev_path):
    """
    Runs 'udisksctl mount -b dev_path'
    :param dev_path: Path to block device to mount
    :return: Whether the operation was successful
    """
    if not run_cmd(CMD_MNT.format(dev_path)):
        return False

    # TODO: Get the mount path

    return True


def unmount_device(dev_or_mount_path):
    """
    :param dev_or_mount_path: Filesystem or block device path to unmount
    :return: Whether the operation was successful
    """
    return run_cmd(CMD_UMNT.format(dev_or_mount_path))


def get_partition_uuid(dev_path):
    """
    Gets the filesystem uuid for the device at dev_path
    :param dev_path: Path to device
    :return: The uuid or None on error
    """
    return run_cmd(CMD_PART_UUID.format(dev_path), return_output=True)


def losetup_create(file_name):
    """
    Mounts an image file as a loop device
    :param file_name: File name to mount as a loop device
    :return: The name of the loop device created or None on error
    """
    if not run_cmd(CMD_LOOP_DEV_CREATE.format(file_name)):
        return None

    # Locate the loop device path
    loop_device = None
    for loopdev in losetup_list()["loopdevices"]:
        if file_name in loopdev["back-file"]:
            loop_device = loopdev["name"]
            break
    if loop_device is None:
        logging.error("Error locating loop device for {}. Exiting.".format(file_name))

    return loop_device


def losetup_delete(loop_dev):
    """
    Unmounts a loop device
    :param loop_dev: Loop device path
    :return: Whether the operation was successful
    """
    return run_cmd(CMD_LOOP_DEV_DELETE.format(loop_dev))


def losetup_list():
    """
    :return: Object representing loop devices on machine. See losetup -J
    """
    try:
        raw_output = run_cmd(CMD_LOOP_DEV_LIST, return_output=True).strip()
        return json.loads(raw_output)
    except Exception as e:
        logging.error("Error getting loop devices: {}".format(e))
        return None


def format_partition(dev_path, fs_type):
    """
    Formats the partition at dev_path using fs_type
    :param dev_path: Device path to partition
    :param fs_type: Filesystem type
    :return: Whether the operation was successful
    """
    # These are all we need for the PI and is a good sanity check
    if fs_type not in SUPPORTED_FSTYPES:
        logging.error("{} is not a valid filesystem type".format(fs_type))
        logging.error("Supported values are: ".format(SUPPORTED_FSTYPES))
        return False
    return run_cmd("mkfs.{} {}".format(fs_type, dev_path))


def partition_loop_dev(loop_dev):
    """
    Partitions the given loop device with
        - 256M fat32 partition
        - 256M -> 100% ext4 partition
    :param loop_dev: The device to format
    :return: Whether the operation was successful
    """
    return run_cmd(CMD_PARTITION_LOOP_DEV.format(loop_dev))
