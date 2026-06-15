#!/usr/bin/env python3
import os, json, urllib.request, urllib.parse

KEY=None
for line in open("/home/ubuntu/tools/travel_APP/.env"):
    if line.startswith("PEXELS_KEY="):
        KEY=line.split("=",1)[1].strip()

outdir="/home/ubuntu/tools/travel_APP/scripts/img_candidates/us_gap"
os.makedirs(outdir, exist_ok=True)
queries=[
 {"attraction":"圣地亚哥海洋世界SeaWorld","city":"圣地亚哥","query":"SeaWorld San Diego orca killer whale show"},
 {"attraction":"芝加哥艺术博物馆","city":"芝加哥","query":"Art Institute of Chicago museum bronze lion entrance"},
 {"attraction":"哈雷阿卡拉国家公园","city":"茂宜岛","query":"Haleakala National Park Maui sunrise crater summit"},
]

def search(q, per=8):
    url="https://api.pexels.com/v1/search?"+urllib.parse.urlencode({"query":q,"per_page":per,"orientation":"landscape"})
    req=urllib.request.Request(url, headers={"Authorization":KEY})
    return json.load(urllib.request.urlopen(req, timeout=30))

meta={}
for item in queries:
    slug=item["attraction"]
    r=search(item["query"])
    photos=r.get("photos",[])
    print(f"{slug}: {len(photos)} photos")
    meta[slug]=[]
    for i,p in enumerate(photos):
        src=p["src"]["large"]
        fn=f"{outdir}/{slug}_{i+1}.jpg"
        try:
            urllib.request.urlretrieve(src, fn)
            meta[slug].append({"file":fn,"id":p["id"],"artist":p["photographer"],"alt":(p.get("alt") or "")[:60]})
            print(f"  {i+1}. id={p['id']} {p['photographer']} | {(p.get('alt') or '')[:50]}")
        except Exception as e:
            print(f"  {i+1}. ERR {e}")
json.dump(meta,open(f"{outdir}/meta.json","w"),ensure_ascii=False,indent=2)
print("SAVED")
