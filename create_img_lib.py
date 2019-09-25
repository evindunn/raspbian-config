import crypt
import logging
import re

from lib.common import run_cmd
from lib.disk import mount_device, unmount_device

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

CONFIG_FSTAB = """
/dev/mmcblk0p1  /boot/firmware  vfat    defaults            0 2
/dev/mmcblk0p2  /               ext4    defaults,noatime    0 1
proc            /proc           proc    defaults            0 0
"""

CONFIG_LANG = """
LANG={}
LC_ALL={}
LANGUAGE={}
"""

CMD_KERNEL_INSTALL = "chroot {} apt-get install -y linux-image-arm64"

MSG_IMGFILE_CREATED = "Created image file '{}' of size {} MB"


def do_debootstrap(mnt_point, extra_pks):
    """
    :param mnt_point: Create debootstrap chroot here
    :param extra_pks: Packages to include
    :return: Whether the operation was successful
    """

    # Need debootstrap, qemu, binfmt-support, qemu-user-static
    return run_cmd(CMD_DEBOOTSTRAP.format(",".join(extra_pks), mnt_point))


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
            f.write(CONFIG_LANG)
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
