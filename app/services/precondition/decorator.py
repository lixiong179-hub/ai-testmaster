
"""前置条件错误处理装饰器。"""
import functools
from typing import Any, Callable

from loguru import logger
from app.services.precondition.models import PreconditionError


def handle_precondition_errors(func: Callable) -> Callable:
    """前置条件错误处理装饰器。

    处理策略:
        - PreconditionError及其子类: 直接抛出，不转换
        - BrowserError: 转换为PreconditionError
        - 其他异常: 转换为PreconditionError，记录完整堆栈
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except PreconditionError:
            raise
        except Exception as e:
            from app.utils.browser_controller_v2 import BrowserError
            if isinstance(e, BrowserError):
                error_msg = f"浏览器操作失败: {str(e)}"
                logger.error(error_msg)
                raise PreconditionError(error_msg) from e
            error_msg = f"{func.__name__} 失败: {str(e)}"
            logger.error(error_msg)
            raise PreconditionError(error_msg) from e
    return wrapper
