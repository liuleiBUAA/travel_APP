"""
会员权限服务
- 所有功能定义在这里
- 要修改功能权限/价格，只需改这个文件
"""

# ============================================================
# 全局开关：False = 所有功能免费，True = 启用会员权限检查
# ============================================================
ENABLE_MEMBERSHIP = False

# ============================================================
# 会员等级定义
# ============================================================
TIERS = {
    "free": {
        "name": "体验版",
        "price_quarterly": 0,
        "price_yearly": 0,
        "guide_addon_quarterly": 0,
        "guide_addon_yearly": 0,
    },
    "basic": {
        "name": "付费版",
        "price_quarterly": 59,
        "price_yearly": 199,
        "guide_addon_quarterly": 20,
        "guide_addon_yearly": 50,
    },
    "vip": {
        "name": "高级会员",
        "price_quarterly": 89,
        "price_yearly": 299,
        "guide_addon_quarterly": 20,
        "guide_addon_yearly": 50,
    },
}

# ============================================================
# 功能定义
# key: 功能标识符（代码里用这个）
# ============================================================
FEATURES = {
    "publish_trip": {
        "name": "发布行程",
        "description": "发布搭子帖",
        # 每种会员的次数限制：-1 = 无限，数字 = 具体次数
        "free": {"limit": -1, "note": "无限"},
        "basic": {"limit": -1, "note": "无限"},
        "vip": {"limit": -1, "note": "无限"},
    },
    "search_trip": {
        "name": "搜索搭子",
        "description": "搜索和查看其他人的搭子帖",
        "free": {"limit": 3, "note": "仅预览3条"},
        "basic": {"limit": -1, "note": "无限"},
        "vip": {"limit": -1, "note": "无限"},
    },
    "ai_guide": {
        "name": "AI生成攻略",
        "description": "AI生成定制化行程攻略",
        "free": {"limit": 3, "note": "3次"},
        "basic": {"limit": 10, "note": "10次"},
        "vip": {"limit": -1, "note": "无限"},
    },
    "destination_recommend": {
        "name": "AI目的地推荐",
        "description": "AI推荐适合的目的地",
        "free": {"limit": -1, "note": "无限"},
        "basic": {"limit": -1, "note": "无限"},
        "vip": {"limit": -1, "note": "无限"},
    },
    "guide_library": {
        "name": "攻略库阅读",
        "description": "阅读完整攻略库内容",
        "free": {"limit": 0, "note": "仅预览"},
        "basic": {"limit": -1, "note": "全部"},
        "vip": {"limit": -1, "note": "全部"},
    },
}


# ============================================================
# 核心函数
# ============================================================

def check_permission(user_id: str, feature_key: str) -> dict:
    """
    检查用户是否有某功能的权限

    返回：
        {
            "allowed": True/False,
            "remaining": 剩余次数（-1=无限）,
            "note": "显示文案",
            "tier": "当前会员等级",
            "upgrade_tips": "升级提示（无权限时）"
        }
    """
    if not ENABLE_MEMBERSHIP:
        # 开关关闭，所有功能免费
        return {
            "allowed": True,
            "remaining": -1,
            "note": "全功能免费开放",
            "tier": "free",
            "upgrade_tips": None,
        }

    from models import UserMembership
    from database import get_db

    db = next(get_db())
    try:
        membership = db.query(UserMembership).filter(
            UserMembership.user_id == user_id
        ).first()

        if not membership:
            tier = "free"
        else:
            tier = membership.tier

        # 查功能定义
        feature = FEATURES.get(feature_key)
        if not feature:
            return {
                "allowed": False,
                "remaining": 0,
                "note": "功能不存在",
                "tier": tier,
                "upgrade_tips": None,
            }

        tier_config = feature.get(tier, feature["free"])
        limit = tier_config["limit"]

        if limit == -1:
            return {
                "allowed": True,
                "remaining": -1,
                "note": tier_config["note"],
                "tier": tier,
                "upgrade_tips": None,
            }

        # 有次数限制，查已用次数
        used = _get_used_count(membership, feature_key)
        remaining = limit - used

        if remaining <= 0:
            return {
                "allowed": False,
                "remaining": 0,
                "note": f"已达上限（{tier_config['note']}）",
                "tier": tier,
                "upgrade_tips": f"升级到付费版，解锁更多次数",
            }

        return {
            "allowed": True,
            "remaining": remaining,
            "note": f"剩余{remaining}次",
            "tier": tier,
            "upgrade_tips": None,
        }
    finally:
        db.close()


def use_permission(user_id: str, feature_key: str) -> bool:
    """
    消耗一次权限（扣减次数）
    返回是否成功
    """
    if not ENABLE_MEMBERSHIP:
        return True

    from models import UserMembership
    from database import get_db

    db = next(get_db())
    try:
        membership = db.query(UserMembership).filter(
            UserMembership.user_id == user_id
        ).first()

        if not membership:
            return True  # free用户不记录

        tier = membership.tier
        feature = FEATURES.get(feature_key)
        if not feature:
            return True

        tier_config = feature.get(tier, feature["free"])
        limit = tier_config["limit"]

        if limit == -1:
            return True  # 无限次不扣

        # 扣减对应字段
        if feature_key == "ai_guide":
            membership.guide_used = (membership.guide_used or 0) + 1
        elif feature_key == "publish_trip":
            membership.publish_used = (membership.publish_used or 0) + 1

        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def _get_used_count(membership, feature_key: str) -> int:
    """获取已使用次数"""
    if feature_key == "ai_guide":
        return membership.guide_used or 0
    elif feature_key == "publish_trip":
        return membership.publish_used or 0
    return 0


def get_user_tier(user_id: str) -> str:
    """获取用户当前会员等级"""
    if not ENABLE_MEMBERSHIP:
        return "free"

    from models import UserMembership
    from database import get_db

    db = next(get_db())
    try:
        membership = db.query(UserMembership).filter(
            UserMembership.user_id == user_id
        ).first()
        return membership.tier if membership else "free"
    finally:
        db.close()


def get_tier_status(user_id: str) -> dict:
    """
    获取用户会员状态（用于前端展示）
    """
    if not ENABLE_MEMBERSHIP:
        return {
            "tier": "free",
            "tier_name": "体验版",
            "expired_at": None,
            "features": {key: {"allowed": True, "remaining": -1, "note": "免费"}
                         for key in FEATURES},
        }

    from models import UserMembership
    from database import get_db

    db = next(get_db())
    try:
        membership = db.query(UserMembership).filter(
            UserMembership.user_id == user_id
        ).first()

        tier = membership.tier if membership else "free"
        tier_name = TIERS[tier]["name"]
        expired_at = membership.expired_at.isoformat() if membership and membership.expired_at else None

        features = {}
        for key, feature in FEATURES.items():
            result = check_permission(user_id, key)
            features[key] = {
                "allowed": result["allowed"],
                "remaining": result["remaining"],
                "note": result["note"],
                "upgrade_tips": result["upgrade_tips"],
            }

        return {
            "tier": tier,
            "tier_name": tier_name,
            "expired_at": expired_at,
            "features": features,
            "tiers": TIERS,  # 包含所有等级和价格，供前端渲染
        }
    finally:
        db.close()
