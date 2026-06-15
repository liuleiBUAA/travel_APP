import requests,subprocess,os,sys,time,statistics as st
from PIL import Image,ImageDraw,ImageFont
UA_API='Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0'
UA_DL='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
def gray(fp):
    try:
        im=Image.open(fp).convert('RGB').resize((60,60));px=list(im.getdata())
        return st.mean(max(r,g,b)-min(r,g,b) for r,g,b in px)
    except: return -1
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
def fetch(page,spot,outdir,want=4,bad=None):
    bad=bad or ['.svg','map','coat','logo','icon','plan','diagram','engraving','malton','1746','1778','aerial']
    os.makedirs(outdir,exist_ok=True)
    url=f'https://en.wikipedia.org/api/rest_v1/page/media-list/{page}'
    r=requests.get(url,headers={'User-Agent':UA_API},timeout=30)
    items=r.json().get('items',[])
    kept=[]
    for it in items:
        if it.get('type')!='image' or not it.get('srcset'): continue
        t=it.get('title','').lower()
        if any(b in t for b in bad): continue
        src=it['srcset'][-1]['src']
        if src.startswith('//'): src='https:'+src
        src=src.replace('/330px-','/1280px-').replace('/220px-','/1280px-')
        fp=os.path.join(outdir,f'raw_{len(kept)}.jpg')
        subprocess.run(['curl','-s','-m','40','-A',UA_DL,'-o',fp,src],check=False)
        if os.path.exists(fp) and os.path.getsize(fp)>8000 and gray(fp)>=14:
            kept.append(fp);print(f'  {spot} kept{len(kept)}: {t[:45]}',flush=True)
        time.sleep(0.5)
        if len(kept)>=want: break
    mp=os.path.join(os.path.dirname(outdir.rstrip("/")),f'{spot}.png')
    montage(spot,kept,mp);print(f'{spot} -> {len(kept)} {mp}',flush=True)
base='/home/ubuntu/.hermes-bot2/media_cache/bw_wiki'
fetch('Royal_Crescent','皇家新月楼',base+'/皇家新月楼_raw')
fetch('Palace_of_Holyroodhouse','荷里路德宫',base+'/荷里路德宫_raw')
fetch('Lello_Bookstore','莱罗书店',base+'/莱罗书店_raw',want=6)
print('ALLDONE',flush=True)
