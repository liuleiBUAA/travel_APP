#!/usr/bin/env python3
# 对每个景点,用Commons搜索API找到真实存在的Category名(命名空间14)
import sys,json,urllib.parse,urllib.request,time
UA="TravelAppBot/1.0 (https://awesometravelpartner.cn; ops@awesometravelpartner.cn)"
def api(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def search_cat(term):
    base="https://commons.wikimedia.org/w/api.php?"
    p={"action":"query","format":"json","list":"search","srsearch":term,
       "srnamespace":"14","srlimit":"5"}
    try:
        d=api(base+urllib.parse.urlencode(p))
        return [x["title"] for x in (d.get("query") or {}).get("search",[])]
    except Exception as e:
        return [f"ERR:{e}"]
items=json.load(open(sys.argv[1],encoding="utf-8"))
for it in items:
    cats=search_cat(it["term"])
    print(f"{it['spot']:24} term={it['term']!r}")
    for c in cats: print(f"    {c}")
    time.sleep(0.3)
