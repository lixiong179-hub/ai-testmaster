"""Agent 审计服务模块。

提供 AgentAudit 的写入、查询、HITL 审批与回滚能力。回滚操作不修改原
审计记录，而是写入 action_type=rollback_<原type> 的新审计记录，
action_detail 含 original_audit_id 与补偿详情，保留完整决策链条。

审批状态：0=待审批, 1=已批准, 2=已拒绝。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_audit import AgentAudit
from app.services.agent._rollback_handlers import get_rollback_handler
from app.services.agent.exceptions import AgentError
from app.utils.db_time import utcnow


# 审批状态枚举常量，集中维护便于一致性引用
HUMAN_APPROVAL_PENDING = 0
HUMAN_APPROVAL_APPROVED = 1
HUMAN_APPROVAL_REJECTED = 2


class AgentAuditService:
    """Agent 审计与回滚服务。"""

    async def record_action(
        self, db: AsyncSession, *, session_id: int, iteration: int,
        action_type: str, action_detail: dict,
        decision_confidence: Optional[float] = None,
    ) -> AgentAudit:
        """记录一轮 Agent 决策动作。

        Raises:
            AgentError: action_type 或 decision_confidence 校验失败。
        """
        if not AgentAudit.validate_action_type(action_type):
            raise AgentError(
                f"非法 action_type: {action_type}", session_id=session_id,
            )
        if not AgentAudit.validate_confidence(decision_confidence):
            raise AgentError(
                f"非法 decision_confidence: {decision_confidence}",
                session_id=session_id,
            )
        audit = AgentAudit(
            session_id=session_id, iteration=iteration, action_type=action_type,
            action_detail=action_detail, decision_confidence=decision_confidence,
            human_approved=HUMAN_APPROVAL_PENDING,
        )
        db.add(audit)
        await db.flush()
        await db.refresh(audit)
        logger.info(
            f"Agent 审计写入: id={audit.id} session={session_id} "
            f"iter={iteration} action={action_type} confidence={decision_confidence}"
        )
        return audit

    async def get_session_audit(
        self, db: AsyncSession, session_id: int,
    ) -> List[AgentAudit]:
        """查询会话完整审计链，按 id 升序返回。"""
        stmt = (
            select(AgentAudit)
            .where(AgentAudit.session_id == session_id)
            .order_by(AgentAudit.id.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_approvals(
        self, db: AsyncSession, *, offset: int = 0, limit: int = 20,
    ) -> Tuple[List[AgentAudit], int]:
        """分页查询待审批动作（human_approved=0），按创建时间升序。"""
        cond = AgentAudit.human_approved == HUMAN_APPROVAL_PENDING
        stmt = (
            select(AgentAudit)
            .where(cond)
            .order_by(AgentAudit.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count(AgentAudit.id)).where(cond)
        result = await db.execute(stmt)
        records = list(result.scalars().all())
        count_result = await db.execute(count_stmt)
        total = int(count_result.scalar() or 0)
        return records, total

    async def approve_action(
        self, db: AsyncSession, *, audit_id: int, approved_by: int,
        approved: bool = True,
    ) -> AgentAudit:
        """标记审计记录的审批结果（更新三字段：human_approved/approved_by/approved_at）。

        Raises:
            AgentError: 审计记录不存在。
        """
        status_val = HUMAN_APPROVAL_APPROVED if approved else HUMAN_APPROVAL_REJECTED
        stmt = (
            update(AgentAudit)
            .where(AgentAudit.id == audit_id)
            .values(
                human_approved=status_val,
                approved_by=approved_by,
                approved_at=utcnow(),
            )
        )
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise AgentError(f"审计记录不存在: audit_id={audit_id}")
        await db.flush()
        refreshed = await self._get_audit(db, audit_id)
        if refreshed is None:
            raise AgentError(f"审计记录不存在: audit_id={audit_id}")
        logger.info(
            f"Agent 审计审批: id={audit_id} approved={approved} by={approved_by}"
        )
        return refreshed

    async def rollback_action(
        self, db: AsyncSession, *, audit_id: int, rolled_by: int,
        reason: str = "",
    ) -> AgentAudit:
        """回滚已记录的 Agent 动作。

        流程：select 原审计 → 校验 handler 已注册（否则 NotImplementedError）
        → 调用 handler 获取补偿详情 → 写入新审计 action_type=rollback_<原type>。

        Raises:
            AgentError: 原审计记录不存在。
            NotImplementedError: action_type 未注册回滚处理器。
        """
        original = await self._get_audit(db, audit_id)
        if original is None:
            raise AgentError(f"审计记录不存在: audit_id={audit_id}")

        handler = get_rollback_handler(original.action_type)
        if handler is None:
            raise NotImplementedError(
                f"未注册的回滚处理器: {original.action_type}"
            )

        compensation = await handler(db, original)
        rollback_detail = {
            "original_audit_id": original.id,
            "rolled_by": rolled_by,
            "reason": reason,
            "compensation": compensation,
        }
        rollback_audit = AgentAudit(
            session_id=original.session_id, iteration=original.iteration,
            action_type=f"rollback_{original.action_type}",
            action_detail=rollback_detail, decision_confidence=None,
            human_approved=HUMAN_APPROVAL_APPROVED, approved_by=rolled_by,
            approved_at=utcnow(),
        )
        db.add(rollback_audit)
        await db.flush()
        await db.refresh(rollback_audit)
        logger.info(
            f"Agent 审计回滚: origin={audit_id} new={rollback_audit.id} "
            f"action={rollback_audit.action_type} by={rolled_by}"
        )
        return rollback_audit

    async def _get_audit(
        self, db: AsyncSession, audit_id: int,
    ) -> Optional[AgentAudit]:
        """按 ID 查询审计记录，不存在返回 None。"""
        stmt = select(AgentAudit).where(AgentAudit.id == audit_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["AgentAuditService"]
