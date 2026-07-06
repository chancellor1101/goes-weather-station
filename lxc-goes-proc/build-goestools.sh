#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "=== goes-proc: build goestools (with proj + opencv) ==="
apt-get update -qq
apt-get install -y build-essential cmake pkg-config git ca-certificates \
    libusb-1.0-0-dev librtlsdr-dev libopencv-dev libproj-dev nlohmann-json3-dev \
    rclone imagemagick ffmpeg python3-pil python3-numpy >/dev/null
echo "[ok] deps installed (incl. proj, opencv, ffmpeg, imagemagick, PIL/numpy for loops)"
mkdir -p /opt/goes-build && cd /opt/goes-build
[ -d goestools ] || git clone --depth 1 https://github.com/pietern/goestools.git
cd goestools && git submodule update --init --recursive 2>/dev/null || true
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local 2>&1 | grep -iE "proj|opencv" || true
make -j"$(nproc)" 2>&1 | tail -2
make install >/dev/null
ldconfig
echo "PROC_BUILD_DONE"
which goesproc && goesproc --help 2>&1 | head -1
