"""Prompt 模板版本管理模型

支持 Prompt 的多版本管理、默认版本切换、版本回滚等能力。
通过 prompt_key + prompt_version 复合唯一索引保证版本唯一性，
prompt_hash 用于内容变更检测，避免重复注册相同内容。
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from app.db.database import Base


class PromptTemplate(Base):
    """Prompt 模板版本记录，同一 prompt_key 可存在多个版本，仅一个为默认"""
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("prompt_key", "prompt_version", name="uq_prompt_key_version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    prompt_key = Column(String(80), nullable=False, index=True, comment="Prompt唯一标识键")
    prompt_version = Column(Integer, nullable=False, comment="版本号，同一key内自增")
    prompt_hash = Column(String(64), nullable=False, comment="内容SHA256哈希，用于变更检测")
    content = Column(Text, nullable=False, comment="Prompt内容")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    is_default = Column(Boolean, default=False, nullable=False, comment="是否为当前key的默认版本")
    description = Column(String(500), nullable=True, comment="版本描述")
    created_at = Column(DateTime, default=func.now(), nullable=False, comment="创建时间")
