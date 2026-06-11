"""生成抓图结果预览页（人工抽查用）。

用法:
    python3 make_image_preview.py <图片目录(含manifest.json)> <输出html>
"""
import json
import os
import sys
from collections import defaultdict


def main(img_dir, out_html):
    manifest = json.load(open(os.path.join(img_dir, "manifest.json"), encoding="utf-8"))
    by_city = defaultdict(list)
    for m in manifest:
        by_city[m["city"]].append(m)

    ok = sum(1 for m in manifest if m["status"] == "ok")
    parts = [
        "<html><head><meta charset='utf-8'><title>抓图预览</title><style>",
        "body{font-family:sans-serif;margin:20px}h2{border-bottom:2px solid #333;padding-bottom:4px}",
        ".grid{display:flex;flex-wrap:wrap;gap:12px}",
        ".card{width:260px;border:1px solid #ccc;border-radius:6px;padding:8px}",
        ".card img{width:100%;height:170px;object-fit:cover;border-radius:4px}",
        ".miss{background:#fee}.name{font-weight:bold;margin:6px 0 2px}",
        ".meta{font-size:11px;color:#666}",
        "</style></head><body>",
        f"<h1>抓图预览：命中 {ok}/{len(manifest)}</h1>",
    ]
    rel = os.path.relpath(img_dir, os.path.dirname(os.path.abspath(out_html)))
    for city, items in by_city.items():
        parts.append(f"<h2>{city}</h2><div class='grid'>")
        for m in items:
            if m["status"] == "ok":
                src = os.path.join(rel, m["local"])
                parts.append(
                    f"<div class='card'><img src='{src}' loading='lazy'>"
                    f"<div class='name'>{m['attraction']}</div>"
                    f"<div class='meta'>{m.get('source','')}<br>{m.get('license','')} / {m.get('artist','')}</div></div>"
                )
            else:
                parts.append(
                    f"<div class='card miss'><div class='name'>{m['attraction']}</div>"
                    f"<div class='meta'>{m['status']}: {m.get('error','')[:60]}</div></div>"
                )
        parts.append("</div>")
    parts.append("</body></html>")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"预览页: {out_html}（命中 {ok}/{len(manifest)}）")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
