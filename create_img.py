#!/usr/bin/env python3

import os
import logging
import sys

from create_img_lib import (
    change_rootpw,
    configure_apt,
    configure_keyboard,
    configure_locale,
    do_debootstrap,
    install_kernel,
    write_fstab,
    write_vimconfig
)
from lib.network import configure_hostname, configure_networking

from lib.common import run_cmd, load_status, exit_script

from lib.disk import (
    dd,
    format_partition,
    losetup_create,
    get_partition_uuid,
    partition_loop_dev,
    mount_device,
    unmount_device,
    losetup_delete
)

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

CHROOT_LOCATION = "/mnt"
STATUS_FILENAME = ".status"


def main():
    logging.basicConfig(
        format=LOG_FMT_MSG,
        datefmt=LOG_FMT_DATE,
        level="INFO"
    )

    override = False
    old_status = load_status(STATUS_FILENAME)
    if type(old_status) != dict:
        logging.warning("{} is corrupted, starting over".format(STATUS_FILENAME))
        old_status = dict()
    new_status = dict()

    if not override and "img_file" in old_status.keys():
        img_file = old_status["img_file"]
        logging.info(
            "{} already exists".format(img_file)
        )
    else:
        img_file = "test.img"
        img_file_size = 2048
        if not dd("/dev/zero", img_file, block_bytes="1M", block_count=img_file_size):
            return exit_script(1, STATUS_FILENAME, new_status)
        logging.info("Created image file {} of size {} MB".format(img_file, img_file_size))
    new_status["img_file"] = img_file

    if not override and "loop_dev" in old_status.keys():
        loop_dev = old_status["loop_dev"]
        logging.info(
            "{} already using {}".format(img_file, loop_dev)
        )
    else:
        loop_dev = losetup_create(img_file)
        if loop_dev is None:
            return exit_script(1, STATUS_FILENAME, new_status)
        logging.info(
            "Created loop device at {} for {}".format(loop_dev, img_file)
        )
    new_status["loop_dev"] = loop_dev

    boot_partition = "{}p1".format(loop_dev)
    root_partition = "{}p2".format(loop_dev)

    # loop_dev_fmt stage
    if not override and "loop_dev_fmt" not in old_status.keys():
        logging.info("Formatting {}...".format(loop_dev))

        if not partition_loop_dev(loop_dev):
            return exit_script(1, STATUS_FILENAME, new_status)

        if not format_partition(boot_partition, "vfat"):
            logging.error("Failed to partition {}".format(boot_partition))
            return exit_script(1, STATUS_FILENAME, new_status)

        if not format_partition(root_partition, "ext4"):
            logging.error("Failed to partition {}".format(root_partition))
            return exit_script(1, STATUS_FILENAME, new_status)

    else:
        logging.info("{} is already formatted".format(loop_dev))
    new_status["loop_dev_fmt"] = True

    boot_partition_uuid = get_partition_uuid(boot_partition)
    root_partition_uuid = get_partition_uuid(root_partition)

    if boot_partition_uuid is None:
        logging.error("Could not get uuid for partition {}".format(boot_partition))
        exit_script(1, STATUS_FILENAME, new_status)
    if root_partition_uuid is None:
        logging.error("Could not get uuid for partition {}".format(root_partition))
        exit_script(1, STATUS_FILENAME, new_status)

    # TODO: Generated fstab based on uuids
    logging.info("Boot partition at {} has uuid {}".format(boot_partition, boot_partition_uuid))
    logging.info("Root partition at {} has uuid {}".format(root_partition, root_partition_uuid))

    # root_mounted stage
    if "mount_root" not in old_status.keys():
        logging.info("Mounting {} on {}...".format(root_partition, CHROOT_LOCATION))
        if not mount_device(root_partition, CHROOT_LOCATION, "-i -o exec,dev"):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("{} already mounted on {}...".format(root_partition, CHROOT_LOCATION))
    new_status["mount_root"] = True

    try:
        os.makedirs("{}/boot/firmware".format(CHROOT_LOCATION), mode=0o755, exist_ok=1)
    except OSError as e:
        logging.error(e)
        return 1

    # boot_mounted stage
    if "mount_boot" not in old_status.keys():
        logging.info("Mounting {} on {}/boot/firmware...".format(boot_partition, CHROOT_LOCATION))
        if not mount_device(boot_partition, "{}/boot/firmware".format(CHROOT_LOCATION), "-i -o exec,dev"):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("{} already mounted on {}/boot/firmware...".format(boot_partition, CHROOT_LOCATION))
    new_status["mount_boot"] = True

    # debootstrap stage
    if not override and "debootstrap" not in old_status.keys():
        logging.info("Creating minimal debian system at {}...".format(CHROOT_LOCATION))
        if not do_debootstrap(CHROOT_LOCATION, PKG_INCLUDES):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("debootstrap has already compeleted at {}".format(CHROOT_LOCATION))
    new_status["debootstrap"] = True

    # configure stage
    if not configure_hostname(CHROOT_LOCATION, "raspberrypi"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_networking(CHROOT_LOCATION):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_locale(CHROOT_LOCATION, "en_US.UTF-8"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_keyboard(CHROOT_LOCATION, "us"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_apt(CHROOT_LOCATION):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not write_fstab(CHROOT_LOCATION):
        return exit_script(1, STATUS_FILENAME, new_status)

    if "kernel" not in old_status.keys():
        logging.info("Installing kernel...")
        if not install_kernel(CHROOT_LOCATION):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("Kernel is already installed")
    new_status["kernel"] = True

    # Change rootpw stage
    logging.info("Changing root password...")
    change_rootpw(CHROOT_LOCATION, "toor")

    # Write vim config
    logging.info("Writing vim config...")
    write_vimconfig(CHROOT_LOCATION)

    logging.info("Configuring locales...")
    if not run_cmd("locale-gen --purge en_US.UTF-8"):
        exit_script(1, STATUS_FILENAME, new_status)

    # unmount_boot stage
    logging.info("Unmounting {}...".format(boot_partition))
    if not unmount_device(boot_partition):
        return exit_script(1, STATUS_FILENAME, new_status)
    if "mount_boot" in new_status.keys():
        new_status.pop("mount_boot")

    # ummount_root stage
    logging.info("Unmounting {}...".format(root_partition))
    if not unmount_device(root_partition):
        return exit_script(1, STATUS_FILENAME, new_status)
    if "mount_root" in new_status.keys():
        new_status.pop("mount_root")

    # delete loop device, created every time
    logging.info("Deleting loop device {}...".format(loop_dev))
    if not losetup_delete(loop_dev):
        return exit_script(1, STATUS_FILENAME, new_status)
    if "loop_dev" in new_status.keys():
        new_status.pop("loop_dev")

    logging.info("Done.")

    # If we haven't logged any new statuses and haven't failed by now,
    # we skipped all of the steps and can skip next time too
    if len(new_status.keys()) == 0:
        new_status = old_status
    return exit_script(0, STATUS_FILENAME, new_status)


if __name__ == "__main__":
    sys.exit(main())

