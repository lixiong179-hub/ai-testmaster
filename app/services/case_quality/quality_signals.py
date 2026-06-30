"""质量信号构建与格式化（Task 16）。

将质量校验问题与维度评分结构化为 quality_signals dict，供
run_quality_feedback_loop 在第 N+1 轮注入重生成 Prompt。

设计要点（历史避坑要点 4）：
- 禁止盲重试：必须通过 quality_signals 传递具体失败原因与低分维度，
  让 AI 在下一轮针对具体问题修复，而非无信息地重复生成。
- 与 QualityScoringService 共享维度名，保证信号与评分口径一致。
"""
from typing import Any, Dict, List, Optional

# 维度得分低于此阈值视为低分维度，需在信号中重点标注修复
LOW_DIMENSION_THRESHOLD = 7.0


def build_quality_signals(
    issues: List[str],
    dim_scores: Optional[Dict[str, float]] = None,
    case: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构建质量信号字典。

    Args:
        issues: validate_single_case_status 返回的问题列表（非空字符串）。
        dim_scores: QualityScoringService.score_dimensions 返回的 7 维度评分。
            为 None 时通过 QualityScoringService 现算，保证信号与当前用例一致。
        case: 当前用例字典，dim_scores 为 None 时用于现算维度评分。

    Returns:
        {"issues": [...], "dim_scores": {...}, "low_dimensions": [...]}
        issues 为去空后的字符串列表；low_dimensions 为得分低于阈值的维度名列表。
    """
    clean_issues: List[str] = []
    for issue in issues or []:
        text = str(issue).strip()
        if text:
            clean_issues.append(text)

    scores = dim_scores
    if scores is None and case is not None:
        from app.services.case_quality.quality_scoring_service import QualityScoringService
        scores = QualityScoringService.score_dimensions(case)
    if not scores:
        scores = {}

    low_dimensions: List[str] = [
        name for name, score in scores.items()
        if isinstance(score, (int, float)) and score < LOW_DIMENSION_THRESHOLD
    ]

    return {
        "issues": clean_issues,
        "dim_scores": dict(scores),
        "low_dimensions": low_dimensions,
    }


def format_quality_signals(signals: Optional[Dict[str, Any]]) -> str:
    """将质量信号格式化为 Prompt 文本段。

    Args:
        signals: build_quality_signals 返回的字典。

    Returns:
        格式化的质量信号文本；signals 为空或无内容时返回空字符串，
        供调用方按需追加到 Prompt（避免注入空段污染 Prompt）。
    """
    if not signals or not isinstance(signals, dict):
        return ""

    issues = signals.get("issues") or []
    dim_scores = signals.get("dim_scores") or {}
    low_dimensions = signals.get("low_dimensions") or []

    if not issues and not dim_scores:
        return ""

    lines: List[str] = [
        "## 质量信号（上轮生成的具体问题，本轮必须逐条修复）"
    ]

    if issues:
        lines.append("### 具体问题")
        for issue in issues:
            lines.append(f"- {issue}")

    if dim_scores:
        lines.append(f"### 维度评分（0-10，低于{LOW_DIMENSION_THRESHOLD:.1f} 需重点修复）")
        for name, score in dim_scores.items():
            marker = " [低于阈值，需修复]" if name in low_dimensions else ""
            lines.append(f"- {name}: {score}{marker}")

    lines.append("请针对以上具体问题逐条修复，禁止忽略或无信息盲重试。")
    return "\n".join(lines)
