"""用例重复校验器。

校验用例标题与已有用例的相似度，超过阈值时标记为 pending_review。
使用简单的字符级 Jaccard 相似度计算。
"""
from typing import Dict, List, Optional, Set

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
)


class DuplicationValidator(BaseValidator):
    """用例重复校验器，基于标题相似度检测重复用例。"""

    def __init__(self, similarity_threshold: float = 0.9) -> None:
        self.similarityThreshold = similarity_threshold

    @staticmethod
    def _char_ngrams(text: str, n: int = 2) -> Set[str]:
        """生成字符n-gram集合。"""
        text = text.strip()
        if len(text) < n:
            return {text} if text else set()
        return {text[i:i + n] for i in range(len(text) - n + 1)}

    def _jaccard_similarity(self, text_a: str, text_b: str) -> float:
        """计算两个文本的Jaccard相似度。"""
        set_a = self._char_ngrams(text_a)
        set_b = self._char_ngrams(text_b)
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return intersection / union

    def validate(
        self,
        case_data: Dict,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """校验用例重复。"""
        ctx = context or {}
        threshold = ctx.get("duplication_threshold", self.similarityThreshold)
        existing_titles = ctx.get("existing_titles") or []

        title = (case_data.get("title") or "").strip()
        if not title or not existing_titles:
            return ValidationResult(status="passed", issues=[])

        similar: List[str] = []
        for existing in existing_titles:
            existing_str = str(existing).strip()
            if not existing_str:
                continue
            sim = self._jaccard_similarity(title, existing_str)
            if sim >= threshold:
                similar.append(existing_str)

        if not similar:
            return ValidationResult(status="passed", issues=[])

        issue = ValidationIssue(
            field="title",
            message=(
                f"标题与已有用例相似度≥{threshold:.0%}，"
                f"相似用例: {similar[:3]}"
            ),
            severity="pending_review",
        )
        return ValidationResult(status="pending_review", issues=[issue])
