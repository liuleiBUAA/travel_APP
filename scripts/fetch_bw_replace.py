#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch color replacement candidates for B&W images.
Pexels via curl (key from .env), Commons via requests. Grayscale-filter, montage per spot.
Usage: python3 fetch_bw_replace.py <queries.json> <batch_out_dir>
queries.json = [{file, spot, q, src:"pexels"|"commons"}]
"""
import json,os,sys,subprocess,statistics as st
from PIL import Image,ImageDraw,ImageFont
import requests
from urllib.parse import quote

QF=sys.argv[1]; OUT=sys.argv[2]
os.makedirs(OUT,exist_ok=True)
queries=json.load(open(QF,encoding="utf-8"))

# read PEXELS_KEY
KEY=None
for line in open("/home/ubuntu/tools/travel_APP/.env"):
    if line.startswith("PEXELS_KEY="): KEY=line.strip().split("=",1)[1]
UA="travelapp/1.0 (contact@example.com)"

def gray_score(fp):
    try:
        im=Image.open(fp).convert('RGB').resize((60,60)); px=list(im.getdata())
        return st.mean(max(r,g,b)-min(r,g,b) for r,g,b in px)
    except: return -1

def fetch_pexels(q,n=8):
    url=f"https://api.pexels.com/v1/search?query={quote(q)}&per_page={n}&orientation=landscape"
    r=subprocess.run(["curl","-s","-m","30","-H",f"Authorization: {KEY}",url],capture_output=True,text=True)
    try: data=json.loads(r.stdout)
    except: return []
    return [p["src"]["large"] for p in data.get("photos",[])]

def fetch_commons(q,n=12):
    url=f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={quote(q)}&gsrnamespace=6&gsrlimit={n}&prop=imageinfo&iiprop=url&iiurlwidth=1000&format=json"
    try:
        r=requests.get(url,headers={"User-Agent":UA},timeout=40); data=r.json()
    except: return []
    out=[]
    for pid,p in data.get("query",{}).get("pages",{}).items():
        ii=p.get("imageinfo",[])
        if ii:
            t=p.get("title","").lower()
            if any(b in t for b in ["map","plan","armour","artillery","interior","aerial","postcard",".svg","diagram"]): continue
            out.append(ii[0].get("thumburl") or ii[0].get("url"))
    return out

def dl(url,fp):
    try:
        if "wikimedia" in url or "wikipedia" in url:
            r=requests.get(url,headers={"User-Agent":UA},timeout=60)
            if r.status_code==200 and len(r.content)>5000: open(fp,"wb").write(r.content); return True
        else:
            subprocess.run(["curl","-s","-m","40","-o",fp,url],check=False)
            if os.path.exists(fp) and os.path.getsize(fp)>5000: return True
    except: pass
    return False

def montage(spot,imgs,outp):
    n=len(imgs)
    if n==0: return False
    cols=2; rows=(n+1)//2
    cw,ch=400,280
    canvas=Image.new("RGB",(cols*cw,rows*ch),(30,30,40))
    d=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",28)
    except: font=ImageFont.load_default()
    for i,fp in enumerate(imgs):
        try:
            im=Image.open(fp).convert("RGB"); im.thumbnail((cw-10,ch-10))
            x=(i%cols)*cw; y=(i//cols)*ch
            canvas.paste(im,(x+5,y+5))
            d.rectangle([x+5,y+5,x+55,y+38],fill=(0,0,0))
            d.text((x+12,y+8),f"#{i+1}",fill=(255,255,0),font=font)
        except: pass
    canvas.save(outp); return True

results={}
for item in queries:
    spot=item["spot"]; src=item["src"]; q=item["q"]
    sdir=os.path.join(OUT,spot); os.makedirs(sdir,exist_ok=True)
    urls=fetch_commons(q) if src=="commons" else fetch_pexels(q)
    kept=[]
    for j,u in enumerate(urls):
        fp=os.path.join(sdir,f"raw_{j}.jpg")
        if dl(u,fp):
            gs=gray_score(fp)
            if gs>=14:  # color only
                kept.append((gs,fp))
        if len(kept)>=4: break
    kept_fps=[fp for gs,fp in kept]
    mp=os.path.join(OUT,f"{spot}.png")
    ok=montage(spot,kept_fps,mp)
    results[spot]={"src":src,"q":q,"kept":len(kept_fps),"montage":mp if ok else None,"file":item["file"]}
    print(f"{spot:10} {src:7} 候选{len(urls)} 彩色保留{len(kept_fps)} {'OK' if ok else 'NO_MONTAGE'}")

json.dump(results,open(os.path.join(OUT,"_results.json"),"w"),ensure_ascii=False,indent=1)
print("\nDONE",OUT)
