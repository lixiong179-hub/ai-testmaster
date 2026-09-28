"""Agent 会话服务模块。

封装 AgentSession 与 AgentMessage 的写入/查询接口，所有方法接收外部
AsyncSession，由调用方管理事务边界。

设计要点：
    - 创建后 flush + refresh 让数据库默认值与生成字段生效，避免 MissingGreenlet
    - 状态/类型校验调用模型层 AgentSession.validate_status / validate_agent_type
    - 状态变更走 update() 语句，避免加载完整对象再写回
    - 异常包装为 AgentError，保留 agent_type/session_id 上下文
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.services.agent.exceptions import AgentError
from app.utils.db_time import utcnow


class SessionService:
    """Agent 会话与消息持久化服务。

    方法均接收 AsyncSession，无内部状态，便于在多个事务上下文复用。
    """

    async def create_session(
        self, db: AsyncSession, *, agent_type: str,
        project_id: int, created_by: Optional[int] = None,
    ) -> AgentSession:
        """创建 Agent 会话，初始 status=running、token_cost=0。

        Raises:
            AgentError: agent_type 不在 AGENT_TYPE_VALUES 内。
        """
        if not AgentSession.validate_agent_type(agent_type):
            raise AgentError(
                f"非法 agent_type: {agent_type}", agent_type=agent_type,
            )
        session = AgentSession(
            project_id=project_id, agent_type=agent_type, status="running",
            token_cost=0, iteration_count=0, loop_detected=False,
            created_by=created_by,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        logger.info(
            f"Agent 会话创建: id={session.id} agent_type={agent_type} "
            f"project_id={project_id} created_by={created_by}"
        )
        return session

    async def append_message(
        self, db: AsyncSession, *, session_id: int, role: str,
        content: dict, artifact_refs: Optional[list] = None,
        tool_call_id: Optional[str] = None, tool_name: Optional[str] = None,
        token_cost: int = 0,
    ) -> AgentMessage:
        """追加一条消息到会话历史。

        Raises:
            AgentError: role 不在 MESSAGE_ROLE_VALUES 内。
        """
        if not AgentMessage.validate_role(role):
            raise AgentError(
                f"非法消息角色: {role}", session_id=session_id,
            )
        message = AgentMessage(
            session_id=session_id, role=role, content=content,
            artifact_refs=artifact_refs, tool_call_id=tool_call_id,
            tool_name=tool_name, token_cost=token_cost,
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)
        return message

    async def get_history(
        self, db: AsyncSession, session_id: int, limit: int = 50,
    ) -> List[AgentMessage]:
        """按时间顺序获取会话消息流（最旧 → 最新），返回最多 limit 条。"""
        stmt = (
            select(AgentMessage)
            .where(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.asc(), AgentMessage.id.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def complete_session(
        self, db: AsyncSession, *, session_id: int, status: str,
        token_cost: Optional[int] = None, iteration_count: Optional[int] = None,
        loop_detected: Optional[bool] = None,
    ) -> AgentSession:
        """关闭会话：写入 status、completed_at 与可选统计字段。

        None 值的统计字段不参与更新。状态非法或会话不存在时抛 AgentError。
        """
        if not AgentSession.validate_status(status):
            raise AgentError(
                f"非法会话状态: {status}", session_id=session_id,
            )
        values: dict = {"status": status, "completed_at": utcnow()}
        if token_cost is not None:
            values["token_cost"] = token_cost
        if iteration_count is not None:
            values["iteration_count"] = iteration_count
        if loop_detected is not None:
            values["loop_detected"] = loop_detected

        stmt = (
            update(AgentSession)
            .where(AgentSession.id == session_id)
            .values(**values)
        )
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise AgentError(
                f"会话不存在或状态更新失败: session_id={session_id}",
                session_id=session_id,
            )
        await db.flush()
        # 重新加载最新数据，避免依赖 returning 在 MySQL 方言上的差异
        refreshed = await self.get_session(db, session_id)
        if refreshed is None:
            raise AgentError(
                f"会话不存在: session_id={session_id}", session_id=session_id,
            )
        logger.info(
            f"Agent 会话关闭: id={session_id} status={status} "
            f"token_cost={refreshed.token_cost} iterations={refreshed.iteration_count}"
        )
        return refreshed

    async def cancel_session(
        self, db: AsyncSession, session_id: int,
    ) -> AgentSession:
        """取消会话（status=cancelled）。"""
        return await self.complete_session(
            db, session_id=session_id, status="cancelled",
        )

    async def get_session(
        self, db: AsyncSession, session_id: int,
    ) -> Optional[AgentSession]:
        """按 ID 查询会话，不存在返回 None。"""
        stmt = select(AgentSession).where(AgentSession.id == session_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sessions(
        self, db: AsyncSession, *, project_id: Optional[int] = None,
        agent_type: Optional[str] = None, status: Optional[str] = None,
        offset: int = 0, limit: int = 20,
    ) -> Tuple[List[AgentSession], int]:
        """分页查询会话列表，按 id 倒序。

        所有过滤参数为 None 时不参与 WHERE 条件。返回 (列表, 总数)。

        Raises:
            AgentError: agent_type 或 status 校验失败。
        """
        conditions = []
        if project_id is not None:
            conditions.append(AgentSession.project_id == project_id)
        if agent_type is not None:
            if not AgentSession.validate_agent_type(agent_type):
                raise AgentError(
                    f"非法 agent_type: {agent_type}", agent_type=agent_type,
                )
            conditions.append(AgentSession.agent_type == agent_type)
        if status is not None:
            if not AgentSession.validate_status(status):
                raise AgentError(f"非法会话状态: {status}")
            conditions.append(AgentSession.status == status)

        base_stmt = select(AgentSession)
        count_stmt = select(func.count(AgentSession.id))
        for cond in conditions:
            base_stmt = base_stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        base_stmt = (
            base_stmt.order_by(AgentSession.id.desc()).offset(offset).limit(limit)
        )

        result = await db.execute(base_stmt)
        sessions = list(result.scalars().all())
        count_result = await db.execute(count_stmt)
        total = int(count_result.scalar() or 0)
        return sessions, total


__all__ = ["SessionService"]
