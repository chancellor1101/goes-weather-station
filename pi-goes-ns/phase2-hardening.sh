#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "=== Phase 2: Base hardening ==="

# --- 1. Packages ---
sudo apt-get update -qq
sudo apt-get install -y ufw fail2ban unattended-upgrades apt-listchanges chrony >/dev/null
echo "[ok] packages installed"

# --- 2. Firewall (ufw) ---------------------------------------------------
# The Pi only needs inbound SSH (from your LAN) plus the goesrecv packet
# publisher port 5004 reachable by the processing LXC. Adjust the CIDRs.
LAN=10.10.0.0/24          # your LAN subnet
LXC_IP=10.10.0.11         # the goes-proc LXC that subscribes to the packet stream
sudo sed -i 's/^IPV6=.*/IPV6=yes/' /etc/default/ufw
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from "$LAN" to any port 22 proto tcp comment 'ssh'
sudo ufw allow from "$LXC_IP" to any port 5004 proto tcp comment 'goesrecv packet stream'
sudo ufw --force enable
echo "[ok] ufw enabled"

# --- 3. SSH hardening (key-only) — key auth already confirmed working -----
sudo tee /etc/ssh/sshd_config.d/99-goesns.conf >/dev/null <<'EOF'
# goes-ns hardening
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowUsers cchance
EOF
# Validate before applying; reload (keeps current session alive)
sudo sshd -t && sudo systemctl reload ssh
echo "[ok] sshd hardened & reloaded"

# --- 4. unattended-upgrades (security only, NO auto-reboot for 24/7 appliance) ---
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
sudo tee /etc/apt/apt.conf.d/52goesns-unattended >/dev/null <<'EOF'
Unattended-Upgrade::Origins-Pattern {
    "origin=Debian,codename=${distro_codename},label=Debian-Security";
    "origin=Debian,codename=${distro_codename}-security,label=Debian-Security";
    "origin=Raspberry Pi Foundation";
};
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
sudo systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true
echo "[ok] unattended-upgrades configured (security only, no auto-reboot)"

# --- 5. fail2ban sshd jail ------------------------------------------------
sudo tee /etc/fail2ban/jail.d/goesns.local >/dev/null <<'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 4
backend  = systemd

[sshd]
enabled = true
EOF
sudo systemctl enable --now fail2ban >/dev/null 2>&1 || true
echo "[ok] fail2ban enabled"

# --- 6. NTP client -> TimeLord stratum-1 (this box is no longer the NTP server) ---
sudo tee /etc/chrony/conf.d/10-timelord.conf >/dev/null <<'EOF'
server 172.16.50.207 iburst prefer
pool time.cloudflare.com iburst maxsources 2
EOF
# Ensure timesyncd isn't fighting chrony
sudo systemctl disable --now systemd-timesyncd >/dev/null 2>&1 || true
sudo systemctl enable --now chrony >/dev/null 2>&1 || true
sudo systemctl restart chrony
echo "[ok] chrony -> TimeLord (172.16.50.207)"

# --- 7. Trim attack surface: disable bluetooth (headless appliance) -------
sudo systemctl disable --now bluetooth hciuart >/dev/null 2>&1 || true
echo "[ok] bluetooth disabled"

echo "=== Phase 2 complete ==="
