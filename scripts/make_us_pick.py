#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os
base="/home/ubuntu/tools/travel_APP/scripts/img_candidates/us_gap"
outd="/home/ubuntu/.hermes-bot2/media_cache/img_pick"
os.makedirs(outd, exist_ok=True)

try:
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
except:
    font=ImageFont.load_default()

def make_pair(title, items, outname):
    # items: list of (label, filepath)
    cell_w, cell_h = 640, 440
    pad=12; lab_h=56
    n=len(items)
    W=cell_w*n + pad*(n+1)
    H=cell_h + lab_h + pad*2
    canvas=Image.new("RGB",(W,H),(245,245,245))
    d=ImageDraw.Draw(canvas)
    for i,(label,fp) in enumerate(items):
        x=pad+i*(cell_w+pad)
        try:
            im=Image.open(fp).convert("RGB")
            im.thumbnail((cell_w,cell_h))
            ox=x+(cell_w-im.width)//2
            oy=lab_h+pad+(cell_h-im.height)//2
            canvas.paste(im,(ox,oy))
        except Exception as e:
            d.text((x+10,lab_h+20),f"ERR {e}",fill=(200,0,0),font=font)
        d.text((x+10,10),label,fill=(20,20,20),font=font)
    out=f"{outd}/{outname}"
    canvas.save(out)
    print(out)

make_pair("SeaWorld", [("#1 虎鲸群跳", f"{base}/SeaWorld圣地亚哥_2.jpg"),
                       ("#2 虎鲸+看台", f"{base}/SeaWorld圣地亚哥_6.jpg")], "us_seaworld.png")
make_pair("哈雷阿卡拉", [("#1 火山口日出/小径", f"{base}/哈雷阿卡拉_1.jpg"),
                       ("#2 云海金光", f"{base}/哈雷阿卡拉_5.jpg")], "us_haleakala.png")
make_pair("芝加哥艺博", [("#1 门口青铜狮", f"{base}/芝加哥艺术博物馆_1.jpg"),
                       ("#2 内部大楼梯", f"{base}/芝加哥艺术博物馆_7.jpg")], "us_artic.png")
print("ALL DONE")
