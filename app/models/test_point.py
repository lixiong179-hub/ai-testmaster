"""
测试点模型模块

本模块定义了测试点（TestPoint）模型，测试点是需求到测试用例的中间产物，
用于从需求文档中提取关键测试关注点，再由AI基于测试点生成详细测试用例。

核心类概览：
    - TestPoint : 测试点模型，记录模块-测试点二级结构

表关系：
    Project → TestPoint（一对多，级联删除）
    Requirement → TestPoint（一对多，SET NULL，需求删除后测试点保留）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base
from app.models.enums import TestPointStatus


class TestPoint(Base):
    """
    测试点模型

    测试点采用"模块-测试点"结构组织，是AI生成测试用例的输入源。
    AI根据测试点的描述和优先级，自动生成对应的测试用例。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → Requirement（关联需求，SET NULL）

    使用场景：
        - AI从需求文档中提取测试点
        - 基于测试点批量生成测试用例
        - 按模块组织测试关注点
    """
    __tablename__ = "test_points"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                           # 测试点主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID，多项目隔离核心")  # 项目ID，级联删除
    capability_id = Column(Integer, ForeignKey("test_capabilities.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联业务能力ID（可选）")  # 能力ID，SET NULL保留测试点
    requirement_id = Column(Integer, ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True, comment="关联需求ID（可选）")  # 需求ID，SET NULL保留测试点
    module = Column(String(100), nullable=False, comment="模块名称，如'登录模块'")                      # 一级分类：功能模块
    point = Column(String(500), nullable=False, comment="测试点描述，如'输入错误密码登录'")               # 三级分类：具体测试关注点
    priority = Column(Integer, nullable=False, comment="优先级：1高2中3低")                             # 优先级，1=高，2=中，3=低
    create_time = Column(DateTime, default=utcnow, nullable=False, comment="创建时间")                  # 创建时间，UTC时区
    created_by = Column(String(100), nullable=True, comment="创建人用户名")                              # 创建人用户名，兼容历史数据允许为空
    ai_prompt = Column(Text, nullable=True, comment="AI分析时的提示词")                                 # AI生成用例时的额外提示信息
    version = Column(Integer, nullable=False, default=1, comment="版本号，每次变更递增")                    # 版本号
    status = Column(String(20), nullable=False, default=TestPointStatus.ACTIVE.value, comment="状态：draft/active/deprecated/archived")  # 生命周期状态

    __table_args__ = (
        Index("ix_test_points_capability_status", "capability_id", "status"),
    )

    # 关联关系 - 通过project_id隔离
    project = relationship("Project", back_populates="test_points")                                   # 所属项目
    capability = relationship("TestCapability", back_populates="test_points", foreign_keys=[capability_id])  # 关联业务能力
    requirement = relationship("Requirement", back_populates="test_points")                           # 关联需求
