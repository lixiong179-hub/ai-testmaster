"""
Pipeline 配置模型模块

本模块定义 pipeline_config 表，集中管理所有可调参数。
禁止硬编码配置项，所有参数从此表或 settings 读取。

核心类概览：
    - PipelineConfig : 配置项键值对，支持 int/float/str/bool/json 类型

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from app.utils.db_time import utcnow
from app.db.database import Base


class PipelineConfig(Base):
    """
    Pipeline 配置项模型

    集中管理所有可调参数，key 唯一。
    敏感配置（API key 等）仍在环境变量 / settings，不入 DB。
    """
    __tablename__ = "pipeline_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, comment="配置项键名")
    value = Column(Text, nullable=False, comment="配置项值（文本存储）")
    value_type = Column(
        String(8), nullable=False, default="str",
        comment="值类型: int/float/str/bool/json",
    )
    description = Column(Text, nullable=True, comment="配置项说明")
    updated_by = Column(Integer, nullable=True, comment="最后修改人ID")
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, comment="最后修改时间")

    __table_args__ = (
        UniqueConstraint("key", name="uq_pipeline_config_key"),
    )
