"""prior 质量评分函数（0-25 分制精排序）。

正则模式统一从 quality_scoring_constants 导入，与 grade_status /
score_dimensions 共享底层模糊判定规则。本模块保留 prior 特有的
长度细分、堆砌降分、步骤序号连续性等精排序逻辑。
"""
import re
from typing import Any

from app.services.case_quality.quality_scoring_constants import (
    EXPECTED_VAGUE_PATTERNS,
    MANUAL_JUDGMENT_PATTERN,
    QUANTIFIABLE_PATTERNS,
    STEP_UNCERTAINTY_PATTERN,
    TITLE_ATOMICITY_VIOLATION_PATTERN,
    TITLE_VAGUE_PATTERNS,
    VERB_STACKING_PATTERN,
)


def _score_title(title: str) -> float:
    if not title or not title.strip():
        return 0.0

    title = title.strip()
    base_score: float

    if TITLE_VAGUE_PATTERNS.match(title):
        base_score = 5.0
    elif TITLE_ATOMICITY_VIOLATION_PATTERN.search(title):
        base_score = 5.0
    else:
        length = len(title)
        if length < 15:
            base_score = 10.0
        elif length > 40:
            base_score = 15.0
        else:
            base_score = 25.0

    if VERB_STACKING_PATTERN.search(title) and len(title) > 30 and base_score >= 15.0:
        return 15.0

    return base_score


def _extract_step_number(step: dict) -> int | None:
    step_val = step.get("step")
    if step_val is None:
        return None
    if isinstance(step_val, int):
        return step_val
    if isinstance(step_val, str):
        match = re.search(r'\d+', step_val)
        if match:
            return int(match.group())
    return None


def _score_steps(steps: Any, case_type: str = "") -> float:
    if not steps:
        return 0.0

    if isinstance(steps, list):
        count = len(steps)
    elif isinstance(steps, str):
        return 5.0
    else:
        return 5.0

    if count <= 0:
        return 0.0
    if count == 1:
        return 5.0

    complete_count = 0
    step_numbers: list[int] = []
    uncertainty_deduction = 0.0
    manual_judgment_deduction = 0.0

    for s in steps:
        if isinstance(s, dict):
            has_action = bool(s.get("action") or s.get("description"))
            has_expected = bool(s.get("expected_result") or s.get("expected"))
            if has_action and has_expected:
                complete_count += 1
            num = _extract_step_number(s)
            if num is not None:
                step_numbers.append(num)
            action_text = (s.get("action") or s.get("description") or "")
            if STEP_UNCERTAINTY_PATTERN.search(action_text):
                uncertainty_deduction += 3.0
            if case_type == "ui_automation" and MANUAL_JUDGMENT_PATTERN.search(action_text):
                manual_judgment_deduction += 5.0

    completeness_ratio = complete_count / count if count > 0 else 0.0

    if count == 2:
        score = round(10.0 + 10.0 * completeness_ratio, 1)
    else:
        score = round(15.0 + 10.0 * completeness_ratio, 1)

    if count > 7:
        excess = count - 7
        step_count_deduction = min(excess * 1.5, 6.0)
        score = max(0.0, score - step_count_deduction)

    if step_numbers and len(step_numbers) >= 2:
        sorted_nums = sorted(set(step_numbers))
        max_num = sorted_nums[-1]
        expected_total = max_num
        actual_total = len(sorted_nums)
        missing_count = expected_total - actual_total
        if missing_count > 0:
            deduction = min(missing_count, 5)
            score = max(0.0, score - deduction)

    uncertainty_deduction = min(uncertainty_deduction, 6.0)
    score = max(0.0, score - uncertainty_deduction)

    manual_judgment_deduction = min(manual_judgment_deduction, 10.0)
    score = max(0.0, score - manual_judgment_deduction)

    return score


def _score_expected_result(expected: str) -> float:
    if not expected or not expected.strip():
        return 0.0

    if QUANTIFIABLE_PATTERNS.search(expected):
        return 25.0

    if EXPECTED_VAGUE_PATTERNS.search(expected):
        return 5.0

    return 15.0


def _score_precondition(precondition: str) -> float:
    if not precondition or not precondition.strip():
        return 0.0

    pc_lower = precondition.lower()

    has_network = bool(re.search(r'(网络|network|浏览器网络|设备网络|wifi|联网)', pc_lower))
    has_login = bool(re.search(r'(登录|login|已登录|账号已登录|token|auth|鉴权|bearer|已授权)', pc_lower))
    has_permission = bool(re.search(r'(权限|permission|授权|已授权|角色|role)', pc_lower))

    if has_network and has_login and has_permission:
        score = 25.0
    elif has_network and has_login:
        score = 20.0
    elif has_login:
        score = 15.0
    elif has_network:
        score = 10.0
    else:
        score = 5.0

    has_env = bool(re.search(
        r'(chrome|firefox|safari|edge|iPhone|iPad|Android|Windows|Mac|iOS|浏览器|设备|操作系统|系统版本)',
        pc_lower,
    ))
    if has_env and score < 25.0:
        score = min(25.0, score + 2.0)

    return score
