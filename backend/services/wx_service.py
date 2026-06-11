"""微信服务端接口：access_token 缓存 + 内容安全检测 msgSecCheck"""

import json
import os
import time
import urllib.request

WX_MINI_APPID = os.environ.get("WX_MINI_APPID", "")
WX_MINI_SECRET = os.environ.get("WX_MINI_SECRET", "")

# access_token 内存缓存（微信有效期7200秒，提前200秒刷新）
_token_cache = {"token": None, "expires_at": 0}


def get_access_token() -> str:
    """获取小程序全局 access_token，带内存缓存"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    url = (
        f"https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={WX_MINI_APPID}&secret={WX_MINI_SECRET}"
    )
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())
    if "access_token" not in data:
        raise RuntimeError(f"获取access_token失败: {data}")
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 7200) - 200
    return _token_cache["token"]


def msg_sec_check(content: str, openid: str, scene: int = 2) -> dict:
    """
    内容安全检测（msgSecCheck v2）
    scene: 1=资料 2=评论 3=论坛 4=社交日志
    返回 {"pass": bool, "label": 命中类别}
    未配置 appid（本地开发模式）时直接放行。
    """
    if not WX_MINI_APPID or not WX_MINI_SECRET:
        return {"pass": True, "label": "dev_mode"}

    try:
        token = get_access_token()
        url = f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}"
        payload = json.dumps({
            "version": 2,
            "openid": openid,
            "scene": scene,
            "content": content,
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        # 微信接口不可用时放行（不因第三方故障阻塞用户），但记录日志
        print(f"⚠️ msgSecCheck 调用失败，放行: {e}")
        return {"pass": True, "label": "check_unavailable"}

    if data.get("errcode") != 0:
        print(f"⚠️ msgSecCheck 返回错误，放行: {data}")
        return {"pass": True, "label": "check_error"}

    result = data.get("result", {})
    suggest = result.get("suggest", "pass")
    return {"pass": suggest == "pass", "label": str(result.get("label", ""))}
