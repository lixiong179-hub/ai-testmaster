"""
迭代模型模块

本模块定义了项目迭代（Iteration）和迭代输入（IterationInput）模型，
用于管理项目的迭代周期、版本规划，以及流水线运行的输入信号。

核心类概览：
    - Iteration : 迭代模型，管理项目迭代周期（流水线上下文根实体）
    - IterationInput : 迭代输入模型，流水线输入信号持久化

表关系：
    Project → Iteration（一对多，级联删除）
    Iteration → Iteration（自引用，base_iteration_id）
    Iteration → IterationInput（一对多，级联删除）
    Iteration → ProjectFile（一对多，SET NULL）
    Iteration → UIPrototypeProject（一对多，SET NULL）

索引设计：
    - uq_iteration_project_name(project_id, name) : 同一项目下迭代名称唯一
    - ix_iteration_project_status(project_id, status) : 按项目+状态查询迭代
    - ix_iteration_project_version(project_id, version) : 按项目+版本号查询迭代
    - ix_iteration_input_iter_kind(iteration_id, kind) : 按迭代+输入类型查询

约束：
    - ck_iteration_status : 状态字段仅允许 draft/in_pipeline/in_review/finalized/archived

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
    - app.models.enums         : IterationPipelineStatus, IterationInputKind
"""
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.enums import IterationPipelineStatus


class Iteration(Base):
    """
    迭代模型

    管理项目的迭代周期，每个迭代包含名称、版本号、状态和时间范围。
    迭代作为流水线运行的根上下文，所有 PipelineRun 必须关联一个 Iteration。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 自引用 → Iteration（base_iteration_id，基线迭代）

    约束：
        - 同一项目下迭代名称唯一（uq_iteration_project_name）
        - status 仅允许 draft/in_pipeline/in_review/finalized/archived

    使用场景：
        - 按迭代组织测试用例和测试任务
        - 迭代进度跟踪和版本管理
        - 按迭代归档项目文件和UI原型
        - 作为流水线上下文根实体
    """
    __tablename__ = "iterations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                            # 迭代主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID")  # 项目ID，级联删除
    name = Column(String(200), nullable=False, comment="迭代名称")                                     # 迭代名称，同一项目下唯一
    version = Column(String(50), nullable=False, default="v1.0", comment="版本号")                     # 版本号，默认v1.0
    description = Column(Text, nullable=True, comment="迭代描述")                                      # 迭代描述和目标说明
    status = Column(String(20), nullable=False, default=IterationPipelineStatus.DRAFT.value, comment="状态: draft/in_pipeline/in_review/finalized/archived")  # 流水线状态，由系统自动驱动
    start_date = Column(DateTime, nullable=True, comment="开始日期")                                   # 迭代开始日期
    end_date = Column(DateTime, nullable=True, comment="结束日期")                                     # 迭代结束日期
    create_time = Column(DateTime, nullable=False, default=utcnow)                                    # 创建时间，UTC时区
    update_time = Column(DateTime, default=utcnow, onupdate=utcnow)                                   # 更新时间

    # 流水线上下文字段
    base_iteration_id = Column(Integer, ForeignKey("iterations.id", ondelete="SET NULL"), nullable=True, comment="基线迭代ID，用于跨迭代对比")  # 基线迭代，SET NULL保留当前迭代
    target_device = Column(String(20), nullable=True, comment="迭代目标设备：tablet/phone/desktop/web")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建人ID")  # 创建人，SET NULL保留迭代
    finalized_at = Column(DateTime, nullable=True, comment="定稿时间")                                 # 评审 finalize 时设置

    project = relationship("Project", back_populates="iterations")                                    # 所属项目
    base_iteration = relationship("Iteration", remote_side=[id], foreign_keys=[base_iteration_id], back_populates="derived_iterations")  # 基线迭代
    derived_iterations = relationship("Iteration", back_populates="base_iteration", foreign_keys=[base_iteration_id])  # 派生迭代列表
    creator = relationship("User", foreign_keys=[created_by])                                         # 创建人
    inputs = relationship("IterationInput", back_populates="iteration", cascade="all, delete-orphan", order_by="IterationInput.id")  # 迭代输入列表
    pipeline_runs = relationship("PipelineRun", back_populates="iteration", cascade="all, delete-orphan", order_by="PipelineRun.id")  # Pipeline 运行列表

    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_iteration_project_name'),                     # 同一项目下迭代名称唯一
        Index('ix_iteration_project_status', 'project_id', 'status'),                                 # 按项目+状态查询
        Index('ix_iteration_project_version', 'project_id', 'version'),                               # 按项目+版本号查询
        CheckConstraint("status IN ('draft', 'in_pipeline', 'in_review', 'finalized', 'archived')", name='ck_iteration_status'),  # 状态值约束
    )


class IterationInput(Base):
    """
    迭代输入模型

    流水线输入信号的持久化实体。每个 IterationInput 代表一份输入资源
    （PRD 文档、UI 原型、XMind、测试点、补充表单），供 Pipeline Step 消费。

    表关系：
        - 多对一 → Iteration（所属迭代，级联删除）
        - 多对一 → ProjectFile（关联文件，SET NULL）

    约束：
        - kind 仅允许 prd/prototype/xmind/testpoint/supplement_form (CHECK 约束)
        - content_hash 字段用于幂等校验（相同 content_hash 不重复添加）
    """
    __tablename__ = "iteration_inputs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                            # 输入主键ID
    iteration_id = Column(Integer, ForeignKey("iterations.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联迭代ID")  # 迭代ID，级联删除
    kind = Column(String(30), nullable=False, comment="输入类型: prd/prototype/xmind/testpoint/supplement_form/change_notes")  # 输入类型
    file_id = Column(Integer, ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True, comment="关联项目文件ID")  # 文件ID，SET NULL保留输入记录
    payload = Column(JSON, nullable=True, comment="非文件型输入的JSON载荷（如补充表单）")               # JSON payload
    content_hash = Column(String(64), nullable=False, comment="输入内容哈希，用于幂等校验")                 # SHA-256 哈希
    uploaded_at = Column(DateTime, nullable=False, default=utcnow, comment="上传时间")                  # 上传时间

    iteration = relationship("Iteration", back_populates="inputs")                                     # 所属迭代
    file = relationship("ProjectFile", foreign_keys=[file_id])                                        # 关联文件

    __table_args__ = (
        Index('ix_iteration_input_iter_kind', 'iteration_id', 'kind'),                                # 按迭代+输入类型查询
        CheckConstraint(
            "kind IN ('prd', 'prototype', 'xmind', 'testpoint', 'supplement_form', 'change_notes')",
            name='ck_iteration_input_kind',
        ),
    )
