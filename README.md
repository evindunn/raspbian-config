# Custom debian 64 raspberry pi image
- Does localization
- Uses systemd-networkd / systemd-resolve for all DHCP/DNS client functionality
- Root is only user, default password toor


#### Create the custom image
1. `docker-compose up -d` to speed up subsequent builds
2. `conda env create -f environment.yml && conda activate rpi-64`
3. `sudo PATH="$PATH" bash -c './create_img.py'`
4. Use [Drewsif's](https://github.com/Drewsif) awesome [pishrink.sh](https://github.com/Drewsif/PiShrink) script to create a small, bootable pi image
5. `docker-compose down`
