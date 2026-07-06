# Architecture

Two-box split so the SD-card Raspberry Pi does only the light, hardware-bound work
(demodulation) and a Proxmox LXC does the heavy image processing.

```
  1694.1 MHz HRIT (GOES-19 / GOES-East)
        │  Nooelec SMArTee XTR v5 (E4000) + SAWbird+ GOES LNA (bias-tee)
        ▼
┌─────────────────────────┐        packet stream          ┌──────────────────────────────┐
│  Pi  goes-ns 10.10.0.9  │  tcp://10.10.0.9:5004 (nng)   │  LXC 204 goes-proc 10.10.0.11 │
│  • goesrecv (demod)     │ ────────────────────────────▶ │  • goesproc (decode+overlays) │
│  • network packet stream│                               │  • make_loop.py (IR loop)     │
│  • statsd+node exporters│                               │  • emwin_alerts.py (VTEC→HA)  │
│  ~22% CPU               │                               │  • rclone → MinIO             │
└─────────────────────────┘                               └───────────────┬──────────────┘
                                                                           │
                     ┌─────────────────────────────────────────┬──────────┴─────────┐
                     ▼                                          ▼                    ▼
          MinIO S3 (LXC 203 10.10.0.10)          Home Assistant 10.10.0.5    Grafana/Prometheus
          bucket `goes` (products archive)       camera.goes19_ir_loop        172.16.50.146
          backed by ZFS Local_Array/minio_s3     sensor.goes_wx_kmob          (4 scrape jobs)
```

## Hosts
- **Raspberry Pi** — Raspberry Pi OS (Debian). Demod only (`goesrecv`).
  SD-card hardened (log2ram, tmpfs, capped journald, weekly fstrim), key-only SSH,
  ufw, unattended security upgrades.
- **goes-proc** — Proxmox LXC 204 (Debian 13, 6 vCPU/4 GB). All decode/processing.
- **MinIO** — existing LXC 203; a scoped `goes` bucket + least-privilege `goessvc` user
  were added; Prometheus metrics enabled.

## Data flow
1. `goesrecv` on the Pi demodulates HRIT and publishes VCDU packets on `:5004`.
2. `goesproc` on the LXC subscribes over the network, decodes imagery (with coastline/state
   overlays) + EMWIN/NWS text to `/srv/goes`.
3. `rclone` archives `/srv/goes` to the MinIO `goes` bucket; a prune keeps 24 h locally.
4. `make_loop.py` crops the last 18 Full-Disk Band-13 frames to a ~500 mi box around KMOB
   (geostationary → Plate Carrée reprojection), builds an animated GIF/MP4, served on `:8099`.
5. `emwin_alerts.py` parses VTEC from local NWS products, tracks active hazards for WFO KMOB,
   and pushes `sensor.goes_wx_kmob` + notifications to Home Assistant.

## Notes / gotchas
- Build goestools **with `libproj-dev`** or goesproc rejects the map-overlay handlers.
- This build supports goes18/goes19 (`handler_goesr.cc`).
- HRIT carries Full Disk + Mesoscale + EMWIN — **no CONUS sector** (that's on GRB).
- Do **not** run `rtl_test -t` on the E4000 — it wedges the dongle into a USB latch that
  only a physical replug clears.
