"""
审计日志模型模块

本模块定义不可变、仅追加的审计日志表，记录所有关键操作。
禁止 UPDATE 和 DELETE（ORM 层 before_flush event hook 强制）。

核心类概览：
    - AuditLog : 审计日志记录，不可变仅追加

表关系：
    PipelineRun → AuditLog（一对多，run_id 可选关联）
    Iteration → AuditLog（一对多，iteration_id 可选关联）

索引设计：
    - ix_audit_log_target : 按 (target_kind, target_id) 查询
    - ix_audit_log_actor : 按 actor_id 查询
    - ix_audit_log_action : 按 action 查询
    - ix_audit_log_created_at : 按时间范围查询

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Index, event
from sqlalchemy.orm import Session
from app.utils.db_time import utcnow
from app.db.database import Base


class AuditLog(Base):
    """
    审计日志模型 - 不可变、仅追加

    记录所有关键操作（状态变更、决策、权限操作等），
    禁止 UPDATE 和 DELETE，确保审计追踪完整性。

    action 枚举值：
        lifecycle_transition, review_decide, review_rollback, review_undo,
        review_finalize, pipeline_start, pipeline_step_complete, pipeline_pause,
        pipeline_resume, pipeline_cancel, permission_change, config_change,
        case_version_create, locator_version_create, force_cancel_review
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(64), nullable=False, comment="操作类型枚举")
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="操作人ID")
    target_kind = Column(String(32), nullable=False, comment="目标实体类型")
    target_id = Column(Integer, nullable=False, comment="目标实体ID")
    detail = Column(JSON, nullable=True, comment="变更详情（before/after快照）")
    run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True, comment="关联PipelineRun")
    iteration_id = Column(Integer, ForeignKey("iterations.id", ondelete="SET NULL"), nullable=True, comment="关联迭代")
    created_at = Column(DateTime, nullable=False, default=utcnow, comment="操作时间（服务器时间）")

    __table_args__ = (
        Index("ix_audit_log_target", "target_kind", "target_id"),
        Index("ix_audit_log_action", "action"),
        Index("ix_audit_log_created_at", "created_at"),
    )


@event.listens_for(Session, "before_flush")
def _guard_audit_log_immutability(session, flush_context, instances):
    """拦截 AuditLog 的 UPDATE 和 DELETE 操作，确保不可变性。"""
    for instance in session.dirty:
        if isinstance(instance, AuditLog):
            raise RuntimeError(
                f"UPDATE on audit_log is forbidden (id={instance.id}). "
                f"Audit logs are immutable and append-only."
            )
    for instance in session.deleted:
        if isinstance(instance, AuditLog):
            raise RuntimeError(
                f"DELETE on audit_log is forbidden (id={instance.id}). "
                f"Audit logs are immutable and append-only."
            )
