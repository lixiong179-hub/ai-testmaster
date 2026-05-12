"""
需求管理模型模块

本模块定义了需求（Requirement）模型，用于管理项目需求，
支持从文件导入或手动创建，是测试点生成的输入源。

核心类概览：
    - Requirement : 需求模型，管理项目需求信息

表关系：
    Project → Requirement（一对多，级联删除）
    ProjectFile → Requirement（一对多，来源文件）
    Requirement → TestPoint（一对多，需求到测试点）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class Requirement(Base):
    """
    需求模型

    管理项目需求，支持从需求文档文件中AI提取或手动创建。
    需求是测试点生成的输入源，需求 -> 测试点 -> 测试用例
    构成完整的测试生成链路。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → ProjectFile（来源文件）
        - 一对多 → TestPoint（测试点）

    使用场景：
        - AI从需求文档提取需求
        - 手动创建和管理需求
        - 基于需求生成测试点
        - 需求状态跟踪
    """
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 需求主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID")  # 项目ID，级联删除

    # 需求基本信息
    req_no = Column(String(50), nullable=False, unique=True, index=True, comment="需求编号，如'REQ-PROJ1-001'")  # 需求编号，全局唯一
    title = Column(String(255), nullable=False, comment="需求标题")                                     # 需求标题
    description = Column(Text, nullable=False, comment="需求详细描述")                                  # 需求详细描述

    # 状态和优先级
    status = Column(String(20), nullable=False, default="draft", comment="状态: draft/approved/developing/testing/completed/cancelled")  # draft=草稿，approved=已审批，developing=开发中，testing=测试中，completed=已完成，cancelled=已取消
    priority = Column(Integer, nullable=False, comment="优先级：1高/2中/3低")                           # 1=高，2=中，3=低

    # 来源追踪
    source_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=True, comment="来源文件ID（从哪个文件提取的）")  # AI提取时的源文件

    # 时间信息
    create_time = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")                  # 创建时间，UTC时区
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow, comment="更新时间")                 # 更新时间

    # 关联关系
    project = relationship("Project", backref="requirements")                                         # 所属项目
    source_file = relationship("ProjectFile")                                                         # 来源文件
    test_points = relationship("TestPoint", back_populates="requirement", foreign_keys="TestPoint.requirement_id")  # 关联测试点

    def __repr__(self) -> str:
        """返回需求的字符串表示，便于调试和日志输出。"""
        return f"<Requirement(id={self.id}, req_no={self.req_no}, title='{self.title}')>"
