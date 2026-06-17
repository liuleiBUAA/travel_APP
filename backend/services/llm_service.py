"""LLM 服务：意图识别 + 槽位抽取 + 追问/回话生成。

封装原则（重要）：
- 所有大模型调用都收口到本文件，业务代码（main.py）不直接碰 LLM 细节。
- 将来要换自部署开源模型 / 换别家 API，只改本文件的 chat_completion()，
  上层 parse_intent() 的返回结构不变，业务层一行不用动。
- API key 只读环境变量 DEEPSEEK_API_KEY，绝不硬编码、绝不进 git。
"""

import json
import os
import urllib.request
import urllib.error

# ── 可替换的模型配置（换模型只动这里） ──────────────────────────
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.deepseek.com/chat/completions")
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-flash")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "15"))

# ── 意图路由 system prompt ────────────────────────────────────
INTENT_SYSTEM_PROMPT = """你是旅行小程序「找搭子」的语音助手。用户用一句话或多轮对话表达需求，你要判断意图、抽取关键信息、必要时追问，并生成口语化回话。

【四种意图 intent】
- find_companion：找旅行搭子（"找个一起去日本的""有没有7月去北海道的搭子"）
- publish_route：发布自己的行程招搭子（"我想发布去瑞士10天的行程""帮我发个找搭子"）
- search_guide：查攻略/玩法（"圣托里尼有什么好玩的""悉尼攻略"）
- unknown：和旅行无关（天气、闲聊等）

【要抽取的槽位 slots】
- cities：城市/国家/目的地名数组，如 ["日本"]、["瑞士","法国"]
- travel_month：旅行月份，必须是数字 1-12（用户说"7月"→输出 7；说不清就 null）
- duration_days：天数，数字（说"10天"→10；没说→null）
- seeking：找搭子的对象描述，原样保留用户说的（如"小姐姐""情侣""不限"；没说→null，不要瞎编人数）

【必填校验】
- find_companion 和 publish_route：必须有 cities 和 travel_month，缺哪个就追问。
- search_guide：必须有 cities，缺就追问。
- unknown：不用追问。

【输出 JSON（只输出 JSON，不要多余文字）】
{
  "intent": "find_companion|publish_route|search_guide|unknown",
  "slots": {"cities": [], "travel_month": null, "duration_days": null, "seeking": null},
  "need_more": true/false,
  "missing": ["地点"或"时间"等中文],
  "reply": "口语化回话：need_more时是追问，否则是确认正在执行的话"
}

【规则】
- travel_month 一定是数字或 null，绝不输出"7月"这种字符串。
- seeking 用户没提就保持 null，不要替用户编人数或性别。
- 多轮对话时，把历史里已说过的槽位累积下来，不要重复追问已知信息。
- reply 自然口语，简短友好。"""


def chat_completion(messages, temperature=0.0, json_mode=True):
    """底层 LLM 调用。换模型/换厂商只改这个函数。

    Args:
        messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
        temperature: 采样温度
        json_mode: 是否强制 JSON 输出
    Returns:
        str: 模型返回的文本内容
    Raises:
        RuntimeError: 未配置 key 或调用失败
    """
    if not LLM_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY 环境变量")

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LLM_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"LLM HTTP {e.code}: {detail}")
    except Exception as e:
        raise RuntimeError(f"LLM 调用失败: {e}")


def _clean_month(val):
    """travel_month 兜底清洗：把'7月'/'7'/7 都规整成 1-12 的 int 或 None。"""
    if val is None:
        return None
    if isinstance(val, int) and 1 <= val <= 12:
        return val
    if isinstance(val, str):
        import re
        m = re.search(r"\d{1,2}", val)
        if m:
            n = int(m.group())
            if 1 <= n <= 12:
                return n
    return None


def parse_intent(dialog_messages):
    """对一段对话历史做意图识别+槽位抽取。

    Args:
        dialog_messages: 用户与助手的对话历史
            [{"role": "user"|"assistant", "content": str}, ...]
    Returns:
        dict: {
            "intent": str,
            "slots": {"cities": [...], "travel_month": int|None,
                      "duration_days": int|None, "seeking": str|None},
            "need_more": bool,
            "missing": [str, ...],
            "reply": str
        }
    """
    messages = [{"role": "system", "content": INTENT_SYSTEM_PROMPT}] + dialog_messages
    raw = chat_completion(messages, temperature=0.0, json_mode=True)
    result = json.loads(raw)

    # 结构兜底，保证下游字段齐全
    result.setdefault("intent", "unknown")
    slots = result.setdefault("slots", {})
    slots.setdefault("cities", [])
    slots["travel_month"] = _clean_month(slots.get("travel_month"))
    slots.setdefault("duration_days", None)
    slots.setdefault("seeking", None)
    result.setdefault("need_more", False)
    result.setdefault("missing", [])
    result.setdefault("reply", "")
    return result
