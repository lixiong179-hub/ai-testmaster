"""IterationReview / ReviewDecision / ReviewLock 模型

评审快照与不可变决策记录，支持正向/反向/合并评审。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import ReviewKind, ReviewStatus, ReviewTargetKind
from app.utils.db_time import utcnow

VALID_VERDICTS = {"keep", "modify", "deprecate"}


class IterationReview(Base):
    __tablename__ = "iteration_review"

    id = Column(Integer, primary_key=True, autoincrement=True)
    iteration_id = Column(
        Integer, ForeignKey("iterations.id", ondelete="CASCADE"), nullable=False,
    )
    kind = Column(
        String(20), nullable=False,
        comment="评审类型：forward/backward/merged",
    )
    status = Column(
        String(20), nullable=False, default="draft",
        comment="评审状态：draft/in_progress/finalized/cancelled",
    )
    created_at = Column(DateTime, nullable=False, default=utcnow)
    finalized_at = Column(DateTime, nullable=True)
    finalized_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    decisions = relationship(
        "ReviewDecision", back_populates="review", cascade="all, delete-orphan",
    )
    locks = relationship(
        "ReviewLock", back_populates="review", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_iteration_review_iteration_id", "iteration_id"),
        Index("ix_iteration_review_status", "status"),
    )

    def is_finalized(self) -> bool:
        return self.status == ReviewStatus.FINALIZED.value


class ReviewDecision(Base):
    __tablename__ = "review_decision"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(
        Integer, ForeignKey("iteration_review.id", ondelete="CASCADE"), nullable=False,
    )
    target_kind = Column(
        String(20), nullable=False,
        comment="目标类型：case/testpoint/capability",
    )
    target_id = Column(Integer, nullable=False)
    target_version = Column(Integer, nullable=True)
    ai_verdict = Column(String(50), nullable=True, comment="AI 判定：keep/modify/deprecate")
    ai_confidence = Column(Integer, nullable=True, comment="AI 置信度 0-100")
    ai_reason = Column(Text, nullable=True)
    modification_hint = Column(Text, nullable=True)
    deprecate_reason = Column(Text, nullable=True)
    human_verdict = Column(String(50), nullable=True, comment="人工判定：keep/modify/deprecate")
    human_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    human_reason = Column(Text, nullable=True)
    final_verdict = Column(String(50), nullable=False, comment="最终判定：取 human_verdict 或 ai_verdict")
    decided_at = Column(DateTime, nullable=False, default=utcnow)
    conflict_marker = Column(Boolean, nullable=False, default=False)
    accepted_low_confidence = Column(Boolean, nullable=False, default=False)

    review = relationship("IterationReview", back_populates="decisions")

    __table_args__ = (
        Index("ix_review_decision_review_id", "review_id"),
        Index("ix_review_decision_target", "target_kind", "target_id"),
    )

    @staticmethod
    def compute_final_verdict(
        ai_verdict: Optional[str],
        human_verdict: Optional[str],
    ) -> Tuple[str, bool]:
        if human_verdict is not None:
            conflict = ai_verdict is not None and human_verdict != ai_verdict
            return human_verdict, conflict
        return ai_verdict or "keep", False


class ReviewLock(Base):
    __tablename__ = "review_lock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(
        Integer, ForeignKey("iteration_review.id", ondelete="CASCADE"), nullable=False,
    )
    target_kind = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=False)
    locked_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False)

    review = relationship("IterationReview", back_populates="locks")

    __table_args__ = (
        Index("ix_review_lock_target", "target_kind", "target_id"),
        Index("ix_review_lock_expires", "expires_at"),
    )

    @staticmethod
    def default_expiry() -> datetime:
        return utcnow() + timedelta(hours=24)

    def is_expired(self) -> bool:
        return utcnow() > self.expires_at
