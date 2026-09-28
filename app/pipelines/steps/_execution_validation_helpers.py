"""ExecutionValidation 辅助工具模块

集中存放 execution_validation Step 使用的常量与防御性校验函数，
使主 Step 文件保持在 350 行以内，同时便于单元测试独立验证。

内容:
    - 失败类型常量（与 TestCase.execution_failure_type 列保持一致）
    - VALID_FAILURE_TYPES 合法集合
    - 三个 sanitize_* 函数：对外部输入做类型/范围校验后返回安全值
"""
from typing import Any, Optional

from loguru import logger


# 执行失败类型常量
FAILURE_TYPE_ELEMENT_NOT_FOUND = "element_not_found"
FAILURE_TYPE_TIMEOUT = "timeout"
FAILURE_TYPE_ASSERTION_FAILED = "assertion_failed"
FAILURE_TYPE_NETWORK_ERROR = "network_error"
FAILURE_TYPE_OTHER = "other"

# 合法失败类型集合，用于校验外部输入
# 与迁移脚本 alembic/versions/20260624_add_execution_failure_type_and_verified_at.py
# 的 comment 列保持一致：element_not_found/timeout/assertion_failed/network_error/other
VALID_FAILURE_TYPES = frozenset({
    FAILURE_TYPE_ELEMENT_NOT_FOUND,
    FAILURE_TYPE_TIMEOUT,
    FAILURE_TYPE_ASSERTION_FAILED,
    FAILURE_TYPE_NETWORK_ERROR,
    FAILURE_TYPE_OTHER,
})


def sanitize_verified(value: Any) -> Optional[bool]:
    """校验 execution_verified 字段。

    Args:
        value: 外部输入值。

    Returns:
        合法的 bool 值或 None。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    logger.warning(
        "execution_verified 非法类型: {}，已置为 None",
        type(value).__name__,
    )
    return None


def sanitize_ratio(value: Any) -> Optional[float]:
    """校验 element_verified_ratio 字段，约束在 [0.0, 1.0] 范围内。

    Args:
        value: 外部输入值。

    Returns:
        合法的 float 值或 None。
    """
    if value is None:
        return None
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        logger.warning("element_verified_ratio 非法值: {}，已置为 None", value)
        return None
    if ratio < 0.0 or ratio > 1.0:
        logger.warning(
            "element_verified_ratio 越界: {}，已钳制到 [0.0, 1.0]", ratio,
        )
        ratio = max(0.0, min(1.0, ratio))
    return ratio


def sanitize_failure_type(value: Any) -> Optional[str]:
    """校验 execution_failure_type 字段，必须是合法枚举值。

    Args:
        value: 外部输入值。

    Returns:
        合法的失败类型字符串或 None。
    """
    if value is None:
        return None
    if isinstance(value, str) and value in VALID_FAILURE_TYPES:
        return value
    logger.warning("execution_failure_type 非法值: {}，已置为 None", value)
    return None


__all__ = [
    "FAILURE_TYPE_ELEMENT_NOT_FOUND",
    "FAILURE_TYPE_TIMEOUT",
    "FAILURE_TYPE_ASSERTION_FAILED",
    "FAILURE_TYPE_NETWORK_ERROR",
    "FAILURE_TYPE_OTHER",
    "VALID_FAILURE_TYPES",
    "sanitize_verified",
    "sanitize_ratio",
    "sanitize_failure_type",
]
