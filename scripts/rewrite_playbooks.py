#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量把各国 playbook 重写成瑞士样板深度。
严格铁律：
  - 按源站映射取 raw（欧萌客=欧洲+中东 / 美旅通=美洲 / 日旅通=日本 / 澳新通=大洋洲），绝不混用。
  - 只用 raw 真实数据；价格归属严格（不串价）；raw 没有的字段留空，不编造。
  - 瑞士本身是样板，跳过不重写。
输出：覆盖写回 playbook JSON（先备份到 scripts/playbook_bak/）。
"""
import os, json, re, sys, time, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3

BASE   = "/home/ubuntu/tools/travel_APP/travel_guide/data/playbooks"
RAW    = "/home/ubuntu/tools/travel_APP/scripts/raw"
BAK    = "/home/ubuntu/tools/travel_APP/scripts/playbook_bak"
LOG    = "/home/ubuntu/tools/travel_APP/scripts/rewrite_log.txt"
MODEL  = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
os.makedirs(BAK, exist_ok=True)

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

EU = ["瑞士","意大利","法国","英国","西班牙","德国","北欧","希腊","奥地利","葡萄牙",
      "荷兰","捷克","匈牙利","冰岛","芬兰","挪威","克罗地亚","土耳其","埃及","阿联酋"]
C2S = {c:"oumengke" for c in EU}
C2S.update({"美国":"meilvtong","加拿大":"meilvtong","日本":"rilvtong",
            "澳大利亚":"aoxintong","新西兰":"aoxintong","斐济":"aoxintong"})

SKIP_COUNTRY = {"瑞士"}  # 瑞士是样板

# ---------- raw 全文索引 ----------
RAW_TEXT = {}   # (site, filename) -> text
for site in os.listdir(RAW):
    sdir = os.path.join(RAW, site)
    if not os.path.isdir(sdir): continue
    for f in os.listdir(sdir):
        if f.endswith(".md"):
            try:
                RAW_TEXT[(site, f)] = open(os.path.join(sdir, f), encoding="utf-8").read()
            except Exception:
                RAW_TEXT[(site, f)] = open(os.path.join(sdir, f), encoding="gbk", errors="replace").read()

def core(name):
    n = name.replace(".json","")
    for suf in ["城市攻略","旅游攻略","攻略"]:
        if n.endswith(suf): n = n[:-len(suf)]
    return n

def gather_material(country, pf, pb):
    """收集该 playbook 在对应源站的相关 raw 全文。"""
    site = C2S.get(country)
    if not site: return site, []
    names = set()
    key = core(pf)
    if key: names.add(key)
    for k in ("city","name"):
        if pb.get(k): names.add(pb[k])
    for a in pb.get("attractions",[]) or []:
        if a.get("name"): names.add(a["name"])
    for al in pb.get("aliases",[]) or []:
        names.add(al)
    names = {n for n in names if n and len(n)>=2}
    hits = []
    for (s,f), txt in RAW_TEXT.items():
        if s != site: continue
        fn = f.replace(".md","")
        if any(n in fn for n in names):
            hits.append((fn, txt))
    # 城市页主帖优先（含"旅游攻略"/"城市"），去重排序
    hits = sorted(set(hits), key=lambda x: (0 if (key and key in x[0] and ("攻略" in x[0])) else 1, x[0]))
    return site, hits

# ---------- schema & prompt ----------
CITY_SCHEMA = '''{
  "name":"城市名","type":"city","aliases":["别名/外文名"],"city":"城市名","country":"国家",
  "summary":"1-2句城市定位（核心理由+怎么玩）",
  "transport":{"fly_train":"机场→市区线路/时长/票价","drive":"城际/景观/自驾要点","local":"市内交通票种价格"},
  "hotels":[{"name":"","area":"","star":数字,"score":"","reviews":"","note":"","link":""}],
  "hotel_intro":"住宿区域建议",
  "attractions":[{"name":"","order":数字,"tagline":"亮点+时长（价格仅当素材明确归属该景点时才写）","has_detail":false}],
  "itinerary":[{"day":"1","title":"","detail":""}],
  "sections":[{"title":"","content":"详细散文"}],
  "duration":"","best_time":""
}'''

ATTR_SCHEMA = '''{
  "name":"景点名","type":"attraction","aliases":["别名/外文名"],"city":"所在城市","country":"国家",
  "summary":"1-2句景点定位",
  "facts":{"海拔/规模等关键事实":"值"},
  "price":"门票价格（仅写素材明确标注的）",
  "activities":["可做的活动/看点"],
  "tips":["实用贴士"],
  "sections":[{"title":"","content":"详细散文"}],
  "duration":"","best_time":""
}'''

SYS_CITY = f'''你是旅游攻略数据工程师。根据【源站原始攻略素材】把城市攻略改写成结构化JSON，严格对齐schema。
schema（瑞士样板）：
{CITY_SCHEMA}
铁律（违反=数据作废）：
1. 只用素材里出现的真实信息。酒店名/星级/评分/评价数/交通票价/景点门票必须逐字来自素材。
2. 【价格归属铁律】门票价格只能写给素材中明确标注该价格的那个景点。绝不把A景点价格安到B景点。某景点素材没写价格，tagline只写亮点+时长，不准编价格、不准借用别处价格。
3. 素材没有的字段留空[]或""，绝不编造。
4. hotels只填素材真实推荐的（含星级评分评价数），没有给[]。star是数字（无星级填0）。
5. attractions按素材顺序，tagline浓缩亮点/时长。
6. transport三段从"如何到达/市内交通/地铁"提炼真实线路票价。
7. 只输出JSON，无解释无markdown标记。务必输出完整闭合的JSON。'''

SYS_ATTR = f'''你是旅游攻略数据工程师。根据【源站原始攻略素材】把景点攻略改写成结构化JSON，严格对齐schema。
schema（瑞士样板）：
{ATTR_SCHEMA}
铁律（违反=数据作废）：
1. 只用素材里真实信息。价格/海拔/规模/开放时间等必须逐字来自素材。
2. price只写素材明确标注的该景点价格，没有就留""，绝不编造或借用别处价格。
3. facts/activities/tips只填素材里有的，没有就留空。
4. 只输出JSON，无解释无markdown标记。务必输出完整闭合的JSON。'''

def _invoke(system, user, max_tokens=8192):
    body={"anthropic_version":"bedrock-2023-05-31","max_tokens":max_tokens,
          "system":system,"messages":[{"role":"user","content":user}]}
    r=bedrock.invoke_model(modelId=MODEL,contentType="application/json",
                           accept="application/json",body=json.dumps(body))
    return json.loads(r["body"].read())["content"][0]["text"].strip()

def _clean(txt):
    txt=txt.strip()
    txt=re.sub(r'^```(json)?','',txt).strip()
    txt=re.sub(r'```$','',txt).strip()
    return txt

def parse_json_retry(system, user, label):
    """调用并解析JSON，截断/解析失败重试一次（更大token + 提示精简）。"""
    for attempt in range(2):
        mt = 8192 if attempt==0 else 8192
        try:
            raw_out=_invoke(system,user,mt)
            txt=_clean(raw_out)
            return json.loads(txt)
        except json.JSONDecodeError as e:
            log(f"  [{label}] JSON解析失败(尝试{attempt+1}): {e}")
            if attempt==0:
                # 第二次要求更紧凑：限制 hotels/sections 数量
                user=user+"\n\n注意：上次输出超长被截断。请精简——hotels最多保留8家最具代表性的，sections最多4节，确保JSON完整闭合。"
            else:
                return None
    return None

def log(msg):
    line=f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG,"a",encoding="utf-8") as fp:
        fp.write(line+"\n")

# ---------- 单篇处理 ----------
def process_one(country, pf):
    path=os.path.join(BASE,country,pf)
    try:
        pb=json.load(open(path,encoding="utf-8"))
    except Exception as e:
        return (country,pf,"READ_ERR",str(e))
    site,hits=gather_material(country,pf,pb)
    if not site:
        return (country,pf,"NO_SITE","")
    if not hits:
        return (country,pf,"NO_RAW","源站无匹配素材，保持原样")
    is_city = (pb.get("type")=="city") or pf.endswith("城市攻略.json")
    mat="\n\n---\n\n".join(f"【{n}】\n{t[:6000]}" for n,t in hits[:8])
    mat=mat[:55000]
    if is_city:
        system=SYS_CITY
        user=(f"城市：{pb.get('city')} 国家：{country}\n"
              f"参考：name={pb.get('name')}, aliases={pb.get('aliases')}, "
              f"duration={pb.get('duration')}, best_time={pb.get('best_time')}\n\n"
              f"【源站原始攻略素材】：\n{mat}\n\n输出对齐schema的JSON。")
        label=f"{country}/{pf}(city)"
    else:
        system=SYS_ATTR
        user=(f"景点：{pb.get('name')} 城市：{pb.get('city')} 国家：{country}\n"
              f"参考：aliases={pb.get('aliases')}, duration={pb.get('duration')}, best_time={pb.get('best_time')}\n\n"
              f"【源站原始攻略素材】：\n{mat}\n\n输出对齐schema的JSON。")
        label=f"{country}/{pf}(attr)"
    d=parse_json_retry(system,user,label)
    if d is None:
        return (country,pf,"PARSE_FAIL","")
    # 强制字段对齐
    d["country"]=country
    if "type" not in d:
        d["type"]="city" if is_city else "attraction"
    if not d.get("name"): d["name"]=pb.get("name")
    if not d.get("city"): d["city"]=pb.get("city")
    if pb.get("transport_map"): d["transport_map"]=pb["transport_map"]
    # 备份原文件
    bdir=os.path.join(BAK,country); os.makedirs(bdir,exist_ok=True)
    shutil.copy2(path, os.path.join(bdir,pf))
    # 写回
    with open(path,"w",encoding="utf-8") as fp:
        json.dump(d,fp,ensure_ascii=False,indent=2)
    nh=len(d.get("hotels",[])) if is_city else 0
    na=len(d.get("attractions",[])) if is_city else len(d.get("activities",[]))
    return (country,pf,"OK",f"hotels={nh} attr/act={na} raw={len(hits)}")

# ---------- 主流程 ----------
def main():
    open(LOG,"w").close()
    tasks=[]
    for country in sorted(os.listdir(BASE)):
        cdir=os.path.join(BASE,country)
        if not os.path.isdir(cdir): continue
        if country in SKIP_COUNTRY:
            log(f"跳过样板国家 {country}"); continue
        if country not in C2S:
            log(f"⚠️ {country} 无源站映射，跳过"); continue
        for pf in sorted(os.listdir(cdir)):
            if pf.endswith(".json"):
                tasks.append((country,pf))
    log(f"待重写 {len(tasks)} 篇，启动并发(4)...")
    results=[]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(process_one,c,p):(c,p) for c,p in tasks}
        done=0
        for fut in as_completed(futs):
            c,p=futs[fut]
            try:
                r=fut.result()
            except Exception as e:
                r=(c,p,"EXC",str(e)[:200])
            results.append(r)
            done+=1
            log(f"[{done}/{len(tasks)}] {r[0]}/{r[1]} -> {r[2]} {r[3]}")
    # 汇总
    from collections import Counter
    cnt=Counter(r[2] for r in results)
    log(f"\n===== 完成 =====\n{dict(cnt)}")
    for r in results:
        if r[2] not in ("OK",):
            log(f"  非OK: {r[0]}/{r[1]} -> {r[2]} {r[3]}")

if __name__=="__main__":
    main()
