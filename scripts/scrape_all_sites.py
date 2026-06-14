#!/usr/bin/env python3
"""Scrape all 4 Discuz travel sites (oumengke/meilvtong/rilvtong/aoxintong).
For each site: pull index title->tid map, then fetch every thread, extract
visible text + folded 景点详解 (GLxx anchored display:none blocks), save raw.
Output: scripts/raw/<site>/<title>_<tid>.md  +  scripts/raw/<site>/_index.json
"""
import subprocess, re, html, os, json, time, sys

ROOT = "/home/ubuntu/tools/travel_APP/scripts/raw"

SITES = {
    "oumengke":  {"base": "https://www.oumengke.com",  "view": "viewthread.php?tid={tid}", "idx": "https://www.oumengke.com/"},
    "meilvtong": {"base": "https://www.meilvtong.com", "view": "viewthread.php?tid={tid}", "idx": "https://www.meilvtong.com/"},
    "rilvtong":  {"base": "https://www.rilvtong.com",  "view": "viewthread.php?tid={tid}", "idx": "https://www.rilvtong.com/"},
    # aoxintong uses rewritten thread-<tid>-1-1.html URLs
    "aoxintong": {"base": "https://www.aoxintong.com", "view": "thread-{tid}-1-1.html", "idx": "https://www.aoxintong.com/", "rewrite": True},
}

def fetch(url):
    r = subprocess.run(["curl","-sS","-m","30","-A","Mozilla/5.0 (Windows NT 10.0; Win64; x64)","-L",url],
                       capture_output=True)
    raw = r.stdout
    # Declared meta charset is unreliable (sites declare gbk but serve utf-8).
    # Try utf-8 strict first; if it fails, use gbk. Pick by fewest errors.
    best = None; best_bad = 1e18
    for enc in ('utf-8','gbk'):
        try:
            dec = raw.decode(enc)
            return dec  # strict success = correct
        except Exception:
            dec = raw.decode(enc,'replace')
            bad = dec.count('\ufffd')
            if bad < best_bad:
                best_bad = bad; best = dec
    return best

def index_map(site):
    cfg = SITES[site]
    idx = fetch(cfg['idx'])
    if cfg.get('rewrite'):
        pairs = re.findall(r'<a[^>]*href="\.?/?thread-(\d+)-\d+-\d+\.html[^"]*"[^>]*>(.*?)</a>', idx, re.S)
    else:
        pairs = re.findall(r'<a[^>]*href="[^"]*viewthread\.php\?tid=(\d+)"[^>]*>(.*?)</a>', idx, re.S)
    seen = {}
    for tid, txt in pairs:
        t = re.sub(r'<[^>]*>','',txt); t = html.unescape(t).strip()
        if t and tid not in seen:
            seen[tid] = t
    return seen

def strip_tags(s):
    s = re.sub(r'<script.*?</script>','',s,flags=re.S|re.I)
    s = re.sub(r'<style.*?</style>','',s,flags=re.S|re.I)
    s = re.sub(r'<br\s*/?>','\n',s,flags=re.I)
    s = re.sub(r'</(p|div|tr|li|h\d|table)>','\n',s,flags=re.I)
    s = re.sub(r'<[^>]+>',' ',s)
    s = html.unescape(s)
    s = re.sub(r'[ \t]+',' ',s)
    s = re.sub(r'\n{3,}','\n\n',s)
    return s.strip()

def extract_thread(content_html):
    # main post cell: table[id^=pid] td  -> fall back to whole body
    m = re.search(r'(<table[^>]*id="pid[^"]*"[^>]*>.*?</table>)', content_html, re.S|re.I)
    cell = m.group(1) if m else content_html
    visible = strip_tags(cell)
    # folded GLxx blocks: from <a name="GLxx"> up to next <a name=...>
    folded = []
    anchors = list(re.finditer(r'<a\s+name="(GL\d+)"', content_html, re.I))
    for i,a in enumerate(anchors):
        gid = a.group(1)
        start = a.end()
        end = anchors[i+1].start() if i+1 < len(anchors) else min(start+8000, len(content_html))
        chunk = strip_tags(content_html[start:end])
        if len(chunk) > 30:
            folded.append(f"[{gid}] {chunk[:3000]}")
    return visible, folded

def scrape_site(site, delay=0.8):
    cfg = SITES[site]
    outdir = os.path.join(ROOT, site)
    os.makedirs(outdir, exist_ok=True)
    idx = index_map(site)
    json.dump(idx, open(os.path.join(outdir,"_index.json"),"w"), ensure_ascii=False, indent=2)
    print(f"[{site}] {len(idx)} threads")
    done = 0
    for tid, title in idx.items():
        safe = re.sub(r'[\\/:*?"<>|]','_', title)[:50]
        path = os.path.join(outdir, f"{safe}_{tid}.md")
        if os.path.exists(path):
            done += 1; continue
        url = cfg['base'] + "/" + cfg['view'].format(tid=tid)
        try:
            page = fetch(url)
            vis, folded = extract_thread(page)
            body = f"# {title}\nURL: {url}\nTID: {tid}\nSITE: {site}\n\n## 正文\n{vis}\n"
            if folded:
                body += "\n## 折叠详解 (GLxx)\n" + "\n\n".join(folded) + "\n"
            open(path,"w").write(body)
            done += 1
            if done % 20 == 0:
                print(f"[{site}] {done}/{len(idx)}")
        except Exception as e:
            print(f"[{site}] FAIL tid={tid} {title}: {e}")
        time.sleep(delay)
    print(f"[{site}] DONE {done}/{len(idx)}")

if __name__ == "__main__":
    sites = sys.argv[1:] or list(SITES.keys())
    for s in sites:
        scrape_site(s)
