"""异步任务桥接工具（Phase 1 Task 3）

业务用途：Celery Worker 是同步进程，需将 async def 任务函数桥接为同步调用。
设计原则：单 Worker 内 asyncio.run 串行，禁止嵌套事件循环。

依赖：asyncio（标准库）
"""
import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def async_task(coro_func: Callable[..., T]) -> Callable[..., T]:
    """将 async def 包装为 Celery 同步任务。

    边界场景：
    1. 已存在事件循环时（如嵌套调用）使用 run_until_complete 兜底；
    2. 异步函数异常透传给 Celery 任务基类处理。

    用法：
        @async_task
        async def my_task(x: int) -> int:
            return x + 1

        # 等价于：
        def my_task(x: int) -> int:
            return asyncio.run(_original_coro(x))
    """

    @wraps(coro_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 嵌套场景：创建新事件循环避免冲突
                logger.warning("检测到嵌套事件循环，创建新循环执行任务")
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(coro_func(*args, **kwargs))
                finally:
                    new_loop.close()
        except RuntimeError:
            pass  # 无事件循环，走 asyncio.run 路径
        return asyncio.run(coro_func(*args, **kwargs))

    return wrapper
