import logging
import os
import re

from lib.common import systemd_enable, write_file, read_file, run_cmd
from lib.disk import unmount_device

CONFIG_DHCP = """
[Match]
Name=*

[Network]
DHCP=ipv4
"""

CONFIG_HOSTS = """
127.0.0.1    localhost
127.0.1.1    {}
"""

DIR_RESOLVCONF = "/run/systemd/resolve"

FILE_HOSTNAME = "/etc/hostname"
FILE_HOSTS = "/etc/hosts"

FILE_NETWORKD_DEFAULT = "/etc/systemd/network/99-default.network"
FILE_RESOLVCONF_RUN = "/run/systemd/resolve/resolv.conf"
FILE_RESOLVCONF_ETC = "/etc/resolv.conf"

FILE_SSHD = "/etc/ssh/sshd_config"


def configure_hostname(hostname):
    """
    Configures /etc/hostname and /etc/hosts
    :param hostname: Hostname
    :return: Whether the operation was successful
    """
    return (
        write_file(FILE_HOSTNAME, "{}\n".format(hostname)) and
        write_file(FILE_HOSTS, CONFIG_HOSTS.format(hostname))
    )


def configure_networking():
    """
    Configures networking in the given chroot using systemd-networkd and
    systemd-resolved
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
    success = systemd_enable("dbus")

    if success:
        logging.info("Configuring systemd-networkd...")
        success = (
            write_file(FILE_NETWORKD_DEFAULT, CONFIG_DHCP) and
            success and systemd_enable("systemd-networkd")
        )

    if success:
        logging.info("Configuring systemd-resolved...")
        try:
            os.makedirs(DIR_RESOLVCONF, mode=0o755, exist_ok=True)
            success = (
                run_cmd("cp {} {}".format(FILE_RESOLVCONF_ETC, FILE_RESOLVCONF_RUN)) and
                unmount_device(FILE_RESOLVCONF_ETC)
            )
            os.remove(FILE_RESOLVCONF_ETC)
        except Exception as e:
            logging.error("Error copying systemd-resolved files: {}".format(e))
            success = False

        if success:
            try:
                os.symlink(FILE_RESOLVCONF_RUN, FILE_RESOLVCONF_ETC)
            except Exception as e:
                logging.error("Error symlinking resolvconf: {}".format(e))
                success = False

        if success:
            success = systemd_enable("systemd-resolved")

        if success:
            ssh_config = read_file(FILE_SSHD)
            try:
                ssh_config = re.sub(
                    r"# +(?=PermitRootLogin\s+yes|no|prohibit-password)$",
                    "",
                    ssh_config,
                    re.MULTILINE
                )
            except Exception as e:
                logging.error("Error formatting ssh config: {}".format(e))
                success = False

            if success:
                success = (
                    write_file(FILE_SSHD, ssh_config) and
                    systemd_enable("ssh")
                )

    return success
