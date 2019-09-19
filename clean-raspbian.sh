#!/bin/bash

# Configure localization
raspi-config nonint do_wifi_country US
raspi-config nonint do_change_locale en_US.UTF-8
raspi-config nonint do_configure_keyboard us
timedatectl set-timezone US/Arizona

cat << EOF >> /etc/default/locale
LANGUAGE=en_US.UTF-8
LC_ALL=en_US.UTF-8
LANG=en_US.UTF-8
EOF

cat << EOF >> /etc/default/keyboard
# KEYBOARD CONFIGURATION FILE

# Consult the keyboard(5) manual page.

XKBMODEL="pc105"
XKBLAYOUT="us"
XKBVARIANT=""
XKBOPTIONS=""

BACKSPACE="guess"
EOF

export LANGUAGE=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export XKBMODEL="pc105"
export XKBLAYOUT="us"

# Root login only
userdel -rf pi

# Remove uneeded packages
apt-get remove --purge  -y  \
    avahi*                  \
    dhcpcd5                 \
    ifupdown                \
    isc-dhcp-client         \
    net-tools               \
    openresolv
apt autoremove --purge -y

# Upgrade & install vim
apt-get update && apt-get dist-upgrade -y
apt-get install vim -y

cat << EOF > /etc/vim/vimrc.local
syntax on
set number
set ts=4
set sts=4
set sw=4
set expandtab

autocmd FileType make setlocal noexpandtab
autocmd FileType yaml setlocal ts=2 sts=2 sw=2 expandtab
EOF

# Remove old config files
rm -rf /etc/dhcp*
rm -rf /var/run/avahi-daemon/
rm -rf /etc/network*
rm /etc/resolv.conf

# Disable wifi & bt
cat << EOF > /etc/modprobe.d/blacklist-wifi-bt.conf
# wifi
blacklist brcmfmac
blacklist brcmutil

# bt
blacklist btbcm
blacklist hci_uart

EOF
update-initramfs -u

# Disable ipv6
cat << EOF > /etc/sysctl.d/99-disable-ipv6.conf
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1

EOF
sysctl -p

# Disable unneeded services
systemctl disable bluetooth
systemctl disable hciuart

# Configure networking with systemd-resolved and systemd-networkd
ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf
cat << EOF > /etc/systemd/network/99-default.network
[Match]
Name=*

[Network]
DHCP=ipv4

[DHCP]
UseDomains=yes

# Disable link-local addressing & ipv6
LinkLocalAddressing=no
IPv6AcceptRA=no

EOF

# Enable needed services
systemctl enable systemd-resolved
systemctl enable systemd-networkd
systemctl enable systemd-networkd-wait-online

# Reboot
echo "Rebooting..."
reboot
