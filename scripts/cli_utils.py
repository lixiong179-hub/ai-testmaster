"""CLI 脚本共享工具 — 数据库会话构建与生命周期管理"""
from typing import Tuple

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def build_session() -> Tuple[Session, Engine]:
    """构建独立数据库会话，供 CLI 脚本使用

    Returns:
        (session, engine) 元组，调用方负责关闭
    """
    db_url = settings.DATABASE_URL
    engine = create_engine(
        db_url,
        connect_args={"init_command": "SET sql_mode='NO_ENGINE_SUBSTITUTION'"},
        pool_pre_ping=True,
    )
    session_cls = sessionmaker(bind=engine)
    return session_cls(), engine
