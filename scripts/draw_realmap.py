import json, os
from staticmap import StaticMap, CircleMarker, Line
from staticmap.staticmap import _lon_to_x, _lat_to_y
from PIL import Image, ImageDraw, ImageFont
from math import radians, cos, sin, asin, sqrt

base='/home/ubuntu/tools/travel_APP/travel_guide/data'
coords=json.load(open(f'{base}/geo/瑞士_coords.json'))
def ok(v): return 45.8<v['lat']<47.8 and 5.9<v['lon']<10.5
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
if not os.path.exists(FONT): FONT='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
# 地形底图(OpenTopoMap, 免费)
TERRAIN='https://a.tile.opentopomap.org/{z}/{x}/{y}.png'

def haversine(la1,lo1,la2,lo2):
    dla=radians(la2-la1);dlo=radians(lo2-lo1)
    a=sin(dla/2)**2+cos(radians(la1))*cos(radians(la2))*sin(dlo/2)**2
    return 6371*2*asin(sqrt(a))

def place_labels(items, draw, font):
    """items: [(x,y,txt,fill,prefer_dy)] -> 避让重叠,返回最终位置"""
    placed=[]  # (x1,y1,x2,y2)
    out=[]
    def overlap(b1,b2):
        return not(b1[2]<b2[0] or b1[0]>b2[2] or b1[3]<b2[1] or b1[1]>b2[3])
    for x,y,txt,fill,pdy in items:
        bb=draw.textbbox((0,0),txt,font=font); tw,th=bb[2]-bb[0],bb[3]-bb[1]
        # 尝试多个竖直偏移
        for dy in [pdy, pdy+ (24 if pdy>0 else -24), pdy+(48 if pdy>0 else -48),
                   pdy+(72 if pdy>0 else -72), pdy-24, pdy+24]:
            px,py=x-tw/2, y+dy
            box=(px-5,py-3,px+tw+5,py+th+6)
            if not any(overlap(box,b) for b in placed):
                placed.append(box); out.append((px,py,txt,fill,bb)); break
        else:
            px,py=x-tw/2,y+pdy; placed.append((px-5,py-3,px+tw+5,py+th+6)); out.append((px,py,txt,fill,bb))
    return out

def draw_intracity(city, hub, fname, title, zoom=11):
    pts={k:v for k,v in coords.items() if v.get('city')==city and ok(v)}
    W,H=900,700
    m=StaticMap(W,H,url_template=TERRAIN,headers={'User-Agent':'TravelGuideBot/1.0'},padding_x=80,padding_y=90)
    for name,v in pts.items():
        m.add_line(Line([hub,(v['lon'],v['lat'])],'#1565c0',3))
    for name,v in pts.items():
        m.add_marker(CircleMarker((v['lon'],v['lat']),'white',15)); m.add_marker(CircleMarker((v['lon'],v['lat']),'#2e7d32',11))
    m.add_marker(CircleMarker(hub,'white',21)); m.add_marker(CircleMarker(hub,'#c62828',16))
    img=m.render(zoom=zoom).convert('RGB')
    draw=ImageDraw.Draw(img)
    f1=ImageFont.truetype(FONT,22); f2=ImageFont.truetype(FONT,17)
    def px(lon,lat): return m._x_to_px(_lon_to_x(lon,zoom)), m._y_to_px(_lat_to_y(lat,zoom))
    items=[]
    for name,v in pts.items():
        x,y=px(v['lon'],v['lat']); km=haversine(hub[1],hub[0],v['lat'],v['lon'])
        items.append((x,y,f'{name} {km:.0f}km','#1b5e20',16))
    for px_,py_,txt,fill,bb in place_labels(items,draw,f2):
        draw.rectangle([px_-5,py_-3,px_+(bb[2]-bb[0])+5,py_+(bb[3]-bb[1])+6],fill=(255,255,255))
        draw.text((px_,py_-bb[1]+2),txt,font=f2,fill=fill)
    hx,hy=px(*hub)
    bb=draw.textbbox((0,0),city+'·火车枢纽',font=f1); tw=bb[2]-bb[0]
    draw.rectangle([hx-tw/2-6,hy-46,hx+tw/2+6,hy-46+(bb[3]-bb[1])+8],fill=(255,255,255))
    draw.text((hx-tw/2,hy-46-bb[1]+3),city+'·火车枢纽',font=f1,fill='#c62828')
    draw.rectangle([0,0,W,46],fill=(21,69,124))
    draw.text((16,10),title,font=f1,fill='white')
    out=f'/home/ubuntu/.hermes-bot2/media_cache/{fname}'
    img.save(out); print("OK:",out,img.size,"pts:",len(pts))
    _save_repo(img, fname)

def _save_repo(img, fname):
    """同时存进仓库静态目录 maps/瑞士/，文件名映射成 JSON 里引用的中文名。"""
    repo_map={'swiss_il_realmap.png':'瑞士/因特拉肯_交通图.png',
              'swiss_intercity_realmap.png':'瑞士/瑞士城市间_交通图.png'}
    if fname in repo_map:
        dst=f'{base}/maps/{repo_map[fname]}'
        os.makedirs(os.path.dirname(dst),exist_ok=True)
        img.save(dst); print("  -> repo:",dst)

# 城市间真地图
def draw_intercity(fname,title,zoom=8):
    routes=json.load(open(f'{base}/Europe/transport_routes.json'))
    cities={'苏黎世':(8.540,47.377),'日内瓦':(6.143,46.204),'伯尔尼':(7.447,46.948),
            '因特拉肯':(7.863,46.686),'卢塞恩':(8.307,47.050),'采尔马特':(7.749,46.020),
            '蒙特勒':(6.911,46.433),'圣莫里茨':(9.838,46.498),'巴塞尔':(7.588,47.559),'洛桑':(6.633,46.519)}
    W,H=950,720
    m=StaticMap(W,H,url_template=TERRAIN,headers={'User-Agent':'TravelGuideBot/1.0'},padding_x=70,padding_y=80)
    drawn=set(); seg=[]
    for k,v in routes.items():
        if '->' not in k: continue
        a,b=k.split('->')
        if a in cities and b in cities:
            key=tuple(sorted([a,b]))
            if key in drawn: continue
            drawn.add(key)
            m.add_line(Line([cities[a],cities[b]],'#37474f',2))
            seg.append((a,b,v.get('train_time_hours',0)))
    big={'苏黎世','日内瓦','因特拉肯'}
    for name,(lon,lat) in cities.items():
        r=16 if name in big else 12
        m.add_marker(CircleMarker((lon,lat),'white',r+4)); m.add_marker(CircleMarker((lon,lat),'#c62828' if name in big else '#1565c0',r))
    img=m.render(zoom=zoom).convert('RGB')
    draw=ImageDraw.Draw(img)
    f1=ImageFont.truetype(FONT,22); f2=ImageFont.truetype(FONT,18); f3=ImageFont.truetype(FONT,14)
    def px(lon,lat): return m._x_to_px(_lon_to_x(lon,zoom)), m._y_to_px(_lat_to_y(lat,zoom))
    # 火车时长标在线中点(只标近线<3h避免太密)
    for a,b,tt in seg:
        if tt and tt<3:
            xa,ya=px(*cities[a]); xb,yb=px(*cities[b]); mx,my=(xa+xb)/2,(ya+yb)/2
            t=f'{tt:.1f}h'; bb=draw.textbbox((0,0),t,font=f3); tw=bb[2]-bb[0]
            draw.rectangle([mx-tw/2-3,my-2,mx+tw/2+3,my+bb[3]-bb[1]+4],fill=(255,255,255,230))
            draw.text((mx-tw/2,my-bb[1]+1),t,font=f3,fill='#1565c0')
    items=[]
    for name,(lon,lat) in cities.items():
        x,y=px(lon,lat); items.append((x,y,name,'#c62828' if name in big else '#1a237e',-34))
    for px_,py_,txt,fill,bb in place_labels(items,draw,f2):
        draw.rectangle([px_-5,py_-3,px_+(bb[2]-bb[0])+5,py_+(bb[3]-bb[1])+6],fill=(255,255,255))
        draw.text((px_,py_-bb[1]+2),txt,font=f2,fill=fill)
    draw.rectangle([0,0,W,46],fill=(21,69,124))
    draw.text((16,10),title,font=f1,fill='white')
    out=f'/home/ubuntu/.hermes-bot2/media_cache/{fname}'
    img.save(out); print("OK:",out,img.size,"segs:",len(seg))
    _save_repo(img, fname)

draw_intracity('因特拉肯',(7.8632,46.6863),'swiss_il_realmap.png','因特拉肯 · 市内交通图')
draw_intercity('swiss_intercity_realmap.png','瑞士 · 城市间交通图')
