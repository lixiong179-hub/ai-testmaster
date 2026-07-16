"""AI 生成并发信号量单例测试（P-2 修复验证）。

覆盖点：
1. 模块级单例：多次获取返回同一实例
2. 信号量并发限制：跨请求总并发不超过 AI_CASE_GENERATION_CONCURRENCY
3. 跨事件循环安全：在不同事件循环中均可使用
4. reset_ai_generation_semaphore 重置功能
5. 异常退出时信号量正确释放（上下文管理器 finally）
"""
import asyncio
import threading

import pytest

from app.utils.ai_concurrency import (
    _get_ai_semaphore,
    ai_generation_slot,
    reset_ai_generation_semaphore,
)
from app.core.config import settings


def test_singleton_returns_same_instance() -> None:
    """多次获取返回同一个 Semaphore 实例（模块级单例）。"""
    reset_ai_generation_semaphore()
    sem1 = _get_ai_semaphore()
    sem2 = _get_ai_semaphore()
    assert sem1 is sem2


def test_reset_creates_new_instance() -> None:
    """reset 后获取的是新实例。"""
    sem1 = _get_ai_semaphore()
    reset_ai_generation_semaphore()
    sem2 = _get_ai_semaphore()
    assert sem1 is not sem2


def test_concurrency_matches_settings() -> None:
    """信号量初始可用槽位等于 settings.AI_CASE_GENERATION_CONCURRENCY。"""
    reset_ai_generation_semaphore()
    sem = _get_ai_semaphore()
    expected = max(1, int(getattr(settings, "AI_CASE_GENERATION_CONCURRENCY", 3)))
    # Semaphore._value 是当前可用数（非公开 API，但 CPython 稳定）
    assert sem._value == expected


@pytest.mark.asyncio
async def test_slot_releases_on_normal_exit() -> None:
    """正常退出上下文后信号量槽位归还。"""
    reset_ai_generation_semaphore()
    sem = _get_ai_semaphore()
    initial = sem._value
    async with ai_generation_slot():
        assert sem._value == initial - 1
    assert sem._value == initial


@pytest.mark.asyncio
async def test_slot_releases_on_exception() -> None:
    """异常退出上下文也归还槽位（finally 保护）。"""
    reset_ai_generation_semaphore()
    sem = _get_ai_semaphore()
    initial = sem._value
    with pytest.raises(RuntimeError, match="test error"):
        async with ai_generation_slot():
            assert sem._value == initial - 1
            raise RuntimeError("test error")
    assert sem._value == initial


@pytest.mark.asyncio
async def test_cross_request_total_concurrency_limit() -> None:
    """跨多个并发请求的总 AI 并发不超过配置上限。

    模拟 N 个并发任务同时进入 ai_generation_slot，验证同时持有的最大数
    不超过 AI_CASE_GENERATION_CONCURRENCY。
    """
    reset_ai_generation_semaphore()
    sem = _get_ai_semaphore()
    limit = sem._value
    # 启动 limit * 3 个任务，确保超限部分被阻塞
    task_count = limit * 3

    current_concurrent = 0
    max_concurrent = 0
    lock = threading.Lock()

    async def _worker():
        nonlocal current_concurrent, max_concurrent
        async with ai_generation_slot():
            with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.05)
            with lock:
                current_concurrent -= 1

    await asyncio.gather(*[_worker() for _ in range(task_count)])
    assert max_concurrent <= limit, (
        f"并发数 {max_concurrent} 超过限制 {limit}"
    )
    # 至少应该达到 limit（否则信号量未生效）
    assert max_concurrent == limit, (
        f"未达到预期并发 {limit}，实际 {max_concurrent}（信号量可能未生效）"
    )


@pytest.mark.asyncio
async def test_semaphore_works_in_new_event_loop() -> None:
    """跨事件循环安全：在新事件循环中使用不报错。

    场景：batch_orchestrator 在 iter_async_gen_in_thread 创建的
    独立线程事件循环中运行，threading.Semaphore 跨循环安全。
    """
    reset_ai_generation_semaphore()

    def _run_in_new_loop():
        async def _inner():
            async with ai_generation_slot():
                await asyncio.sleep(0.01)
            return True

        return asyncio.run(_inner())

    # 在独立线程中创建新事件循环运行
    result = await asyncio.to_thread(_run_in_new_loop)
    assert result is True
