"""数据库配置和初始化"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite数据库路径
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "travel_companion.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 创建引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite需要
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base类
Base = declarative_base()


def init_db():
    """初始化数据库表"""
    from models import Companion, User, UserMembership, Comment, ContactExchange  # 导入模型
    Base.metadata.create_all(bind=engine)
    print(f"✅ 数据库初始化完成: {DATABASE_PATH}")


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
