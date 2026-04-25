"""覆盖度评估Mixin - 评估测试用例的功能覆盖度。

性能优化（T15）：
    _analyze_coverage 支持预取数据上下文（coverage_context），
    避免循环内重复查询 ElementLocator。
"""
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from app.models.test_case import TestStep
from app.models.element_locator import ElementLocator
from app.services.case_quality.models import CoverageScore


class CoverageMixin:

    def _analyze_coverage(
        self,
        steps: List[TestStep],
        coverage_context: Optional[Dict[str, Any]] = None,
    ) -> CoverageScore:
        """计算覆盖率，支持传入预取数据上下文。

        Args:
            steps: 测试步骤列表。
            coverage_context: 预取的覆盖率数据上下文，包含：
                - locators_by_step: Dict[int, List[ElementLocator]]
                为None时回退到逐条查询模式。

        Returns:
            CoverageScore: 覆盖率评分。
        """
        score = CoverageScore()

        locators_by_step: Optional[Dict[int, List[ElementLocator]]] = (
            coverage_context.get("locators_by_step") if coverage_context else None
        )

        step_ids = [step.id for step in steps]

        if locators_by_step is not None:
            # 使用预取数据：从映射中筛选当前步骤的定位器
            locators: List[ElementLocator] = []
            for sid in step_ids:
                locators.extend(locators_by_step.get(sid, []))
        else:
            # 回退到数据库查询
            locators = (
                self.db.query(ElementLocator).filter(
                    ElementLocator.step_id.in_(step_ids)
                ).all() if step_ids else []
            )

        covered_step_ids: Set[int] = set()
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

        logger.info(
            f"覆盖率分析: 总元素={score.total_elements}, "
            f"已覆盖={score.covered_elements}, "
            f"覆盖率={score.coverage_rate:.2%}, 等级={score.level}"
        )
        return score
