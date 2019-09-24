#!/usr/bin/env python3

import os
import logging
import sys

from create_img_lib import (
    change_rootpw,
    configure_apt,
    configure_hostname,
    configure_keyboard,
    configure_locale,
    configure_networking,
    create_imgfile,
    delete_loop_dev,
    do_debootstrap,
    exit_script,
    format_loop_dev,
    img_file_to_loop_dev,
    install_kernel,
    load_status,
    mount_device,
    unmount_device,
    write_fstab
)

LOG_FMT_MSG = "[%(asctime)s][%(levelname)s] %(message)s"
LOG_FMT_DATE = "%H:%M:%S %Y-%m-%d"


PKG_KERNEL = "linux-image-arm64"
PKG_INCLUDES = [
    "dosfstools",
    "firmware-brcm80211",
    "firmware-realtek",
    "haveged",
    "iproute2",
    "parted",
    "raspi3-firmware",
    "systemd",
    "systemd-sysv",
    "ssh",
    "wireless-tools",
    "wpasupplicant"
]

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
        if not create_imgfile(img_file, 2048):
            return exit_script(1, STATUS_FILENAME, new_status)
    new_status["img_file"] = img_file

    if not override and "loop_dev" in old_status.keys():
        loop_dev = old_status["loop_dev"]
        logging.info(
            "{} already using {}".format(img_file, loop_dev)
        )
    else:
        loop_dev = img_file_to_loop_dev(img_file)
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
        if not format_loop_dev(loop_dev):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("{} is already formatted".format(loop_dev))
    new_status["loop_dev_fmt"] = True

    # root_mounted stage
    if "mount_root" not in old_status.keys():
        logging.info("Mounting {} on /mnt...".format(root_partition))
        if not mount_device(root_partition, "/mnt", "-i -o exec,dev"):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("{} already mounted on /mnt...".format(root_partition))
    new_status["mount_root"] = True

    try:
        os.makedirs("/mnt/boot/firmware", mode=0o755, exist_ok=1)
    except OSError as e:
        logging.error(e)
        return 1

    # boot_mounted stage
    if "mount_boot" not in old_status.keys():
        logging.info("Mounting {} on /mnt/boot/firmware...".format(boot_partition))
        if not mount_device(boot_partition, "/mnt/boot/firmware", "-i -o exec,dev"):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("{} already mounted on /mnt/boot/firmware...".format(boot_partition))
    new_status["mount_boot"] = True

    # debootstrap stage
    if not override and "debootstrap" not in old_status.keys():
        logging.info("Creating minimal debian system at /mnt...")
        if not do_debootstrap("/mnt", PKG_INCLUDES):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("debootstrap has already compeleted at /mnt")
    new_status["debootstrap"] = True

    # configure stage
    if not configure_hostname("/mnt", "raspberrypi"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_locale("/mnt", "en_US.UTF-8"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_keyboard("/mnt", "us"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_apt("/mnt"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not configure_networking("/mnt"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if not write_fstab("/mnt"):
        return exit_script(1, STATUS_FILENAME, new_status)

    if "kernel" not in old_status.keys():
        logging.info("Installing kernel...")
        if not install_kernel("/mnt"):
            return exit_script(1, STATUS_FILENAME, new_status)
    else:
        logging.info("Kernel is already installed")
    new_status["kernel"] = True

    # Change rootpw stage
    logging.info("Changing root password...")
    change_rootpw("/mnt", "toor")

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
    if not delete_loop_dev(loop_dev):
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

