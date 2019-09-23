#!/bin/bash
set -e

function printf_blue {
    printf "\u001b[34;1m"
    printf "$@"
    printf "\u001b[0m"
}

if [ -z "$1" ]; then
    printf_blue "You have to specify a *.img file\n"
    exit 1
fi

if [ -f "$1" ]; then
    rm $1
fi

printf_blue "Creating %s...\n" $1
dd                          \
    status=progress         \
    if=/dev/zero            \
    of="$1"                 \
    iflag=fullblock         \
    bs=1M                   \
    count=2048
printf "\n"

mount_loc=$(losetup -f -P --show $1)
printf_blue "Image %s mounted at %s\n\n" $1 $mount_loc

printf_blue "Formatting %s...\n" $mount_loc
parted -s $mount_loc mklabel msdos
parted -s -a optimal $mount_loc mkpart primary fat32 0% 256M
parted -s -a optimal $mount_loc mkpart primary ext4 256M 100%
mkfs.vfat "$mount_loc"p1
mkfs.ext4 "$mount_loc"p2

mount -i -o exec,dev "$mount_loc"p2 /mnt
printf_blue "Root partition mounted at /mnt\n"

mkdir -p /mnt/boot/firmware
mount -i -o exec,dev "$mount_loc"p1 /mnt/boot/firmware
printf_blue "Boot partition mounted at /mnt/boot/firmware\n\n"

include_pkgs=(
    dosfstools
    firmware-brcm80211
    firmware-misc-nonfree
    firmware-realtek
    haveged
    parted
    raspi3-firmware
    systemd
    ssh
    wireless-tools
    wpasupplicant
)
include_pkgs=$(printf "%s," "${include_pkgs[@]}")
printf_blue "Creating minimal linux system at /mnt\n"
qemu-debootstrap                                                \
    --keyring=/usr/share/keyrings/debian-archive-keyring.gpg    \
    --components=main,contrib,non-free                          \
    --include=${include_pkgs:0:-1}                              \
    --variant=minbase                                           \
    --arch=arm64                                                \
    stable                                                      \
    /mnt                                                        \
    http://ftp.debian.org/debian 

cat << EOF > /mnt/etc/default/locale
LANG=en_US.UTF-8
LC_ALL=en_US.UTF-8
LANGUAGE=en_US.UTF-8
EOF

cat << EOF > /mnt/etc/default/keyboard
XKBMODEL="pc105"
XKBLAYOUT="us"
XKBVARIANT=""
XKBOPTIONS=""
BACKSPACE="guess"
EOF

cat << EOF > /mnt/etc/apt/sources.list
deb http://deb.debian.org/debian stable main contrib non-free
EOF

cat << EOF > /mnt/etc/hostname
raspberrypi
EOF

cat << EOF > /mnt/etc/hosts
127.0.0.1	localhost
127.0.1.1	raspberrypi
EOF

chroot /mnt rm -f /sbin/init
chroot /mnt ln -s /lib/systemd/systemd /sbin/init

mount -o bind /proc /mnt/proc
mount -o bind /sys /mnt/sys
mount -o bind /dev /mnt/dev
mount -o bind /dev/pts /mnt/dev/pts

mkdir -p /mnt/run/systemd/resolve
rm /mnt/etc/resolv.conf
cp /run/systemd/resolve/stub-resolv.conf /mnt/run/systemd/resolve/stub-resolv.conf
chroot /mnt ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

chroot /mnt systemctl enable systemd-networkd
chroot /mnt systemctl enable systemd-resolved

cat << EOF > /mnt/etc/fstab
/dev/mmcblk0p1  /boot/firmware  vfat    defaults            0 2
/dev/mmcblk0p2  /               ext4    defaults,noatime    0 1
proc            /proc           proc    defaults            0 0
EOF

printf_blue "Installing kernel in /mnt...\n"
chroot /mnt apt-get install -y linux-image-arm64

# Allow root logins with no password
sed -i 's,root:[^:]*:,root::,' /mnt/etc/shadow

printf_blue "Unmounting...\n"
umount /mnt/proc
umount /mnt/sys
umount /mnt/dev/pts
umount /mnt/dev
umount /mnt/boot/firmware
umount /mnt
losetup -d $mount_loc

printf_blue "Done. Burn $1 to an SD card\n"
