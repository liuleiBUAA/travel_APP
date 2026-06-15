#!/bin/bash
cd /home/ubuntu/tools/travel_APP
KEY=$(grep '^PEXELS_KEY=' .env | cut -d= -f2)
OUT=scripts/img_candidates/us_gap
mkdir -p $OUT
> $OUT/meta.txt

fetch() {
  local slug="$1"; local q="$2"
  echo "=== $slug ==="
  local eq=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$q")
  local json=$(curl -s -m 30 -H "Authorization: $KEY" "https://api.pexels.com/v1/search?query=$eq&per_page=8&orientation=landscape")
  echo "$json" | python3 -c "
import sys,json
d=json.load(sys.stdin)
slug='$slug'
out='$OUT'
import subprocess
for i,p in enumerate(d.get('photos',[])):
    url=p['src']['large']
    fn=f'{out}/{slug}_{i+1}.jpg'
    subprocess.run(['curl','-s','-m','40','-o',fn,url])
    line=f\"{slug}\t{i+1}\t{p['id']}\t{p['photographer']}\t{(p.get('alt') or '')[:60]}\"
    print('  '+line)
    open(f'{out}/meta.txt','a').write(line+'\n')
"
}

fetch "SeaWorld圣地亚哥" "SeaWorld San Diego orca killer whale show"
fetch "芝加哥艺术博物馆" "Art Institute of Chicago museum bronze lion entrance"
fetch "哈雷阿卡拉" "Haleakala National Park Maui sunrise crater summit clouds"
echo "DONE"
ls -la $OUT/*.jpg | wc -l