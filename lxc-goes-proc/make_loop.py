#!/usr/bin/env python3
"""Crop recent GOES-19 FD Band-13 frames to the KMOB region (reprojected to
Plate Carree), annotate, and assemble an animated loop for Home Assistant."""
import glob, os, re, sys, subprocess, datetime, zoneinfo
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC="/srv/goes/goes19/fd/ch13"
OUT="/srv/goes/loop"; FRAMES=os.path.join(OUT,"frames")
NFRAMES=18            # ~3-4h at 10-15min cadence
OW,OH=900,777
LON_MIN,LON_MAX,LAT_MIN,LAT_MAX=-95.4,-78.6,23.4,37.9
TZ=zoneinfo.ZoneInfo("America/Chicago")

# GOES-R fixed grid (FD 2km) projection constants
LON0=np.deg2rad(-75.0); H=42164160.0; R_EQ=6378137.0; R_POL=6356752.31414
E2=(R_EQ**2-R_POL**2)/R_EQ**2
XOFF=-0.151844; XSCALE=5.6e-05; YOFF=0.151844; YSCALE=-5.6e-05

def build_map():
    lons=np.linspace(LON_MIN,LON_MAX,OW); lats=np.linspace(LAT_MAX,LAT_MIN,OH)
    LON,LAT=np.meshgrid(np.deg2rad(lons),np.deg2rad(lats))
    phi_c=np.arctan((R_POL**2/R_EQ**2)*np.tan(LAT))
    rc=R_POL/np.sqrt(1-E2*np.cos(phi_c)**2)
    sx=H-rc*np.cos(phi_c)*np.cos(LON-LON0); sy=-rc*np.cos(phi_c)*np.sin(LON-LON0); sz=rc*np.sin(phi_c)
    x=np.arcsin(-sy/np.sqrt(sx**2+sy**2+sz**2)); y=np.arctan2(sz,sx)
    vis=H*(H-sx) >= (sy**2+(R_EQ**2/R_POL**2)*sz**2)
    col=np.clip(np.round((x-XOFF)/XSCALE).astype(int),0,5423)
    row=np.clip(np.round((y-YOFF)/YSCALE).astype(int),0,5423)
    return col,row,vis
COL,ROW,VIS=build_map()

# Enhanced-IR colour LUT (input = Band-13 brightness, bright=cold cloud tops):
# warm/low stays greyscale; cold tops ramp cyan->blue->green->yellow->orange->red->magenta.
def _build_ir_lut():
    # Band-13 data: clear-sky ~48, clouds ~60-143 (calm) up to ~255 (deep convection);
    # value 255 = baked-in white map overlays. Colour ramp starts just above clear sky.
    lut=np.zeros((256,3),dtype=np.uint8); T=60
    g=(np.arange(T)/max(T-1,1)*70).astype(np.uint8)          # clear/warm -> dark grey
    lut[:T,0]=g; lut[:T,1]=g; lut[:T,2]=g
    # clouds warm->cold: grey -> blue -> cyan -> green -> yellow -> orange -> red -> magenta -> white
    anchors=[(0.00,70,70,70),(0.06,60,80,140),(0.16,0,110,205),(0.28,0,185,205),
             (0.40,0,190,0),(0.53,205,205,0),(0.66,255,150,0),(0.78,220,0,0),
             (0.88,255,0,255),(0.96,255,255,255),(1.00,255,255,255)]
    p=(np.arange(T,256)-T)/(255-T); xs=[a[0] for a in anchors]
    for ch in range(3):
        lut[T:,ch]=np.interp(p,xs,[a[1+ch] for a in anchors]).astype(np.uint8)
    return lut
IR_LUT=_build_ir_lut()

def ts_from_name(fn):
    m=re.search(r'(\d{8}T\d{6}Z)',fn)
    if not m: return None
    return datetime.datetime.strptime(m.group(1),"%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc)

def render(path):
    im=np.asarray(Image.open(path).convert("L"))
    if im.shape!=(5424,5424): return None
    out=im[ROW,COL]; out[~VIS]=0
    img=Image.fromarray(IR_LUT[out],"RGB")
    t=ts_from_name(os.path.basename(path))
    d=ImageDraw.Draw(img)
    try: font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",22)
    except Exception: font=ImageFont.load_default()
    if t:
        loc=t.astimezone(TZ)
        label=f"GOES-19  Band 13 (Enhanced IR)   {t:%Y-%m-%d %H:%M} UTC  /  {loc:%I:%M %p %Z}"
    else: label="GOES-19 Band 13 (Enhanced IR)"
    d.rectangle([0,OH-34,OW,OH],fill=(0,0,0)); d.text((8,OH-30),label,fill=(255,255,255),font=font)
    return img

def main():
    os.makedirs(FRAMES,exist_ok=True)
    files=sorted(glob.glob(os.path.join(SRC,"**","*.jpg"),recursive=True), key=lambda p: ts_from_name(os.path.basename(p)) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc))
    files=files[-NFRAMES:]
    if not files: print("no FD ch13 frames yet"); return
    for f in glob.glob(os.path.join(FRAMES,"*.png")): os.remove(f)
    imgs=[]
    for i,f in enumerate(files):
        img=render(f)
        if img is None: continue
        img.save(os.path.join(FRAMES,f"frame_{i:03d}.png")); imgs.append(img)
    if not imgs: print("no valid frames"); return
    imgs[-1].save(os.path.join(OUT,"latest.jpg"),quality=88)
    # animated GIF (hold last frame longer)
    durs=[400]*(len(imgs)-1)+[1500]
    pal=[im.convert("P",palette=Image.ADAPTIVE,colors=96) for im in imgs]
    pal[0].save(os.path.join(OUT,"loop.gif"),save_all=True,append_images=pal[1:],duration=durs,loop=0,optimize=True,disposal=2)
    # MP4 via ffmpeg
    subprocess.run(["ffmpeg","-y","-framerate","4","-i",os.path.join(FRAMES,"frame_%03d.png"),
                    "-vf","pad=ceil(iw/2)*2:ceil(ih/2)*2","-pix_fmt","yuv420p","-loglevel","error",
                    os.path.join(OUT,"loop.mp4")],check=False)
    print(f"loop built: {len(imgs)} frames -> {OUT}/loop.gif, loop.mp4, latest.jpg")

if __name__=="__main__": main()
