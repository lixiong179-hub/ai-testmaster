"""覆盖度评估Mixin - 评估测试用例的功能覆盖度。
"""
from typing import Dict, Any, List
from loguru import logger

from app.models.test_case import TestStep
from app.models.element_locator import ElementLocator
from app.services.case_quality.models import CoverageScore


class CoverageMixin:

    def _analyze_coverage(self, steps: List[TestStep]) -> CoverageScore:
        score = CoverageScore()

        step_ids = [step.id for step in steps]
        locators = self.db.query(ElementLocator).filter(
            ElementLocator.step_id.in_(step_ids)
        ).all() if step_ids else []

        covered_step_ids = set()
        for locator in locators:
            if locator.step_id:
                covered_step_ids.add(locator.step_id)

        score.total_elements = len(steps)
        score.covered_elements = len(covered_step_ids)
        score.uncovered_elements = score.total_elements - score.covered_elements

        if score.total_elements > 0:
            score.coverage_rate = score.covered_elements / score.total_elements
        else:
            score.coverage_rate = 0.0

        coverage_points = score.coverage_rate * 10
        score.score = round(coverage_points, 2)

        if score.coverage_rate >= 0.9:
            score.level = "high"
        elif score.coverage_rate >= 0.7:
            score.level = "moderate"
        elif score.coverage_rate >= 0.5:
            score.level = "low"
        else:
            score.level = "very_low"

        logger.info(f"覆盖率分析: 总元素={score.total_elements}, 已覆盖={score.covered_elements}, 覆盖率={score.coverage_rate:.2%}, 等级={score.level}")
        return score
