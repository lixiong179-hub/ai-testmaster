"""
运行时特性开关模型

支持全局开关、灰度比例（rollout_percentage）和项目级定向投放（target_type/target_project_ids），
用于控制功能的渐进式发布与精准投放。
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from app.utils.db_time import utcnow
from app.db.database import Base


class FeatureFlag(Base):
    """运行时特性开关，以 key 为主键，支持灰度与项目级定向"""
    __tablename__ = "feature_flags"

    key = Column(String(80), primary_key=True, comment="特性开关唯一标识")
    name = Column(String(200), nullable=False, comment="特性开关显示名称")
    description = Column(String(500), nullable=True, comment="特性开关描述")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    rollout_percentage = Column(Integer, default=100, nullable=False, comment="灰度比例(0-100)")
    target_project_ids = Column(JSON, nullable=True, comment="目标项目ID列表")
    target_type = Column(String(20), default="all", nullable=False, comment="投放类型: all/specific")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
