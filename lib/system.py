import crypt
import re

from lib.common import run_cmd, read_file, write_file

CONFIG_APT_SUGGESTS = """
APT::Install-Recommends "false";
APT::Install-Suggested "false";
""".strip()

CONFIG_FSTAB = """
/dev/mmcblk0p1          /boot/firmware  vfat    defaults            0 2
/dev/mmcblk1p2          /               ext4    defaults,noatime    0 1
proc                    /proc           proc    defaults            0 0
""".strip()

CONFIG_LANG = """
LANG="{0}"
""".strip()

CONFIG_KEYBOARD = """
XKBMODEL={}
XKBLAYOUT={}
XKBVARIANT={}
XKBOPTIONS={}
BACKSPACE={}
""".strip()

CONFIG_VIM = """
syntax on
set number
set ts=4
set sts=4
set sw=4
set expandtab

autocmd FileType make setlocal noexpandtab
autocmd FileType yaml setlocal ts=2 sts=2 sw=2 expandtab
""".strip()

CMD_KERNEL_INSTALL = "apt-get install -y linux-image-arm64"

FILE_APT_SOURCES = "/etc/apt/sources.list"
FILE_APT_CONFIG = "/etc/apt/apt.conf.d/99disable-suggested"
FILE_FSTAB = "/etc/fstab"
FILE_KEYBOARD = "/etc/default/keyboard"
FILE_LOCALES = "/etc/default/locale"
FILE_PASSWD = "/etc/shadow"
FILE_VIMRC = "/etc/vim/vimrc"
FILE_SSHD = "/etc/ssh/sshd_config"


def configure_sshd():
    """
    Configures SSHD to allow root logins
    :return: Whether the operation was successful
    """
    sshd_config = read_file(FILE_SSHD)
    re.sub(
        r"^#?\s*PermitRootLogin\s+(no|prohibit-password)$",
        "PermitRootLogin yes",
        sshd_config,
        flags=re.MULTILINE
    )
    return write_file(FILE_SSHD, sshd_config)


def configure_locale(locale):
    """
    Configure /etc/default/locale
    :param locale: Locale
    :return: Whether the operation was successful
    """
    return (
        write_file(FILE_LOCALES, CONFIG_LANG.format(locale)) and
        run_cmd("locale-gen --purge {}".format(locale))
    )


def configure_keyboard(xkblayout, xkbmodel="pc105", xkbvariant="", xkboptions="", backspace="guess"):
    """
    Configure /etc/default/keyboard
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
    return write_file(FILE_KEYBOARD, keyboard_config)


def configure_apt(url="http://deb.debian.org/debian", distrib="stable", components=("main", "contrib", "non-free")):
    """
    Writes /etc/apt/source.list
    :param url: Repo url
    :param distrib: stable, unstable, stretch, buster, etc...
    :param components: main, contrib, non-free
    :return: Whether the operation was successful
    """
    sources_content = "deb {} {} {}\n".format(
        url,
        distrib,
        " ".join(components)
    )
    return (
            write_file(FILE_APT_CONFIG, CONFIG_APT_SUGGESTS) and
            write_file(FILE_APT_SOURCES, sources_content) and
            run_cmd("apt-get update")
    )


def write_fstab(boot_uuid, root_uuid):
    """
    Writes rpi fstab using boot_uuid and root_uuid
    :param boot_uuid: Boot partition uuid
    :param root_uuid: Root partition uuid
    :return: Whether the operation was successful
    """
    return write_file(FILE_FSTAB, CONFIG_FSTAB.format(boot_uuid, root_uuid))


def install_kernel():
    """
    Installs the Debian Arm64 kernel package
    :return: Whether the operation was successful
    """
    return run_cmd(CMD_KERNEL_INSTALL)


def change_rootpw(passwd):
    """
    Changes the system root password
    :param passwd: New root password
    :return: Whether the operation was successful
    """
    shadow_contents = read_file(FILE_PASSWD)
    if shadow_contents is not None:
        shadow_contents = re.sub(
            r"(?<=^root:)\*(?=:)",
            crypt.crypt(passwd, salt=crypt.METHOD_SHA256),
            shadow_contents
        )
        return write_file(FILE_PASSWD, shadow_contents)


def configure_vim():
    """
    Writes my prefered vim config
    :return: Whether the operation was successful
    """
    return write_file(FILE_VIMRC, CONFIG_VIM)
