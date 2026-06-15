#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补跑脚本：处理主批处理里 NO_RAW / PARSE_FAIL / EXC 的篇目。
改进点：
  1. 新增源站 yinglunka（英国），英国从欧萌客改到英伦咖。
  2. 景点页/城市页若文件名匹配不到独立 raw，回退用「国家总览帖 + 全文搜得到的帖」按景点名切片喂模型。
  3. 英国别名映射（天空岛/苏格兰高地/英国湖区/披头士→利物浦）。
  4. Bedrock timeout(EXC) 重试 3 次，退避。
  5. botocore read_timeout 拉长到 120s。
只处理传入清单或自动扫描出的"非瑞士深度"篇目，成功才备份+写回。
"""
import os, json, re, time, shutil, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from botocore.config import Config

BASE = "/home/ubuntu/tools/travel_APP/travel_guide/data/playbooks"
RAW  = "/home/ubuntu/tools/travel_APP/scripts/raw"
BAK  = "/home/ubuntu/tools/travel_APP/scripts/playbook_bak"
LOG  = "/home/ubuntu/tools/travel_APP/scripts/rewrite_fix_log.txt"
MODEL= "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
os.makedirs(BAK, exist_ok=True)

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                       config=Config(read_timeout=120, connect_timeout=20, retries={"max_attempts":2}))

EU = ["瑞士","意大利","法国","西班牙","德国","北欧","希腊","奥地利","葡萄牙",
      "荷兰","捷克","匈牙利","冰岛","芬兰","挪威","克罗地亚","土耳其","埃及","阿联酋"]
C2S = {c:"oumengke" for c in EU}
C2S["英国"] = "yinglunka"   # 英国 → 英伦咖
C2S.update({"美国":"meilvtong","加拿大":"meilvtong","日本":"rilvtong",
            "澳大利亚":"aoxintong","新西兰":"aoxintong","斐济":"aoxintong"})
SKIP_COUNTRY = {"瑞士"}

# 国家总览帖（回退用）：playbook 城市/景点没独立帖时，从这些帖切片
COUNTRY_OVERVIEW = {
    "冰岛": ["冰岛旅游攻略_228.md"],
    "克罗地亚": ["克罗地亚旅游攻略_249.md","十六湖旅游攻略_247.md"],
    "挪威": ["挪威旅游攻略_252.md"],
    "土耳其": ["土耳其旅游攻略_262.md","伊斯坦布尔旅游攻略_230.md"],
    "埃及": ["埃及旅游攻略_265.md","开罗旅游攻略_256.md"],
    "希腊": ["雅典旅游攻略_51.md"],
}
# 特例别名：playbook名 -> 源站 raw 文件名关键词（精确兜底）
ALIAS_FILE = {
    ("英国","天空岛.json"): ["格伦科峡谷","本尼维斯山","格伦芬南大桥","尼斯湖"],
    ("英国","苏格兰高地.json"): ["尼斯湖","格伦科峡谷","本尼维斯山","格伦芬南大桥","洛蒙德湖","因弗尼斯"],
    ("英国","英国湖区城市攻略.json"): ["温德米尔湖","湖区公交"],
    ("英国","披头士博物馆.json"): ["利物浦旅游攻略"],
    ("意大利","最后的晚餐.json"): ["米兰旅游攻略","米兰酒店"],
    ("意大利","托斯卡纳城市攻略.json"): ["佛罗伦萨旅游攻略","锡耶纳"],
    ("匈牙利","塞切尼温泉.json"): ["布达佩斯攻略","布达佩斯旅游"],
    ("捷克","布拉格城堡.json"): ["布拉格攻略"],
    ("奥地利","美泉宫.json"): ["维也纳旅游攻略"],
    ("希腊","雅典卫城.json"): ["雅典旅游攻略"],
    ("葡萄牙","莱罗书店.json"): ["波尔图攻略"],
    ("西班牙","阿尔罕布拉宫.json"): ["格拉纳达"],
    ("北欧","雷克雅未克城市攻略.json"): ["冰岛旅游攻略"],
    ("北欧","罗弗敦城市攻略.json"): ["挪威旅游攻略"],
    ("挪威","罗弗敦群岛.json"): ["挪威旅游攻略"],
    ("斐济","楠迪城市攻略.json"): ["斐济旅游攻略"],
    ("日本","那霸城市攻略.json"): ["冲绳岛旅游攻略"],
    ("美国","夏威夷大岛城市攻略.json"): ["大岛旅游攻略","夏威夷旅游攻略"],
    ("美国","檀香山城市攻略.json"): ["欧胡岛","夏威夷旅游攻略"],
    ("美国","红杉公园城市攻略.json"): ["红杉国家公园"],
    ("土耳其","以弗所古城.json"): ["伊兹密尔旅游攻略","土耳其旅游攻略"],
    ("土耳其","圣索菲亚大教堂.json"): ["伊斯坦布尔旅游攻略"],
    ("土耳其","蓝色清真寺.json"): ["伊斯坦布尔旅游攻略"],
    ("埃及","阿布辛贝神庙.json"): ["阿斯旺旅游攻略","埃及旅游攻略"],
    ("克罗地亚","十六湖国家公园.json"): ["十六湖旅游攻略","克罗地亚旅游攻略"],
    ("冰岛","黄金圈.json"): ["冰岛旅游攻略"],
    ("法国","波尔多城市攻略.json"): ["法国旅游攻略"],
    ("西班牙","帕尔马城市攻略.json"): ["马略卡岛攻略"],
    ("加拿大","瀑布城城市攻略.json"): ["尼亚加拉","多伦多"],
}

# raw 全文索引
RAW_TEXT = {}
for site in os.listdir(RAW):
    sdir=os.path.join(RAW,site)
    if not os.path.isdir(sdir): continue
    for f in os.listdir(sdir):
        if f.endswith(".md"):
            try: RAW_TEXT[(site,f)]=open(os.path.join(sdir,f),encoding="utf-8").read()
            except: RAW_TEXT[(site,f)]=open(os.path.join(sdir,f),encoding="gbk",errors="replace").read()

def core(name):
    n=name.replace(".json","")
    for suf in ["城市攻略","旅游攻略","攻略"]:
        if n.endswith(suf): n=n[:-len(suf)]
    return n

def gather_material(country, pf, pb):
    site=C2S.get(country)
    if not site: return site, []
    names=set(); key=core(pf)
    if key: names.add(key)
    for k in ("city","name"):
        if pb.get(k): names.add(pb[k])
    for a in pb.get("attractions",[]) or []:
        if a.get("name"): names.add(a["name"])
    for al in pb.get("aliases",[]) or []: names.add(al)
    names={n for n in names if n and len(n)>=2}
    hits=[]
    for (s,f),txt in RAW_TEXT.items():
        if s!=site: continue
        if any(n in f.replace(".md","") for n in names):
            hits.append((f.replace(".md",""),txt))
    # 别名兜底
    if not hits and (country,pf) in ALIAS_FILE:
        for kw in ALIAS_FILE[(country,pf)]:
            for (s,f),txt in RAW_TEXT.items():
                if s==site and kw in f:
                    hits.append((f.replace(".md",""),txt))
    # 国家总览帖回退（按景点名切片）
    if not hits and country in COUNTRY_OVERVIEW:
        for ov in COUNTRY_OVERVIEW[country]:
            if (site,ov) in RAW_TEXT:
                txt=RAW_TEXT[(site,ov)]
                hits.append((ov.replace(".md",""),txt))
    hits=sorted(set(hits), key=lambda x:(0 if (key and key in x[0] and "攻略" in x[0]) else 1, x[0]))
    return site, hits

# ---- schema/prompt 复用主脚本 ----
import importlib.util
spec=importlib.util.spec_from_file_location("mainrw","/home/ubuntu/tools/travel_APP/scripts/rewrite_playbooks.py")
M=importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

def log(msg):
    line=f"[{time.strftime('%H:%M:%S')}] {msg}"; print(line,flush=True)
    open(LOG,"a",encoding="utf-8").write(line+"\n")

def invoke_retry(system,user,mt=8192):
    for att in range(3):
        try:
            body={"anthropic_version":"bedrock-2023-05-31","max_tokens":mt,"system":system,"messages":[{"role":"user","content":user}]}
            r=bedrock.invoke_model(modelId=MODEL,contentType="application/json",accept="application/json",body=json.dumps(body))
            return json.loads(r["body"].read())["content"][0]["text"].strip()
        except Exception as e:
            log(f"  invoke 失败(尝试{att+1}): {repr(e)[:120]}")
            time.sleep(5*(att+1))
    return None

def parse_retry(system,user,label):
    for att in range(2):
        out=invoke_retry(system,user)
        if out is None: return None
        txt=M._clean(out)
        try: return json.loads(txt)
        except json.JSONDecodeError:
            try: return json.loads(M._repair_json(txt))
            except json.JSONDecodeError as e:
                log(f"  [{label}] JSON失败(尝试{att+1}): {e}")
                user=user+"\n\n注意：上次输出超长被截断。hotels≤8家，sections≤4节，确保JSON完整闭合。"
    return None

def process_one(country,pf):
    path=os.path.join(BASE,country,pf)
    try: pb=json.load(open(path,encoding="utf-8"))
    except Exception as e: return (country,pf,"READ_ERR",str(e))
    site,hits=gather_material(country,pf,pb)
    if not site: return (country,pf,"NO_SITE","")
    if not hits: return (country,pf,"NO_RAW","源站仍无素材")
    is_city=(pb.get("type")=="city") or pf.endswith("城市攻略.json")
    mat="\n\n---\n\n".join(f"【{n}】\n{t[:6000]}" for n,t in hits[:8])[:55000]
    if is_city:
        system=M.SYS_CITY
        user=(f"城市：{pb.get('city')} 国家：{country}\n参考：name={pb.get('name')}, aliases={pb.get('aliases')}, duration={pb.get('duration')}, best_time={pb.get('best_time')}\n\n【源站原始攻略素材】：\n{mat}\n\n输出对齐schema的JSON。")
        label=f"{country}/{pf}(city)"
    else:
        system=M.SYS_ATTR
        user=(f"景点：{pb.get('name')} 城市：{pb.get('city')} 国家：{country}\n参考：aliases={pb.get('aliases')}, duration={pb.get('duration')}, best_time={pb.get('best_time')}\n\n【源站原始攻略素材】：\n{mat}\n\n输出对齐schema的JSON。")
        label=f"{country}/{pf}(attr)"
    d=parse_retry(system,user,label)
    if d is None: return (country,pf,"PARSE_FAIL","")
    d["country"]=country
    if "type" not in d: d["type"]="city" if is_city else "attraction"
    if not d.get("name"): d["name"]=pb.get("name")
    if not d.get("city"): d["city"]=pb.get("city")
    if pb.get("transport_map"): d["transport_map"]=pb["transport_map"]
    bdir=os.path.join(BAK,country); os.makedirs(bdir,exist_ok=True)
    if not os.path.exists(os.path.join(bdir,pf)): shutil.copy2(path,os.path.join(bdir,pf))
    json.dump(d,open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    nh=len(d.get("hotels",[])) if is_city else 0
    na=len(d.get("attractions",[])) if is_city else len(d.get("activities",[]))
    return (country,pf,"OK",f"hotels={nh} attr/act={na} raw={len(hits)}")

def needs_fix(country,pf):
    """判断该篇是否需重修：①还是浅文本 ②或景点页格式不对(facts非数组/activities非对象/无route_note)。"""
    d=json.load(open(os.path.join(BASE,country,pf),encoding="utf-8"))
    t=d.get("type")
    if t=="city":
        return sum(1 for k in ("transport","hotels","attractions","itinerary") if d.get(k))<3
    elif t=="attraction":
        # 浅：四字段全空
        if sum(1 for k in ("facts","price","activities","tips") if d.get(k))<1:
            return True
        # 格式错(旧prompt产物)：facts应是数组[{k,v}]，activities应是对象数组，应有route_note
        facts=d.get("facts")
        if facts and not (isinstance(facts,list) and facts and isinstance(facts[0],dict)):
            return True
        acts=d.get("activities")
        if acts and not (isinstance(acts,list) and acts and isinstance(acts[0],dict)):
            return True
        if not d.get("route_note"):  # 交通缺失
            return True
        return False
    return True  # type=None 一定要修

def main(argv):
    open(LOG,"w").close()
    tasks=[]
    for country in sorted(os.listdir(BASE)):
        cdir=os.path.join(BASE,country)
        if not os.path.isdir(cdir) or country in SKIP_COUNTRY or country not in C2S: continue
        for pf in sorted(os.listdir(cdir)):
            if not pf.endswith(".json"): continue
            if needs_fix(country,pf):
                tasks.append((country,pf))
    log(f"待补跑 {len(tasks)} 篇（仍浅或源站新增），并发3...")
    results=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(process_one,c,p):(c,p) for c,p in tasks}
        done=0
        for fut in as_completed(futs):
            c,p=futs[fut]
            try: r=fut.result()
            except Exception as e: r=(c,p,"EXC",str(e)[:150])
            results.append(r); done+=1
            log(f"[{done}/{len(tasks)}] {r[0]}/{r[1]} -> {r[2]} {r[3]}")
    from collections import Counter
    log(f"\n===== 补跑完成 =====\n{dict(Counter(r[2] for r in results))}")
    for r in results:
        if r[2]!="OK": log(f"  非OK: {r[0]}/{r[1]} -> {r[2]} {r[3]}")

if __name__=="__main__":
    main(sys.argv[1:])
