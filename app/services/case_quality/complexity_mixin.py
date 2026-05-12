"""复杂度评估Mixin - 评估测试用例的步骤复杂度。
"""
from typing import List
from loguru import logger

from app.models.test_case import TestStep, TestCasePreconditionStep
from app.services.case_quality.models import ComplexityScore


class ComplexityMixin:

    def _analyze_complexity(self, steps: List[TestStep], precondition_steps: List[TestCasePreconditionStep]) -> ComplexityScore:
        score = ComplexityScore()

        score.step_count = len(steps)
        score.precondition_count = len(precondition_steps)

        action_types = set()
        for step in steps:
            action = step.action.lower()
            if "点击" in action or "click" in action:
                action_types.add("click")
            elif "输入" in action or "填写" in action or "input" in action:
                action_types.add("input")
            elif "验证" in action or "检查" in action or "verify" in action:
                action_types.add("verify")
                score.has_verification = True
            elif "验证码" in action or "captcha" in action:
                action_types.add("captcha")
                score.has_captcha = True
            elif "导航" in action or "访问" in action or "navigate" in action:
                action_types.add("navigate")
            elif "等待" in action or "wait" in action:
                action_types.add("wait")
            elif "滚动" in action or "scroll" in action:
                action_types.add("scroll")
            elif "悬停" in action or "hover" in action:
                action_types.add("hover")
            elif "选择" in action or "select" in action:
                action_types.add("select")

        score.action_variety = len(action_types)

        complexity_points = 0.0

        if score.step_count <= 3:
            complexity_points += 1
        elif score.step_count <= 6:
            complexity_points += 2
        elif score.step_count <= 10:
            complexity_points += 3
        else:
            complexity_points += 5

        complexity_points += min(score.action_variety * 0.5, 3)
        complexity_points += min(score.precondition_count * 0.5, 2)

        if score.has_verification:
            complexity_points += 1
        if score.has_captcha:
            complexity_points += 2

        score.score = min(complexity_points, 10)

        if score.score <= 2:
            score.level = "simple"
        elif score.score <= 4:
            score.level = "moderate"
        elif score.score <= 7:
            score.level = "complex"
        else:
            score.level = "very_complex"

        logger.info(f"复杂度分析: 步骤数={score.step_count}, 动作种类={score.action_variety}, 得分={score.score}, 等级={score.level}")
        return score
