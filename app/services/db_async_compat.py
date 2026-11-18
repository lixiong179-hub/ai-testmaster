"""同步 Session / 异步 Session 双兼容的 DB 执行辅助（R2-1 过渡期）。

背景：R2-1 阶段三把端点依赖从异步会话依赖（AsyncSession）收敛为 `get_db`
（同步 Session），但部分服务层方法仍保留 `async def` 签名（内部含 AI 调用等
异步编排）。为了让同一份服务代码既能被同步请求会话驱动、又能被遗留的
AsyncSession（如后台任务的独立会话、测试桥接壳）驱动，这里统一提供：

- `execute_async(db, stmt)`：`execute` 为协程时直接 await，否则转线程池；
- `get_async(db, model, ident)`：按主键查询，语义同上；
- `flush_async(db)` / `commit_async(db)` / `rollback_async(db)`：同上；
- `refresh_async(db, obj)` / `delete_async(db, obj)`：同上；
- `run_sync_async(db, fn, *args)`：优先用会话自带的 `run_sync`，否则转线程池。

约定：调用方保持 `await`，无需关心底层会话类型。阶段四会话层收尾后，
本模块随异步会话依赖一并删除。
"""
import asyncio
import inspect
from typing import Any, TypeVar
from collections.abc import Callable

T = TypeVar("T")


def _is_async_callable(fn: Callable) -> bool:
    return inspect.iscoroutinefunction(fn)


async def execute_async(db: Any, stmt: Any) -> Any:
    """执行查询语句，返回 Result。"""
    fn = db.execute
    if _is_async_callable(fn):
        return await fn(stmt)
    return await asyncio.to_thread(fn, stmt)


async def get_async(db: Any, model: Any, ident: Any) -> Any:
    """按主键查询单个实例。"""
    fn = db.get
    if _is_async_callable(fn):
        return await fn(model, ident)
    return await asyncio.to_thread(fn, model, ident)


async def flush_async(db: Any) -> None:
    """刷新会话挂起变更。"""
    fn = db.flush
    if _is_async_callable(fn):
        await fn()
        return
    await asyncio.to_thread(fn)


async def commit_async(db: Any) -> None:
    """提交事务。"""
    fn = db.commit
    if _is_async_callable(fn):
        await fn()
        return
    await asyncio.to_thread(fn)


async def rollback_async(db: Any) -> None:
    """回滚事务。"""
    fn = db.rollback
    if _is_async_callable(fn):
        await fn()
        return
    await asyncio.to_thread(fn)


async def refresh_async(db: Any, instance: Any) -> None:
    """刷新单个实例。"""
    fn = db.refresh
    if _is_async_callable(fn):
        await fn(instance)
        return
    await asyncio.to_thread(fn, instance)


async def delete_async(db: Any, instance: Any) -> None:
    """删除实例。"""
    fn = db.delete
    if _is_async_callable(fn):
        await fn(instance)
        return
    await asyncio.to_thread(fn, instance)


async def run_sync_async(db: Any, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在会话内执行同步函数（优先复用会话的 `run_sync` 桥接）。"""
    runner = getattr(db, "run_sync", None)
    if runner is not None and _is_async_callable(runner):
        return await runner(fn, *args, **kwargs)
    return await asyncio.to_thread(fn, db, *args, **kwargs)


__all__ = [
    "execute_async",
    "get_async",
    "flush_async",
    "commit_async",
    "rollback_async",
    "refresh_async",
    "delete_async",
    "run_sync_async",
]
