#!/usr/bin/env python3
# 从 Wikimedia Commons 抓对题图: API搜图 -> 下载 -> gray过滤 -> 每城montage供vision核对
import sys,os,json,re,time,urllib.parse,urllib.request
from PIL import Image,ImageDraw,ImageFont
from collections import defaultdict

ITEMS=json.load(open(sys.argv[1],encoding="utf-8"))
REVIEW=os.environ.get("REVIEW_DIR","/tmp/commons_fill")
RAW=f"{REVIEW}/raw"
os.makedirs(RAW,exist_ok=True)
UA="TravelAppBot/1.0 (https://awesometravelpartner.cn; ops@awesometravelpartner.cn)"
def safe(s): return re.sub(r'[/\\]','_',s)

def api(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.load(r)

def search_images(q,limit=6):
    # generator=search in File namespace, get imageinfo url
    base="https://commons.wikimedia.org/w/api.php?"
    p={"action":"query","format":"json","generator":"search",
       "gsrsearch":f"filetype:bitmap {q}","gsrnamespace":"6","gsrlimit":str(limit),
       "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":"800"}
    try:
        d=api(base+urllib.parse.urlencode(p))
    except Exception as e:
        print("   api err",e); return []
    pages=(d.get("query") or {}).get("pages") or {}
    out=[]
    for pg in pages.values():
        ii=(pg.get("imageinfo") or [{}])[0]
        url=ii.get("thumburl") or ii.get("url")
        w=ii.get("width",0); h=ii.get("height",0)
        if url and url.lower().endswith((".jpg",".jpeg",".png")):
            out.append((url,w,h,pg.get("title","")))
    return out

def gray_score(fp):
    try:
        im=Image.open(fp).convert("RGB").resize((60,60)); px=list(im.getdata())
        # 越大越彩色(饱和度), 灰图低分
        s=0
        for r,g,b in px:
            mx=max(r,g,b);mn=min(r,g,b); s+=(mx-mn)
        return s/len(px)
    except: return 0

def download(url,dest):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r:
        data=r.read()
    open(dest,"wb").write(data)

results=[]; bycity=defaultdict(list); spot_q={}
for it in ITEMS:
    region,city,spot,q=it["region"],it["city"],it["spot"],it["q"]
    cand=search_images(q,limit=6)
    best=None;bestgs=-1
    for url,w,h,title in cand:
        ext=os.path.splitext(url.split("?")[0])[1] or ".jpg"
        tmp=f"{RAW}/{safe(city)}_{safe(spot)}_{len(results)}_{abs(hash(url))%9999}{ext}"
        try: download(url,tmp)
        except Exception as e: continue
        gs=gray_score(tmp)
        # 横图优先(景点照),太小跳过
        if w and h and w/max(h,1)<0.6: continue
        if gs>bestgs: bestgs=gs; best=tmp
    status="OK" if best else "NOIMG"
    if best:
        results.append({"region":region,"city":city,"spot":spot,"q":q,"src":best,"gs":round(bestgs,1)})
        bycity[(region,city)].append((spot,best))
        spot_q[(region,city,spot)]=q
    print(f"  {city:8} {spot:22} gs={round(bestgs,1)} {status} q={q!r}")
    time.sleep(0.3)

# montages
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
print(f"\nCommons搜到图 {len(results)}/{len(ITEMS)}  montage在 {REVIEW}/<city>.png")
