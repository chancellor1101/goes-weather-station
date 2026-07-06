#!/usr/bin/env python3
"""Keep the latest of selected EMWIN graphic products (normalized to PNG for a
stable URL), serve them for Home Assistant, and delete all other unused graphics.
Served by goes-web on :8099 -> http://<lxc>:8099/graphics/<slug>.png"""
import os, re, glob, time
from PIL import Image

EMWIN = "/srv/goes/emwin"
OUT   = "/srv/goes/loop/graphics"     # under the goes-web docroot (/srv/goes/loop)
MAXAGE = 7200                          # delete raw (unused) EMWIN graphics older than 2h; selected ones
                                       # are copied to OUT first so tiles persist between issuances

# EMWIN product id (suffix before extension) -> (slug matching camera.wx_<slug>, friendly name).
SELECTED = {
    "RADSTHES": ("radar",     "Southeast US Radar (NWS)"),
    "CSA001US": ("tropical",  "NHC Tropical Surface Analysis"),
    "G02HURUS": ("surface",   "Tropical Atlantic (GOES-19 Enhanced IR)"),
    "G16CIRUS": ("spc_day1",  "CONUS East IR 2km (GOES-19)"),
    "MODDY1US": ("spc_conv",  "SPC Day 1 Convective Outlook"),   # issues 06/13/1630/20Z
}

def newest(pid):
    pat = re.compile(rf"-{re.escape(pid)}\.(GIF|JPG|PNG)$", re.I)
    cands = [f for f in glob.glob(os.path.join(EMWIN, "**", "*"), recursive=True)
             if os.path.isfile(f) and pat.search(os.path.basename(f))]
    return max(cands, key=os.path.getmtime) if cands else None

def main():
    os.makedirs(OUT, exist_ok=True)
    for pid, (slug, _name) in SELECTED.items():
        src = newest(pid)
        if not src:
            continue
        dst = os.path.join(OUT, slug + ".png")
        try:
            Image.open(src).convert("RGB").save(dst + ".tmp", "PNG")
            os.replace(dst + ".tmp", dst)
        except Exception as e:
            print("convert failed", src, e)
    # cleanup: raw EMWIN graphics are only needed transiently — selected ones are
    # already copied to OUT; delete everything older than MAXAGE.
    now = time.time()
    for f in glob.glob(os.path.join(EMWIN, "**", "*"), recursive=True):
        if os.path.isfile(f) and not f.lower().endswith(".txt"):
            try:
                if now - os.path.getmtime(f) > MAXAGE:
                    os.remove(f)
            except OSError:
                pass

if __name__ == "__main__":
    main()
