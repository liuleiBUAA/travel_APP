#!/usr/bin/env python3
# 按精确文件名从Commons下载,montage供vision核对
import sys,os,json,re,urllib.parse,urllib.request,time
from PIL import Image,ImageDraw,ImageFont
from collections import defaultdict
UA="TravelAppBot/1.0 (https://awesometravelpartner.cn; ops@awesometravelpartner.cn)"
REVIEW=os.environ.get("REVIEW_DIR","/tmp/pick"); RAW=f"{REVIEW}/raw"; os.makedirs(RAW,exist_ok=True)
def safe(s): return re.sub(r'[/\\]','_',s)
def api(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def file_url(fname):
    base="https://commons.wikimedia.org/w/api.php?"
    p={"action":"query","format":"json","titles":"File:"+fname,"prop":"imageinfo",
       "iiprop":"url","iiurlwidth":"800"}
    d=api(base+urllib.parse.urlencode(p))
    for pg in (d.get("query") or {}).get("pages",{}).values():
        for ii in pg.get("imageinfo",[]):
            return ii.get("thumburl") or ii.get("url")
    return None
def download(url,dest):
    for a in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
            open(dest,"wb").write(data); return True
        except: time.sleep(2*(a+1))
    return False
items=json.load(open(sys.argv[1],encoding="utf-8"))  # [{region,city,spot,files:[...]}]
results=[]
for it in items:
    spot=it["spot"]
    cand=[]
    for j,fn in enumerate(it["files"]):
        try: u=file_url(fn)
        except Exception as e: print("  url err",fn,e); continue
        if not u: continue
        dest=f"{RAW}/{safe(spot)}_{j}.jpg"
        if download(u,dest): cand.append((fn,dest))
        time.sleep(0.2)
    # montage 全部候选
    n=len(cand)
    if not n:
        print(f"{spot}: NO CAND"); continue
    cols=min(3,n); rows=(n+cols-1)//cols; cw,ch=380,300
    canvas=Image.new("RGB",(cols*cw,rows*ch),(30,30,40)); d=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",16)
    except: font=ImageFont.load_default()
    for i,(fn,fp) in enumerate(cand):
        try:
            im=Image.open(fp).convert("RGB"); im.thumbnail((cw-10,ch-30))
            x=(i%cols)*cw; y=(i//cols)*ch; canvas.paste(im,(x+5,y+5))
            d.rectangle([x+5,y+ch-26,x+cw-5,y+ch-2],fill=(0,0,0))
            d.text((x+8,y+ch-24),f"{i+1}.{fn[:30]}",fill=(255,255,0),font=font)
        except Exception as e: print("paste err",e)
    canvas.save(f"{REVIEW}/{safe(spot)}.png")
    results.append({"spot":spot,"region":it["region"],"city":it["city"],"cand":[{"fn":fn,"fp":fp} for fn,fp in cand]})
    print(f"{spot}: {n} cands -> {REVIEW}/{safe(spot)}.png")
json.dump(results,open(f"{REVIEW}/_pick.json","w"),ensure_ascii=False,indent=1)
