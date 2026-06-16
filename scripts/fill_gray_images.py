#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end: search Pexels for missing-image attractions, gray-filter, ingest to disk + manifest.
Usage: python3 fill_gray_images.py <missing_q.json> <region_filter|ALL> [--commit]
missing_q.json items: {country,city,region,name,q,has_dir}
Saves best color image to images/<region>/<city>/<name>_1.jpg and registers in that manifest.json
Also makes a montage per city under /tmp/gray_fill/<city>.png for vision review.
"""
import json,os,sys,subprocess,statistics as st,re
from PIL import Image,ImageDraw,ImageFont
from urllib.parse import quote

QF=sys.argv[1]; RFILTER=sys.argv[2]
DO_COMMIT="--commit" in sys.argv
ROOT="/home/ubuntu/tools/travel_APP/travel_guide/data"
IMG=f"{ROOT}/images"
REVIEW=os.environ.get("REVIEW_DIR","/tmp/gray_fill"); os.makedirs(REVIEW,exist_ok=True)

KEY=None
for line in open("/home/ubuntu/tools/travel_APP/.env"):
    if line.startswith("PEXELS_KEY="): KEY=line.strip().split("=",1)[1]

def gray_score(fp):
    try:
        im=Image.open(fp).convert('RGB').resize((60,60)); px=list(im.getdata())
        return st.mean(max(r,g,b)-min(r,g,b) for r,g,b in px)
    except: return -1

def fetch_pexels(q,n=8):
    import time
    url=f"https://api.pexels.com/v1/search?query={quote(q)}&per_page={n}&orientation=landscape"
    for attempt in range(4):
        r=subprocess.run(["curl","-s","-m","30","-H",f"Authorization: {KEY}",url],capture_output=True,text=True)
        try: data=json.loads(r.stdout)
        except: data={}
        photos=data.get("photos")
        if photos: return [(p["src"]["large"],p.get("alt","")) for p in photos]
        # empty or rate-limited: backoff and retry
        time.sleep(2.5*(attempt+1))
    return []

def dl(url,fp):
    subprocess.run(["curl","-s","-m","40","-o",fp,url],check=False)
    return os.path.exists(fp) and os.path.getsize(fp)>5000

import hashlib
def md5(fp):
    try: return hashlib.md5(open(fp,"rb").read()).hexdigest()
    except: return None

def safe(s): return re.sub(r'[/\\]','_',s)

items=json.load(open(QF,encoding="utf-8"))
if RFILTER!="ALL":
    items=[m for m in items if m["region"]==RFILTER]
# optional query override: env QOVERRIDE=path to json {name: english_query}
QOV={}
_ov=os.environ.get("QOVERRIDE")
if _ov and os.path.exists(_ov):
    QOV=json.load(open(_ov,encoding="utf-8"))
print(f"处理 {len(items)} 个景点 (region={RFILTER}) commit={DO_COMMIT} override={len(QOV)}")

# group by (region,city) for montage
from collections import defaultdict
bycity=defaultdict(list)
results=[]
city_seen_md5=defaultdict(set)   # per-city md5 to drop generic repeats
for m in items:
    spot=m["name"]; q=QOV.get(m["name"]) or m["q"]; region=m["region"]; city=m["city"]
    cdir=f"{IMG}/{region}/{city}"; os.makedirs(cdir,exist_ok=True)
    rawdir=f"{REVIEW}/raw/{safe(region)}_{safe(city)}/{safe(spot)}"; os.makedirs(rawdir,exist_ok=True)
    urls=fetch_pexels(q)
    # collect color candidates with md5, pick first that's NOT a city-duplicate
    cands=[]
    for j,(u,alt) in enumerate(urls):
        fp=f"{rawdir}/raw_{j}.jpg"
        if dl(u,fp):
            gs=gray_score(fp)
            if gs>=14: cands.append((gs,fp,alt,md5(fp)))
    cands.sort(key=lambda x:-x[0])
    best=None;bestgs=-1;bestalt=""
    for gs,fp,alt,h in cands:
        if h and h in city_seen_md5[(region,city)]: continue   # skip generic repeat
        best,bestgs,bestalt=fp,gs,alt
        if h: city_seen_md5[(region,city)].add(h)
        break
    status="OK" if best else ("DUP/NOIMG")
    if best:
        dest=f"{cdir}/{safe(spot)}_1.jpg"
        results.append({"region":region,"city":city,"spot":spot,"q":q,"src":best,"dest":dest,"gs":round(bestgs,1),"alt":bestalt})
        bycity[(region,city)].append((spot,best))
    print(f"  {city:8} {spot:20} gs={round(bestgs,1)} {status} q={q!r}")

# montages per city for vision
# results entries carry the english query; build a lookup spot->q for labeling
spot_q={}
for r in results:
    spot_q[(r["region"],r["city"],r["spot"])]=r.get("q","")
for (region,city),spots in bycity.items():
    n=len(spots)
    cols=2; rows=(n+1)//2; cw,ch=400,300
    canvas=Image.new("RGB",(cols*cw,max(rows,1)*ch),(30,30,40)); d=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",18)
    except:
        try: font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",18)
        except: font=ImageFont.load_default()
    for i,(spot,fp) in enumerate(spots):
        try:
            im=Image.open(fp).convert("RGB"); im.thumbnail((cw-10,ch-52))
            x=(i%cols)*cw; y=(i//cols)*ch
            canvas.paste(im,(x+5,y+5))
            q=spot_q.get((region,city,spot),"")
            d.rectangle([x+5,y+ch-44,x+cw-5,y+ch-2],fill=(0,0,0))
            d.text((x+10,y+ch-42),f"{i+1}.{spot[:16]}",fill=(255,255,0),font=font)
            d.text((x+10,y+ch-22),f"[{q[:34]}]",fill=(120,220,255),font=font)
        except: pass
    canvas.save(f"{REVIEW}/{safe(city)}.png")

json.dump(results,open(f"{REVIEW}/_ingest_{safe(RFILTER)}.json","w"),ensure_ascii=False,indent=1)
print(f"\n搜到图 {len(results)}/{len(items)}  评审montage在 {REVIEW}/<city>.png")

if DO_COMMIT:
    # write into per-region manifest.json
    from collections import defaultdict
    bym=defaultdict(list)
    for r in results: bym[r["region"]].append(r)
    for region,rs in bym.items():
        mf=f"{IMG}/{region}/manifest.json"
        data=json.load(open(mf,encoding="utf-8")) if os.path.exists(mf) else []
        for r in rs:
            local=f"{r['city']}/{safe(r['spot'])}_1.jpg"
            data.append({"city":r["city"],"attraction":r["spot"],"status":"ok",
                         "local":local,"license":"Pexels","artist":r.get("alt",""),
                         "source":"pexels","extras":[]})
        json.dump(data,open(mf,"w"),ensure_ascii=False,indent=1)
        print(f"  写入 {mf}: +{len(rs)}条")
    print("COMMIT done")
