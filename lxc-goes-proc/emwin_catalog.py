import glob,os,re,shutil
EM="/srv/goes/emwin"; SAMP="/srv/goes/loop/samples"
os.makedirs(SAMP,exist_ok=True)
files=[f for f in glob.glob(os.path.join(EM,"**","*"),recursive=True) if os.path.isfile(f) and not f.lower().endswith(".txt")]
prod={}
for f in files:
    b=os.path.basename(f)
    m=re.search(r"-([A-Z0-9]+)\.(GIF|JPG|PNG)$",b,re.I)
    mo=re.match(r"Z_[A-Z0-9]{6}([A-Z]{4})",b)
    pid=m.group(1) if m else "UNK"; off=mo.group(1) if mo else "?"
    d=prod.setdefault(pid,{"n":0,"off":off,"sample":f})
    d["n"]+=1
    if os.path.getmtime(f)>os.path.getmtime(d["sample"]): d["sample"]=f
print(f"ACCUMULATED {len(files)} graphics, {len(prod)} distinct products")
for p,d in sorted(prod.items(),key=lambda x:(x[1]["off"],-x[1]["n"])):
    ext=os.path.splitext(d["sample"])[1]
    try: shutil.copy2(d["sample"],os.path.join(SAMP,f"{d['off']}_{p}{ext}"))
    except Exception: pass
    print(f"{p}\t{d['off']}\t{d['n']}")
