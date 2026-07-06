#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "=== Phase 4a: goestools build ==="

# 1. Build deps + RTL-SDR userspace tools (rtl_test / rtl_biast)
sudo apt-get update -qq
sudo apt-get install -y build-essential cmake pkg-config git \
    libusb-1.0-0-dev librtlsdr-dev rtl-sdr libopencv-dev nlohmann-json3-dev >/dev/null
echo "[ok] build deps installed"

# 2. Free the RTL-SDR: blacklist the DVB-T kernel driver
sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf >/dev/null <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
blacklist dvb_usb_v2
EOF
sudo modprobe -r dvb_usb_rtl28xxu 2>/dev/null || true
echo "[ok] rtl28xxu blacklisted"

# 3. Clone + build goestools
cd ~/goes-ns-build
if [ ! -d goestools ]; then
  git clone --depth 1 https://github.com/pietern/goestools.git
fi
cd goestools
git submodule update --init --recursive 2>/dev/null || true
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local >/dev/null
make -j"$(nproc)"
sudo make install
sudo ldconfig
echo "[ok] goestools built + installed"
which goesrecv goesproc
goesrecv --help 2>&1 | head -3 || true
echo "=== Phase 4a complete ==="
