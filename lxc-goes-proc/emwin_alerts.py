#!/usr/bin/env python3
"""Watch decoded EMWIN/NWS text for the local WFO (KMOB), parse VTEC, track
active hazards, and push to Home Assistant (sensor + notifications)."""
import os,re,glob,json,time,datetime,urllib.request,zoneinfo

HA_URL=os.environ.get("HA_URL","http://10.10.0.5:8123")
HA_TOKEN=os.environ["HA_TOKEN"]
OFFICE="KMOB"                       # local NWS office (WFO Mobile)
WATCH=["/srv/goes/text/nws","/srv/goes/text/other","/srv/goes/emwin"]
STATE="/var/lib/goes/alert_state.json"
TZ=zoneinfo.ZoneInfo("America/Chicago")
LIFE_SAFETY={("TO","W"),("SV","W"),("FF","W"),("FL","W"),("EW","W"),("SM","W"),("MA","W"),("SV","A"),("TO","A")}
PHEN={"TO":"Tornado","SV":"Severe Thunderstorm","FF":"Flash Flood","FL":"Flood","FA":"Areal Flood",
      "MA":"Marine","SM":"Special Marine","EW":"Extreme Wind","HU":"Hurricane","TR":"Tropical Storm",
      "HW":"High Wind","WI":"Wind","HT":"Heat","FG":"Dense Fog","CF":"Coastal Flood","RP":"Rip Current",
      "SU":"High Surf","FZ":"Freeze","WS":"Winter Storm","BZ":"Blizzard","FR":"Frost","SV.A":"Svr Watch"}
SIG={"W":"Warning","A":"Watch","Y":"Advisory","S":"Statement","F":"Forecast","O":"Outlook"}
VTEC=re.compile(r"/[OTEX]\.(NEW|CON|CAN|EXP|EXA|EXB|EXT|UPG|ROU)\.([A-Z]{4})\.([A-Z]{2})\.([AWYSFO])\.(\d{4})\.(\d{6}T\d{4}Z)-(\d{6}T\d{4}Z)/")

def hapost(path,obj):
    req=urllib.request.Request(HA_URL+path,data=json.dumps(obj).encode(),
        headers={"Authorization":f"Bearer {HA_TOKEN}","Content-Type":"application/json"},method="POST")
    try: urllib.request.urlopen(req,timeout=10).read()
    except Exception as e: print("HA post err",path,e)

def vtec_time(s): return datetime.datetime.strptime(s,"%y%m%dT%H%MZ").replace(tzinfo=datetime.timezone.utc)

def load():
    try: return json.load(open(STATE))
    except Exception: return {"seen":[],"active":{}}
def save(st): os.makedirs(os.path.dirname(STATE),exist_ok=True); json.dump(st,open(STATE,"w"))

def push_ha(active):
    now=datetime.datetime.now(datetime.timezone.utc)
    items=[]
    for k,a in active.items():
        exp=vtec_time(a["end"])
        items.append({"event":a["name"],"expires":exp.astimezone(TZ).strftime("%a %I:%M %p %Z"),"etn":a["etn"],"raw":k})
    items.sort(key=lambda x:x["raw"])
    state=len(items)
    hazards=", ".join(sorted({i["event"] for i in items})) or "None"
    hapost("/api/states/sensor.goes_wx_kmob",{"state":state,
        "attributes":{"friendly_name":"GOES EMWIN Alerts (KMOB)","unit_of_measurement":"active",
            "icon":"mdi:alert" if state else "mdi:shield-check","hazards":hazards,"alerts":items,
            "updated":now.astimezone(TZ).strftime("%Y-%m-%d %I:%M %p %Z")}})

def main():
    st=load(); seen=set(st.get("seen",[])); active=st.get("active",{})
    push_ha(active)
    while True:
        files=[]
        for d in WATCH: files+=glob.glob(os.path.join(d,"**","*.TXT"),recursive=True)+glob.glob(os.path.join(d,"**","*.txt"),recursive=True)
        for f in files:
            b=os.path.basename(f)
            try:
                if (time.time()-os.path.getmtime(f)) < 20: continue   # too fresh; let goesproc finish writing
            except OSError:
                continue
            if b in seen:                                             # already processed a prior cycle
                try: os.remove(f)
                except OSError: pass
                continue
            seen.add(b)
            try: txt=open(f,errors="ignore").read()
            except Exception: txt=""
            for m in VTEC.finditer(txt):
                action,office,phen,sig,etn,t0,t1=m.groups()
                if office!=OFFICE: continue          # my WFO only
                key=f"{office}.{phen}.{sig}.{etn}"
                name=f"{PHEN.get(phen,phen)} {SIG.get(sig,sig)}"
                if action in ("CAN","EXP","UPG"):
                    active.pop(key,None)
                else:
                    isnew = key not in active and action=="NEW"
                    active[key]={"name":name,"end":t1,"etn":etn,"phen":phen,"sig":sig}
                    if isnew and (phen,sig) in LIFE_SAFETY:
                        exp=vtec_time(t1).astimezone(TZ).strftime("%I:%M %p %Z")
                        hapost("/api/services/persistent_notification/create",
                            {"title":f"⚠️ {name} — KMOB","message":f"NWS Mobile issued a {name} (#{etn}). In effect until {exp}. Source: GOES-19 EMWIN.",
                             "notification_id":f"goes_{key}"})
                        hapost("/api/events/goes_wx_warning",{"event":name,"etn":etn,"office":office,"expires":t1})
            # NWS text is consumed only here (alerts) — delete after processing; graphics handled separately
            try: os.remove(f)
            except OSError: pass
        # expire old
        now=datetime.datetime.now(datetime.timezone.utc)
        for k in [k for k,a in active.items() if vtec_time(a["end"])<now]: active.pop(k,None)
        push_ha(active)
        st={"seen":list(seen)[-5000:],"active":active}; save(st)
        time.sleep(30)

if __name__=="__main__": main()
