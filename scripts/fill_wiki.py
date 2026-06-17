#!/usr/bin/env python3
# 抓维基百科条目首图(lead image)+条目内多张图, 生成montage供vision核对
import sys,os,json,re,time,urllib.parse,urllib.request
from PIL import Image,ImageDraw,ImageFont
from collections import defaultdict

ITEMS=json.load(open(sys.argv[1],encoding="utf-8"))
REVIEW=os.environ.get("REVIEW_DIR","/tmp/wiki_fill")
RAW=f"{REVIEW}/raw"; os.makedirs(RAW,exist_ok=True)
UA="TravelAppBot/1.0 (https://awesometravelpartner.cn; ops@awesometravelpartner.cn)"
def safe(s): return re.sub(r'[/\\]','_',s)
def api(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def download(url,dest):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    open(dest,"wb").write(data); return len(data)
def gray_score(fp):
    try:
        im=Image.open(fp).convert("RGB").resize((60,60)); px=list(im.getdata())
        return sum(max(r,g,b)-min(r,g,b) for r,g,b in px)/len(px)
    except: return 0

def page_images(title):
    # 取条目里所有图片文件名, 然后取它们的url; 优先pageimage(lead)
    base="https://en.wikipedia.org/w/api.php?"
    # 1) lead image via pageimages
    p={"action":"query","format":"json","titles":title,"prop":"pageimages","piprop":"original","pilimit":"1"}
    lead=None
    try:
        d=api(base+urllib.parse.urlencode(p))
        for pg in (d.get("query") or {}).get("pages",{}).values():
            o=pg.get("original") or {}
            if o.get("source"): lead=o["source"]
    except Exception as e: print("  lead err",e)
    # 2) 条目内图片列表
    urls=[]
    if lead: urls.append(lead)
    p2={"action":"query","format":"json","titles":title,"prop":"images","imlimit":"20"}
    try:
        d2=api(base+urllib.parse.urlencode(p2))
        files=[]
        for pg in (d2.get("query") or {}).get("pages",{}).values():
            for im in pg.get("images",[]):
                t=im.get("title","")
                if t.lower().endswith((".jpg",".jpeg",".png")) and "logo" not in t.lower() and "icon" not in t.lower() and "map" not in t.lower():
                    files.append(t)
        # 解析这些File的真实url
        for i in range(0,len(files),10):
            batch=files[i:i+10]
            p3={"action":"query","format":"json","titles":"|".join(batch),"prop":"imageinfo","iiprop":"url|size","iiurlwidth":"800"}
            d3=api(base+urllib.parse.urlencode(p3))
            for pg in (d3.get("query") or {}).get("pages",{}).values():
                ii=(pg.get("imageinfo") or [{}])[0]
                u=ii.get("thumburl") or ii.get("url")
                w=ii.get("width",0);h=ii.get("height",0)
                if u and u.lower().endswith((".jpg",".jpeg",".png")) and (not w or w/max(h,1)>=0.6):
                    urls.append(u)
    except Exception as e: print("  imgs err",e)
    # 去重保序
    seen=set();out=[]
    for u in urls:
        if u in seen: continue
        seen.add(u); out.append(u)
    return out[:8]

results=[]; bycity=defaultdict(list); spot_q={}
for it in ITEMS:
    region,city,spot,title=it["region"],it["city"],it["spot"],it["title"]
    urls=page_images(title)
    best=None;bestgs=-1
    for j,u in enumerate(urls):
        ext=os.path.splitext(u.split("?")[0])[1] or ".jpg"
        tmp=f"{RAW}/{safe(city)}_{safe(spot)}_{j}{ext}"
        try: download(u,tmp)
        except: continue
        gs=gray_score(tmp)
        # lead image(j==0)给加权,优先选条目代表图
        score=gs+(40 if j==0 else 0)
        if score>bestgs: bestgs=score; best=tmp
    status="OK" if best else "NOIMG"
    if best:
        results.append({"region":region,"city":city,"spot":spot,"q":title,"src":best,"gs":round(bestgs,1)})
        bycity[(region,city)].append((spot,best)); spot_q[(region,city,spot)]=title
    print(f"  {city:8} {spot:22} {status} title={title!r} ({len(urls)}imgs)")
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
print(f"\n维基首图搜到 {len(results)}/{len(ITEMS)}")
