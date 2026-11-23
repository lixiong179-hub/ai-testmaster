"""复杂度评估Mixin - 评估测试用例的步骤复杂度。"""

from loguru import logger

from app.models.test_case import TestStep, TestCasePreconditionStep
from app.services.case_quality.models import ComplexityScore

# 动作关键词表：顺序即优先级（先命中先生效），与步骤动作的中英文别名一一对应
_ACTION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("click", ("点击", "click")),
    ("input", ("输入", "填写", "input")),
    ("captcha", ("验证码", "captcha")),
    ("verify", ("验证", "检查", "verify")),
    ("navigate", ("导航", "访问", "navigate")),
    ("wait", ("等待", "wait")),
    ("scroll", ("滚动", "scroll")),
    ("hover", ("悬停", "hover")),
    ("select", ("选择", "select")),
)


def _classify_step_action(action: str) -> str | None:
    """按关键词优先级归类单个步骤动作，未命中返回 None。"""
    lowered = (action or "").lower()
    for action_key, keywords in _ACTION_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return action_key
    return None


class ComplexityMixin:
    def _analyze_complexity(
        self, steps: list[TestStep], precondition_steps: list[TestCasePreconditionStep]
    ) -> ComplexityScore:
        score = ComplexityScore()

        score.step_count = len(steps)
        score.precondition_count = len(precondition_steps)

        action_types = self._collect_action_types(steps)
        score.action_variety = len(action_types)
        score.has_captcha = "captcha" in action_types
        score.has_verification = "verify" in action_types

        score.score = self._compute_complexity_points(score)
        score.level = self._complexity_level(score.score)

        logger.info(
            f"复杂度分析: 步骤数={score.step_count}, 动作种类={score.action_variety}, 得分={score.score}, 等级={score.level}"
        )
        return score

    @staticmethod
    def _collect_action_types(steps: list[TestStep]) -> set[str]:
        """收集步骤中出现的动作类别集合（同一类别只计一次）。"""
        action_types: set[str] = set()
        for step in steps:
            action_key = _classify_step_action(step.action)
            if action_key:
                action_types.add(action_key)
        return action_types

    def _compute_complexity_points(self, score: ComplexityScore) -> float:
        """复杂度得分：步骤数基线 + 动作种类/前置条件加权 + 验证与验证码加成，封顶 10。"""
        points = self._step_count_points(score.step_count)
        points += min(score.action_variety * 0.5, 3)
        points += min(score.precondition_count * 0.5, 2)
        if score.has_verification:
            points += 1
        if score.has_captcha:
            points += 2
        return min(points, 10)

    @staticmethod
    def _step_count_points(step_count: int) -> float:
        """步骤数分段基线分。"""
        if step_count <= 3:
            return 1.0
        if step_count <= 5:
            return 2.0
        if step_count <= 7:
            return 3.0
        return 5.0

    @staticmethod
    def _complexity_level(score_value: float) -> str:
        """按最终得分映射复杂度等级。"""
        if score_value <= 2:
            return "simple"
        if score_value <= 4:
            return "moderate"
        if score_value <= 7:
            return "complex"
        return "very_complex"
