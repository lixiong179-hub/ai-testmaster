"""辅助函数 - 流程图 Prompt 构建所需的工具函数。

提供:
    - _safe_int: 安全整数转换
    - _find_main_step: 主干步骤查找
"""
from typing import List, Dict, Any, Optional

from loguru import logger


def _safe_int(value: Any) -> Optional[int]:
    """安全地将值转换为整数。

    Args:
        value: 待转换的值，支持 int/str 类型。

    Returns:
        转换后的整数，失败时返回 None。
    """
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"连线source/target格式错误: {value}")
        return None


def _find_main_step(main_nodes: List[Dict[str, Any]], screen_id: int) -> str:
    """在主干流程中查找指定 screen_id 对应的步骤序号。

    Args:
        main_nodes: 主干流程节点列表（已按 screen_order 排序）。
        screen_id: 待查找的屏幕 ID。

    Returns:
        步骤序号字符串，未找到时返回 '?'。
    """
    for i, node in enumerate(main_nodes, 1):
        if node.get('screen_id') == screen_id:
            return str(i)
    return '?'
