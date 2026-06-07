"""微信登录 + 用户管理"""

import hashlib
import hmac
import json
import os
import time
import urllib.request
from typing import Optional
from sqlalchemy.orm import Session

# ---- 配置 ----
# 小程序
WX_MINI_APPID = os.environ.get("WX_MINI_APPID", "")
WX_MINI_SECRET = os.environ.get("WX_MINI_SECRET", "")
# 网页端（公众号/开放平台，后续扩展）
WX_WEB_APPID = os.environ.get("WX_WEB_APPID", "")
WX_WEB_SECRET = os.environ.get("WX_WEB_SECRET", "")
# Token签名密钥
TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "travel-companion-dev-secret-change-me")
TOKEN_EXPIRE = 7 * 24 * 3600  # 7天


# ---- 简易Token（不依赖PyJWT） ----
def _sign(payload_b64: str) -> str:
    return hmac.new(TOKEN_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]


def create_token(user_id: int, openid: str) -> str:
    """生成token: base64(payload).signature"""
    import base64
    payload = json.dumps({"uid": user_id, "oid": openid, "exp": int(time.time()) + TOKEN_EXPIRE})
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = _sign(b64)
    return f"{b64}.{sig}"


def verify_token(token: str) -> Optional[dict]:
    """验证token，返回payload或None"""
    import base64
    try:
        b64, sig = token.rsplit(".", 1)
        if _sign(b64) != sig:
            return None
        # 补齐padding
        padded = b64 + "=" * (4 - len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ---- 微信登录 ----
def wx_code2session(code: str) -> Optional[dict]:
    """小程序 code 换 openid + session_key"""
    if not WX_MINI_APPID or not WX_MINI_SECRET:
        # 开发模式：没配appid时用code模拟openid
        return {"openid": f"dev_{code}", "session_key": "dev"}

    url = (
        f"https://api.weixin.qq.com/sns/jscode2session"
        f"?appid={WX_MINI_APPID}&secret={WX_MINI_SECRET}"
        f"&js_code={code}&grant_type=authorization_code"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if "openid" in data:
            return data
        print(f"微信登录失败: {data}")
        return None
    except Exception as e:
        print(f"微信登录请求失败: {e}")
        return None


def login_or_register(db: Session, openid: str, union_id: str = None,
                      nickname: str = None, avatar_url: str = None,
                      login_type: str = "miniprogram") -> dict:
    """根据openid登录或自动注册，返回用户信息+token"""
    from models import User

    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        # 自动注册
        user = User(
            openid=openid,
            union_id=union_id,
            nickname=nickname or f"旅行者{openid[-4:]}",
            avatar_url=avatar_url,
            login_type=login_type
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new = True
    else:
        is_new = False
        # 更新信息
        if nickname and nickname != user.nickname:
            user.nickname = nickname
        if avatar_url and avatar_url != user.avatar_url:
            user.avatar_url = avatar_url
        db.commit()

    token = create_token(user.id, user.openid)
    return {
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "token": token,
        "is_new_user": is_new
    }


def get_current_user(db: Session, token: str):
    """从token获取当前用户，返回User对象或None"""
    from models import User
    payload = verify_token(token)
    if not payload:
        return None
    return db.query(User).filter(User.id == payload["uid"]).first()


# ---- 密码哈希 ----
def _hash_password(password: str) -> str:
    salt = TOKEN_SECRET[:8]
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


# ---- 网页版注册/登录 ----
def register_web(db: Session, username: str, password: str, nickname: str = None) -> dict:
    """网页版注册"""
    from models import User

    if len(username) < 3 or len(password) < 6:
        raise ValueError("用户名至少3位，密码至少6位")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise ValueError("用户名已存在")

    user = User(
        openid=f"web_{username}",
        username=username,
        password_hash=_hash_password(password),
        nickname=nickname or username,
        login_type="web"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, user.openid)
    return {
        "user_id": user.id,
        "nickname": user.nickname,
        "token": token
    }


def login_web(db: Session, username: str, password: str) -> dict:
    """网页版登录"""
    from models import User

    user = db.query(User).filter(User.username == username).first()
    if not user or user.password_hash != _hash_password(password):
        raise ValueError("用户名或密码错误")

    token = create_token(user.id, user.openid)
    return {
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "token": token
    }


def update_profile(db: Session, token: str, nickname: str = None, gender: str = None, avatar_url: str = None) -> dict:
    """更新用户资料"""
    user = get_current_user(db, token)
    if not user:
        raise ValueError("未登录或token无效")

    if nickname:
        user.nickname = nickname
    if gender:
        user.gender = gender
    if avatar_url:
        user.avatar_url = avatar_url
    db.commit()

    return {
        "user_id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "gender": user.gender
    }
