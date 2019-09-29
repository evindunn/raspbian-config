import re
from .common import run_cmd

CMD_DEBOOTSTRAP = re.sub(r"\s+", " ", """
    qemu-debootstrap
        --arch={}
        --keyring=/usr/share/keyrings/debian-archive-keyring.gpg
        --components={}
        --include={}
        --variant={}
        stable
        {}
        {}
""").strip()


def debootstrap(mnt_point, arch="arm64", components=("main", "contrib", "non-free"), extra_pks=(), variant="minbase", repo="http://ftp.debian.org/debian"):
    """
    Run debootrap at mnt_point
    :param mnt_point: Chroot for debootrap system
    :param arch: Chroot system architecture
    :param components: Debian components for Chroot packages
    :param extra_pks: Extra packages to install
    :param variant: Debootstrap variant to install
    :return: Whether the operation was successful
    """

    # Need debootstrap, debian-archive-keyring, qemu, binfmt-support, qemu-user-static
    extra_pks = ",".join(extra_pks)
    components = ",".join(components)
    return run_cmd(
        CMD_DEBOOTSTRAP.format(
            arch,
            components,
            extra_pks,
            variant,
            mnt_point,
            repo
        )
    )
