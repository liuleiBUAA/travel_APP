#!/usr/bin/env python3
"""生成景点位置示意图（欧萌客风格）：真实地图底图 + 标号红点 + 中文图例。

底图用 OpenStreetMap 瓦片（© OpenStreetMap contributors, ODbL）。
注意：OSM 官方瓦片有使用条款，量大/商用建议换自建或商用瓦片服务。
本脚本仅用于打样验证形式。

用法: python3 make_map.py  （内置少女峰区域样板）
"""
import io
import math
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

TILE = 256
ROOT = Path(__file__).resolve().parents[2]


def deg2num(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def fetch_tile(z, x, y):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    req = urllib.request.Request(url, headers={"User-Agent": "TravelGuideBot/1.0 (map sample)"})
    return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGBA")


def pick_zoom(pts, target_px=720):
    """选一个能把所有点容纳进 ~720px 的缩放级别。"""
    lats = [p[1] for p in pts]
    lons = [p[2] for p in pts]
    for z in range(13, 7, -1):
        xs = [deg2num(la, lo, z)[0] for la, lo in zip(lats, lons)]
        ys = [deg2num(la, lo, z)[1] for la, lo in zip(lats, lons)]
        span_x = (max(xs) - min(xs)) * TILE
        span_y = (max(ys) - min(ys)) * TILE
        if span_x < target_px and span_y < target_px:
            return z
    return 9


def font(size):
    """中文字体（含数字回退）。"""
    for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
              "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def font_num(size):
    """纯数字/拉丁用，DroidSansFallback 渲染数字会变方块，单独用 DejaVu。"""
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return font(size)


def make_map(points, out_path, title=""):
    """points: [(标号, 名称, lat, lon), ...]"""
    pts = [(p[0], p[1], p[2], p[3]) for p in points]
    z = pick_zoom([(p[0], p[2], p[3]) for p in pts])

    xs = [deg2num(p[2], p[3], z)[0] for p in pts]
    ys = [deg2num(p[2], p[3], z)[1] for p in pts]
    pad = 1.2
    x0, x1 = math.floor(min(xs) - pad), math.ceil(max(xs) + pad)
    y0, y1 = math.floor(min(ys) - pad), math.ceil(max(ys) + pad)

    canvas = Image.new("RGBA", ((x1 - x0) * TILE, (y1 - y0) * TILE), "white")
    for tx in range(x0, x1):
        for ty in range(y0, y1):
            try:
                canvas.paste(fetch_tile(z, tx, ty), ((tx - x0) * TILE, (ty - y0) * TILE))
            except Exception:
                pass

    draw = ImageDraw.Draw(canvas)
    f_num = font_num(22)
    for idx, name, la, lo in pts:
        px = (deg2num(la, lo, z)[0] - x0) * TILE
        py = (deg2num(la, lo, z)[1] - y0) * TILE
        r = 16
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(229, 57, 53, 255), outline="white", width=3)
        tb = draw.textbbox((0, 0), str(idx), font=f_num)
        draw.text((px - (tb[2] - tb[0]) / 2, py - (tb[3] - tb[1]) / 2 - tb[1]), str(idx), fill="white", font=f_num)

    # 裁掉边缘多余留白：以点的包围盒为中心裁到 ~760px 见方
    cx = sum((deg2num(p[2], p[3], z)[0] - x0) * TILE for p in pts) / len(pts)
    cy = sum((deg2num(p[2], p[3], z)[1] - y0) * TILE for p in pts) / len(pts)
    half = 380
    crop = canvas.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half)))

    # 底部图例条
    f_leg = font(20)
    f_leg_num = font_num(20)
    line_h = 28
    cols = 2
    rows = math.ceil(len(pts) / cols)
    legend_h = rows * line_h + 50
    out = Image.new("RGBA", (crop.width, crop.height + legend_h), "white")
    out.paste(crop, (0, 0))
    ld = ImageDraw.Draw(out)
    if title:
        ld.text((12, crop.height + 8), title, fill=(33, 33, 33), font=font(22))
    for i, (idx, name, _, _) in enumerate(pts):
        col = i // rows
        row = i % rows
        x = 12 + col * (crop.width // cols)
        y = crop.height + 38 + row * line_h
        prefix = f"{idx}. "
        ld.text((x, y), prefix, fill=(60, 60, 60), font=f_leg_num)
        pw = ld.textlength(prefix, font=f_leg_num)
        ld.text((x + pw, y), name, fill=(60, 60, 60), font=f_leg)
    ld.text((12, out.height - 20), "(c) OpenStreetMap contributors", fill=(150, 150, 150), font=font_num(14))

    out.convert("RGB").save(out_path, quality=88)
    print(f"地图已生成: {out_path} ({out.width}x{out.height})", flush=True)


if __name__ == "__main__":
    # 少女峰区域样板
    points = [
        (1, "少女峰", 46.547559, 7.985392),
        (2, "格林德尔瓦尔德", 46.577632, 8.005469),
        (3, "劳特布龙嫩", 46.596089, 7.907566),
        (4, "翁根", 46.605441, 7.921724),
        (5, "梦幻山坡", 46.669581, 8.020953),
    ]
    out = ROOT / "data" / "images" / "瑞士" / "少女峰区域示意图.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    make_map(points, str(out), title="少女峰区域景点位置示意图")
