"""数据库模型"""

from sqlalchemy import Column, Integer, String, Text, Date, DateTime
from sqlalchemy.sql import func
from database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    openid = Column(String(100), unique=True, nullable=False, index=True, comment="微信openid")
    union_id = Column(String(100), nullable=True, index=True, comment="微信union_id（跨平台）")
    username = Column(String(50), nullable=True, unique=True, index=True, comment="网页版用户名")
    password_hash = Column(String(128), nullable=True, comment="网页版密码哈希")
    nickname = Column(String(50), nullable=True, comment="昵称")
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    gender = Column(String(10), nullable=True, comment="性别")
    login_type = Column(String(20), default="miniprogram", comment="登录方式: miniprogram/web")

    # 旅行名片（全部可选，发帖时作为默认值预填）
    bio = Column(String(200), nullable=True, comment="一句话自我介绍")
    budget_level = Column(String(20), nullable=True, comment="消费习惯：穷游/经济/舒适/轻奢")
    good_at_photo = Column(String(10), nullable=True, comment="拍照技能：一般/擅长/大师")
    accommodation_pref = Column(String(20), nullable=True, comment="住宿偏好：不限/可拼房/各住各的")
    driving = Column(String(20), nullable=True, comment="驾驶：不会开车/会开但尽量不开/愿意当司机")
    tags = Column(String(300), nullable=True, comment="兴趣标签（逗号分隔）：早起党/夜猫子/美食控等")
    wechat_id = Column(String(100), nullable=True, comment="微信号（私密，仅交换成功的对方可见）")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User {self.id}: {self.nickname}>"


class Companion(Base):
    """找搭子发布表"""
    __tablename__ = "companions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, index=True, comment="用户ID")
    user_name = Column(String(50), nullable=False, comment="用户昵称")

    # 路线信息（JSON存储）
    route_json = Column(Text, nullable=False, comment="完整路线JSON")

    # 🚀 性能优化：独立存储城市列表，用于快速搜索
    cities = Column(String(500), nullable=True, index=True, comment="城市列表（逗号分隔），用于搜索优化")

    # 时间信息
    travel_date = Column(Date, nullable=False, index=True, comment="出发日期")
    duration_days = Column(Integer, nullable=False, comment="行程天数")
    flexibility_days = Column(Integer, default=3, comment="时间灵活度（天）")

    # 找搭子需求（JSON存储）
    seeking = Column(Text, nullable=False, comment="找搭子需求：人数范围/性别/年龄")

    # 出行偏好（必填）
    transport_mode = Column(String(50), nullable=True, comment="交通方式：不限/公共交通为主/自驾为主/混合")
    accommodation = Column(String(50), nullable=True, comment="住宿安排：不限/可拼房/各住各的")
    budget_level = Column(String(100), nullable=True, comment="消费水平（多选，逗号分隔）：穷游/经济/舒适/轻奢")

    # 个人信息
    good_at_photo = Column(String(10), nullable=True, comment="拍照技能：一般/擅长/大师")
    user_male_count = Column(Integer, nullable=True, comment="男生人数")
    user_female_count = Column(Integer, nullable=True, comment="女生人数")
    contact_wechat = Column(String(100), nullable=True, comment="联系方式（微信号），登录后在详情页可见")

    # 其他偏好（JSON存储，可选）
    preferences = Column(Text, nullable=True, comment="其他偏好")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<Companion {self.id}: {self.user_name} - {self.travel_date}>"


class Comment(Base):
    """帖子留言表"""
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    companion_id = Column(Integer, nullable=False, index=True, comment="所属搭子帖ID")
    user_id = Column(String(50), nullable=False, index=True, comment="留言用户ID")
    content = Column(String(500), nullable=False, comment="留言内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<Comment {self.id} on companion {self.companion_id}>"


class ContactExchange(Base):
    """交换微信申请表（双向：帖主和留言者都可发起）"""
    __tablename__ = "contact_exchanges"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    companion_id = Column(Integer, nullable=False, index=True, comment="关联的搭子帖ID")
    from_user_id = Column(Integer, nullable=False, index=True, comment="发起方用户ID")
    to_user_id = Column(Integer, nullable=False, index=True, comment="接收方用户ID")
    message = Column(String(200), nullable=True, comment="申请附言")
    status = Column(String(20), default="pending", index=True, comment="状态: pending/accepted/rejected")
    created_at = Column(DateTime, server_default=func.now(), comment="发起时间")
    handled_at = Column(DateTime, nullable=True, comment="处理时间")

    def __repr__(self):
        return f"<ContactExchange {self.id}: {self.from_user_id}->{self.to_user_id} {self.status}>"


class UserMembership(Base):
    """用户会员表"""
    __tablename__ = "user_memberships"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True, comment="用户ID")
    tier = Column(String(20), default="free", comment="会员等级: free/basic/vip")
    guide_used = Column(Integer, default=0, comment="AI攻略已用次数")
    publish_used = Column(Integer, default=0, comment="发布已用次数")
    expired_at = Column(DateTime, nullable=True, comment="到期时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<UserMembership {self.user_id}: {self.tier}>"
