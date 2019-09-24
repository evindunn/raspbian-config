# Custom debian 64 raspberry pi image
- Does localization
- Uses systemd-networkd / systemd-resolve for all DHCP/DNS client functionality
- Root is only user, default password toor


#### Create the custom image
1. Run create_img.py
2. Use [Drewsif's](https://github.com/Drewsif) awesome [pishrink.sh](https://github.com/Drewsif/PiShrink) script to create a small, bootable pi image
