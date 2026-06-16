#!/usr/bin/env python3
"""
找搭子小程序后端 - FastAPI
核心功能：发布行程 → 生成路线 → 匹配算法

Harness Engineering 集成：
- hooks: 自动验证 API 返回格式、记录指标、检测慢接口
- constraints: 权限边界、循环检测
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import json
import sys
import os
from pathlib import Path

# 添加 backend 和 travel_guide 到路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "travel_guide"))

# ==================== Harness 集成 ====================
from harness import harness
from harness.constraints import PermissionBoundary

# 创建权限边界
boundary = PermissionBoundary()

# 注册自定义 Hook：API 返回后检查数据完整性
@harness.on("after_api_call")
async def check_data_integrity(context):
    """检查返回数据中不应包含的敏感信息"""
    result = context.get("result", {})
    if not isinstance(result, dict):
        return

    sensitive_keys = ["password", "secret", "token", "openid", "session_key"]
    found = [k for k in result if k in sensitive_keys]
    if found:
        harness.record_violation(f"API返回包含敏感字段: {found}", {"endpoint": context.get("endpoint", "")})

# 注册自定义 Hook：错误发生时记录详情
@harness.on("on_error")
async def log_error_detail(context):
    """记录错误详情到经验库"""
    error = context.get("error", "")
    endpoint = context.get("endpoint", "")
    print(f"🔴 Harness 错误捕获 [{endpoint}]: {error[:100]}")

# Harness 健康检查端点（仅开发环境使用）
# ==================== end Harness ====================

from database import init_db, get_db
from services.route_service import RouteService
from services.match_service import MatchService
from services.auth_service import (wx_code2session, login_or_register, get_current_user,
                                    register_web, login_web, update_profile, verify_token)
from services.wx_service import msg_sec_check
from models import User

app = FastAPI(title="找搭子小程序API", version="1.0.0")

# 景点图片静态托管。挂在 /api/ 下是为了复用 nginx 现有的 /api/ 代理，生产不用改 nginx
from fastapi.staticfiles import StaticFiles
_attractions_dir = Path(__file__).parent.parent / "travel_guide" / "data" / "images"
if _attractions_dir.exists():
    app.mount("/api/static/attractions", StaticFiles(directory=str(_attractions_dir)), name="attractions")

# 交通图（市内/城市间地形图）静态托管
_maps_dir = Path(__file__).parent.parent / "travel_guide" / "data" / "maps"
if _maps_dir.exists():
    app.mount("/api/static/maps", StaticFiles(directory=str(_maps_dir)), name="maps")

# CORS配置 - 修复：使用白名单替代 *
ALLOWED_ORIGINS = [
    "https://ht.awesometravelpartner.cn",
    "https://awesometravelpartner.cn",
    "http://localhost:8080",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_db()

# 服务实例
route_service = RouteService()
match_service = MatchService()

# ==================== 鉴权依赖 ====================
def get_current_user_from_token(authorization: Optional[str] = Header(None)) -> User:
    """统一鉴权：从 Authorization header 获取当前用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    # 验证 token
    payload = verify_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    # 从数据库获取用户
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == payload["uid"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    finally:
        db.close()

def _get_display_name(db, user_id_str: str, fallback_name: str) -> str:
    """从 User 表获取最新昵称，user_id 可能是整数字符串或旧格式如 'user_xxx'"""
    try:
        uid = int(user_id_str)
        owner = db.query(User).filter(User.id == uid).first()
        if owner and owner.nickname:
            return owner.nickname
    except (ValueError, TypeError):
        pass
    return fallback_name

def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """可选鉴权：token 存在时返回用户，不存在返回 None"""
    if not authorization:
        return None
    try:
        payload = verify_token(authorization)
        if not payload:
            return None
        db = next(get_db())
        try:
            return db.query(User).filter(User.id == payload["uid"]).first()
        finally:
            db.close()
    except:
        return None


# ==================== 数据模型 ====================

class RouteGenerateRequest(BaseModel):
    """路线生成请求"""
    mode: str  # "recommend" | "manual" | "destination"
    cities: Optional[List[str]] = None  # 手动模式：城市列表
    destinations: Optional[List[str]] = None  # 目的地模式：目的地名称
    travel_month: Optional[int] = None  # 推荐模式：旅行月份
    duration_days: Optional[int] = None  # 推荐模式：天数
    manual_route: Optional[Dict[str, Any]] = None  # 手动输入的完整路线

    # 推荐模式额外参数（完整推荐算法）
    region: Optional[str] = None  # 区域筛选：Europe/Asia/North_America/Oceania
    countries: Optional[List[str]] = None  # 国家筛选：["法国", "意大利"]
    tags: Optional[List[str]] = None  # 标签筛选：["自然风光", "人文历史"]
    start_city: Optional[str] = None  # 起点城市（推荐算法用）

    # 路线生成选项
    force_gateway_departure: Optional[bool] = True  # 是否大城市出发/离开
    force_order: Optional[bool] = False  # 是否保持输入顺序
    same_day_max_hours: Optional[float] = 4.0  # 单日最大行程时间（小时）
    start_node: Optional[str] = None  # 指定起始城市（路线生成用）
    end_node: Optional[str] = None  # 指定结束城市
    transport_preference: Optional[str] = "auto"  # 交通偏好：auto/train/flight
    options_display_mode: Optional[str] = "compact"  # 显示模式：compact/detailed


class CompanionPublishRequest(BaseModel):
    """发布找搭子请求 - 已修复：user_id 和 user_name 从 token 自动获取"""
    route_json: Dict[str, Any]  # 完整的路线JSON
    travel_date: str  # "2026-05-01"
    duration_days: int
    flexibility_days: int = 3  # 时间灵活度
    seeking: Dict[str, Any]  # {"people_min": 1, "people_max": 2, "gender": "不限", "age_range": "25-35"}

    # 出行偏好（必填）
    transport_mode: Optional[str] = "不限"  # 交通方式
    accommodation: Optional[str] = "不限"  # 住宿安排
    budget_level: Optional[str] = "经济"  # 消费水平（多选，逗号分隔）

    # 个人信息
    good_at_photo: Optional[str] = "不限"  # 拍照技能：不限/一般/擅长/大师
    user_male_count: int = 0  # 男生人数
    user_female_count: int = 1  # 女生人数
    contact_wechat: Optional[str] = None  # 联系方式（微信号），详情页仅登录用户可见

    preferences: Optional[Dict[str, Any]] = None  # 其他偏好


class CompanionMatchRequest(BaseModel):
    """匹配搜索请求"""
    route_json: Dict[str, Any]
    travel_date: str
    time_flexibility_days: int = 7

    # 用户偏好（用于匹配计算）
    transport_mode: Optional[str] = "不限"
    accommodation: Optional[str] = "不限"
    budget_level: Optional[str] = "经济"
    good_at_photo: Optional[str] = "不限"
    user_male_count: int = 0  # 男生人数
    user_female_count: int = 1  # 女生人数

    # 找搭子筛选条件（可选）
    people_min: Optional[int] = None  # 找搭子最少人数
    people_max: Optional[int] = None  # 找搭子最多人数
    gender: Optional[str] = None  # 性别要求（"不限"/"男"/"女"）


# ==================== Auth 数据模型 ====================

class WxLoginRequest(BaseModel):
    """微信登录请求"""
    code: str  # wx.login() 返回的 code
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


class WebRegisterRequest(BaseModel):
    """网页注册请求"""
    username: str
    password: str
    nickname: Optional[str] = None


class WebLoginRequest(BaseModel):
    """网页登录请求"""
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    """更新资料请求 - 已修复：不需要token参数"""
    nickname: Optional[str] = None
    gender: Optional[str] = None
    avatar_url: Optional[str] = None
    # 旅行名片字段（可选）
    bio: Optional[str] = None
    budget_level: Optional[str] = None
    good_at_photo: Optional[str] = None
    accommodation_pref: Optional[str] = None
    driving: Optional[str] = None
    tags: Optional[str] = None
    mbti: Optional[str] = None
    zodiac: Optional[str] = None
    wechat_id: Optional[str] = None


# 名片选择字段的合法值（"" 表示清空）
PROFILE_FIELD_OPTIONS = {
    "budget_level": ["穷游", "经济", "舒适", "轻奢"],
    "good_at_photo": ["一般", "擅长", "大师"],
    "accommodation_pref": ["不限", "可拼房", "各住各的"],
    "driving": ["不会开车", "会开但尽量不开", "愿意当司机"],
    "mbti": ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
             "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"],
    "zodiac": ["白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
               "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座"],
}


def _profile_card_dict(user: User) -> dict:
    """用户旅行名片字段（对外展示用）"""
    return {
        "bio": getattr(user, "bio", None),
        "budget_level": getattr(user, "budget_level", None),
        "good_at_photo": getattr(user, "good_at_photo", None),
        "accommodation_pref": getattr(user, "accommodation_pref", None),
        "driving": getattr(user, "driving", None),
        "mbti": getattr(user, "mbti", None),
        "zodiac": getattr(user, "zodiac", None),
        "tags": [t for t in (getattr(user, "tags", None) or "").split(",") if t],
    }


class CommentCreateRequest(BaseModel):
    """发表留言请求"""
    content: str


class ExchangeCreateRequest(BaseModel):
    """发起交换微信申请"""
    companion_id: int
    to_user_id: int
    message: Optional[str] = None


class ExchangeHandleRequest(BaseModel):
    """处理交换申请：accept / reject"""
    action: str


class TeamApplyRequest(BaseModel):
    """申请加入队伍"""
    message: Optional[str] = None


class TeamHandleRequest(BaseModel):
    """队长处理入队申请：approve / reject"""
    member_id: int
    action: str


class TeamKickRequest(BaseModel):
    """队长踢人"""
    member_id: int


class FlightStatusRequest(BaseModel):
    """队员更新自己的机票状态: none/searching/booked"""
    flight_status: str


# ==================== API路由 ====================

@app.get("/")
async def root():
    return {
        "message": "找搭子小程序API",
        "version": "1.0.0",
        "endpoints": [
            "POST /api/auth/wx-login - 微信登录",
            "GET /api/auth/me - 获取当前用户",
            "POST /api/routes/generate - 生成路线",
            "POST /api/companions/publish - 发布找搭子",
            "POST /api/companions/match - 匹配搜索",
            "GET /api/companions/list - 获取所有发布",
            "GET /api/companions/my - 获取我的发布",
            "GET /api/companions/{id} - 获取行程详情",
        ]
    }


# ==================== 用户认证 ====================

@app.post("/api/auth/wx-login")
async def wx_login(req: WxLoginRequest):
    """微信小程序登录（code换token）"""
    session = wx_code2session(req.code)
    if not session:
        raise HTTPException(status_code=400, detail="微信登录失败，code无效")

    db = next(get_db())
    try:
        result = login_or_register(
            db,
            openid=session["openid"],
            union_id=session.get("unionid"),
            nickname=req.nickname,
            avatar_url=req.avatar_url,
            login_type="miniprogram"
        )
        return {"success": True, **result}
    finally:
        db.close()


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user_from_token)):
    """获取当前登录用户信息 - 已修复：从 Authorization header 获取 token"""
    return {
        "success": True,
        "user_id": current_user.id,
        "nickname": current_user.nickname,
        "avatar_url": current_user.avatar_url,
        "gender": current_user.gender,
        "wechat_id": getattr(current_user, "wechat_id", None),
        **_profile_card_dict(current_user)
    }


@app.post("/api/auth/register")
async def web_register(req: WebRegisterRequest):
    """网页版注册"""
    db = next(get_db())
    try:
        result = register_web(db, req.username, req.password, req.nickname)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.post("/api/auth/login")
async def web_login(req: WebLoginRequest):
    """网页版登录"""
    db = next(get_db())
    try:
        result = login_web(db, req.username, req.password)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.post("/api/auth/update-profile")
async def api_update_profile(req: UpdateProfileRequest, current_user: User = Depends(get_current_user_from_token)):
    """更新用户资料 - 已修复：从 Authorization header 获取 token"""
    db = next(get_db())
    try:
        # 🔒 安全修复：从鉴权中间件获取的 current_user 更新资料
        # current_user 来自已关闭的session，需在本session重新查询
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")

        if req.nickname:
            user.nickname = req.nickname
        if req.gender:
            user.gender = req.gender
        if req.avatar_url:
            user.avatar_url = req.avatar_url

        # 旅行名片：bio 过内容安全检测
        if req.bio is not None:
            bio = req.bio.strip()
            if len(bio) > 200:
                raise HTTPException(status_code=400, detail="自我介绍最多200字")
            if bio:
                check = msg_sec_check(bio, user.openid, scene=1)
                if not check["pass"]:
                    raise HTTPException(status_code=400, detail="自我介绍包含违规内容，请修改")
            user.bio = bio or None

        # 名片选择字段：校验合法值（传 "" 清空）
        for field, options in PROFILE_FIELD_OPTIONS.items():
            value = getattr(req, field)
            if value is not None:
                if value and value not in options:
                    raise HTTPException(status_code=400, detail=f"{field} 取值无效")
                setattr(user, field, value or None)

        if req.tags is not None:
            tag_list = [t.strip() for t in req.tags.split(",") if t.strip()]
            if len(tag_list) > 10:
                raise HTTPException(status_code=400, detail="标签最多10个")
            user.tags = ",".join(tag_list) or None

        # 微信号（私密字段，传 "" 清空）
        if req.wechat_id is not None:
            wechat = req.wechat_id.strip()
            if len(wechat) > 100:
                raise HTTPException(status_code=400, detail="微信号过长")
            user.wechat_id = wechat or None

        db.commit()
        db.refresh(user)

        return {
            "success": True,
            "user_id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "gender": user.gender,
            "wechat_id": getattr(user, "wechat_id", None),
            **_profile_card_dict(user)
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.post("/api/routes/generate")
@harness.api_guard  # Harness 守卫：自动计时 + 验证返回格式
async def generate_route(request: RouteGenerateRequest):
    """
    生成路线JSON
    支持三种模式：
    1. recommend: 基于月份和天数推荐
    2. destination: 基于目的地列表生成
    3. manual: 手动输入路线（标准化格式）
    """
    try:
        if request.mode == "recommend":
            if not request.travel_month or not request.duration_days:
                raise HTTPException(400, "推荐模式需要提供travel_month和duration_days")

            result = route_service.recommend_route(
                month=request.travel_month,
                days=request.duration_days,
                destinations=request.destinations or [],
                region=request.region,
                countries=request.countries,
                tags=request.tags,
                start_city=request.start_city,
                force_gateway_departure=request.force_gateway_departure,
                force_order=request.force_order,
                same_day_max_hours=request.same_day_max_hours,
                transport_preference=request.transport_preference,
                options_display_mode=request.options_display_mode
            )

        elif request.mode == "destination":
            if not request.cities:
                raise HTTPException(400, "目的地模式需要提供cities列表")

            result = route_service.generate_from_cities(
                cities=request.cities,
                force_gateway_departure=request.force_gateway_departure,
                force_order=request.force_order,
                same_day_max_hours=request.same_day_max_hours,
                start_node=request.start_node,
                end_node=request.end_node,
                region=request.region,
                transport_preference=request.transport_preference,
                options_display_mode=request.options_display_mode
            )

        elif request.mode == "manual":
            if not request.manual_route:
                raise HTTPException(400, "手动模式需要提供manual_route")
            if not request.region:
                raise HTTPException(400, "手动模式需要提供region（Europe/North_America/Asia/Oceania）")
            if not request.countries or len(request.countries) == 0:
                raise HTTPException(400, "手动模式需要选择至少一个国家")

            result = route_service.format_manual_route(
                route=request.manual_route,
                region=request.region,
                countries=request.countries
            )

        else:
            raise HTTPException(400, f"不支持的模式: {request.mode}")

        # Harness 传感器：自动验证路线结构和业务约束
        if isinstance(result, dict):
            route_issues = harness.validate_route_json(result)
            if route_issues:
                print(f"⚠️ Harness 路线验证 [{request.mode}]: {'; '.join(route_issues)}")

        return {
            "success": True,
            "route": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"路线生成失败: {str(e)}")


@app.post("/api/companions/publish")
@harness.api_guard  # Harness 守卫：自动计时 + 验证返回格式 + 异常捕获
async def publish_companion(request: CompanionPublishRequest, current_user: User = Depends(get_current_user_from_token)):
    """发布找搭子信息 - 已修复：从 token 获取 user_id"""
    # Harness 约束：发布前验证数据完整性
    publish_data = request.model_dump()
    issues = harness.validate_companion_data(publish_data)
    if issues:
        print(f"⚠️ Harness 数据验证: {issues}")

    db = next(get_db())

    try:
        from models import Companion

        # 🔒 安全修复：从 token 解析的 current_user 获取真实 user_id，不信任请求体
        # 🚀 性能优化：提取城市列表到独立字段，用于快速搜索
        cities_list = []
        if request.route_json and isinstance(request.route_json, dict):
            cities_list = request.route_json.get('cities', [])
        cities_str = ','.join(cities_list) if cities_list else ''

        # 创建发布记录
        companion = Companion(
            user_id=str(current_user.id),  # ✅ 从鉴权中间件获取，转字符串匹配列类型
            user_name=current_user.nickname or f"旅行者{current_user.id}",  # ✅ 从数据库获取
            route_json=json.dumps(request.route_json, ensure_ascii=False),
            cities=cities_str,  # ✅ 独立存储城市列表
            travel_date=datetime.strptime(request.travel_date, "%Y-%m-%d").date(),
            duration_days=request.duration_days,
            flexibility_days=request.flexibility_days,
            seeking=json.dumps(request.seeking, ensure_ascii=False),
            transport_mode=request.transport_mode,
            accommodation=request.accommodation,
            budget_level=request.budget_level,
            good_at_photo=request.good_at_photo,
            user_male_count=request.user_male_count,
            user_female_count=request.user_female_count,
            preferences=json.dumps(request.preferences or {}, ensure_ascii=False)
        )

        db.add(companion)

        # 兼容老版本客户端：发布时带的微信号存入用户私密字段（帖子上不再展示）
        wechat = (request.contact_wechat or '').strip()[:100]
        if wechat:
            publisher = db.query(User).filter(User.id == current_user.id).first()
            if publisher and not getattr(publisher, "wechat_id", None):
                publisher.wechat_id = wechat

        db.commit()
        db.refresh(companion)

        return {
            "success": True,
            "companion_id": companion.id,
            "message": "发布成功"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"发布失败: {str(e)}")


@app.post("/api/companions/match")
@harness.api_guard  # Harness 守卫
async def match_companions(request: CompanionMatchRequest):
    """匹配相似路线的搭子"""
    db = next(get_db())

    try:
        from models import Companion

        # 解析目标日期范围
        target_date = datetime.strptime(request.travel_date, "%Y-%m-%d").date()
        date_start = target_date - timedelta(days=request.time_flexibility_days)
        date_end = target_date + timedelta(days=request.time_flexibility_days)

        # 查询时间范围内的所有发布
        companions = db.query(Companion).filter(
            Companion.travel_date >= date_start,
            Companion.travel_date <= date_end
        ).all()

        # 计算匹配度
        matches = []
        for companion in companions:
            companion_route = json.loads(companion.route_json)

            # 性别匹配过滤（基于男女人数）
            seeking = json.loads(companion.seeking)
            seeking_gender = seeking.get("gender", "不限")

            # 计算用户的性别组成
            user_has_male = request.user_male_count > 0
            user_has_female = request.user_female_count > 0

            # 用户是否为情侣：正好一男一女
            user_is_couple = (request.user_male_count == 1 and request.user_female_count == 1)

            # 性别匹配逻辑：
            # 1. 对方要求"不限" → 任何组成都可以
            # 2. 对方要求"男" → 用户必须有男生（可以有女生）
            # 3. 对方要求"女" → 用户必须有女生（可以有男生）
            # 4. 对方要求"情侣" → 用户必须是一男一女
            if seeking_gender == "男":
                if not user_has_male:
                    continue  # 用户没有男生，不匹配
            elif seeking_gender == "女":
                if not user_has_female:
                    continue  # 用户没有女生，不匹配
            elif seeking_gender == "情侣":
                if not user_is_couple:
                    continue  # 用户不是一男一女，不匹配

            # ========== 用户的找搭子筛选条件（可选）==========

            # 1. 用户的找搭子人数要求
            if request.people_min is not None or request.people_max is not None:
                # 对方目前的人数
                companion_current = (getattr(companion, "user_male_count", 0) +
                                   getattr(companion, "user_female_count", 1))
                # 对方找的人数范围
                seeking_people_min = seeking.get("people_min", 1)
                seeking_people_max = seeking.get("people_max", 2)

                # 检查是否兼容：用户要找的人数 和 对方要找的人数 有交集
                user_min = request.people_min if request.people_min is not None else 1
                user_max = request.people_max if request.people_max is not None else 10

                # 人数范围无交集则跳过
                if user_max < seeking_people_min or user_min > seeking_people_max:
                    continue

            # 2. 用户的性别要求
            if request.gender and request.gender != "不限":
                # 对方的男女组成
                companion_male = getattr(companion, "user_male_count", 0)
                companion_female = getattr(companion, "user_female_count", 1)
                companion_has_male = companion_male > 0
                companion_has_female = companion_female > 0
                # 对方是否为情侣：正好一男一女
                companion_is_couple = (companion_male == 1 and companion_female == 1)

                # 用户要求"男" → 对方必须有男生
                if request.gender == "男":
                    if not companion_has_male:
                        continue
                # 用户要求"女" → 对方必须有女生
                elif request.gender == "女":
                    if not companion_has_female:
                        continue
                # 用户要求"情侣" → 对方必须是一男一女
                elif request.gender == "情侣":
                    if not companion_is_couple:
                        continue

            # 计算路线相似度
            similarity = match_service.calculate_route_similarity(
                request.route_json,
                companion_route
            )

            # ⭐ 关键：必须有城市重合才继续
            if similarity == 0:
                continue

            # ========== 精准筛选（硬性条件）==========

            # 1. 交通方式筛选（新规则）
            companion_transport = getattr(companion, "transport_mode", "不限")
            user_transport = request.transport_mode or "不限"

            # 定义交通方式兼容性
            def transport_compatible(t1, t2):
                if t1 == "不限" or t2 == "不限":
                    return True
                if t1 == "混合" or t2 == "混合":
                    return True
                return t1 == t2

            if not transport_compatible(user_transport, companion_transport):
                continue  # 交通方式不兼容，跳过

            # 2. 住宿安排筛选（新规则）
            companion_accom = getattr(companion, "accommodation", "不限")
            user_accom = request.accommodation or "不限"

            def accommodation_compatible(a1, a2):
                if a1 == "不限" or a2 == "不限":
                    return True
                if {a1, a2} == {"可拼房", "各住各的"}:
                    return False  # 利益冲突，无法凑一起
                return a1 == a2

            if not accommodation_compatible(user_accom, companion_accom):
                continue  # 住宿安排不兼容，跳过

            # 3. 消费水平筛选（必须有交集）
            companion_budget = getattr(companion, "budget_level", "经济")
            user_budgets = set(request.budget_level.split(',')) if request.budget_level else {"经济"}
            companion_budgets = set(companion_budget.split(',')) if ',' in companion_budget else {companion_budget}

            if not (user_budgets & companion_budgets):  # 无交集
                continue  # 消费水平无交集，跳过

            # ========== 计算分数（仅用于排序）==========
            # 计算时间契合度
            time_score = match_service.calculate_time_score(
                target_date,
                companion.travel_date,
                request.time_flexibility_days
            )

            # 计算偏好匹配度（仅用于排序，不做筛选）
            preference_score = match_service.calculate_preference_match(
                {
                    "transport_mode": companion_transport,
                    "accommodation": companion_accom,
                    "budget_level": companion_budget,
                    "good_at_photo": getattr(companion, "good_at_photo", "不限")
                },
                {
                    "transport_mode": request.transport_mode or "不限",
                    "accommodation": request.accommodation or "不限",
                    "budget_level": request.budget_level or "经济",
                    "good_at_photo": request.good_at_photo or "不限"
                }
            )

            # 综合分数：路线40% + 时间20% + 偏好40%（仅用于排序）
            total_score = similarity * 0.4 + time_score * 0.2 + preference_score * 0.4

            # 所有硬性条件已通过，加入结果
            if True:  # 改为始终通过（硬性条件已在前面筛选）
                matches.append({
                    "companion_id": companion.id,
                    "user_name": _get_display_name(db, companion.user_id, companion.user_name),
                    "route": companion_route,
                    "travel_date": companion.travel_date.strftime("%Y-%m-%d"),
                    "duration_days": companion.duration_days,
                    "seeking": json.loads(companion.seeking),
                    "preferences": json.loads(companion.preferences) if companion.preferences else {},
                    "transport_mode": getattr(companion, "transport_mode", "不限"),
                    "accommodation": getattr(companion, "accommodation", "不限"),
                    "budget_level": getattr(companion, "budget_level", "经济"),
                    "good_at_photo": getattr(companion, "good_at_photo", "不限"),
                    "user_male_count": getattr(companion, "user_male_count", 0),
                    "user_female_count": getattr(companion, "user_female_count", 1),
                    "current_people": f"{getattr(companion, 'user_male_count', 0)}男{getattr(companion, 'user_female_count', 1)}女",
                    "team": _team_brief(db, companion),
                    "match_score": round(total_score, 2),
                    "similarity_score": round(similarity, 2),
                    "time_score": round(time_score, 2),
                    "preference_score": round(preference_score, 2)
                })

        # 按匹配度排序
        matches.sort(key=lambda x: x["match_score"], reverse=True)

        return {
            "success": True,
            "count": len(matches),
            "matches": matches
        }

    except Exception as e:
        raise HTTPException(500, f"匹配失败: {str(e)}")


@app.get("/api/companions/search")
async def search_companions(keyword: str = "", limit: int = 20, offset: int = 0):
    """按目的地关键词搜索搭子 - 已优化：使用索引字段搜索"""
    if not keyword.strip():
        raise HTTPException(400, "请输入搜索关键词")

    db = next(get_db())
    try:
        from models import Companion

        # 🚀 性能优化：优先使用 cities 字段搜索（有索引），fallback 到 route_json
        companions = db.query(Companion).filter(
            Companion.cities.like(f"%{keyword}%")
        ).order_by(Companion.created_at.desc()).limit(limit).offset(offset).all()

        # 如果 cities 字段为空（旧数据），fallback 到 route_json 搜索
        if not companions:
            companions = db.query(Companion).filter(
                Companion.route_json.like(f"%{keyword}%")
            ).order_by(Companion.created_at.desc()).limit(limit).offset(offset).all()

        result = []
        for c in companions:
            # 从 User 表获取最新昵称
            display_name = _get_display_name(db, c.user_id, c.user_name)
            result.append({
                "companion_id": c.id,
                "user_name": display_name,
                "route": json.loads(c.route_json),
                "travel_date": c.travel_date.strftime("%Y-%m-%d"),
                "duration_days": c.duration_days,
                "seeking": json.loads(c.seeking),
                "transport_mode": getattr(c, "transport_mode", "不限"),
                "accommodation": getattr(c, "accommodation", "不限"),
                "budget_level": getattr(c, "budget_level", "经济"),
                "good_at_photo": getattr(c, "good_at_photo", "不限"),
                "user_male_count": getattr(c, "user_male_count", 0),
                "user_female_count": getattr(c, "user_female_count", 1),
                "current_people": f"{getattr(c, 'user_male_count', 0)}男{getattr(c, 'user_female_count', 1)}女",
                "team": _team_brief(db, c),
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M")
            })

        return {
            "success": True,
            "keyword": keyword,
            "count": len(result),
            "data": result
        }
    except Exception as e:
        raise HTTPException(500, f"搜索失败: {str(e)}")


@app.get("/api/companions/list")
async def list_companions(limit: int = 20, offset: int = 0):
    """获取所有发布列表"""
    db = next(get_db())

    try:
        from models import Companion

        companions = db.query(Companion)\
            .order_by(Companion.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()

        result = []
        for c in companions:
            # 从 User 表获取最新昵称
            display_name = _get_display_name(db, c.user_id, c.user_name)
            result.append({
                "companion_id": c.id,
                "user_name": display_name,
                "route": json.loads(c.route_json),
                "travel_date": c.travel_date.strftime("%Y-%m-%d"),
                "duration_days": c.duration_days,
                "seeking": json.loads(c.seeking),
                "transport_mode": getattr(c, "transport_mode", "不限"),
                "accommodation": getattr(c, "accommodation", "不限"),
                "budget_level": getattr(c, "budget_level", "经济"),
                "good_at_photo": getattr(c, "good_at_photo", "不限"),
                "user_male_count": getattr(c, "user_male_count", 0),
                "user_female_count": getattr(c, "user_female_count", 1),
                "current_people": f"{getattr(c, 'user_male_count', 0)}男{getattr(c, 'user_female_count', 1)}女",
                "team": _team_brief(db, c),
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M")
            })

        return {
            "success": True,
            "count": len(result),
            "data": result
        }

    except Exception as e:
        raise HTTPException(500, f"查询失败: {str(e)}")


@app.get("/api/companions/my")
async def get_my_companions(current_user: User = Depends(get_current_user_from_token), limit: int = 20, offset: int = 0):
    """获取当前用户发布的行程 - 已修复：从 token 获取 user_id"""
    db = next(get_db())

    try:
        from models import Companion

        # 🔒 安全修复：从鉴权中间件获取的 current_user 查询，不信任 query 参数
        # 使用 str() 确保类型匹配（user_id 是 String 列）
        companions = db.query(Companion)\
            .filter(Companion.user_id == str(current_user.id))\
            .order_by(Companion.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()

        result = []
        for c in companions:
            # 从 User 表获取最新昵称
            display_name = _get_display_name(db, c.user_id, c.user_name)
            result.append({
                "companion_id": c.id,
                "user_name": display_name,
                "route": json.loads(c.route_json),
                "travel_date": c.travel_date.strftime("%Y-%m-%d"),
                "duration_days": c.duration_days,
                "seeking": json.loads(c.seeking),
                "transport_mode": getattr(c, "transport_mode", "不限"),
                "accommodation": getattr(c, "accommodation", "不限"),
                "budget_level": getattr(c, "budget_level", "经济"),
                "good_at_photo": getattr(c, "good_at_photo", "不限"),
                "user_male_count": getattr(c, "user_male_count", 0),
                "user_female_count": getattr(c, "user_female_count", 1),
                "current_people": f"{getattr(c, 'user_male_count', 0)}男{getattr(c, 'user_female_count', 1)}女",
                "team": _team_brief(db, c),
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M")
            })

        return {
            "success": True,
            "count": len(result),
            "data": result
        }

    except Exception as e:
        raise HTTPException(500, f"查询失败: {str(e)}")


@app.get("/api/companions/{companion_id}")
async def get_companion_detail(companion_id: int, current_user: Optional[User] = Depends(get_optional_user)):
    """获取行程详情"""
    db = next(get_db())

    try:
        from models import Companion

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")

        # 从 User 表获取最新昵称
        display_name = _get_display_name(db, companion.user_id, companion.user_name)

        # 作者旅行名片（供详情页作者卡片渲染）
        author = None
        try:
            owner = db.query(User).filter(User.id == int(companion.user_id)).first()
            if owner:
                author = {
                    "user_id": owner.id,
                    "nickname": owner.nickname,
                    "avatar_url": owner.avatar_url,
                    **_profile_card_dict(owner)
                }
        except (ValueError, TypeError):
            pass

        return {
            "success": True,
            "data": {
                "companion_id": companion.id,
                "user_id": companion.user_id,
                "user_name": display_name,
                "author": author,
                "is_mine": current_user is not None and str(current_user.id) == str(companion.user_id),
                "route": json.loads(companion.route_json),
                "travel_date": companion.travel_date.strftime("%Y-%m-%d"),
                "duration_days": companion.duration_days,
                "flexibility_days": companion.flexibility_days,
                "seeking": json.loads(companion.seeking),
                "transport_mode": getattr(companion, "transport_mode", "不限"),
                "accommodation": getattr(companion, "accommodation", "不限"),
                "budget_level": getattr(companion, "budget_level", "经济"),
                "good_at_photo": getattr(companion, "good_at_photo", "不限"),
                "user_male_count": getattr(companion, "user_male_count", 0),
                "user_female_count": getattr(companion, "user_female_count", 1),
                "current_people": f"{getattr(companion, 'user_male_count', 0)}男{getattr(companion, 'user_female_count', 1)}女",
                "preferences": json.loads(companion.preferences) if companion.preferences else {},
                "view_count": getattr(companion, "view_count", 0) or 0,
                "like_count": getattr(companion, "like_count", 0) or 0,
                "liked_by_me": _liked_by_me(db, companion.id, current_user),
                "team": _team_payload(db, companion, current_user),
                "created_at": companion.created_at.strftime("%Y-%m-%d %H:%M")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"查询失败: {str(e)}")


@app.delete("/api/companions/{companion_id}")
async def delete_companion(companion_id: int, current_user: User = Depends(get_current_user_from_token)):
    """删除自己发布的行程"""
    db = next(get_db())
    try:
        from models import Companion

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")
        if str(companion.user_id) != str(current_user.id):
            raise HTTPException(403, "只能删除自己发布的行程")

        db.delete(companion)
        db.commit()
        return {"success": True, "message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"删除失败: {str(e)}")
    finally:
        db.close()


# ==================== 用户主页 ====================

@app.get("/api/users/{user_id}/profile")
async def get_user_profile(user_id: int):
    """用户公开主页：昵称/头像/性别/旅行名片/发布数（无需登录）"""
    db = next(get_db())
    try:
        from models import Companion

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "用户不存在")

        companion_count = db.query(Companion).filter(
            Companion.user_id == str(user.id)
        ).count()

        return {
            "success": True,
            "data": {
                "user_id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "gender": user.gender,
                "joined_at": user.created_at.strftime("%Y-%m") if user.created_at else None,
                "companion_count": companion_count,
                **_profile_card_dict(user)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"查询失败: {str(e)}")
    finally:
        db.close()


# ==================== 帖子留言 ====================

@app.get("/api/companions/{companion_id}/comments")
async def list_comments(companion_id: int, current_user: Optional[User] = Depends(get_optional_user)):
    """留言列表（公开），按时间正序，附带留言者最新昵称头像"""
    db = next(get_db())
    try:
        from models import Comment, Companion

        if not db.query(Companion).filter(Companion.id == companion_id).first():
            raise HTTPException(404, "行程不存在")

        comments = db.query(Comment).filter(
            Comment.companion_id == companion_id
        ).order_by(Comment.created_at.asc(), Comment.id.asc()).all()

        # 批量取留言者信息，避免 N+1
        uids = {int(c.user_id) for c in comments if str(c.user_id).isdigit()}
        users = {u.id: u for u in db.query(User).filter(User.id.in_(uids)).all()} if uids else {}

        items = []
        for c in comments:
            u = users.get(int(c.user_id)) if str(c.user_id).isdigit() else None
            items.append({
                "comment_id": c.id,
                "user_id": c.user_id,
                "nickname": u.nickname if u else "旅行者",
                "avatar_url": u.avatar_url if u else None,
                "content": c.content,
                "is_mine": current_user is not None and str(current_user.id) == str(c.user_id),
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
            })

        return {"success": True, "data": items, "total": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"查询失败: {str(e)}")
    finally:
        db.close()


@app.post("/api/companions/{companion_id}/comments")
async def create_comment(companion_id: int, req: CommentCreateRequest,
                         current_user: User = Depends(get_current_user_from_token)):
    """发表留言（需登录），内容过微信 msgSecCheck"""
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(400, "留言内容不能为空")
    if len(content) > 500:
        raise HTTPException(400, "留言最多500字")

    check = msg_sec_check(content, current_user.openid, scene=2)
    if not check["pass"]:
        raise HTTPException(400, "留言包含违规内容，请修改")

    db = next(get_db())
    try:
        from models import Comment, Companion

        if not db.query(Companion).filter(Companion.id == companion_id).first():
            raise HTTPException(404, "行程不存在")

        comment = Comment(
            companion_id=companion_id,
            user_id=str(current_user.id),
            content=content
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)

        return {
            "success": True,
            "data": {
                "comment_id": comment.id,
                "user_id": comment.user_id,
                "nickname": current_user.nickname,
                "avatar_url": current_user.avatar_url,
                "content": comment.content,
                "is_mine": True,
                "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M") if comment.created_at else ""
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"留言失败: {str(e)}")
    finally:
        db.close()


@app.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: int, current_user: User = Depends(get_current_user_from_token)):
    """删除自己的留言"""
    db = next(get_db())
    try:
        from models import Comment

        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            raise HTTPException(404, "留言不存在")
        if str(comment.user_id) != str(current_user.id):
            raise HTTPException(403, "只能删除自己的留言")

        db.delete(comment)
        db.commit()
        return {"success": True, "message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"删除失败: {str(e)}")
    finally:
        db.close()


# ==================== 交换微信 ====================

EXCHANGE_DAILY_LIMIT = 20          # 每人每天最多发起申请数
EXCHANGE_REJECT_COOLDOWN_DAYS = 7  # 被拒后对同一人冷却天数


def _exchange_dict(ex, db, me_id: int) -> dict:
    """交换申请的对外序列化；accepted 时附上对方微信号"""
    other_id = ex.to_user_id if ex.from_user_id == me_id else ex.from_user_id
    other = db.query(User).filter(User.id == other_id).first()
    item = {
        "exchange_id": ex.id,
        "companion_id": ex.companion_id,
        "from_user_id": ex.from_user_id,
        "to_user_id": ex.to_user_id,
        "is_sender": ex.from_user_id == me_id,
        "message": ex.message,
        "status": ex.status,
        "created_at": ex.created_at.strftime("%Y-%m-%d %H:%M") if ex.created_at else "",
        "other": None,
        "other_wechat_id": None,
    }
    if other:
        item["other"] = {
            "user_id": other.id,
            "nickname": other.nickname,
            "avatar_url": other.avatar_url,
            **_profile_card_dict(other)
        }
        if ex.status == "accepted":
            item["other_wechat_id"] = getattr(other, "wechat_id", None)
    return item


@app.post("/api/exchanges")
async def create_exchange(req: ExchangeCreateRequest, current_user: User = Depends(get_current_user_from_token)):
    """发起交换微信申请（帖主和留言者都可发起）"""
    db = next(get_db())
    try:
        from models import ContactExchange, Companion, Comment

        me = db.query(User).filter(User.id == current_user.id).first()
        if not me:
            raise HTTPException(401, "用户不存在")
        if not getattr(me, "wechat_id", None):
            raise HTTPException(400, "请先在「我的旅行名片」里填写你的微信号")
        if req.to_user_id == me.id:
            raise HTTPException(400, "不能和自己交换微信")

        target = db.query(User).filter(User.id == req.to_user_id).first()
        if not target:
            raise HTTPException(404, "对方用户不存在")

        companion = db.query(Companion).filter(Companion.id == req.companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")

        # 双方必须与该帖相关：帖主，或在帖下留过言
        def related(uid: int) -> bool:
            if str(companion.user_id) == str(uid):
                return True
            return db.query(Comment).filter(
                Comment.companion_id == companion.id,
                Comment.user_id == str(uid)
            ).first() is not None

        if not related(me.id) or not related(target.id):
            raise HTTPException(400, "请先在帖子下留言聊一聊，再申请交换微信")

        # 同一对用户同一帖子：已通过则不必重复；有待处理则不能重发
        existing = db.query(ContactExchange).filter(
            ContactExchange.companion_id == companion.id,
            ((ContactExchange.from_user_id == me.id) & (ContactExchange.to_user_id == target.id)) |
            ((ContactExchange.from_user_id == target.id) & (ContactExchange.to_user_id == me.id))
        ).order_by(ContactExchange.created_at.desc()).first()
        if existing:
            if existing.status == "accepted":
                raise HTTPException(400, "你们已经交换过微信了，去「我的搭子」查看")
            if existing.status == "pending":
                if existing.from_user_id == me.id:
                    raise HTTPException(400, "申请已发出，等待对方处理")
                raise HTTPException(400, "对方已向你发出申请，去「我的搭子」处理即可")
            # rejected：冷却期内不能再发
            if existing.from_user_id == me.id and existing.handled_at:
                cooldown_end = existing.handled_at + timedelta(days=EXCHANGE_REJECT_COOLDOWN_DAYS)
                if datetime.now() < cooldown_end:
                    raise HTTPException(400, f"对方暂未同意，{EXCHANGE_REJECT_COOLDOWN_DAYS}天后可再次申请")

        # 每日发起上限
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = db.query(ContactExchange).filter(
            ContactExchange.from_user_id == me.id,
            ContactExchange.created_at >= today_start
        ).count()
        if today_count >= EXCHANGE_DAILY_LIMIT:
            raise HTTPException(400, "今日申请次数已用完，明天再来吧")

        message = (req.message or "").strip()[:200]
        if message:
            check = msg_sec_check(message, me.openid, scene=2)
            if not check["pass"]:
                raise HTTPException(400, "附言包含违规内容，请修改")

        ex = ContactExchange(
            companion_id=companion.id,
            from_user_id=me.id,
            to_user_id=target.id,
            message=message or None,
            status="pending"
        )
        db.add(ex)
        db.commit()
        db.refresh(ex)
        return {"success": True, "data": _exchange_dict(ex, db, me.id)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"申请失败: {str(e)}")
    finally:
        db.close()


@app.post("/api/exchanges/{exchange_id}/handle")
async def handle_exchange(exchange_id: int, req: ExchangeHandleRequest,
                          current_user: User = Depends(get_current_user_from_token)):
    """同意/拒绝交换申请（仅接收方）；同意后双方互见微信号"""
    if req.action not in ("accept", "reject"):
        raise HTTPException(400, "action 必须是 accept 或 reject")
    db = next(get_db())
    try:
        from models import ContactExchange

        ex = db.query(ContactExchange).filter(ContactExchange.id == exchange_id).first()
        if not ex:
            raise HTTPException(404, "申请不存在")
        if ex.to_user_id != current_user.id:
            raise HTTPException(403, "只能处理发给你的申请")
        if ex.status != "pending":
            raise HTTPException(400, "该申请已处理过")

        if req.action == "accept":
            me = db.query(User).filter(User.id == current_user.id).first()
            if not getattr(me, "wechat_id", None):
                raise HTTPException(400, "请先在「我的旅行名片」里填写你的微信号，再同意交换")

        ex.status = "accepted" if req.action == "accept" else "rejected"
        ex.handled_at = datetime.now()
        db.commit()
        db.refresh(ex)
        return {"success": True, "data": _exchange_dict(ex, db, current_user.id)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"处理失败: {str(e)}")
    finally:
        db.close()


@app.get("/api/exchanges/my")
async def list_my_exchanges(current_user: User = Depends(get_current_user_from_token)):
    """我的交换列表：收到的待处理 / 我发出的 / 已交换成功"""
    db = next(get_db())
    try:
        from models import ContactExchange

        rows = db.query(ContactExchange).filter(
            (ContactExchange.from_user_id == current_user.id) |
            (ContactExchange.to_user_id == current_user.id)
        ).order_by(ContactExchange.created_at.desc()).limit(100).all()

        received, sent, accepted = [], [], []
        for ex in rows:
            item = _exchange_dict(ex, db, current_user.id)
            if ex.status == "accepted":
                accepted.append(item)
            elif ex.to_user_id == current_user.id and ex.status == "pending":
                received.append(item)
            elif ex.from_user_id == current_user.id:
                sent.append(item)
        return {"success": True, "received": received, "sent": sent, "accepted": accepted}
    except Exception as e:
        raise HTTPException(500, f"查询失败: {str(e)}")
    finally:
        db.close()


@app.get("/api/exchanges/status")
async def get_exchange_status(companion_id: int, other_user_id: int,
                              current_user: User = Depends(get_current_user_from_token)):
    """查询当前用户与某人在某帖下的交换状态（前端按钮态用）"""
    db = next(get_db())
    try:
        from models import ContactExchange

        ex = db.query(ContactExchange).filter(
            ContactExchange.companion_id == companion_id,
            ((ContactExchange.from_user_id == current_user.id) & (ContactExchange.to_user_id == other_user_id)) |
            ((ContactExchange.from_user_id == other_user_id) & (ContactExchange.to_user_id == current_user.id))
        ).order_by(ContactExchange.created_at.desc()).first()

        if not ex:
            return {"success": True, "status": "none", "data": None}
        return {"success": True, "status": ex.status, "data": _exchange_dict(ex, db, current_user.id)}
    except Exception as e:
        raise HTTPException(500, f"查询失败: {str(e)}")
    finally:
        db.close()


# ==================== 组队 / 社交化 ====================

FLIGHT_STATUS_VALUES = {"none", "searching", "booked"}


def _liked_by_me(db, companion_id, viewer):
    """当前用户是否已点赞该帖。"""
    if viewer is None:
        return False
    from models import CompanionLike
    return db.query(CompanionLike).filter(
        CompanionLike.companion_id == companion_id,
        CompanionLike.user_id == viewer.id,
    ).first() is not None


def _ensure_leader(db, companion):
    """确保帖主有一条 leader 成员记录（老帖兼容兜底）。返回 leader 记录。"""
    from models import TeamMember
    try:
        leader_uid = int(companion.user_id)
    except (ValueError, TypeError):
        return None
    leader = db.query(TeamMember).filter(
        TeamMember.companion_id == companion.id,
        TeamMember.user_id == leader_uid,
    ).first()
    if not leader:
        leader = TeamMember(
            companion_id=companion.id, user_id=leader_uid,
            role="leader", status="approved", flight_status="none",
        )
        db.add(leader)
        db.flush()
    return leader


def _team_size(db, companion):
    """队伍目标总人数（含队长）。优先用已存的 team_size，否则按 seeking.people_max+1。"""
    ts = getattr(companion, "team_size", None)
    if ts:
        return ts
    try:
        seeking = json.loads(companion.seeking) if companion.seeking else {}
        return int(seeking.get("people_max", 1) or 1) + 1
    except (ValueError, TypeError, json.JSONDecodeError):
        return 2


def _approved_count(db, companion_id):
    from models import TeamMember
    return db.query(TeamMember).filter(
        TeamMember.companion_id == companion_id,
        TeamMember.status == "approved",
    ).count()


def _refresh_team_status(db, companion):
    """根据已批准人数刷新 team_status（closed 不在此自动改回）。"""
    if getattr(companion, "team_status", None) == "closed":
        return companion.team_status
    size = _team_size(db, companion)
    approved = _approved_count(db, companion.id)
    companion.team_status = "full" if approved >= size else "recruiting"
    if getattr(companion, "team_size", None) is None:
        companion.team_size = size
    return companion.team_status


def _member_dict(db, m, viewer_id, leader_id, can_see_wechat):
    """成员对外序列化。can_see_wechat 控制是否附微信号。"""
    u = db.query(User).filter(User.id == m.user_id).first()
    item = {
        "member_id": m.id,
        "user_id": m.user_id,
        "role": m.role,
        "status": m.status,
        "flight_status": m.flight_status or "none",
        "message": m.message,
        "is_me": viewer_id is not None and int(viewer_id) == int(m.user_id),
        "nickname": u.nickname if u else None,
        "avatar_url": u.avatar_url if u else None,
        "wechat_id": None,
    }
    if u:
        item.update(_profile_card_dict(u))
        if can_see_wechat:
            item["wechat_id"] = getattr(u, "wechat_id", None)
    return item


def _team_payload(db, companion, viewer):
    """组装某帖的组队信息（详情页用）。"""
    from models import TeamMember
    _ensure_leader(db, companion)
    db.flush()
    size = _team_size(db, companion)
    status = _refresh_team_status(db, companion)
    db.commit()

    leader_id = None
    try:
        leader_id = int(companion.user_id)
    except (ValueError, TypeError):
        pass
    viewer_id = viewer.id if viewer else None
    is_leader = viewer_id is not None and leader_id is not None and int(viewer_id) == leader_id

    approved_members = db.query(TeamMember).filter(
        TeamMember.companion_id == companion.id,
        TeamMember.status == "approved",
    ).order_by(TeamMember.role.desc(), TeamMember.created_at.asc()).all()

    # 我（如果是已批准成员）能看队内所有人微信；队长能看全部
    viewer_approved = viewer_id is not None and any(
        int(m.user_id) == int(viewer_id) for m in approved_members
    )
    members = [
        _member_dict(db, m, viewer_id, leader_id, can_see_wechat=(viewer_approved or is_leader))
        for m in approved_members
    ]

    # 待审批申请（仅队长可见）
    pending = []
    if is_leader:
        pend_rows = db.query(TeamMember).filter(
            TeamMember.companion_id == companion.id,
            TeamMember.status == "pending",
        ).order_by(TeamMember.created_at.asc()).all()
        pending = [_member_dict(db, m, viewer_id, leader_id, can_see_wechat=False) for m in pend_rows]

    # 我的成员记录（用于前端按钮态）
    my_member = None
    if viewer_id is not None:
        mine = db.query(TeamMember).filter(
            TeamMember.companion_id == companion.id,
            TeamMember.user_id == int(viewer_id),
        ).order_by(TeamMember.created_at.desc()).first()
        if mine:
            my_member = {
                "member_id": mine.id,
                "role": mine.role,
                "status": mine.status,
                "flight_status": mine.flight_status or "none",
            }

    approved_count = len(members)
    return {
        "team_size": size,
        "team_status": status,
        "joined_count": approved_count,
        "open_slots": max(0, size - approved_count),
        "is_leader": is_leader,
        "members": members,
        "pending": pending,
        "pending_count": len(pending),
        "my_member": my_member,
    }


def _team_brief(db, companion):
    """列表卡用的精简组队信息。"""
    _ensure_leader(db, companion)
    size = _team_size(db, companion)
    status = _refresh_team_status(db, companion)
    db.commit()
    joined = _approved_count(db, companion.id)
    return {
        "team_size": size,
        "team_status": status,
        "joined_count": joined,
        "open_slots": max(0, size - joined),
        "view_count": getattr(companion, "view_count", 0) or 0,
        "like_count": getattr(companion, "like_count", 0) or 0,
    }


@app.get("/api/companions/{companion_id}/team")
async def get_team(companion_id: int, current_user: Optional[User] = Depends(get_optional_user)):
    """获取某帖的组队信息（成员墙 / 待审批 / 我的状态）"""
    db = next(get_db())
    try:
        from models import Companion
        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")
        return {"success": True, "data": _team_payload(db, companion, current_user)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"查询失败: {str(e)}")
    finally:
        db.close()


@app.post("/api/companions/{companion_id}/team/apply")
async def apply_team(companion_id: int, req: TeamApplyRequest,
                     current_user: User = Depends(get_current_user_from_token)):
    """申请加入队伍（需先在帖下留言，且填了自己微信号）"""
    db = next(get_db())
    try:
        from models import Companion, Comment, TeamMember

        me = db.query(User).filter(User.id == current_user.id).first()
        if not me:
            raise HTTPException(401, "用户不存在")
        if not getattr(me, "wechat_id", None):
            raise HTTPException(400, "请先在「我的旅行名片」里填写你的微信号，通过后队长才能联系你")

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")
        if str(companion.user_id) == str(me.id):
            raise HTTPException(400, "你是队长，无需申请加入自己的队伍")

        _ensure_leader(db, companion)

        # 满员 / 已关闭不可申请
        status = _refresh_team_status(db, companion)
        if status == "closed":
            raise HTTPException(400, "该队伍已关闭招募")
        if status == "full":
            raise HTTPException(400, "队伍已满员")

        # 先在帖下留过言才能申请（落实「先聊一聊再组队」）
        commented = db.query(Comment).filter(
            Comment.companion_id == companion.id,
            Comment.user_id == str(me.id),
        ).first()
        if not commented:
            raise HTTPException(400, "请先在帖子下留言聊一聊，再申请加入队伍")

        # 已有记录处理
        existing = db.query(TeamMember).filter(
            TeamMember.companion_id == companion.id,
            TeamMember.user_id == me.id,
        ).order_by(TeamMember.created_at.desc()).first()
        if existing:
            if existing.status == "approved":
                raise HTTPException(400, "你已在队伍中")
            if existing.status == "pending":
                raise HTTPException(400, "申请已提交，等待队长同意")
            # rejected / removed / quit：允许重新申请（复用同一条记录）
            existing.status = "pending"
            existing.message = (req.message or "").strip()[:200] or None
            existing.handled_at = None
            existing.created_at = datetime.now()
            db.commit()
            db.refresh(existing)
            return {"success": True, "message": "申请已提交", "member_id": existing.id}

        message = (req.message or "").strip()[:200]
        if message:
            check = msg_sec_check(message, me.openid, scene=2)
            if not check["pass"]:
                raise HTTPException(400, "附言包含违规内容，请修改")

        m = TeamMember(
            companion_id=companion.id, user_id=me.id,
            role="member", status="pending",
            flight_status="none", message=message or None,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return {"success": True, "message": "申请已提交，等待队长同意", "member_id": m.id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"申请失败: {str(e)}")
    finally:
        db.close()


@app.post("/api/companions/{companion_id}/team/handle")
async def handle_team(companion_id: int, req: TeamHandleRequest,
                      current_user: User = Depends(get_current_user_from_token)):
    """队长同意 / 拒绝入队申请（同意=占位+双方微信互见+满员检测）"""
    if req.action not in ("approve", "reject"):
        raise HTTPException(400, "action 必须是 approve 或 reject")
    db = next(get_db())
    try:
        from models import Companion, TeamMember

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")
        if str(companion.user_id) != str(current_user.id):
            raise HTTPException(403, "只有队长可以处理申请")

        m = db.query(TeamMember).filter(
            TeamMember.id == req.member_id,
            TeamMember.companion_id == companion.id,
        ).first()
        if not m:
            raise HTTPException(404, "申请不存在")
        if m.status != "pending":
            raise HTTPException(400, "该申请已处理")

        if req.action == "reject":
            m.status = "rejected"
            m.handled_at = datetime.now()
            db.commit()
            return {"success": True, "message": "已拒绝"}

        # approve：满员校验 -> 占位
        _ensure_leader(db, companion)
        size = _team_size(db, companion)
        if _approved_count(db, companion.id) >= size:
            raise HTTPException(400, "队伍已满员，无法再同意")

        m.status = "approved"
        m.handled_at = datetime.now()
        db.flush()

        # 同意即解锁微信：双方互见 -> 复用 ContactExchange(accepted)
        _grant_mutual_wechat(db, companion.id, int(companion.user_id), int(m.user_id))

        _refresh_team_status(db, companion)
        db.commit()
        return {"success": True, "message": "已同意，微信已互相解锁",
                "team_status": companion.team_status}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"处理失败: {str(e)}")
    finally:
        db.close()


def _grant_mutual_wechat(db, companion_id, leader_id, member_id):
    """在队长与成员间写一条 accepted 的 ContactExchange（幂等），实现微信互见。"""
    from models import ContactExchange
    ex = db.query(ContactExchange).filter(
        ContactExchange.companion_id == companion_id,
        ((ContactExchange.from_user_id == leader_id) & (ContactExchange.to_user_id == member_id)) |
        ((ContactExchange.from_user_id == member_id) & (ContactExchange.to_user_id == leader_id))
    ).order_by(ContactExchange.created_at.desc()).first()
    if ex:
        if ex.status != "accepted":
            ex.status = "accepted"
            ex.handled_at = datetime.now()
    else:
        ex = ContactExchange(
            companion_id=companion_id, from_user_id=member_id,
            to_user_id=leader_id, message="组队入队自动解锁", status="accepted",
            handled_at=datetime.now(),
        )
        db.add(ex)


@app.post("/api/companions/{companion_id}/team/kick")
async def kick_team(companion_id: int, req: TeamKickRequest,
                    current_user: User = Depends(get_current_user_from_token)):
    """队长踢人（释放名额，满员自动转回招募中）"""
    db = next(get_db())
    try:
        from models import Companion, TeamMember

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")
        if str(companion.user_id) != str(current_user.id):
            raise HTTPException(403, "只有队长可以移出队员")

        m = db.query(TeamMember).filter(
            TeamMember.id == req.member_id,
            TeamMember.companion_id == companion.id,
        ).first()
        if not m:
            raise HTTPException(404, "队员不存在")
        if m.role == "leader":
            raise HTTPException(400, "不能移出队长")
        if m.status != "approved":
            raise HTTPException(400, "该用户不是已入队成员")

        m.status = "removed"
        m.handled_at = datetime.now()
        db.flush()
        _refresh_team_status(db, companion)
        db.commit()
        return {"success": True, "message": "已移出该队员", "team_status": companion.team_status}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"操作失败: {str(e)}")
    finally:
        db.close()


@app.post("/api/companions/{companion_id}/flight-status")
async def update_flight_status(companion_id: int, req: FlightStatusRequest,
                               current_user: User = Depends(get_current_user_from_token)):
    """队员更新自己的机票状态（只能改自己的；随时可进可退）"""
    if req.flight_status not in FLIGHT_STATUS_VALUES:
        raise HTTPException(400, "机票状态无效")
    db = next(get_db())
    try:
        from models import Companion, TeamMember

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")
        _ensure_leader(db, companion)
        db.flush()

        m = db.query(TeamMember).filter(
            TeamMember.companion_id == companion.id,
            TeamMember.user_id == current_user.id,
            TeamMember.status == "approved",
        ).first()
        if not m:
            raise HTTPException(403, "只有已入队成员可以更新机票状态")

        m.flight_status = req.flight_status
        db.commit()
        return {"success": True, "flight_status": m.flight_status}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"更新失败: {str(e)}")
    finally:
        db.close()


@app.post("/api/companions/{companion_id}/view")
async def add_view(companion_id: int, current_user: Optional[User] = Depends(get_optional_user)):
    """浏览 +1（仅登录用户、同人去重；匿名不计数避免刷量）"""
    db = next(get_db())
    try:
        from models import Companion, CompanionView

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")

        if current_user is not None:
            seen = db.query(CompanionView).filter(
                CompanionView.companion_id == companion_id,
                CompanionView.user_id == current_user.id,
            ).first()
            if not seen:
                db.add(CompanionView(companion_id=companion_id, user_id=current_user.id))
                companion.view_count = (getattr(companion, "view_count", 0) or 0) + 1
                db.commit()
        return {"success": True, "view_count": getattr(companion, "view_count", 0) or 0}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"操作失败: {str(e)}")
    finally:
        db.close()


@app.post("/api/companions/{companion_id}/like")
async def toggle_like(companion_id: int, current_user: User = Depends(get_current_user_from_token)):
    """点赞 / 取消点赞（登录用户，唯一约束防刷）"""
    db = next(get_db())
    try:
        from models import Companion, CompanionLike

        companion = db.query(Companion).filter(Companion.id == companion_id).first()
        if not companion:
            raise HTTPException(404, "行程不存在")

        existing = db.query(CompanionLike).filter(
            CompanionLike.companion_id == companion_id,
            CompanionLike.user_id == current_user.id,
        ).first()
        if existing:
            db.delete(existing)
            companion.like_count = max(0, (getattr(companion, "like_count", 0) or 0) - 1)
            liked = False
        else:
            db.add(CompanionLike(companion_id=companion_id, user_id=current_user.id))
            companion.like_count = (getattr(companion, "like_count", 0) or 0) + 1
            liked = True
        db.commit()
        return {"success": True, "liked": liked, "like_count": companion.like_count}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"操作失败: {str(e)}")
    finally:
        db.close()


@app.get("/api/destinations/popular")
async def get_popular_destinations(region: Optional[str] = None):
    """
    获取热门目的地城市列表
    ?region=欧洲 - 返回指定区域的城市
    无参数 - 返回所有区域
    """
    try:
        popular_data = route_service.get_popular_destinations(region)

        return {
            "success": True,
            **popular_data
        }
    except Exception as e:
        raise HTTPException(500, f"获取失败: {str(e)}")


@app.get("/api/destinations/search")
async def search_destinations(q: str = ""):
    """搜索目的地联想（国家+城市）"""
    try:
        suggestions = route_service.search_destinations(q)

        return {
            "success": True,
            # results 保留纯城市名数组，兼容旧版客户端
            "results": [s["name"] for s in suggestions if s["type"] == "city"],
            "suggestions": suggestions
        }
    except Exception as e:
        raise HTTPException(500, f"搜索失败: {str(e)}")


@app.get("/api/attractions/playbook")
async def get_attraction_playbook(name: str):
    """景点玩法 / 城市攻略详情（玩法页用）。

    富渲染所需的图片在这里挂：
    - 景点页（type=attraction）：hero 大图 + gallery 图集（按景点本名精确取图）
    - 城市页（type=city）：交通图 URL + 给 attractions 目录每项挂缩略图 + hero
    旧字段 sections/summary 原样保留，前端按 type 决定富渲染或回退。
    """
    from services.playbook_service import get_playbook_index
    from services.image_service import get_image_index
    playbook = get_playbook_index().get(name)
    if not playbook:
        raise HTTPException(404, "暂无该景点的玩法攻略")

    pb = dict(playbook)  # 浅拷贝，不改内存里的原始数据
    img = get_image_index()
    ptype = pb.get("type")

    if ptype == "city":
        # 城市页：交通图 + 景点目录缩略图 + hero（取第一个有图的景点作封面）
        tm = pb.get("transport_map")
        if tm:
            pb["transport_map_url"] = f"/api/static/maps/{tm}"
        hero = None
        attractions = []
        for a in pb.get("attractions", []):
            a = dict(a)
            # 优先用 image_alias（城市页景点名常带英文后缀/+号，与图库名对不上时显式映射）
            first = img.first_image(a.get("image_alias") or a["name"])
            if not first:
                # 无图景点不返回，避免城市页渲染灰块卡（铁律：不可以没有图）
                continue
            a["thumb"] = first["url"]
            if hero is None:
                hero = first["url"]
            attractions.append(a)
        if attractions:
            pb["attractions"] = attractions
        # hero 优先用城市同名首图，否则用第一个有图景点
        city_hero = img.first_image(pb.get("city", "")) or img.first_image(name)
        pb["hero"] = (city_hero["url"] if city_hero else hero)
    else:
        # 景点页：hero + gallery
        pics = img.images_for(name, limit=6)
        if pics:
            pb["hero"] = pics[0]["url"]
            pb["gallery"] = pics

    return {"success": True, "playbook": pb}


@app.get("/api/attractions/search")
async def search_attractions(q: str, limit: int = 30):
    """攻略搜索：按 名称/别名/城市/国家 匹配，返回命中列表（带缩略图）。
    前端搜索框用：输入地名 → 命中卡片 → 点卡片跳详情页。"""
    from services.playbook_service import get_playbook_index
    from services.image_service import get_image_index
    results = get_playbook_index().search(q, limit=limit)
    img = get_image_index()
    for r in results:
        first = img.first_image(r["name"])
        r["thumb"] = first["url"] if first else None
    return {"success": True, "query": q, "count": len(results), "results": results}


@app.get("/api/destinations/structure")
async def get_destination_structure():
    """获取完整的目的地结构（区域→国家→城市）"""
    try:
        structure = route_service.get_destination_structure()

        return {
            "success": True,
            "structure": structure
        }
    except Exception as e:
        raise HTTPException(500, f"获取失败: {str(e)}")


@app.get("/api/destinations/countries")
async def get_countries(region: str):
    """获取指定区域下的所有国家"""
    try:
        countries = route_service.get_countries_by_region(region)

        return {
            "success": True,
            "region": region,
            "countries": countries
        }
    except Exception as e:
        raise HTTPException(500, f"获取失败: {str(e)}")


@app.get("/api/destinations/cities")
async def get_cities(region: str, country: str, limit: int = 16):
    """获取指定国家下的城市/目的地"""
    try:
        cities = route_service.get_cities_by_country(region, country, limit)

        return {
            "success": True,
            "region": region,
            "country": country,
            "cities": cities
        }
    except Exception as e:
        raise HTTPException(500, f"获取失败: {str(e)}")


# ==================== 会员接口 ====================
from services.permission_service import get_tier_status, ENABLE_MEMBERSHIP, TIERS, FEATURES


class MembershipBuyRequest(BaseModel):
    user_id: str
    tier: str        # basic / vip
    period: str      # quarterly / yearly
    with_guide: bool = False  # 是否加购攻略


@app.get("/api/membership/status")
async def get_membership_status(current_user: User = Depends(get_current_user_from_token)):
    """查询用户会员状态 - 已修复：从 token 获取 user_id"""
    status = get_tier_status(str(current_user.id))
    return {"success": True, **status}


@app.get("/api/tiers")
async def get_tiers():
    """获取所有会员等级和价格（前端渲染定价页用）"""
    return {"success": True, "tiers": TIERS, "features": FEATURES}


@app.post("/api/membership/buy")
async def buy_membership(request: MembershipBuyRequest, current_user: User = Depends(get_current_user_from_token)):
    """购买/升级会员 - 已修复：从 token 获取 user_id，需接入真实支付"""
    # 无支付校验，会员体系上线前整体关闭，防止免费拿VIP
    if not ENABLE_MEMBERSHIP:
        raise HTTPException(403, "会员功能暂未开放")
    if request.tier not in ["basic", "vip"]:
        raise HTTPException(400, "无效的会员等级")
    if request.period not in ["quarterly", "yearly"]:
        raise HTTPException(400, "无效的付费周期")

    tier_info = TIERS[request.tier]
    base_price = tier_info["price_quarterly"] if request.period == "quarterly" else tier_info["price_yearly"]
    guide_addon = tier_info["guide_addon_quarterly"] if request.period == "quarterly" else tier_info["guide_addon_yearly"]
    total_price = base_price + (guide_addon if request.with_guide else 0)

    months = 3 if request.period == "quarterly" else 12
    expired_at = datetime.now() + timedelta(days=months * 30)

    db = next(get_db())
    try:
        from models import UserMembership
        # 🔒 安全修复：从 current_user 获取真实 user_id
        membership = db.query(UserMembership).filter(
            UserMembership.user_id == current_user.id
        ).first()

        if membership:
            membership.tier = request.tier
            membership.guide_used = 0
            membership.publish_used = 0
            membership.expired_at = expired_at
        else:
            membership = UserMembership(
                user_id=current_user.id,  # ✅ 从鉴权获取
                tier=request.tier,
                guide_used=0,
                publish_used=0,
                expired_at=expired_at,
            )
            db.add(membership)

        db.commit()
        return {
            "success": True,
            "message": f"开通成功，到期时间：{expired_at.strftime('%Y-%m-%d')}",
            "price": total_price,
            "tier": request.tier,
            "tier_name": tier_info["name"],
            "expired_at": expired_at.isoformat(),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"开通失败: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    print("🚀 启动找搭子小程序后端...")
    print("📍 访问: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("🔧 Harness: http://localhost:8000/api/harness/health")
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ==================== Harness 健康检查 ====================

@app.get("/api/harness/health")
async def harness_health():
    """Harness 系统健康检查（开发/调试用）"""
    return harness.get_health_report()


@app.get("/api/harness/metrics")
async def harness_metrics():
    """Harness 指标面板"""
    return {
        "harness_version": "1.0.0",
        "metrics": harness.get_metrics_summary(),
        "total_violations": len(harness._violations),
        "total_errors": len(harness._errors),
    }
