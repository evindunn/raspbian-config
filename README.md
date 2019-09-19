# Custom rasbian image
Shrinks raspbian stretch by about 300MB, simplifies networking

- Does localization
- Uses systemd-networkd / systemd-resolve for all DHCP/DNS client functionality
    - No dhclient or dhcpcd
    - No resolvconf
- Disables ipv6 (sysctl), bluetooth (module blacklist, systemd services), wifi (module blacklist)
- Vim installed
- Root is only user


#### Create the custom image
1. Boot the generic raspbian stretch image
2. Log in as pi, change root password
3. Enable root ssh:
```
sed -Ei "s/^#? *PermitRootLogin +.*$/PermitRootLogin yes/" /etc/ssh/sshd_config
systemctl enable ssh && systemctl restart ssh
```
3. Copy the script to root user's home directory: `scp clean-raspbian.sh root@raspberry:/root/`
4. Run the script: `ssh root@raspberry 'chmod +x /root/clean-raspbian.sh && /root/clean-raspbian.sh'`
    The pi will reboot when done.
6. dd the image from the SD card to a .img file
7. Use [Drewsif's](https://github.com/Drewsif) awesome [pishrink.sh](https://github.com/Drewsif/PiShrink) script to create a small, bootable pi image
