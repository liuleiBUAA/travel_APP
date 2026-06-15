#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commons-only fetcher with rate-limit handling (sleep between dl, browser UA, retry on 429)."""
import json,os,sys,time,statistics as st
from PIL import Image,ImageDraw,ImageFont
import requests
from urllib.parse import quote

QF=sys.argv[1]; OUT=sys.argv[2]
os.makedirs(OUT,exist_ok=True)
queries=json.load(open(QF,encoding="utf-8"))
UA="Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
API_UA="travelapp-imagefetch/1.0 (https://awesometravelpartner.cn; admin@awesometravelpartner.cn)"

def gray_score(fp):
    try:
        im=Image.open(fp).convert('RGB').resize((60,60)); px=list(im.getdata())
        return st.mean(max(r,g,b)-min(r,g,b) for r,g,b in px)
    except: return -1

def search(q,n=20):
    url=f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={quote(q)}&gsrnamespace=6&gsrlimit={n}&prop=imageinfo&iiprop=url&iiurlwidth=1200&format=json"
    r=requests.get(url,headers={"User-Agent":API_UA},timeout=40); data=r.json()
    out=[]
    for pid,p in data.get("query",{}).get("pages",{}).items():
        t=p.get("title","").lower()
        if any(b in t for b in ["map","plan",".svg","diagram","coat of arms","logo","crest",".pdf","interior","aerial","postcard","engraving","1850","1900","drawing","painting"]): continue
        ii=p.get("imageinfo",[])
        if ii: out.append((ii[0].get("thumburl") or ii[0].get("url"), t))
    return out

def dl(url,fp,tries=4):
    for k in range(tries):
        try:
            r=requests.get(url,headers={"User-Agent":UA},timeout=60)
            if r.status_code==200 and len(r.content)>8000:
                open(fp,"wb").write(r.content); return True
            if r.status_code==429:
                time.sleep(3*(k+1)); continue
        except: time.sleep(2)
    return False

def montage(spot,imgs,outp):
    n=len(imgs)
    if n==0: return False
    cols=2; rows=(n+1)//2; cw,ch=400,280
    canvas=Image.new("RGB",(cols*cw,rows*ch),(30,30,40)); d=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",28)
    except: font=ImageFont.load_default()
    for i,fp in enumerate(imgs):
        try:
            im=Image.open(fp).convert("RGB"); im.thumbnail((cw-10,ch-10))
            x=(i%cols)*cw; y=(i//cols)*ch; canvas.paste(im,(x+5,y+5))
            d.rectangle([x+5,y+5,x+55,y+38],fill=(0,0,0)); d.text((x+12,y+8),f"#{i+1}",fill=(255,255,0),font=font)
        except: pass
    canvas.save(outp); return True

results={}
for item in queries:
    spot=item["spot"]; q=item["q"]
    sdir=os.path.join(OUT,spot); os.makedirs(sdir,exist_ok=True)
    cands=search(q); kept=[]
    for j,(u,title) in enumerate(cands):
        fp=os.path.join(sdir,f"raw_{j}.jpg")
        if dl(u,fp):
            gs=gray_score(fp)
            if gs>=14: kept.append(fp)
        time.sleep(1.2)
        if len(kept)>=4: break
    mp=os.path.join(OUT,f"{spot}.png"); ok=montage(spot,kept,mp)
    results[spot]={"q":q,"kept":len(kept),"montage":mp if ok else None,"file":item["file"]}
    print(f"{spot:10} 候选{len(cands)} 彩色保留{len(kept)} {'OK' if ok else 'NO'}")
json.dump(results,open(os.path.join(OUT,"_results.json"),"w"),ensure_ascii=False,indent=1)
print("DONE",OUT)
