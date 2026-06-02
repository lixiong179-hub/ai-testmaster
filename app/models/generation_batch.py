from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base


class GenerationBatch(Base):
    __tablename__ = "generation_batches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_no = Column(String(40), unique=True, index=True, nullable=False, comment="人类可读批次号，例如GB202606010001")
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="创建人ID")
    entry_type = Column(String(40), index=True, nullable=False, default="NEW_FEATURE_GENERATION", comment="任务入口类型")
    scenario_type = Column(String(60), index=True, nullable=False, comment="资料组合场景")
    generation_strategy = Column(String(80), index=True, nullable=False, comment="生成策略")
    status = Column(String(30), index=True, nullable=False, default="created", comment="批次状态")
    requirement_file_ids_json = Column(JSON, default=list, nullable=False, comment="本次选择的需求文件ID列表")
    test_point_ids_json = Column(JSON, default=list, nullable=False, comment="本次选择的测试点ID列表")
    ui_screen_ids_json = Column(JSON, default=list, nullable=False, comment="本次选择的UI页面ID列表")
    history_asset_ids_json = Column(JSON, default=list, nullable=False, comment="本次选择的历史资产ID列表")
    context_stats_json = Column(JSON, default=dict, nullable=False, comment="上下文统计")
    warnings_json = Column(JSON, default=list, nullable=False, comment="结构化warning")
    evidence_refs_json = Column(JSON, default=dict, nullable=False, comment="来源依据")
    quality_summary_json = Column(JSON, default=dict, nullable=False, comment="质量摘要")
    client_request_id = Column(String(80), nullable=True, comment="前端请求ID")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=utcnow, default=utcnow)

    project = relationship("Project", backref="generation_batches")
    user = relationship("User", backref="generation_batches")
    saves = relationship("GenerationBatchSave", back_populates="batch", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_gen_batch_project_created", "project_id", "created_at"),
        Index("ix_gen_batch_project_status", "project_id", "status"),
        Index("ix_gen_batch_user_created", "user_id", "created_at"),
    )


class GenerationBatchSave(Base):
    __tablename__ = "generation_batch_saves"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("generation_batches.id", ondelete="CASCADE"), nullable=False, index=True, comment="批次ID")
    idempotency_key = Column(String(100), nullable=False, comment="保存幂等键")
    save_mode = Column(String(30), nullable=False, comment="保存模式: draft/formal/passed_only")
    request_hash = Column(String(64), nullable=True, comment="请求体hash，用于排查重复提交")
    result_json = Column(JSON, nullable=False, comment="首次保存结果")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    batch = relationship("GenerationBatch", back_populates="saves")

    __table_args__ = (
        Index("ix_gen_batch_save_unique", "batch_id", "idempotency_key", unique=True),
    )
