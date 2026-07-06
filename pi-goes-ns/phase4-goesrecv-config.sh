#!/usr/bin/env bash
set -euo pipefail
echo "=== Phase 4b: GOES config + services ==="

# 1. dedicated service user (USB access via plugdev)
if ! id goes &>/dev/null; then
  sudo useradd -r -s /usr/sbin/nologin -G plugdev -d /srv/goes goes
  echo "[ok] created user goes"
fi
GID=$(id -g goes); UID_=$(id -u goes)

# 2. also blacklist the V4L2 SDR module (grabs the device)
grep -q rtl2832_sdr /etc/modprobe.d/blacklist-rtlsdr.conf || echo "blacklist rtl2832_sdr" | sudo tee -a /etc/modprobe.d/blacklist-rtlsdr.conf >/dev/null

# 3. udev rule so 'goes' (plugdev) can open the RTL-SDR
sudo tee /etc/udev/rules.d/20-rtlsdr.rules >/dev/null <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0660", GROUP="plugdev", TAG+="uaccess"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger --attr-match=idVendor=0bda 2>/dev/null || true
echo "[ok] udev rule applied"

# 4. tmpfs spool (SD-friendly: products live in RAM, rclone drains to MinIO)
sudo mkdir -p /srv/goes
if ! grep -qE '^\S+\s+/srv/goes\s+tmpfs' /etc/fstab; then
  echo "tmpfs /srv/goes tmpfs defaults,noatime,nosuid,nodev,size=1G,uid=${UID_},gid=${GID},mode=0755 0 0" | sudo tee -a /etc/fstab >/dev/null
fi
mountpoint -q /srv/goes || sudo mount /srv/goes
sudo chown goes:goes /srv/goes
echo "[ok] tmpfs /srv/goes mounted: $(findmnt -no SIZE /srv/goes)"

# 5. install configs + unit files
sudo install -m0644 ~/goes-ns-build/goesrecv.conf  /etc/goesrecv.conf
sudo install -m0644 ~/goes-ns-build/goesproc.conf  /etc/goesproc.conf
sudo install -m0644 ~/goes-ns-build/goesrecv.service /etc/systemd/system/goesrecv.service
sudo install -m0644 ~/goes-ns-build/goesproc.service /etc/systemd/system/goesproc.service
sudo systemctl daemon-reload
echo "[ok] configs + units installed"

# 6. start goesrecv only (validate device + signal before goesproc)
sudo systemctl enable goesrecv goesproc >/dev/null 2>&1
sudo systemctl restart goesrecv
sleep 2
systemctl is-active goesrecv && echo "[ok] goesrecv started" || { echo "goesrecv FAILED"; sudo journalctl -u goesrecv -n 30 --no-pager; }
echo "=== Phase 4b complete ==="
