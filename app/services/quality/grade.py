"""质量分级工具。

将先验/后验质量分（0-100）映射为 A/B/C/D 等级，规则：
    - A: score >= 85
    - B: 65 <= score < 85
    - C: 45 <= score < 65
    - D: score < 45

另提供 grade_status（4档状态）到字母等级的映射（spec Task 17.3）：
    - A=passed / B=warning / C=pending_review / D=rejected

抽取为共享工具以消除 validate_mixin 与 pipelines._signal_scoring 的重复逻辑。
"""
from typing import Dict, Optional

# 等级阈值常量，便于其他模块引用与测试断言
GRADE_A_THRESHOLD: float = 85.0
GRADE_B_THRESHOLD: float = 65.0
GRADE_C_THRESHOLD: float = 45.0

# 合法等级集合
VALID_GRADES: frozenset[str] = frozenset({"A", "B", "C", "D"})

# grade_status（4档状态）到字母等级的映射（spec Task 17.3）
GRADE_STATUS_TO_LETTER: Dict[str, str] = {
    "passed": "A",
    "warning": "B",
    "pending_review": "C",
    "rejected": "D",
}


def score_to_grade(score: Optional[float]) -> Optional[str]:
    """将质量分映射为 A/B/C/D 等级。

    Args:
        score: 质量分（0-100），None 时返回 None（用于未评分用例）。

    Returns:
        等级字符串 "A"/"B"/"C"/"D"；score 为 None 时返回 None。
    """
    if score is None:
        return None
    if score >= GRADE_A_THRESHOLD:
        return "A"
    if score >= GRADE_B_THRESHOLD:
        return "B"
    if score >= GRADE_C_THRESHOLD:
        return "C"
    return "D"


def grade_status_to_letter(status: Optional[str]) -> Optional[str]:
    """将 grade_status（4档状态）映射为 A/B/C/D 等级。

    映射关系（spec Task 17.3）：A=passed/B=warning/C=pending_review/D=rejected。

    Args:
        status: grade_status 状态字符串（passed/warning/pending_review/rejected），
            None 时返回 None（用于未评分用例）。

    Returns:
        等级字符串 "A"/"B"/"C"/"D"；status 为 None 或非法值时返回 None。
    """
    if status is None:
        return None
    return GRADE_STATUS_TO_LETTER.get(status)
