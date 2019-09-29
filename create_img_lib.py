import crypt
import logging
import re

from lib.common import run_cmd, read_file, write_file
from lib.disk import mount_device, unmount_device



CONFIG_FSTAB = """
/dev/mmcblk0p1  /boot/firmware  vfat    defaults            0 2
/dev/mmcblk0p2  /               ext4    defaults,noatime    0 1
proc            /proc           proc    defaults            0 0
"""

CONFIG_LANG = """
LANG={0}
LC_ALL={0}
LANGUAGE={0}
"""

CONFIG_KEYBOARD = """
XKBMODEL={}
XKBLAYOUT={}
XKBVARIANT={}
XKBOPTIONS={}
BACKSPACE={}
"""

CONFIG_VIM = """
syntax on
set number
set ts=4
set sts=4
set sw=4
set expandtab

autocmd FileType make setlocal noexpandtab
autocmd FileType yaml setlocal ts=2 sts=2 sw=2 expandtab
"""

CMD_KERNEL_INSTALL = "apt-get install -y linux-image-arm64"

FILE_APT = "/etc/apt/sources.list"
FILE_FSTAB = "/etc/fstab"
FILE_KEYBOARD = "/etc/default/keyboard"
FILE_LOCALES = "/etc/default/locale"
FILE_PASSWD = "/etc/shadow"
FILE_VIMRC = "/etc/vim/vimrc"

MSG_IMGFILE_CREATED = "Created image file '{}' of size {} MB"





def configure_locale(chroot, locale):
    """
    Configure /etc/default/locale under the given chroot
    :param chroot: Filesystem root
    :param locale: Locale
    :return: Whether the operation was successful
    """
    return write_file(
        "{}{}".format(chroot, FILE_LOCALES),
        CONFIG_LANG.format(locale)
    )


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
    keyboard_config = CONFIG_KEYBOARD.format(
        xkbmodel,
        xkblayout,
        xkbvariant,
        xkboptions,
        backspace
    )
    return write_file("{}{}".format(chroot, FILE_KEYBOARD), keyboard_config)


def configure_apt(chroot, distrib="stable", components=("main", "contrib", "non-free")):
    """
    Configure /etc/apt/source.list under the given chroot
    :param chroot: Filesystem root
    :param distrib: stable, unstable, stretch, buster, etc...
    :param components: main, contrib, non-free
    :return: Whether the operation was successful
    """
    content = "deb http://deb.debian.org/debian {} {}\n".format(
        distrib,
        " ".join(components)
    )
    return write_file("{}{}".format(chroot, FILE_APT), content)


def write_fstab(chroot):
    """
    Configure /etc/fstab under the given chroot
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
    return write_file("{}{}".format(chroot, FILE_FSTAB), CONFIG_FSTAB)


def install_kernel(chroot):
    """
    Installs the Debian Arm64 kernel under the given chroot
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
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
    """
    Changes the root password under the given chroot
    :param chroot: Filesystem root
    :param passwd: New root password
    :return: Whether the operation was successful
    """
    shadow_file = "{}{}".format(chroot, FILE_PASSWD)
    success = shadow_contents = read_file(shadow_file)

    if success:
        shadow_contents = re.sub(
            r"(?<=^root:)\*(?=:)",
            crypt.crypt(passwd, salt=crypt.METHOD_SHA256),
            shadow_contents
        )
        success = write_file(FILE_PASSWD, shadow_contents)

    return success


def write_vimconfig(chroot):
    """
    Writes my prefered vim config to the chroot
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
    return write_file("{}{}".format(chroot, FILE_VIMRC), CONFIG_VIM)
