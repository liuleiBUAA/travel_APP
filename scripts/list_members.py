#!/usr/bin/env python3
# 列出Commons分类全部成员文件名(只列图片),供人工挑选建筑外观图
import sys,json,urllib.parse,urllib.request,time
UA="TravelAppBot/1.0 (https://awesometravelpartner.cn; ops@awesometravelpartner.cn)"
def api(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def members(cat):
    base="https://commons.wikimedia.org/w/api.php?"
    p={"action":"query","format":"json","list":"categorymembers",
       "cmtitle":"Category:"+cat,"cmtype":"file","cmlimit":"100"}
    out=[]
    try:
        d=api(base+urllib.parse.urlencode(p))
        for m in (d.get("query") or {}).get("categorymembers",[]):
            out.append(m["title"].replace("File:",""))
    except Exception as e: out.append(f"ERR:{e}")
    return out
cats=json.load(open(sys.argv[1],encoding="utf-8"))
for c in cats:
    print(f"=== {c} ===")
    for f in members(c): print("  ",f)
    time.sleep(0.3)
