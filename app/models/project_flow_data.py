"""
项目流程数据模型模块

本模块定义项目流程编辑数据的持久化表，用于 AI 用例生成流程中用户对页面流程图的编辑结果保存与恢复。

核心类概览：
    - ProjectFlowData: 项目流程数据表，存储完整流程编辑结果（nodes/edges/module_info）

表关系：
    Project → ProjectFlowData（一对一，级联删除）

依赖关系：
    - app.utils.db_time.utcnow: UTC 时间戳生成
    - app.db.database.Base: SQLAlchemy 声明性基类
"""
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, DateTime, ForeignKey, JSON
from app.db.database import Base


class ProjectFlowData(Base):
    """
    项目流程数据表 - 项目级流程编辑结果持久化

    存储用户在 AI 用例生成流程中对页面流程图（FlowSortEditor）的编辑结果，
    包括节点位置、连线关系、流程类型、模块信息等完整数据。
    每个项目仅保留一条记录（project_id 唯一）。

    表关系：
        - 一对一 → Project（所属项目，级联删除）

    使用场景：
        - AI 用例生成页面中流程视图的自动保存
        - 页面刷新或重新进入时恢复上次编辑状态
        - 多设备间同步流程编辑状态
    """
    __tablename__ = "project_flow_data"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="关联项目ID，一对一",
    )
    flow_data = Column(JSON, nullable=False, comment="完整流程数据（nodes/edges/module_info）")
    create_time = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, comment="更新时间")
