"""测试用例字段级质量校验器。

从 quality_validator.py 拆分，包含标题、前置条件、预期结果与
case_category 单字段校验。所有函数均为模块级纯函数。
"""
from typing import Tuple

from app.services.case_quality.quality_scoring_constants import (
    EXPECTED_VAGUE_WORDS,
    LOGGED_IN_MARKERS,
    LOGGED_OUT_MARKERS,
    TITLE_ATOMICITY_VIOLATION_PATTERN,
    TITLE_VAGUE_WORDS,
    VALID_CASE_CATEGORIES,
)


def validate_title(title: str) -> Tuple[bool, str]:
    """校验标题质量。

    Args:
        title: 用例标题

    Returns:
        (是否通过, 问题描述)
    """
    if not title or not title.strip():
        return False, "标题为空"
    title = title.strip()
    if len(title) < 8:
        return False, f"标题过短（{len(title)}字），需≥8字: {title}"
    if len(title) > 50:
        return False, f"标题过长（{len(title)}字），需≤50字: {title}"
    for word in TITLE_VAGUE_WORDS:
        if word in title:
            return False, f"标题包含模糊词「{word}」: {title}"
    if TITLE_ATOMICITY_VIOLATION_PATTERN.search(title):
        return False, f"标题违反原子性原则（混合主流程与分支/旁路逻辑），应拆分为独立用例: {title}"
    return True, ""


def validate_precondition(precondition: str) -> Tuple[bool, str]:
    """校验前置条件完整性。

    Args:
        precondition: 前置条件文本

    Returns:
        (是否通过, 问题描述)
    """
    if not precondition or not precondition.strip():
        return False, "前置条件为空"
    precondition = precondition.strip()
    has_logged_in = any(marker in precondition for marker in LOGGED_IN_MARKERS)
    has_logged_out = any(marker in precondition for marker in LOGGED_OUT_MARKERS)
    if not has_logged_in and not has_logged_out:
        return False, "前置条件缺少登录状态"
    # 互斥校验：同时出现"已登录"与"未登录"标记属于语义矛盾（如"账号已登录状态为未登录"），
    # 旧实现仅用 any() 命中即放行，无法发现此类矛盾。
    if has_logged_in and has_logged_out:
        return False, "前置条件登录状态自相矛盾（同时含已登录与未登录标记）"
    if len(precondition) < 15:
        return False, f"前置条件过于简单（{len(precondition)}字）: {precondition}"
    return True, ""


def validate_expected_result(expected_result: str) -> Tuple[bool, str]:
    """校验总体预期结果质量。

    检查策略：
        1. 非空且 ≥10 字
        2. 精确匹配模糊短语（如'正常显示''提交成功'）

    Args:
        expected_result: 总体预期结果文本

    Returns:
        (是否通过, 问题描述)
    """
    if not expected_result or not expected_result.strip():
        return False, "总体预期结果为空"
    expected_result = expected_result.strip()
    if len(expected_result) < 10:
        return False, f"预期结果过短（{len(expected_result)}字）: {expected_result}"
    for word in EXPECTED_VAGUE_WORDS:
        if word in expected_result:
            return False, f"预期结果包含模糊短语「{word}」: {expected_result}"
    return True, ""


def validate_case_category(case_category: str) -> Tuple[bool, str]:
    """校验 case_category 合法性。

    Args:
        case_category: 用例分类

    Returns:
        (是否通过, 问题描述)
    """
    if not case_category:
        return False, "case_category 为空"
    if case_category not in VALID_CASE_CATEGORIES:
        return False, f"case_category 非法值「{case_category}」，合法值: {sorted(VALID_CASE_CATEGORIES)}"
    return True, ""
