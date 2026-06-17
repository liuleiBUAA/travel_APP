#!/usr/bin/env python3
# Commons全文搜文件,只列文件名供挑选
import sys,json,urllib.parse,urllib.request,time
UA="TravelAppBot/1.0 (https://awesometravelpartner.cn; ops@awesometravelpartner.cn)"
def api(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def search(term,limit=25):
    base="https://commons.wikimedia.org/w/api.php?"
    p={"action":"query","format":"json","list":"search","srsearch":term,
       "srnamespace":"6","srlimit":str(limit)}
    d=api(base+urllib.parse.urlencode(p))
    return [x["title"].replace("File:","") for x in (d.get("query") or {}).get("search",[])]
qs=json.load(open(sys.argv[1],encoding="utf-8"))
for q in qs:
    print(f"=== {q} ===")
    for f in search(q): print("  ",f)
    time.sleep(0.3)
