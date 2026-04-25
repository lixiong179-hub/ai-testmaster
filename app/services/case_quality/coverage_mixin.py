"""覆盖度评估Mixin - 评估测试用例的多维功能覆盖度。

T1 多维覆盖率（替代旧版单一 locator 覆盖率）：
    coverage_rate = requirement_coverage × 0.3
                  + ui_element_coverage × 0.3
                  + locator_coverage × 0.4

    权重设计 rationale（v2 重校准）：
        - requirement_coverage 是二元变量（0 或 1），过高权重会导致单一开关
          支配评分（每个用例只要忘绑测试点就掉一档），故压到 0.3
        - ui_element_coverage 是基于子串匹配的近似指标，存在解析噪声，
          保持中等权重 0.3
        - locator_coverage 反映"用例能否自动化执行"，是本平台核心价值，
          也是连续型可信指标，提升至 0.4

    维度可用性：
        - requirement_coverage 可用：项目至少有 1 个测试点
        - ui_element_coverage 可用：项目至少有 1 个 UI 元素标签
                                    且用例至少有 1 步含 target_element
        - locator_coverage 可用：用例至少有 1 个步骤

    向后兼容退化：缺失维度时按可用维度的权重重正（避免单维满分导致整体偏低）。
    极端情况（项目无需求 + 无 UI 原型）自动退化为 locator-only。

T15 性能优化：
    支持通过 coverage_context 传入预取数据，避免循环内重复查询数据库。
"""
from typing import Dict, Any, List, Optional, Set, Tuple
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.services.case_quality.models import CoverageScore


# 三维度加权 v2（重校准：需求 30% + UI 30% + 定位 40%，总和 1.0）
# 调整原因详见模块 docstring。修改权重需同步更新测试期望值。
_REQUIREMENT_WEIGHT = 0.3
_UI_ELEMENT_WEIGHT = 0.3
_LOCATOR_WEIGHT = 0.4

# 需求覆盖连续化：当前数据模型仅支持单用例关联 1 个 TestPoint，
# 因此用 TestPoint.priority 将二元“是否绑定”升级为连续“绑定质量”。
_TEST_POINT_PRIORITY_WEIGHTS = {
    1: 1.0,  # 高优测试点
    2: 0.7,  # 中优测试点
    3: 0.4,  # 低优测试点
}
_DEFAULT_TEST_POINT_PRIORITY_WEIGHT = 0.4

# UI 元素匹配最小长度阈值：低于此长度的 label 视为噪音，不参与子串匹配
# 防止 "登录" 误命中 target="退出登录" 之类的短词包含
_MIN_UI_LABEL_LEN = 2


class CoverageMixin:

    def _analyze_coverage(
        self,
        steps: List[TestStep],
        coverage_context: Optional[Dict[str, Any]] = None,
        case: Optional[TestCase] = None,
    ) -> CoverageScore:
        """计算多维覆盖率。

        Args:
            steps: 测试步骤列表。
            coverage_context: 预取数据上下文，可选键：
                - locators_by_step: Dict[int, List[ElementLocator]]
                - project_test_point_priorities: Dict[int, int] 项目下测试点 ID -> priority
                - project_ui_labels: Set[str]        项目下全部 UI 元素标签（小写）
            case: 当前用例对象。提供 case.test_point_id 用于需求覆盖率计算；
                  缺省时该维度始终为 0（视为未关联测试点）。

        Returns:
            CoverageScore: 含三维度分解与加权综合分。
        """
        score = CoverageScore()
        score.total_elements = len(steps)

        ctx: Dict[str, Any] = coverage_context or {}

        # ---------- 维度 1：requirement_coverage ----------
        req_rate, req_details = self._calc_requirement_coverage(case=case, ctx=ctx)
        score.requirement_coverage_rate = req_rate
        score.requirement_details = req_details

        # ---------- 维度 2：ui_element_coverage ----------
        ui_rate, ui_details = self._calc_ui_element_coverage(steps=steps, ctx=ctx)
        score.ui_element_coverage_rate = ui_rate
        score.ui_element_details = ui_details

        # ---------- 维度 3：locator_coverage ----------
        loc_rate, loc_details = self._calc_locator_coverage(steps=steps, ctx=ctx)
        score.locator_coverage_rate = loc_rate
        score.locator_details = loc_details
        # 兼容字段：保持旧 API 语义指向 locator 维度
        score.covered_elements = loc_details.get("covered_step_count", 0)
        score.uncovered_elements = score.total_elements - score.covered_elements

        # ---------- 综合：加权 + 动态重正 ----------
        weighted_rate = self._aggregate_coverage(
            req_rate=req_rate, req_available=req_details.get("available", False),
            ui_rate=ui_rate, ui_available=ui_details.get("available", False),
            loc_rate=loc_rate, loc_available=loc_details.get("available", False),
        )
        score.coverage_rate = weighted_rate
        score.score = round(weighted_rate * 10, 2)
        score.level = self._coverage_level(weighted_rate)

        logger.info(
            f"覆盖率分析: 综合={weighted_rate:.2%} "
            f"(req={req_rate:.2%} ui={ui_rate:.2%} loc={loc_rate:.2%}), "
            f"等级={score.level}"
        )
        return score

    # ============================================================
    # 三维度独立计算
    # ============================================================

    @staticmethod
    def _calc_requirement_coverage(
        case: Optional[TestCase],
        ctx: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """需求覆盖率（连续）：按关联测试点优先级赋予 1.0/0.7/0.4 分值。

        当前 TestCase 仅支持单个 test_point_id，因此无法按“关联测试点数”
        计算连续值；改用 TestPoint.priority 表达该关联的业务重要性。
        """
        project_point_priorities: Dict[int, int] = (
            ctx.get("project_test_point_priorities") or {}
        )
        project_total = len(project_point_priorities)

        case_test_point_id = getattr(case, "test_point_id", None) if case else None
        priority = (
            project_point_priorities.get(case_test_point_id)
            if case_test_point_id is not None else None
        )
        has_link = priority is not None

        # 维度可用：项目至少有一个测试点（否则该项目无法评估需求覆盖）
        available = project_total > 0
        rate = (
            _TEST_POINT_PRIORITY_WEIGHTS.get(
                priority, _DEFAULT_TEST_POINT_PRIORITY_WEIGHT
            )
            if has_link else 0.0
        )

        return rate, {
            "available": available,
            "has_test_point_link": has_link,
            "case_test_point_id": case_test_point_id,
            "test_point_priority": priority,
            "priority_weight": rate if has_link else 0.0,
            "project_total_test_points": project_total,
            "scoring_mode": "priority_weighted_single_link",
        }

    @staticmethod
    def _calc_ui_element_coverage(
        steps: List[TestStep],
        ctx: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """UI 元素覆盖率：步骤的 target_element 命中项目 UI 元素标签的比例。

        分母为"含 target_element 的步骤数"，未填 target_element 的步骤不计入分母。
        匹配规则（详见 _is_ui_match）：
            - 大小写不敏感的双向子串包含
            - label 长度 < _MIN_UI_LABEL_LEN 时必须精确相等（避免短词误命中）
        """
        ui_labels: Set[str] = ctx.get("project_ui_labels") or set()
        total_labels = len(ui_labels)

        steps_with_target = 0
        matched_steps = 0
        for step in steps:
            target = (getattr(step, "target_element", None) or "").strip().lower()
            if not target:
                continue
            steps_with_target += 1
            if total_labels > 0 and any(
                CoverageMixin._is_ui_match(target, lbl) for lbl in ui_labels
            ):
                matched_steps += 1

        # 维度可用：项目有 UI 标签 且 用例至少有 1 步含 target_element
        available = total_labels > 0 and steps_with_target > 0
        rate = (matched_steps / steps_with_target) if steps_with_target > 0 else 0.0

        return rate, {
            "available": available,
            "total_ui_labels": total_labels,
            "steps_with_target": steps_with_target,
            "matched_steps": matched_steps,
        }

    @staticmethod
    def _is_ui_match(target: str, label: str) -> bool:
        """判断步骤 target_element 是否命中 UI label。

        匹配策略：
            - target / label 均为非空字符串（已在上游 lower/strip）
            - label 长度 < _MIN_UI_LABEL_LEN：仅接受精确相等（避免 "是" 误命中 "是否提交"）
            - 否则：双向子串包含（target 含 label 或 label 含 target）

        抽出为独立函数便于未来替换为更复杂的匹配策略（编辑距离、embedding 等）。
        """
        if not target or not label:
            return False
        if len(label) < _MIN_UI_LABEL_LEN:
            return target == label
        return label in target or target in label

    def _calc_locator_coverage(
        self,
        steps: List[TestStep],
        ctx: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """定位器覆盖率：含定位器记录的步骤数 / 总步骤数（旧版语义）。"""
        total_steps = len(steps)
        if total_steps == 0:
            return 0.0, {
                "available": False,
                "covered_step_count": 0,
                "total_step_count": 0,
            }

        step_ids = [s.id for s in steps]
        locators_by_step: Optional[Dict[int, List[ElementLocator]]] = ctx.get(
            "locators_by_step"
        )

        if locators_by_step is not None:
            locators: List[ElementLocator] = []
            for sid in step_ids:
                locators.extend(locators_by_step.get(sid, []))
        else:
            locators = (
                self.db.query(ElementLocator)
                .filter(ElementLocator.step_id.in_(step_ids))
                .all()
            )

        covered_step_ids: Set[int] = {
            loc.step_id for loc in locators if loc.step_id is not None
        }
        covered_count = len(covered_step_ids)
        rate = covered_count / total_steps

        return rate, {
            "available": True,  # 只要有步骤，locator 维度始终可用
            "covered_step_count": covered_count,
            "total_step_count": total_steps,
        }

    # ============================================================
    # 加权聚合 + 等级判定
    # ============================================================

    @staticmethod
    def _aggregate_coverage(
        req_rate: float, req_available: bool,
        ui_rate: float, ui_available: bool,
        loc_rate: float, loc_available: bool,
    ) -> float:
        """加权聚合三维覆盖率。

        策略：动态权重重正
            available_weight_sum = Σ(w_d for d in 可用维度)
            rate = Σ(rate_d × w_d for d in 可用维度) / available_weight_sum

        优势：
            - 维度齐全时 = 0.5*req + 0.3*ui + 0.2*loc（产品规约）
            - 维度缺失时按剩余权重重正，避免"无需求数据导致单维满分但综合偏低"
            - 全部维度都不可用时返回 0
        """
        contributions: List[Tuple[float, float]] = []
        if req_available:
            contributions.append((req_rate, _REQUIREMENT_WEIGHT))
        if ui_available:
            contributions.append((ui_rate, _UI_ELEMENT_WEIGHT))
        if loc_available:
            contributions.append((loc_rate, _LOCATOR_WEIGHT))

        if not contributions:
            return 0.0

        weight_sum = sum(w for _, w in contributions)
        weighted = sum(r * w for r, w in contributions)
        return weighted / weight_sum if weight_sum > 0 else 0.0

    @staticmethod
    def _coverage_level(rate: float) -> str:
        """覆盖率等级（与旧版阈值保持一致）。"""
        if rate >= 0.9:
            return "high"
        if rate >= 0.7:
            return "moderate"
        if rate >= 0.5:
            return "low"
        return "very_low"
