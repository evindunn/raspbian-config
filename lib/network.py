import logging
import os
import re

from lib.common import run_cmd, systemd_enable, Chroot, write_file, read_file

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


def configure_hostname(chroot, hostname):
    """
    Configures /etc/hostname and /etc/hosts for the given chroot directory
    :param chroot: Filesystem root
    :param hostname: Hostname
    :return: Whether the operation was successful
    """
    return (
        write_file("{}{}".format(chroot, FILE_HOSTNAME), "{}\n".format(hostname)) and
        write_file("{}{}".format(chroot, FILE_HOSTS), CONFIG_HOSTS.format(hostname))
    )


def configure_networking(chroot):
    """
    Configures networking in the given chroot using systemd-networkd and
    systemd-resolved
    :param chroot: Filesystem root
    :return: Whether the operation was successful
    """
    logging.info("Enabling dbus...")
    success = systemd_enable("dbus", chroot=chroot)

    if success:
        logging.info("Configuring systemd-networkd...")
        success = write_file(
            "{}{}".format(chroot, FILE_NETWORKD_DEFAULT),
            CONFIG_DHCP
        )
        success = success and systemd_enable("systemd-networkd", chroot=chroot)

    if success:
        logging.info("Configuring systemd-resolved...")
        try:
            os.makedirs(
                "{}{}".format(chroot, DIR_RESOLVCONF),
                mode=0o755,
                exist_ok=True
            )
            os.remove("{}{}".format(chroot, FILE_RESOLVCONF_ETC))
            success = run_cmd(
                "cp {} {}{}".format(
                    FILE_RESOLVCONF_RUN,
                    chroot,
                    FILE_RESOLVCONF_RUN
                )
            )
        except Exception as e:
            logging.error("Error copying systemd-resolved files: {}".format(e))
            success = False

        if success:
            try:
                with Chroot(chroot):
                    os.symlink(FILE_RESOLVCONF_RUN, FILE_RESOLVCONF_ETC)
            except Exception as e:
                logging.error("Error symlinking resolvconf: {}".format(e))
                success = False

        success = success and systemd_enable("systemd-resolved", chroot=chroot)

        if success:
            logging.info("Configuring ssh...")
            ssh_config_file = "{}{}".format(chroot, FILE_SSHD)
            ssh_config = read_file(ssh_config_file)

            try:
                ssh_config = re.sub(
                    r"# ?(?=PermitRootLogin\s+yes|no|prohibit-password)$",
                    "",
                    ssh_config,
                    re.MULTILINE
                )
            except Exception as e:
                logging.error("Error formatting ssh config: {}".format(e))
                success = False

            success = (
                success and
                write_file(ssh_config_file, ssh_config) and
                systemd_enable("ssh", chroot=chroot)
            )

    return success
