import crypt
import json
import logging
import os
import re
import subprocess as sp

CMD_DEBOOTSTRAP = re.sub(r"\s+", " ", """
    qemu-debootstrap
        --arch=arm64
        --keyring=/usr/share/keyrings/debian-archive-keyring.gpg
        --components=main,contrib,non-free
        --include={}
        --variant=minbase
        stable
        {}
        http://ftp.debian.org/debian
""").strip()

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

CMD_NETWORKD = "chroot {} systemctl enable systemd-networkd"

CMD_RESOLVCONF = """
    #!/bin/bash

    mkdir -p {0}/run/systemd/resolve
    rm {0}/etc/resolv.conf
    cp /run/systemd/resolve/stub-resolv.conf {0}/run/systemd/resolve/stub-resolv.conf
    chroot {0} ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
    chroot {0} systemctl enable systemd-resolved
"""

CMD_UMNT = "umount {}"

CONFIG_FSTAB = """
/dev/mmcblk0p1  /boot/firmware  vfat    defaults            0 2
/dev/mmcblk0p2  /               ext4    defaults,noatime    0 1
proc            /proc           proc    defaults            0 0
""".strip()

CONFIG_DHCP = """
[Match]
Name=*

[Network]
DHCP=ipv4
"""

CMD_KERNEL_INSTALL = "chroot {} apt-get install -y linux-image-arm64"

MSG_IMGFILE_CREATED = "Created image file '{}' of size {} MB"


def run_cmd(cmd, return_output=False):
    """
    Runs the given cmd. If return_output, return stdout or None on error.
    Else return a boolean indicating whether the operation was successful
    :param cmd: Command to run
    :param return_output: Whether to return a string or boolean
    :return: Stdout or boolean indicating if the operation was
    sucessful
    """
    completed_process = sp.run(
        cmd,
        shell=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE
    )

    if not return_output:
        logging.debug(completed_process.stdout.decode("utf-8"))

    if completed_process.returncode != 0:
        logging.error(completed_process.stderr.decode("utf-8"))
        if return_output:
            return None
        return False

    if return_output:
        return completed_process.stdout.decode("utf-8").strip()
    return True


def load_status(status_file):
    """
    Loads the given json status_file
    :param status_file: File to load
    :return: A dict based on the json contents of status_file
    """
    current_status = {}
    if os.path.exists(status_file):
        try:
            with open(status_file) as f:
                current_status = json.load(f)
        except Exception as e:
            logging.warning(
                "Error loading status file '{}': {}".format(status_file, e)
            )
    return current_status


def save_status(status_file, status_dict):
    """
    Save the given status as a json file
    :param status_file: File to load
    :param status_dict: Dict of variabled from the script
    :return: None
    """
    try:
        with open(status_file, "w") as f:
            json.dump(status_dict, f)
    except Exception as e:
        logging.error(
            "Error saving status file '{}': {}".format(status_file, e)
        )


def exit_script(status_code, status_file, status_dict):
    """
    Writes status_array to status_file and returns status_code
    :param status_code: Code to return from this function
    :param status_file: File to write status_array to
    :param status_dict: Status dict for the current run of the script
    :return: status_code
    """
    save_status(status_file, status_dict)
    return status_code


def create_imgfile(name, size):
    """
    Creates an empty *.img file using dd
    :param name: Name of the file
    :param size: size of the file
    :return: Whether the process was successful
    """
    return run_cmd(CMD_IMGFILE_CREATE.format(name, size))


def img_file_to_loop_dev(name):
    """
    Mounts an image file as a loop device
    :param name: File name to mount as a loop device
    :return: The name of the loop device created or None on error
    """
    return run_cmd(CMD_LOOP_DEV_CREATE.format(name), return_output=True)


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
    return run_cmd(
        CMD_LOOP_DEV_FORMAT.format(
            disk=loop_dev,
            part_1_name=part_1_name,
            part_2_name=part_2_name
        )
    )


def mount_device(dev_path, mnt_path, opts=""):
    """
    Runs 'mount {opts} {dev_path} {mnt_path}'
    :param dev_path: Path to block device to mount
    :param mnt_path: Path to mount block device on
    :param opts: Mount options
    :return: Whether the operation was successful
    """
    return run_cmd(
        CMD_MNT.format(
            opts,
            dev_path,
            mnt_path
        )
    )


def do_debootstrap(mnt_point, extra_pks):
    """
    :param mnt_point: Create debootstrap chroot here
    :param extra_pks: Packages to include
    :return: Whether the operation was successful
    """

    # Need debootstrap, qemu, binfmt-support, qemu-user-static
    return run_cmd(
        CMD_DEBOOTSTRAP.format(",".join(extra_pks), mnt_point)
    )


def configure_hostname(chroot, hostname):
    """
    Configures /etc/hostname and /etc/hosts for the given chroot directory
    :param chroot: Filesystem root
    :param hostname: Hostname
    :return: Whether the operation was successful
    """
    try:
        logging.info("Writing /etc/hostname...")
        with open("{}/etc/hostname".format(chroot), "w") as f:
            f.write("{}\n".format(hostname))
    except Exception as e:
        logging.error("Error writing {}/etc/hostname: {}".format(chroot, e))
        return False

    try:
        logging.info("Writing /etc/hosts...")
        with open("{}/etc/hosts".format(chroot), "w") as f:
            f.writelines([
                "127.0.0.1    localhost",
                "127.0.1.1    {}".format(hostname)
            ])
    except Exception as e:
        logging.error("Error writing {}/etc/hosts: {}".format(chroot, e))
        return False
    return True


def configure_locale(chroot, locale):
    """
    Configure /etc/default/locale under the given chroot
    :param chroot: Filesystem root
    :param locale: Locale
    :return: Whether the operation was successful
    """
    try:
        logging.info("Writing /etc/default/locale...")
        with open("{}/etc/default/locale".format(chroot), "w") as f:
            f.writelines([
                "LANG={}".format(locale),
                "LC_ALL={}".format(locale),
                "LANGUAGE={}".format(locale)
            ])
    except Exception as e:
        logging.error("Error writing {}/etc/default/locale: {}".format(chroot, e))
        return False
    return True


def configure_keyboard(chroot, xkblayout, xkbmodel="pc105", xkbvariant="", xkboptions="", backspace="guess"):
    """
    Configure /etc/default/keyboard under the given chroot
    :param chroot: Filesystem root
    :param xkblayout: Keyboard layout
    :param xkbmodel: Keyboard model
    :param xkbvariant: Keyboard variant
    :param xkboptions: Keyboard options
    :param backspace: Backspace option
    :return: Whether the operation was successful
    """
    try:
        logging.info("Writing /etc/default/keyboard...")
        with open("{}/etc/default/keyboard".format(chroot), "w") as f:
            f.writelines([
                'XKBMODEL = "{}"'.format(xkbmodel),
                'XKBLAYOUT = "{}"'.format(xkblayout),
                'XKBVARIANT = "{}"'.format(xkbvariant),
                'XKBOPTIONS = ""'.format(xkboptions),
                'BACKSPACE = "{}"'.format(backspace)
            ])
    except Exception as e:
        logging.error("Error writing {}/etc/default/keyboard: {}".format(chroot, e))
        return False
    return True


def configure_apt(chroot, distrib="stable", components=("main", "contrib", "non-free")):
    """
    Configure /etc/apt/source.list under the given chroot
    :param chroot: Filesystem root
    :param distrib: stable, unstable, stretch, buster, etc...
    :param components: main, contrib, non-free
    :return: Whether the operation was successful
    """
    try:
        logging.info("Writing /etc/apt/sources.list...")
        content = "deb http://deb.debian.org/debian {} {}\n".format(
            distrib,
            " ".join(components)
        )
        with open("{}/etc/apt/sources.list".format(chroot), "w") as f:
            f.write(content)
    except Exception as e:
        logging.error("Error writing {}/etc/apt/sources.list: {}".format(chroot, e))
        return False
    return True


def configure_networking(chroot):
    """
    Configures networking in the given chroot using systemd-networkd and
    systemd-resolved
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
    success = True
    logging.info("Configuring systemd-networkd...")
    try:
        with open("{}/etc/systemd/network/99-default.conf".format(chroot), "w") as f:
            f.write(CONFIG_DHCP)
    except Exception as e:
        logging.error("Error writing {}/etc/systemd/network/99-default.conf: {}".format(chroot, e))
        success = False

    if success:
        success = run_cmd(CMD_NETWORKD.format(chroot))

    if success:
        logging.info("Configuring systemd-resolved...")
        success = run_cmd(CMD_RESOLVCONF.format(chroot))

    return success


def write_fstab(chroot):
    """
    Configure /etc/fstab under the given chroot
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
    try:
        logging.info("Writing /etc/fstab...")
        with open("{}/etc/fstab".format(chroot), "w") as f:
            f.write(CONFIG_FSTAB)
    except Exception as e:
        logging.error("Error writing {}/etc/fstab: {}".format(chroot, e))
        return False
    return True


def install_kernel(chroot):
    if not (
        mount_device("/proc", "/mnt/proc", "-o bind") and
        mount_device("/sys", "/mnt/sys", "-o bind") and
        mount_device("/dev", "/mnt/dev", "-o bind") and
        mount_device("/dev/pts", "/mnt/dev/pts", "-o bind")
    ):
        return False

    success = run_cmd(CMD_KERNEL_INSTALL.format(chroot))

    unmount_device("/mnt/proc")
    unmount_device("/mnt/sys")
    unmount_device("/mnt/dev/pts")
    unmount_device("/mnt/dev")

    return success


def change_rootpw(chroot, passwd):

    try:
        with open("{}/etc/shadow".format(chroot)) as f:
            shadow_lines = f.read()

        new_lines = re.sub(
            r"(?<=^root:)\*(?=:)",
            crypt.crypt(passwd, salt=crypt.METHOD_SHA256),
            shadow_lines
        )

        with open("{}/etc/shadow".format(chroot), "w") as f:
            f.write(new_lines)
    except Exception as e:
        logging.error("Error changing root password: {}".format(e))
        return False

    return True


def write_vimconfig(chroot):
    """
    Writes my prefered vim config to the chroot
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
    try:
        with open("{}/etc/vim/vimrc".format(chroot), "w") as f:
            f.writelines([
                "syntax on\n",
                "set number\n",
                "set ts=4\n",
                "set sts=4\n",
                "set sw=4\n",
                "set expandtab\n",
                "\n",
                "autocmd FileType make setlocal noexpandtab\n",
                "autocmd FileType yaml setlocal ts=2 sts=2 sw=2 expandtab\n",
            ])
    except Exception as e:
        logging.error("Error writing /etc/vim/vimrc: {}".format(e))
        return False

    return True


def unmount_device(dev_or_mount_path):
    """
    :param dev_or_mount_path: Filesystem or block device path to unmount
    :return: Whether the operation was successful
    """
    return run_cmd(CMD_UMNT.format(dev_or_mount_path))


def delete_loop_dev(loop_dev):
    """
    Unmounts a loop device
    :param loop_dev: Loop device path
    :return: Whether the operation was successful
    """
    return run_cmd(CMD_LOOP_DEV_DELETE.format(loop_dev))
