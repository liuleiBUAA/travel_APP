import requests,time,os,sys
from urllib.parse import quote
import statistics as st
from PIL import Image
from PIL import ImageDraw,ImageFont
UA='Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0'
API_UA='travelapp/1.0 (admin@awesometravelpartner.cn)'
def gray(fp):
    im=Image.open(fp).convert('RGB').resize((60,60));px=list(im.getdata())
    return st.mean(max(r,g,b)-min(r,g,b) for r,g,b in px)
def montage(spot,imgs,outp):
    n=len(imgs)
    if n==0: return False
    cols=2;rows=(n+1)//2;cw,ch=400,280
    c=Image.new("RGB",(cols*cw,rows*ch),(30,30,40));d=ImageDraw.Draw(c)
    f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",28)
    for i,fp in enumerate(imgs):
        im=Image.open(fp).convert("RGB");im.thumbnail((cw-10,ch-10))
        x=(i%cols)*cw;y=(i//cols)*ch;c.paste(im,(x+5,y+5))
        d.rectangle([x+5,y+5,x+55,y+38],fill=(0,0,0));d.text((x+12,y+8),f"#{i+1}",fill=(255,255,0),font=f)
    c.save(outp);return True
def grab(q,spot,outdir,want=4):
    os.makedirs(outdir,exist_ok=True)
    api=f'https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={quote(q)}&gsrnamespace=6&gsrlimit=30&prop=imageinfo&iiprop=url&iiurlwidth=1200&format=json'
    d=requests.get(api,headers={'User-Agent':API_UA},timeout=40).json()
    pages=list(d.get('query',{}).get('pages',{}).values())
    kept=[]
    for p in pages:
        t=p.get('title','').lower()
        if any(b in t for b in ['map','plan','.svg','diagram','coat','logo','crest','.pdf','interior','aerial','engraving','drawing','painting','1850','1900','19th','18th']): continue
        ii=p.get('imageinfo',[])
        if not ii: continue
        u=ii[0].get('thumburl') or ii[0].get('url')
        fp=os.path.join(outdir,f'raw_{len(kept)}.jpg');ok=False
        for k in range(5):
            try:
                r=requests.get(u,headers={'User-Agent':UA},timeout=60)
                if r.status_code==200 and len(r.content)>8000: open(fp,'wb').write(r.content);ok=True;break
                if r.status_code==429: time.sleep(4*(k+1))
            except: time.sleep(3)
        if ok and gray(fp)>=14:
            kept.append(fp);print(f'  {spot} kept{len(kept)}: {t[:45]}',flush=True)
        time.sleep(2.5)
        if len(kept)>=want: break
    mp=os.path.join(os.path.dirname(outdir),f'{spot}C.png')
    montage(spot,kept,mp);print(f'{spot} -> {len(kept)} montage {mp}',flush=True)
grab('Royal Crescent Bath','皇家新月楼','/home/ubuntu/.hermes-bot2/media_cache/bw_str/皇家新月楼C_raw')
print('---',flush=True)
grab('Holyrood Palace Edinburgh','荷里路德宫','/home/ubuntu/.hermes-bot2/media_cache/bw_str/荷里路德宫C_raw')
print('ALLDONE',flush=True)
