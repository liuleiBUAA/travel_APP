#!/usr/bin/env python3
# 抓Commons分类(Category)成员图片, 几乎都是该地标实拍, 生成montage供vision核对
import sys,os,json,re,time,urllib.parse,urllib.request
from PIL import Image,ImageDraw,ImageFont
from collections import defaultdict

ITEMS=json.load(open(sys.argv[1],encoding="utf-8"))
REVIEW=os.environ.get("REVIEW_DIR","/tmp/cat_fill")
RAW=f"{REVIEW}/raw"; os.makedirs(RAW,exist_ok=True)
UA="TravelAppBot/1.0 (https://awesometravelpartner.cn; ops@awesometravelpartner.cn)"
def safe(s): return re.sub(r'[/\\]','_',s)
def api(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def download(url,dest):
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
            open(dest,"wb").write(data); return len(data)
        except Exception as e:
            if attempt<2: time.sleep(2*(attempt+1))
            else: raise
def gray_score(fp):
    try:
        im=Image.open(fp).convert("RGB").resize((60,60)); px=list(im.getdata())
        return sum(max(r,g,b)-min(r,g,b) for r,g,b in px)/len(px)
    except: return 0

def cat_files(cat):
    base="https://commons.wikimedia.org/w/api.php?"
    p={"action":"query","format":"json","list":"categorymembers",
       "cmtitle":f"Category:{cat}","cmtype":"file","cmlimit":"40"}
    try: d=api(base+urllib.parse.urlencode(p))
    except Exception as e: print("  cat err",e); return []
    files=[m["title"] for m in (d.get("query") or {}).get("categorymembers",[])
           if m["title"].lower().endswith((".jpg",".jpeg",".png"))]
    BAD=["logo","icon","map","plan","diagram","floor","sign ","seal","coat_of_arms","interior_panorama"]
    files=[f for f in files if not any(b in f.lower() for b in BAD)]
    # 取真实url
    urls=[]
    for i in range(0,len(files),10):
        batch=files[i:i+10]
        p2={"action":"query","format":"json","titles":"|".join(batch),"prop":"imageinfo","iiprop":"url|size","iiurlwidth":"800"}
        try: d2=api(base+urllib.parse.urlencode(p2))
        except: continue
        for pg in (d2.get("query") or {}).get("pages",{}).values():
            ii=(pg.get("imageinfo") or [{}])[0]
            u=ii.get("thumburl") or ii.get("url"); w=ii.get("width",0);h=ii.get("height",0)
            if u and u.lower().endswith((".jpg",".jpeg",".png")) and (not w or w/max(h,1)>=0.62):
                urls.append(u)
    return urls

results=[]; bycity=defaultdict(list); spot_q={}
for it in ITEMS:
    region,city,spot,cat=it["region"],it["city"],it["spot"],it["cat"]
    urls=cat_files(cat)
    # 选彩色度最高的横图(实拍外观通常彩色丰富)
    best=None;bestgs=-1
    for j,u in enumerate(urls[:6]):
        ext=os.path.splitext(u.split("?")[0])[1] or ".jpg"
        tmp=f"{RAW}/{safe(city)}_{safe(spot)}_{j}{ext}"
        try: download(u,tmp)
        except: continue
        gs=gray_score(tmp)
        if gs>bestgs: bestgs=gs; best=tmp
        time.sleep(0.2)
    status="OK" if best else "NOIMG"
    if best:
        results.append({"region":region,"city":city,"spot":spot,"q":cat,"src":best,"gs":round(bestgs,1)})
        bycity[(region,city)].append((spot,best)); spot_q[(region,city,spot)]=cat
    print(f"  {city:8} {spot:22} {status} cat={cat!r} ({len(urls)}files)")
    time.sleep(0.3)

for (region,city),spots in bycity.items():
    n=len(spots); cols=2; rows=(n+1)//2; cw,ch=400,300
    canvas=Image.new("RGB",(cols*cw,max(rows,1)*ch),(30,30,40)); d=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",18)
    except: font=ImageFont.load_default()
    for i,(spot,fp) in enumerate(spots):
        try:
            im=Image.open(fp).convert("RGB"); im.thumbnail((cw-10,ch-52))
            x=(i%cols)*cw; y=(i//cols)*ch; canvas.paste(im,(x+5,y+5))
            q=spot_q.get((region,city,spot),"")
            d.rectangle([x+5,y+ch-44,x+cw-5,y+ch-2],fill=(0,0,0))
            d.text((x+10,y+ch-42),f"{i+1}.{spot[:16]}",fill=(255,255,0),font=font)
            d.text((x+10,y+ch-22),f"[{q[:34]}]",fill=(120,220,255),font=font)
        except: pass
    canvas.save(f"{REVIEW}/{safe(city)}.png")
json.dump(results,open(f"{REVIEW}/_ingest.json","w"),ensure_ascii=False,indent=1)
print(f"\n分类抓到 {len(results)}/{len(ITEMS)}")
