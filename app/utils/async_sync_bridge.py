"""
异步/同步桥接工具

性能优化：将 async 端点中调用 sync SQLAlchemy Session 的代码块迁移到独立线程，
避免阻塞 ASGI 事件循环。

背景：
    项目渐进式 async 迁移中，部分 service 仍是 async def 但内部使用 sync_db.query()
    直接执行同步 IO。在 async endpoint 中 await 这类 service 时，sync_db.query() 会
    阻塞主事件循环，影响并发吞吐。

    本模块提供两种桥接模式：
    1. run_async_coro_in_thread: 适用于返回单值的 async 函数（如 get_context_for_generation）
    2. iter_async_gen_in_thread: 适用于 async generator（如 generate_test_cases_batch）

    两种模式都在独立线程中创建新事件循环执行 async 代码，主事件循环通过
    asyncio.to_thread / queue 接收结果，不再阻塞。

约束：
    - 传入的 coro/agen 中如果使用了主线程创建的 AsyncSession，会因跨事件循环失败；
      仅适用于使用 sync Session（PrimarySessionLocal）的场景。
    - 传入的 coro 中如已捕获异常，应通过返回值或 raise 传递到主线程。
"""
from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, AsyncGenerator, Awaitable, Callable, Coroutine, TypeVar

from loguru import logger

T = TypeVar("T")


async def run_async_coro_in_thread(coro: Coroutine[Any, Any, T]) -> T:
    """在独立线程中运行 async 协程，避免其内部 sync IO 阻塞主事件循环。

    适用场景：service 是 async def 但内部使用 sync Session.query()。
    在独立线程中创建新事件循环执行 coro，主事件循环通过 asyncio.to_thread 等待。

    Args:
        coro: 待执行的协程（已构造但未 await）

    Returns:
        协程的返回值

    Raises:
        协程内抛出的任何异常都会传递到调用方
    """
    def _runner() -> T:
        return asyncio.run(coro)

    return await asyncio.to_thread(_runner)


async def iter_async_gen_in_thread(
    agen_factory: Callable[[], AsyncGenerator[T, None]],
) -> AsyncGenerator[T, None]:
    """在独立线程中运行 async generator，主线程通过队列消费产物。

    适用场景：service 是 async generator（如 generate_test_cases_batch），
    内部使用 sync Session.query() 阻塞主事件循环。

    Args:
        agen_factory: 返回 async generator 的工厂函数（无参数调用）。
            使用工厂而非直接传入 generator 是因为 generator 必须在
            其所属事件循环内创建并迭代。

    Yields:
        async generator 产生的每一项

    Raises:
        generator 内抛出的异常会通过队列传递到主线程并重新抛出
    """
    # 使用 queue.Queue 而非 asyncio.Queue，因为生产者在线程中
    item_queue: "queue.Queue[Any]" = queue.Queue()
    # 哨兵对象，标识 generator 结束
    _SENTINEL = object()
    # 异常传递容器
    error_box: list[BaseException] = []

    def _producer() -> None:
        """在独立线程中创建事件循环并迭代 async generator。"""
        async def _consume() -> None:
            agen = agen_factory()
            try:
                async for item in agen:
                    item_queue.put(item)
            except BaseException as e:  # noqa: BLE001 - 需捕获所有异常传递到主线程
                error_box.append(e)
            finally:
                item_queue.put(_SENTINEL)

        try:
            asyncio.run(_consume())
        except BaseException as e:  # noqa: BLE001
            # asyncio.run 自身抛出的异常（如 coroutine never awaited）
            if not error_box:
                error_box.append(e)
            item_queue.put(_SENTINEL)

    producer_thread = threading.Thread(target=_producer, daemon=True)
    producer_thread.start()

    loop = asyncio.get_event_loop()
    try:
        while True:
            # 通过 run_in_executor 拉取队列项，避免阻塞主事件循环
            item = await loop.run_in_executor(None, item_queue.get)
            if item is _SENTINEL:
                break
            yield item
    finally:
        # 确保线程退出
        if producer_thread.is_alive():
            producer_thread.join(timeout=1.0)
        if error_box:
            raise error_box[0]
