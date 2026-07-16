"""AI 生成并发控制 — 模块级信号量单例。

背景：
    审计 P-2 发现 batch_orchestrator 使用局部 asyncio.Semaphore，仅限制单次
    batch 内并发，不限制跨请求总并发；generate_single_test_case 与
    AutoCaseGenerator.generate 完全无信号量保护。多请求并发时 AI 调用总数
    可能超出 AI_CASE_GENERATION_CONCURRENCY 配置，触发 DeepSeek 限流或超时。

设计：
    使用 threading.Semaphore 而非 asyncio.Semaphore，因为 AI 生成入口跨越
    多个事件循环：
    - generate_single_test_case 在主 ASGI 事件循环
    - batch_orchestrator 在 iter_async_gen_in_thread 创建的独立线程事件循环
    - AutoCaseGenerator.generate 在 quick_launcher 后台任务事件循环

    threading.Semaphore 是进程内跨线程/跨事件循环安全的，通过 asyncio.to_thread
    包装 acquire 避免在 async 代码中阻塞事件循环。

    信号量在首次使用时按 settings.AI_CASE_GENERATION_CONCURRENCY 懒加载创建，
    避免导入时副作用；测试可通过 reset_ai_generation_semaphore 重置。
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
from typing import Optional

from app.core.config import settings

# 默认并发数兜底（settings 缺失字段时使用）
_DEFAULT_AI_CONCURRENCY = 3

_ai_gen_semaphore: Optional[threading.Semaphore] = None
_init_lock = threading.Lock()


def _get_ai_semaphore() -> threading.Semaphore:
    """获取 AI 生成模块级信号量单例（线程安全懒加载）。"""
    global _ai_gen_semaphore
    if _ai_gen_semaphore is None:
        with _init_lock:
            if _ai_gen_semaphore is None:
                concurrency = max(
                    1,
                    int(
                        getattr(
                            settings,
                            "AI_CASE_GENERATION_CONCURRENCY",
                            _DEFAULT_AI_CONCURRENCY,
                        )
                    ),
                )
                _ai_gen_semaphore = threading.Semaphore(concurrency)
    return _ai_gen_semaphore


@contextlib.asynccontextmanager
async def ai_generation_slot():
    """AI 生成槽位异步上下文管理器。

    跨事件循环安全：threading.Semaphore 通过 asyncio.to_thread acquire，
    不阻塞当前事件循环；release 是瞬时操作可直接调用。

    使用示例：
        async with ai_generation_slot():
            generated = await run_async_coro_in_thread(service.generate(...))
    """
    sem = _get_ai_semaphore()
    await asyncio.to_thread(sem.acquire)
    try:
        yield
    finally:
        sem.release()


def reset_ai_generation_semaphore() -> None:
    """重置信号量单例（仅测试使用）。

    测试场景下若前序用例异常退出未 release，残留计数会影响后续用例；
    每个 autouse 测试 fixture 调用此函数确保隔离。
    """
    global _ai_gen_semaphore
    with _init_lock:
        _ai_gen_semaphore = None
