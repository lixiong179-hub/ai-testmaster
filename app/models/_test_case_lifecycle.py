"""TestCase lifecycle_status 保护机制与版本快照。

从 `app/models/test_case.py` 拆分而来，集中存放 lifecycle_status 守卫
与版本快照的上下文标记、事件监听器和控制函数，避免单文件超过 350 行。

设计要点：
    - guard 注册在 Session 基类上（@event.listens_for(Session, "before_flush")），
      所有 Session 实例都会触发拦截；
    - 使用 contextvars 而非 threading.local()，支持 asyncio 协程隔离；
    - TestCase 采用延迟导入避免循环依赖（本模块被 test_case.py re-export）。

兼容性：`test_case.py` 通过 re-export 保持
`from app.models.test_case import enable_lifecycle_transition` 等导入路径不变。
"""
import contextvars
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session


# contextvars 上下文标记：LifecycleService 执行迁移时设置，允许通过；其他途径修改则抛错
#
# 设计说明：
#   guard 注册在 Session 基类上（@event.listens_for(Session, "before_flush")），
#   因此所有 Session 实例都会触发拦截，包括业务 Session、迁移脚本、管理后台等。
#   非业务场景如需绕过 guard，必须显式调用 enable_lifecycle_transition() /
#   disable_lifecycle_transition()，确保意图明确可追溯。
#
# 使用 contextvars 而非 threading.local() 的原因：
#   FastAPI 异步模式下，同一线程内可能并发多个协程。threading.local() 在线程内
#   对所有协程共享，可能导致协程 A 开启了 lifecycle 许可，协程 B 绕过 guard。
#   contextvars 天然支持 asyncio 协程隔离，每个协程有独立的上下文副本。
#
# 批量操作逃生舱：
#   对于数据迁移、批量修复等场景，可使用 enable/disable 包裹批量操作：
#       enable_lifecycle_transition()
#       try:
#           for case in cases:
#               case.lifecycle_status = "active"
#           session.flush()
#       finally:
#           disable_lifecycle_transition()
_lifecycle_guard: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'lifecycle_transition_allowed', default=False
)


def _lifecycle_transition_allowed() -> bool:
    """检查当前上下文是否允许修改 lifecycle_status（仅 LifecycleService 调用时为 True）。"""
    return _lifecycle_guard.get()


def enable_lifecycle_transition() -> None:
    """LifecycleService 调用前设置允许标记。"""
    _lifecycle_guard.set(True)


def disable_lifecycle_transition() -> None:
    """LifecycleService 调用后清除允许标记。"""
    _lifecycle_guard.set(False)


@event.listens_for(Session, "before_flush")
def _guard_lifecycle_status(session, flush_context, instances):
    """拦截 TestCase.lifecycle_status 的直接修改。

    如果 lifecycle_status 被修改且当前线程未通过 LifecycleService 授权，
    则抛出 RuntimeError，强制所有状态变更经过 LifecycleService.transition()。

    同时检测追踪字段的变更，自动创建版本快照。
    """
    # 延迟导入避免循环依赖（test_case.py re-export 本模块）
    from app.models.test_case import TestCase

    for instance in session.dirty:
        if not isinstance(instance, TestCase):
            continue
        # 检查 lifecycle_status 是否被修改
        from sqlalchemy import inspect as sa_inspect
        state = sa_inspect(instance)
        hist = state.attrs.lifecycle_status.history
        if hist.deleted or hist.added:
            # lifecycle_status 被修改
            if not _lifecycle_transition_allowed():
                raise RuntimeError(
                    f"Direct update of TestCase.lifecycle_status is forbidden. "
                    f"Use LifecycleService.transition() instead. "
                    f"(case_id={instance.id}, "
                    f"old={hist.deleted[0] if hist.deleted else '?'}, "
                    f"new={hist.added[0] if hist.added else '?'})"
                )

        # 自动版本快照：检测追踪字段变更
        _auto_create_version_snapshot(session, instance, state)


# 上下文标记：跳过自动版本快照（用于批量操作或内部流程手动控制）
_version_snapshot_skip: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'version_snapshot_skip', default=False
)


def skip_version_snapshot() -> None:
    """设置跳过自动版本快照标记。"""
    _version_snapshot_skip.set(True)


def resume_version_snapshot() -> None:
    """恢复自动版本快照标记。"""
    _version_snapshot_skip.set(False)


def _auto_create_version_snapshot(session: Session, instance: "Any", state: Any) -> None:
    """当 TestCase 的追踪字段变更时自动创建版本快照。

    仅在实例有持久化主键且追踪字段真正变更时触发，
    通过 CaseVersionService.create_snapshot 统一处理。
    由于在 before_flush 事件中调用，auto_flush=False 避免递归 flush。

    Args:
        session: 数据库会话。
        instance: TestCase 脏实例（类型标注为 Any 避免循环导入）。
        state: SQLAlchemy instance state。
    """
    if _version_snapshot_skip.get():
        return
    if instance.id is None:
        return

    from app.services.case_version_service import CaseVersionService, TRACKED_FIELDS

    changed_fields = CaseVersionService.build_changed_fields(instance, state)
    if not changed_fields:
        return

    CaseVersionService.create_snapshot(
        db=session,
        test_case_id=instance.id,
        change_type="update",
        changed_fields=changed_fields,
        auto_flush=False,
    )
