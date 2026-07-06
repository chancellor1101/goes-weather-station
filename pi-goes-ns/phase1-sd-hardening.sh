#!/usr/bin/env bash
set -euo pipefail
echo "=== Phase 1: SD-card wear mitigation ==="

# --- 0. Backup fstab & journald.conf once ---
sudo cp -n /etc/fstab /etc/fstab.pre-goesns.bak
sudo cp -n /etc/systemd/journald.conf /etc/systemd/journald.conf.pre-goesns.bak || true

# --- 1. journald caps (bound RAM/disk journal size) ---
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/10-goesns.conf >/dev/null <<'EOF'
[Journal]
Storage=persistent
Compress=yes
SystemMaxUse=100M
SystemMaxFileSize=20M
RuntimeMaxUse=100M
MaxRetentionSec=1month
ForwardToSyslog=no
EOF

# --- 2. tmpfs for /tmp (idempotent fstab entry) ---
if ! grep -qE '^\S+\s+/tmp\s+tmpfs' /etc/fstab; then
  echo 'tmpfs  /tmp  tmpfs  defaults,noatime,nosuid,nodev,size=512M  0  0' | sudo tee -a /etc/fstab >/dev/null
  echo "added tmpfs /tmp to fstab"
else
  echo "tmpfs /tmp already in fstab"
fi

# --- 3. add commit=60 to root mount for fewer metadata flushes (keep noatime) ---
if grep -qE '^\S+\s+/\s+ext4\s+defaults,noatime\s' /etc/fstab; then
  sudo sed -i -E 's#(^\S+\s+/\s+ext4\s+)defaults,noatime(\s)#\1defaults,noatime,commit=60\2#' /etc/fstab
  echo "added commit=60 to root mount"
else
  echo "root fstab line not in expected form; leaving as-is:"; grep -E '\s/\s+ext4' /etc/fstab
fi

# --- 4. weekly fstrim ---
sudo systemctl enable --now fstrim.timer
sudo sed -i 's/^OnCalendar=.*/OnCalendar=weekly/' /lib/systemd/system/fstrim.timer 2>/dev/null || true

# --- 5. log2ram via azlux signed apt repo ---
if ! dpkg -l log2ram 2>/dev/null | grep -q '^ii'; then
  sudo install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://azlux.fr/repo.gpg | sudo tee /etc/apt/keyrings/azlux.gpg >/dev/null
  echo "deb [signed-by=/etc/apt/keyrings/azlux.gpg] http://packages.azlux.fr/debian/ stable main" \
    | sudo tee /etc/apt/sources.list.d/azlux.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y log2ram
else
  echo "log2ram already installed"
fi

# --- 6. tune log2ram: 128M, rsync, no mail ---
if [ -f /etc/log2ram.conf ]; then
  sudo sed -i -E 's/^SIZE=.*/SIZE=128M/' /etc/log2ram.conf
  sudo sed -i -E 's/^USE_RSYNC=.*/USE_RSYNC=true/' /etc/log2ram.conf
  sudo sed -i -E 's/^MAIL=.*/MAIL=false/' /etc/log2ram.conf
  echo "log2ram.conf tuned:"; grep -E '^(SIZE|USE_RSYNC|MAIL)=' /etc/log2ram.conf
fi

echo "=== Phase 1 script complete (reboot needed to activate log2ram + tmpfs + fstab changes) ==="
