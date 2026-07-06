#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
VER="v0.30.0"; VNUM="${VER#v}"
echo "=== Phase 6: GOES + node metrics ==="
sudo apt-get update -qq
sudo apt-get install -y prometheus-node-exporter >/dev/null
echo "[ok] node-exporter installed"

# statsd_exporter from upstream (arm64)
if [ ! -x /usr/local/bin/statsd_exporter ]; then
  cd /tmp
  curl -fsSL "https://github.com/prometheus/statsd_exporter/releases/download/${VER}/statsd_exporter-${VNUM}.linux-arm64.tar.gz" -o se.tgz
  tar xzf se.tgz
  sudo install -m0755 "statsd_exporter-${VNUM}.linux-arm64/statsd_exporter" /usr/local/bin/statsd_exporter
  rm -rf se.tgz "statsd_exporter-${VNUM}.linux-arm64"
fi
/usr/local/bin/statsd_exporter --version 2>&1 | head -1

# systemd unit: ingest statsd on udp :8125 (goesrecv target), expose :9102
sudo tee /etc/systemd/system/statsd_exporter.service >/dev/null <<'EOF'
[Unit]
Description=Prometheus statsd exporter (goesrecv stats)
After=network.target

[Service]
User=nobody
ExecStart=/usr/local/bin/statsd_exporter --statsd.listen-udp=:8125 --web.listen-address=:9102
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now statsd_exporter >/dev/null 2>&1
sudo systemctl enable --now prometheus-node-exporter >/dev/null 2>&1

# ufw: let Grafana/Prometheus host scrape
sudo ufw allow from 172.16.50.146 to any port 9100 proto tcp comment 'node-exporter scrape' >/dev/null
sudo ufw allow from 172.16.50.146 to any port 9102 proto tcp comment 'statsd-exporter scrape' >/dev/null
echo "[ok] exporters + ufw ready"

sleep 4
echo "=== goesrecv statsd metric names being emitted ==="
curl -s http://localhost:9102/metrics | grep -vE '^#|^go_|^process_|^promhttp|^statsd_(build|exporter|metric_mapper)' | awk '{print $1}' | sort -u | head -50
echo "=== services ==="
systemctl is-active statsd_exporter prometheus-node-exporter
