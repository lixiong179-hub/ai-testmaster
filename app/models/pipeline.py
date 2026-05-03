"""
Pipeline 存储模型模块

本模块定义了 Pipeline 运行时持久化的三个核心模型：
    - PipelineRun : 一次 Pipeline 执行的根记录
    - PipelineStep : Run 中的单个 Step 执行记录
    - Artifact : Step 产出的结构化数据实体

表关系：
    Iteration → PipelineRun（一对多，级联删除）
    PipelineRun → PipelineStep（一对多，级联删除）
    PipelineRun → Artifact（一对多，级联删除）

索引设计：
    - ix_pipeline_run_iteration_id : 按迭代查询运行
    - ix_pipeline_step_cache_key : 缓存命中查询
    - uq_artifact_content_hash : artifact content_hash 唯一约束防重复落库

约束：
    - ck_pipeline_run_status : PipelineRun 状态枚举约束
    - ck_pipeline_step_status : PipelineStep 状态枚举约束

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
    - app.models.enums         : PipelineRunStatus, PipelineStepStatus
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON,
    Float, Boolean, Index, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base
from app.models.enums import PipelineRunStatus, PipelineStepStatus


class PipelineRun(Base):
    """
    Pipeline 运行记录

    每次启动 Pipeline 时创建一条记录，跟踪整体执行状态。
    相同 input_hash 的运行幂等返回已有记录（不重复创建）。

    表关系：
        - 多对一 → Iteration（所属迭代，级联删除）
        - 一对多 → PipelineStep（步骤记录，级联删除）
        - 一对多 → Artifact（产物，级联删除）

    约束：
        - status 仅允许 pending/running/waiting_for_user/completed/failed/cancelled
    """
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iteration_id = Column(
        Integer, ForeignKey("iterations.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="关联迭代ID",
    )
    input_hash = Column(String(64), nullable=False, comment="输入内容哈希，用于幂等校验")
    pipeline_version = Column(String(32), nullable=False, default="1.0", comment="Pipeline 版本号")
    status = Column(
        String(20), nullable=False, default=PipelineRunStatus.PENDING.value,
        comment="状态: pending/running/waiting_for_user/completed/failed/cancelled",
    )
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    finished_at = Column(DateTime, nullable=True, comment="执行完成时间")
    error = Column(Text, nullable=True, comment="错误信息")
    pause_payload = Column(JSON, nullable=True, comment="暂停信息：{reason, step_name, schema, paused_at}")

    iteration = relationship("Iteration", back_populates="pipeline_runs")
    steps = relationship(
        "PipelineStep", back_populates="run", cascade="all, delete-orphan",
        order_by="PipelineStep.id",
    )
    artifacts = relationship(
        "Artifact", back_populates="run", cascade="all, delete-orphan",
        order_by="Artifact.id",
    )
    ai_call_logs = relationship(
        "AICallLog", backref="run", passive_deletes=True,
        order_by="AICallLog.id",
    )

    __table_args__ = (
        Index('ix_pipeline_run_iteration_id', 'iteration_id'),
        CheckConstraint(
            "status IN ('pending', 'running', 'waiting_for_user', 'completed', 'failed', 'cancelled')",
            name='ck_pipeline_run_status',
        ),
    )


class PipelineStep(Base):
    """
    Pipeline Step 执行记录

    每个 Step 的执行状态、缓存键、输入输出产物引用。
    cache_key 用于幂等：同 cache_key 已有 done 状态的 step 可跳过执行。

    表关系：
        - 多对一 → PipelineRun（所属运行，级联删除）

    约束：
        - status 仅允许 pending/running/done/failed/skipped/degraded
    """
    __tablename__ = "pipeline_steps"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    run_id = Column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="关联运行ID",
    )
    step_name = Column(String(64), nullable=False, comment="Step 名称")
    step_version = Column(String(32), nullable=False, default="1.0", comment="Step 版本号")
    status = Column(
        String(20), nullable=False, default=PipelineStepStatus.PENDING.value,
        comment="状态: pending/running/done/failed/skipped/degraded",
    )
    cache_key = Column(String(64), nullable=True, index=True, comment="缓存键，用于幂等跳过")
    input_artifact_ids = Column(JSON, nullable=True, comment="输入产物ID列表")
    output_artifact_ids = Column(JSON, nullable=True, comment="输出产物ID列表")
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    finished_at = Column(DateTime, nullable=True, comment="执行完成时间")
    error = Column(Text, nullable=True, comment="错误信息")
    retried_count = Column(Integer, nullable=False, default=0, comment="重试次数")
    degraded = Column(Boolean, nullable=False, default=False, comment="是否降级完成")

    run = relationship("PipelineRun", back_populates="steps")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed', 'skipped', 'degraded')",
            name='ck_pipeline_step_status',
        ),
    )


class Artifact(Base):
    """
    Pipeline 产物

    Step 执行产出的结构化数据，通过 hash 唯一约束防止重复落库。
    payload 使用 LONGTEXT 存储（通过 JSON 类型映射）。

    表关系：
        - 多对一 → PipelineRun（所属运行，级联删除）

    约束：
        - hash 唯一约束防止重复落库
    """
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    run_id = Column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="关联运行ID",
    )
    kind = Column(String(64), nullable=False, comment="产物类型")
    schema_version = Column(String(32), nullable=False, default="1.0", comment="产物 schema 版本")
    payload = Column(JSON, nullable=True, comment="产物 JSON 载荷")
    confidence = Column(Float, nullable=True, comment="置信度分数")
    provenance = Column(JSON, nullable=True, comment="产物来源信息")
    content_hash = Column(String(64), nullable=False, comment="产物内容哈希，防重复落库")
    created_at = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")

    run = relationship("PipelineRun", back_populates="artifacts")

    __table_args__ = (
        UniqueConstraint('content_hash', name='uq_artifact_content_hash'),
    )
