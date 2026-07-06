#!/usr/bin/env python3
"""Guard against SDR USB re-enumeration. goesrecv keeps running but holds a dead
device handle, emitting all-zero stats (omega/gain=0). Detect, auto-restart,
publish a reception-health sensor to Home Assistant, and push a notification.

Config via environment (see /etc/goes/ha.env):
  HA_URL     e.g. http://10.10.0.5:8123
  HA_TOKEN   HA long-lived token
  HA_NOTIFY  notify service to call (default: notify.notify)
"""
import os, re, json, time, subprocess, urllib.request

HA_URL    = os.environ.get("HA_URL", "")
HA_TOKEN  = os.environ.get("HA_TOKEN", "")
HA_NOTIFY = os.environ.get("HA_NOTIFY", "notify.notify")   # e.g. notify.mobile_app_xxx
COOLDOWN  = 300                                            # min seconds between auto-restarts
STATEF    = "/run/goesrecv-watchdog.state"
LASTF     = "/run/goesrecv-watchdog.last"

def ha(path, obj):
    if not (HA_URL and HA_TOKEN): return
    try:
        req = urllib.request.Request(HA_URL + path, data=json.dumps(obj).encode(),
              headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print("HA post error", path, e)

def notify(title, msg, service=HA_NOTIFY):
    dom, _, svc = service.partition(".")
    ha(f"/api/services/{dom}/{svc}", {"title": title, "message": msg})
    ha("/api/services/persistent_notification/create",
       {"title": title, "message": msg, "notification_id": "goes_reception"})

def latest_stat():
    out = subprocess.run(["journalctl", "-u", "goesrecv", "--since", "80 seconds ago", "-o", "cat"],
                         capture_output=True, text=True).stdout
    lines = [l for l in out.splitlines() if "[monitor]" in l]
    if not lines: return None
    l = lines[-1]
    def g(key):
        m = re.search(rf"{key}:\s*([-0-9.]+)", l); return float(m.group(1)) if m else None
    return {"omega": g("omega"), "packets": g("packets"), "vit": g(r"vit\(avg\)"), "gain": g("gain")}

def read(f, d=""):
    try: return open(f).read().strip()
    except OSError: return d

def main():
    active = subprocess.run(["systemctl", "is-active", "--quiet", "goesrecv"]).returncode == 0
    st = latest_stat()
    prev = read(STATEF, "unknown")
    if not active or st is None:
        cur = "down"
    elif not st["omega"]:                       # omega 0/None -> no samples from the SDR
        cur = "stalled"
    else:
        cur = "ok"

    # heartbeat sensor (also lets HA alert if this stops updating)
    if st:
        ha("/api/states/sensor.goesrecv_status", {
            "state": {"ok": "Receiving", "stalled": "Stalled", "down": "Down"}.get(cur, cur),
            "attributes": {"friendly_name": "GOES-19 Reception",
                "icon": "mdi:satellite-uplink" if cur == "ok" else "mdi:satellite-variant",
                "packets": st["packets"], "viterbi_avg": st["vit"], "gain": st["gain"],
                "updated": time.strftime("%Y-%m-%d %H:%M:%S %Z")}})

    if cur != "ok":
        now = time.time(); last = float(read(LASTF, "0") or 0)
        if now - last >= COOLDOWN:
            open(LASTF, "w").write(str(now))
            subprocess.run(["systemctl", "restart", "goesrecv"])
            subprocess.run(["logger", "-t", "goesrecv-watchdog", f"stall ({cur}) — restarted goesrecv"])
            notify("⚠️ GOES-19 reception stalled",
                   "The SDR stopped delivering samples; auto-restarted goesrecv (recovers in ~30s). "
                   "If you keep getting this, the dongle may need a physical unplug/replug.")
    elif prev in ("stalled", "down"):
        notify("✅ GOES-19 reception recovered", "goesrecv re-locked; packets are flowing again.")
        ha("/api/services/persistent_notification/dismiss", {"notification_id": "goes_reception"})

    open(STATEF, "w").write(cur)

if __name__ == "__main__":
    main()
