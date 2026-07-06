#!/usr/bin/env bash
# Deploy goesproc + loop + alerts + uploader on the PVE processing container.
# Run as root inside the LXC after build-goestools.sh. No sudo in minimal LXC.
set -euo pipefail
GOES_S3_SECRET="${GOES_S3_SECRET:?export GOES_S3_SECRET first}"
HA_TOKEN="${HA_TOKEN:?export HA_TOKEN first}"

id goes &>/dev/null || useradd -r -s /usr/sbin/nologin -d /srv/goes goes
install -d -o goes -g goes /srv/goes /var/lib/goes
install -d -m0750 -o root -g goes /etc/goes

# configs + units from this repo dir
install -m0644 etc/goesproc.conf /etc/goesproc.conf
install -m0644 systemd/*.service systemd/*.timer /etc/systemd/system/
install -m0755 make_loop.py emwin_alerts.py /opt/

# secrets (from env, never committed)
sed "s#REPLACE_WITH_GOES_S3_SECRET#${GOES_S3_SECRET}#" etc/goes/rclone.conf.example > /etc/goes/rclone.conf
sed "s#REPLACE_WITH_HA_LONG_LIVED_TOKEN#${HA_TOKEN}#" etc/goes/ha.env.example > /etc/goes/ha.env
chown root:goes /etc/goes/rclone.conf /etc/goes/ha.env
chmod 0640 /etc/goes/rclone.conf /etc/goes/ha.env

systemctl daemon-reload
systemctl enable --now goesproc goes-upload.timer goes-prune.timer goes-loop.timer goes-web goes-alerts
echo "deployed. goesproc subscribes to the Pi at tcp://10.10.0.9:5004"
