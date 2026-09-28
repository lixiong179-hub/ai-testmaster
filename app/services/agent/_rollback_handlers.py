"""Agent 回滚处理器注册表模块。

定义 RollbackHandler 协议与全局注册表，并内置 2 个 handler：
    - create_test_case: 软删除 action_detail.test_case_id 指向的测试用例
    - update_locator: 用 action_detail.old_selector 恢复 ElementLocator.css_selector

未注册的 action_type 在 rollback_action 中抛 NotImplementedError。

扩展方式：
    from app.services.agent._rollback_handlers import register
    register("my_action", my_handler)

设计要点：
    - handler 为 async callable，接收 (db, original_audit) 返回补偿详情 dict
    - 所有 SQL 走 select/update 语句对象，参数化传值，防 SQL 注入
    - handler 内部仅执行补偿动作，不写审计记录（由 audit_service.rollback_action 统一写入）
    - handler 不调用 commit，事务边界由调用方管理
"""
from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_audit import AgentAudit
from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase
from app.utils.db_time import utcnow


# RollbackHandler 协议：异步可调用，接收 (db, original_audit) 返回补偿详情 dict
RollbackHandler = Callable[
    [AsyncSession, AgentAudit], Awaitable[Dict[str, object]]
]


_REGISTRY: Dict[str, RollbackHandler] = {}


def register(action_type: str, handler: RollbackHandler) -> None:
    """注册回滚处理器。重复注册将覆盖旧 handler。"""
    _REGISTRY[action_type] = handler


def get_rollback_handler(action_type: str) -> Optional[RollbackHandler]:
    """获取回滚处理器；未注册返回 None。"""
    return _REGISTRY.get(action_type)


async def _handle_create_test_case(
    db: AsyncSession, original_audit: AgentAudit,
) -> Dict[str, object]:
    """回滚 create_test_case：软删除对应测试用例。

    action_detail 期望含 test_case_id；若用例不存在或已删除，视为已回滚。
    """
    detail = original_audit.action_detail or {}
    test_case_id = detail.get("test_case_id")
    if test_case_id is None:
        return {
            "deleted_test_case_id": None,
            "reason": "action_detail 缺少 test_case_id",
        }

    # 先 select 校验用例存在且未删除，避免无谓 UPDATE
    result = await db.execute(
        select(TestCase.id).where(
            TestCase.id == test_case_id,
            TestCase.is_deleted.is_(False),
        )
    )
    if result.first() is None:
        return {
            "deleted_test_case_id": None,
            "reason": f"用例不存在或已删除: id={test_case_id}",
        }

    await db.execute(
        update(TestCase)
        .where(TestCase.id == test_case_id)
        .values(is_deleted=True, deleted_at=utcnow())
    )
    return {
        "deleted_test_case_id": test_case_id,
        "reason": f"软删除测试用例: id={test_case_id}",
    }


async def _handle_update_locator(
    db: AsyncSession, original_audit: AgentAudit,
) -> Dict[str, object]:
    """回滚 update_locator：将 ElementLocator.css_selector 恢复为 old_selector。

    action_detail 期望含 locator_id 与 old_selector；缺字段返回未恢复说明。
    """
    detail = original_audit.action_detail or {}
    locator_id = detail.get("locator_id")
    old_selector = detail.get("old_selector")
    if locator_id is None or old_selector is None:
        return {
            "restored_selector": None,
            "reason": "action_detail 缺少 locator_id 或 old_selector",
        }

    result = await db.execute(
        update(ElementLocator)
        .where(ElementLocator.id == locator_id)
        .values(css_selector=old_selector, updated_at=utcnow())
    )
    if result.rowcount == 0:
        return {
            "restored_selector": None,
            "reason": f"定位器不存在: id={locator_id}",
        }
    return {
        "restored_selector": old_selector,
        "reason": f"恢复定位器 css_selector: locator_id={locator_id}",
    }


# 内置 handler 注册
register("create_test_case", _handle_create_test_case)
register("update_locator", _handle_update_locator)


__all__ = [
    "RollbackHandler",
    "register",
    "get_rollback_handler",
]
