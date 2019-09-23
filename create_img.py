#!/usr/bin/env python3

import json
import logging
import os
import subprocess as sp
import sys

CMD_IMGFILE_CREATE = "dd status=progress if=/dev/zero of={} iflag=fullblock " \
                     "bs=1M count={}"

CMD_LOOP_DEV_CREATE = "losetup -f -P --show {}"
CMD_LOOP_DEV_DELETE = "losetup -d {}"
CMD_LOOP_DEV_GET = "losetup -a"
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

STATUS_FILENAME = ".status"


def load_status(status_file):
    """
    Loads the given json status_file
    :param status_file: File to load
    :return: A dict based on the json contents of status_file
    """
    current_status = []
    if os.path.exists(status_file):
        try:
            with open(status_file) as f:
                current_status = json.load(f)
        except Exception as e:
            logging.warn(
                "Error loading status file '{}': {}".format(STATUS_FILENAME, e)
            )
    return current_status


def save_status(status_file, status_array):
    """
    Save the given status as a json file
    :param status_file: File to load
    :param status_array: Ordered array of completed stages in the script
    :return: None
    """
    current_status = []
    try:
        with open(status_file, "w") as f:
            json.dump(status_array, f)
    except Exception as e:
        logging.error(
            "Error saving status file '{}': {}".format(STATUS_FILENAME, e)
        )


def exit_script(status_code, status_file, status_array):
    """
    Writes status_array to status_file and returns status_code
    :param status_code: Code to return from this function
    :param status_file: File to write status_array to
    :param status_array: Status array for the current run of the script
    :return: status_code
    """
    save_status(status_file, status_array)
    return status_code


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


def get_loop_devs():
    """
    :return: Key value pair of file names mounted as loop devices
    """
    loop_devs = dict()
    completed_process = sp.run(
        CMD_LOOP_DEV_GET,
        shell=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE
    )
    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
    else:
        proc_stdout = completed_process.stdout.decode("utf-8").strip().split(os.linesep)
        for line in proc_stdout:
            line = line.split(" ")
            dev_name = line[0].strip(":")
            file_name = line[-1].strip("()")
            loop_devs[file_name] = dev_name
    return loop_devs


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
    new_status = list()
    prev_status = load_status(STATUS_FILENAME)
    if type(prev_status) is not list:
        logging.warn("Status file {} is corrupted. Skipping resume...")
        prev_status = list()

    # Create create_imgfile stage
    if "create_imgfile" not in prev_status:
        if not create_imgfile(img_file, 1024):
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("create_imgfile")

    loop_dev = None
    if "imgfile_loop_dev" in prev_status:
        loop_devs = get_loop_devs()
        for k, v in loop_devs.items():
            if k in img_file or img_file in k:
                loop_dev = v
                break
    elif loop_dev is None:
        loop_dev = img_file_to_loop_dev(img_file)

        if loop_dev is None:
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("imgfile_loop_dev")
        logging.info(
            "Created loop device at {} for {}".format(loop_dev, img_file)
        )

    boot_partition = "{}p1".format(loop_dev)
    root_partition = "{}p2".format(loop_dev)

    if "loop_dev_fmt" not in prev_status:
        logging.info("Formatting {}...".format(loop_dev))
        if not format_loop_dev(loop_dev):
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("loop_dev_fmt")

    if "root_mounted" not in prev_status:
        logging.info("Mounting {} on /mnt...".format(root_partition))
        if not mount_device(root_partition, "/mnt", "-i -o exec,dev"):
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("root_mounted")

    try:
        os.makedirs("/mnt/boot/firmware", mode=0o755, exist_ok=1)
    except OSError as e:
        logging.error(e)
        return 1

    if "boot_mounted" not in prev_status:
        logging.info("Mounting {} on /mnt/boot/firmware...".format(boot_partition))
        if not mount_device(boot_partition, "/mnt", "-i -o exec,dev"):
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("boot_mounted")

    # Clean up
    if "unmount_boot" not in prev_status:
        logging.info("Unmounting {}...".format(boot_partition))
        if not unmount_device(boot_partition):
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("unmount_boot")

    if "unmount_root" not in prev_status:
        logging.info("Unmounting {}...".format(root_partition))
        if not unmount_device(root_partition):
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("unmount_root")

    if "loop_dev_delete" not in prev_status:
        logging.info("Deleting loop device {}...".format(loop_dev))
        if not delete_loop_dev(loop_dev):
            return exit_script(1, STATUS_FILENAME, new_status)
        new_status.append("loop_dev_delete")

    logging.info("Done.")

    # If we haven't logged any new statuses and haven't failed by now,
    # we skipped all of the steps and can skip next time too
    if len(new_status) == 0:
        new_status = prev_status
    return exit_script(0, STATUS_FILENAME, new_status)


if __name__ == "__main__":
    sys.exit(main())

