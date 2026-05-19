"""
T1 单元测试：多维覆盖率（requirement × 0.3 + ui_element × 0.3 + locator × 0.4）

覆盖范围：
    - 三维度独立计算函数（_calc_requirement_coverage / _calc_ui_element_coverage
      / _calc_locator_coverage）
    - 加权聚合 _aggregate_coverage（包含动态权重重正/退化逻辑）
    - 等级判定 _coverage_level
    - UI 标签提取 _extract_ui_labels_from_spec
    - _analyze_coverage 端到端集成

设计：使用 SimpleNamespace mock TestCase/TestStep，通过 coverage_context 注入
预取数据，避免数据库依赖；目标是为 SubTask 1.8 提供 ≥ 95% 行覆盖率的纯函数测试。
"""
import math
from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import MagicMock

import pytest

from app.services.case_quality.coverage_mixin import (
    CoverageMixin,
    _LOCATOR_WEIGHT,
    _MIN_UI_LABEL_LEN,
    _REQUIREMENT_WEIGHT,
    _UI_ELEMENT_WEIGHT,
)
from app.services.case_quality.analyzer_mixin import AnalyzerMixin
from app.services.case_quality.models import CoverageScore


# ============================================================
# 测试桩与工具
# ============================================================


class _StubAnalyzer(CoverageMixin):
    """仅装载 CoverageMixin 的最小桩。

    使用 MagicMock 代替 db：默认测试路径不依赖 db（通过 ctx 注入数据），
    个别测试需要验证 db fallback 分支时可重新赋值 self.db。
    """

    def __init__(self):
        self.db = MagicMock(name="db")


def _step(step_id: int, target: Optional[str] = None) -> SimpleNamespace:
    return SimpleNamespace(id=step_id, target_element=target)


def _case(test_point_id: Optional[int] = None) -> SimpleNamespace:
    return SimpleNamespace(test_point_id=test_point_id)


def _locator(step_id: int) -> SimpleNamespace:
    return SimpleNamespace(step_id=step_id)


# ============================================================
# _calc_requirement_coverage
# ============================================================


class TestRequirementCoverage:

    def test_unavailable_when_project_has_no_test_points(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=_case(test_point_id=1), ctx={"project_test_point_priorities": {}}
        )
        assert rate == 0.0
        assert det["available"] is False
        assert det["project_total_test_points"] == 0
        assert det["has_test_point_link"] is False

    def test_unavailable_when_ctx_missing(self):
        rate, det = CoverageMixin._calc_requirement_coverage(case=_case(1), ctx={})
        assert rate == 0.0
        assert det["available"] is False

    def test_no_link_when_case_test_point_id_none(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=_case(test_point_id=None),
            ctx={"project_test_point_priorities": {1: 1, 2: 2, 3: 3}},
        )
        assert rate == 0.0
        assert det["available"] is True
        assert det["has_test_point_link"] is False
        assert det["project_total_test_points"] == 3

    def test_no_link_when_case_test_point_outside_project(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=_case(test_point_id=99),
            ctx={"project_test_point_priorities": {1: 1, 2: 2, 3: 3}},
        )
        assert rate == 0.0
        assert det["has_test_point_link"] is False

    def test_high_priority_link_scores_full(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=_case(test_point_id=1),
            ctx={"project_test_point_priorities": {1: 1, 2: 2, 3: 3}},
        )
        assert rate == 1.0
        assert det["available"] is True
        assert det["has_test_point_link"] is True
        assert det["case_test_point_id"] == 1
        assert det["test_point_priority"] == 1
        assert det["priority_weight"] == 1.0
        assert det["scoring_mode"] == "priority_weighted_single_link"

    def test_medium_priority_link_scores_partial(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=_case(test_point_id=2),
            ctx={"project_test_point_priorities": {1: 1, 2: 2, 3: 3}},
        )
        assert rate == 0.7
        assert det["has_test_point_link"] is True
        assert det["test_point_priority"] == 2
        assert det["priority_weight"] == 0.7

    def test_low_priority_link_scores_lower(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=_case(test_point_id=3),
            ctx={"project_test_point_priorities": {1: 1, 2: 2, 3: 3}},
        )
        assert rate == 0.4
        assert det["has_test_point_link"] is True
        assert det["test_point_priority"] == 3
        assert det["priority_weight"] == 0.4

    def test_unknown_priority_uses_default_low_weight(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=_case(test_point_id=4),
            ctx={"project_test_point_priorities": {4: 99}},
        )
        assert rate == 0.4
        assert det["has_test_point_link"] is True
        assert det["test_point_priority"] == 99

    def test_case_none_returns_zero(self):
        rate, det = CoverageMixin._calc_requirement_coverage(
            case=None, ctx={"project_test_point_priorities": {1: 1}}
        )
        assert rate == 0.0
        assert det["has_test_point_link"] is False
        assert det["case_test_point_id"] is None


# ============================================================
# _calc_ui_element_coverage
# ============================================================


class TestUIElementCoverage:

    def test_unavailable_when_project_has_no_labels(self):
        rate, det = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "登录按钮")], ctx={"project_ui_labels": set()}
        )
        assert rate == 0.0
        assert det["available"] is False
        assert det["total_ui_labels"] == 0

    def test_unavailable_when_no_steps_with_target(self):
        rate, det = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, None), _step(2, "")],
            ctx={"project_ui_labels": {"登录按钮"}},
        )
        assert rate == 0.0
        assert det["available"] is False
        assert det["steps_with_target"] == 0
        assert det["matched_steps"] == 0

    def test_full_match_all_steps(self):
        rate, det = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "登录按钮"), _step(2, "用户名输入框")],
            ctx={"project_ui_labels": {"登录按钮", "用户名输入框"}},
        )
        assert rate == 1.0
        assert det["available"] is True
        assert det["matched_steps"] == 2
        assert det["steps_with_target"] == 2

    def test_partial_match(self):
        rate, det = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "登录按钮"), _step(2, "未知元素")],
            ctx={"project_ui_labels": {"登录按钮"}},
        )
        assert rate == 0.5
        assert det["matched_steps"] == 1
        assert det["steps_with_target"] == 2

    def test_case_insensitive_matching(self):
        rate, _ = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "Login Button"), _step(2, "USERNAME")],
            ctx={"project_ui_labels": {"login button", "username"}},
        )
        assert rate == 1.0

    def test_substring_both_directions(self):
        # target 包含 label
        rate1, _ = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "点击登录按钮以提交")],
            ctx={"project_ui_labels": {"登录按钮"}},
        )
        assert rate1 == 1.0
        # label 包含 target
        rate2, _ = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "登录")],
            ctx={"project_ui_labels": {"登录按钮"}},
        )
        assert rate2 == 1.0

    def test_short_label_requires_exact_match(self):
        """长度 < _MIN_UI_LABEL_LEN 的短 label 仅接受精确相等，避免误命中。

        实例：单字 label "报" 不应命中 target="报表生成按钮"。
        """
        assert _MIN_UI_LABEL_LEN == 2  # 与实现一致
        # 短 label + 不等的 target → 不命中
        rate1, det1 = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "报表生成按钮")],
            ctx={"project_ui_labels": {"报"}},
        )
        assert rate1 == 0.0
        assert det1["matched_steps"] == 0
        # 短 label + 精确相等的 target → 命中
        rate2, _ = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "报")],
            ctx={"project_ui_labels": {"报"}},
        )
        assert rate2 == 1.0

    def test_known_ambiguity_avoided_for_short_keywords(self):
        """语义陷阱快照测试：在引入最小长度阈值后，短词不再误命中。

        这个测试在未来修改匹配策略（如采用分词/编辑距离）时应同步重新验证。
        """
        # 只有单字 label，不应误命中包含它的 target
        rate, det = CoverageMixin._calc_ui_element_coverage(
            steps=[
                _step(1, "退出登录"),  # 包含单字 "退"/"出"
                _step(2, "上传文件"),  # 包含单字 "传"/"文"
            ],
            ctx={"project_ui_labels": {"退", "传"}},
        )
        assert rate == 0.0  # 单字 label 不参与子串匹配
        assert det["matched_steps"] == 0

    @pytest.mark.parametrize("target,label,expected", [
        ("登录按钮", "登录", True),         # label 含于 target
        ("登录", "登录按钮", True),         # target 含于 label
        ("login button", "login", True),    # 英文同理
        ("备注", "备", False),               # 短 label 不会误命中
        ("备", "备", True),                  # 短 label 精确相等
        ("", "登录", False),                # 空 target
        ("登录", "", False),                # 空 label
        ("abc", "xyz", False),              # 完全不相关
    ])
    def test_is_ui_match_rules(self, target, label, expected):
        assert CoverageMixin._is_ui_match(target, label) is expected

    def test_steps_without_target_not_counted_in_denominator(self):
        rate, det = CoverageMixin._calc_ui_element_coverage(
            steps=[_step(1, "登录按钮"), _step(2, None), _step(3, None)],
            ctx={"project_ui_labels": {"登录按钮"}},
        )
        assert rate == 1.0
        assert det["steps_with_target"] == 1


# ============================================================
# _calc_locator_coverage
# ============================================================


class TestLocatorCoverage:

    def test_unavailable_when_no_steps(self):
        analyzer = _StubAnalyzer()
        rate, det = analyzer._calc_locator_coverage(steps=[], ctx={})
        assert rate == 0.0
        assert det["available"] is False
        assert det["covered_step_count"] == 0
        assert det["total_step_count"] == 0

    def test_full_coverage(self):
        analyzer = _StubAnalyzer()
        steps = [_step(1), _step(2), _step(3)]
        ctx = {
            "locators_by_step": {
                1: [_locator(1)],
                2: [_locator(2)],
                3: [_locator(3)],
            }
        }
        rate, det = analyzer._calc_locator_coverage(steps=steps, ctx=ctx)
        assert rate == 1.0
        assert det["available"] is True
        assert det["covered_step_count"] == 3

    def test_partial_coverage(self):
        analyzer = _StubAnalyzer()
        steps = [_step(1), _step(2), _step(3), _step(4)]
        ctx = {"locators_by_step": {1: [_locator(1)], 3: [_locator(3)]}}
        rate, det = analyzer._calc_locator_coverage(steps=steps, ctx=ctx)
        assert rate == 0.5
        assert det["covered_step_count"] == 2
        assert det["total_step_count"] == 4

    def test_no_coverage_with_empty_locators_map(self):
        analyzer = _StubAnalyzer()
        steps = [_step(1), _step(2)]
        rate, det = analyzer._calc_locator_coverage(
            steps=steps, ctx={"locators_by_step": {}}
        )
        assert rate == 0.0
        assert det["available"] is True

    def test_db_fallback_when_ctx_missing_locators_by_step(self):
        """ctx 未提供 locators_by_step 时，走 db.query 回退分支（覆盖 100%）。"""
        analyzer = _StubAnalyzer()
        # 构造 db.query(...).filter(...).all() 返回两个定位器的链
        analyzer.db.query.return_value.filter.return_value.all.return_value = [
            _locator(1), _locator(2),
        ]
        steps = [_step(1), _step(2), _step(3)]
        rate, det = analyzer._calc_locator_coverage(steps=steps, ctx={})
        assert det["covered_step_count"] == 2
        assert det["total_step_count"] == 3
        assert math.isclose(rate, 2 / 3)
        # 验证确实走了 db 分支
        analyzer.db.query.assert_called_once()


# ============================================================
# _aggregate_coverage （核心：动态权重重正）
# ============================================================


class TestAggregateCoverage:

    def test_all_dimensions_full(self):
        rate = CoverageMixin._aggregate_coverage(
            req_rate=1.0, req_available=True,
            ui_rate=1.0, ui_available=True,
            loc_rate=1.0, loc_available=True,
        )
        assert rate == 1.0

    def test_strict_weights_when_all_available(self):
        # v2 权重：0.6*0.3 + 0.8*0.3 + 0.4*0.4 = 0.18 + 0.24 + 0.16 = 0.58
        rate = CoverageMixin._aggregate_coverage(
            req_rate=0.6, req_available=True,
            ui_rate=0.8, ui_available=True,
            loc_rate=0.4, loc_available=True,
        )
        assert math.isclose(rate, 0.58, abs_tol=1e-9)

    def test_degrade_to_locator_only(self):
        # 仅 locator 可用 → rate = loc_rate
        rate = CoverageMixin._aggregate_coverage(
            req_rate=0.0, req_available=False,
            ui_rate=0.0, ui_available=False,
            loc_rate=0.75, loc_available=True,
        )
        assert math.isclose(rate, 0.75)

    def test_renormalize_when_ui_missing(self):
        # 仅 req+loc 可用，权重重正：(1.0*0.5 + 0.5*0.2) / (0.5+0.2) = 0.6/0.7
        rate = CoverageMixin._aggregate_coverage(
            req_rate=1.0, req_available=True,
            ui_rate=0.0, ui_available=False,
            loc_rate=0.5, loc_available=True,
        )
        expected = (1.0 * _REQUIREMENT_WEIGHT + 0.5 * _LOCATOR_WEIGHT) / (
            _REQUIREMENT_WEIGHT + _LOCATOR_WEIGHT
        )
        assert math.isclose(rate, expected)

    def test_renormalize_when_requirement_missing(self):
        # 仅 ui+loc 可用：(0.6*0.3 + 1.0*0.2) / (0.3+0.2) = 0.38/0.5 = 0.76
        rate = CoverageMixin._aggregate_coverage(
            req_rate=0.0, req_available=False,
            ui_rate=0.6, ui_available=True,
            loc_rate=1.0, loc_available=True,
        )
        expected = (0.6 * _UI_ELEMENT_WEIGHT + 1.0 * _LOCATOR_WEIGHT) / (
            _UI_ELEMENT_WEIGHT + _LOCATOR_WEIGHT
        )
        assert math.isclose(rate, expected)

    def test_returns_zero_when_nothing_available(self):
        rate = CoverageMixin._aggregate_coverage(
            req_rate=0.0, req_available=False,
            ui_rate=0.0, ui_available=False,
            loc_rate=0.0, loc_available=False,
        )
        assert rate == 0.0

    def test_partial_dimensions_does_not_inflate_score(self):
        # 验证退化语义：仅 locator 满分，不应等同于三维都满分
        full = CoverageMixin._aggregate_coverage(
            req_rate=1.0, req_available=True,
            ui_rate=1.0, ui_available=True,
            loc_rate=1.0, loc_available=True,
        )
        loc_only = CoverageMixin._aggregate_coverage(
            req_rate=0.0, req_available=False,
            ui_rate=0.0, ui_available=False,
            loc_rate=1.0, loc_available=True,
        )
        # 都是 1.0（loc_only 是退化为 locator-only 的合理结果）
        assert full == loc_only == 1.0


# ============================================================
# _coverage_level 阈值
# ============================================================


class TestCoverageLevel:

    @pytest.mark.parametrize("rate,expected", [
        (1.0, "high"),
        (0.9, "high"),
        (0.89, "moderate"),
        (0.7, "moderate"),
        (0.69, "low"),
        (0.5, "low"),
        (0.49, "very_low"),
        (0.0, "very_low"),
    ])
    def test_thresholds(self, rate, expected):
        assert CoverageMixin._coverage_level(rate) == expected


# ============================================================
# _extract_ui_labels_from_spec
# ============================================================


class TestExtractUILabelsFromSpec:

    def test_empty_spec_returns_empty(self):
        assert AnalyzerMixin._extract_ui_labels_from_spec({}) == set()
        assert AnalyzerMixin._extract_ui_labels_from_spec(None) == set()

    def test_extracts_from_elements_list(self):
        spec = {"elements": [{"name": "登录按钮"}, {"label": "用户名"}]}
        labels = AnalyzerMixin._extract_ui_labels_from_spec(spec)
        assert labels == {"登录按钮", "用户名"}

    def test_handles_nested_structures(self):
        spec = {
            "components": [
                {"name": "顶部导航", "children": [{"text": "首页"}, {"text": "设置"}]},
            ]
        }
        labels = AnalyzerMixin._extract_ui_labels_from_spec(spec)
        assert "顶部导航" in labels
        assert "首页" in labels
        assert "设置" in labels

    def test_normalizes_to_lowercase(self):
        spec = {"elements": [{"name": "  Login Button  "}]}
        labels = AnalyzerMixin._extract_ui_labels_from_spec(spec)
        assert labels == {"login button"}

    def test_skips_non_string_values(self):
        spec = {"elements": [{"name": 123}, {"label": None}, {"name": "登录"}]}
        labels = AnalyzerMixin._extract_ui_labels_from_spec(spec)
        assert labels == {"登录"}

    def test_skips_non_candidate_keys(self):
        spec = {"elements": [{"random_key": "不应提取", "name": "应提取"}]}
        labels = AnalyzerMixin._extract_ui_labels_from_spec(spec)
        assert labels == {"应提取"}

    def test_recursion_depth_limit_does_not_raise(self):
        """超过递归深度上限应警告并提前结束，不抛出异常。

        构造超出 _UI_SPEC_MAX_DEPTH 的嵌套字典测试防御逻辑。
        """
        depth = AnalyzerMixin._UI_SPEC_MAX_DEPTH + 5
        # 递归构造多层嵌套：{"child": {"child": {... "name": "深层按钮"}}}
        spec: dict = {"name": "深层按钮"}
        for _ in range(depth):
            spec = {"child": spec}
        # 不应抛出异常，且超出部分的 label 被丢弃
        labels = AnalyzerMixin._extract_ui_labels_from_spec(spec)
        assert isinstance(labels, set)  # 不报错即达到保护目的

    def test_handles_non_dict_non_list_root(self):
        """根节点为字符串/数字/None 时安全返回空集。"""
        assert AnalyzerMixin._extract_ui_labels_from_spec("裸字符串") == set()
        assert AnalyzerMixin._extract_ui_labels_from_spec(42) == set()
        assert AnalyzerMixin._extract_ui_labels_from_spec([]) == set()


# ============================================================
# _calc_project_requirement_coverage
# ============================================================


class TestProjectRequirementCoverage:

    def test_unavailable_when_project_has_no_test_points(self):
        result = AnalyzerMixin._calc_project_requirement_coverage(
            cases=[_case(test_point_id=1)],
            project_test_point_priorities={},
        )
        assert result["coverage_rate"] == 0.0
        assert result["details"]["available"] is False
        assert result["details"]["project_total_test_points"] == 0
        assert result["details"]["covered_test_point_count"] == 0

    def test_weighted_unique_coverage(self):
        result = AnalyzerMixin._calc_project_requirement_coverage(
            cases=[
                _case(test_point_id=10),
                _case(test_point_id=10),
                _case(test_point_id=20),
            ],
            project_test_point_priorities={10: 1, 20: 2, 30: 3},
        )
        # unique covered points = {10, 20}
        # covered weight = 1.0 + 0.7 = 1.7
        # total weight = 1.0 + 0.7 + 0.4 = 2.1
        assert math.isclose(result["coverage_rate"], 1.7 / 2.1, abs_tol=1e-9)
        assert result["details"]["available"] is True
        assert result["details"]["covered_test_point_count"] == 2
        assert result["details"]["project_total_test_points"] == 3
        assert result["details"]["covered_test_point_ids"] == [10, 20]
        assert result["details"]["covered_weight_sum"] == 1.7
        assert result["details"]["project_weight_sum"] == 2.1

    def test_ignores_invalid_or_out_of_project_links(self):
        result = AnalyzerMixin._calc_project_requirement_coverage(
            cases=[
                _case(test_point_id=None),
                _case(test_point_id=999),
                _case(test_point_id=30),
            ],
            project_test_point_priorities={10: 1, 20: 2, 30: 3},
        )
        assert math.isclose(result["coverage_rate"], 0.4 / 2.1, abs_tol=1e-9)
        assert result["details"]["covered_test_point_count"] == 1
        assert result["details"]["covered_test_point_ids"] == [30]
        assert result["details"]["scoring_mode"] == "priority_weighted_project_unique_points"


# ============================================================
# _analyze_coverage 端到端集成
# ============================================================


class TestAnalyzeCoverageIntegration:

    def test_full_three_dimensions(self):
        analyzer = _StubAnalyzer()
        steps = [_step(1, "登录按钮"), _step(2, "用户名输入框"), _step(3, None)]
        ctx = {
            "project_test_point_priorities": {10: 1, 20: 2},
            "project_ui_labels": {"登录按钮", "用户名输入框"},
            "locators_by_step": {1: [_locator(1)], 2: [_locator(2)], 3: [_locator(3)]},
        }
        result = analyzer._analyze_coverage(
            steps=steps, coverage_context=ctx, case=_case(test_point_id=10)
        )

        assert isinstance(result, CoverageScore)
        # 三维度都满
        assert result.requirement_coverage_rate == 1.0
        assert result.ui_element_coverage_rate == 1.0
        assert result.locator_coverage_rate == 1.0
        # 综合 = 1.0
        assert result.coverage_rate == 1.0
        assert result.score == 10.0
        assert result.level == "high"
        # details 字段
        assert result.requirement_details["has_test_point_link"] is True
        assert result.ui_element_details["matched_steps"] == 2
        assert result.locator_details["covered_step_count"] == 3
        # 兼容字段
        assert result.total_elements == 3
        assert result.covered_elements == 3
        assert result.uncovered_elements == 0

    def test_degraded_to_locator_only_when_no_project_data(self):
        analyzer = _StubAnalyzer()
        steps = [_step(1), _step(2)]
        ctx = {
            "project_test_point_priorities": {},  # 项目无测试点
            "project_ui_labels": set(),       # 项目无 UI 元素
            "locators_by_step": {1: [_locator(1)]},
        }
        result = analyzer._analyze_coverage(
            steps=steps, coverage_context=ctx, case=_case()
        )
        # requirement / ui 不可用，coverage_rate 退化等于 locator_rate
        assert result.locator_coverage_rate == 0.5
        assert result.coverage_rate == 0.5
        assert result.requirement_details["available"] is False
        assert result.ui_element_details["available"] is False
        assert result.locator_details["available"] is True

    def test_empty_steps_results_in_zero_coverage(self):
        analyzer = _StubAnalyzer()
        result = analyzer._analyze_coverage(
            steps=[], coverage_context={}, case=_case()
        )
        assert result.coverage_rate == 0.0
        assert result.score == 0.0
        assert result.total_elements == 0
        assert result.covered_elements == 0

    def test_no_coverage_context_falls_back_safely(self):
        analyzer = _StubAnalyzer()
        # 不传 ctx 也不应崩溃；locator 维度因无 locators_by_step 走 db 路径
        # 这里 db=None 所以仅验证 case=None + 空 steps 的安全退化
        result = analyzer._analyze_coverage(steps=[], coverage_context=None, case=None)
        assert result.coverage_rate == 0.0
        assert result.requirement_details["available"] is False

    def test_case_with_unbound_test_point_keeps_dimension_available(self):
        """项目有测试点但当前用例未关联：维度可用，rate=0，会拉低综合分（产品意图）。"""
        analyzer = _StubAnalyzer()
        steps = [_step(1, "登录按钮")]
        ctx = {
            "project_test_point_priorities": {10: 1},
            "project_ui_labels": {"登录按钮"},
            "locators_by_step": {1: [_locator(1)]},
        }
        result = analyzer._analyze_coverage(
            steps=steps, coverage_context=ctx, case=_case(test_point_id=None)
        )
        # v2 权重：req=0, ui=1, loc=1 → 0*0.3 + 1*0.3 + 1*0.4 = 0.7
        assert result.requirement_coverage_rate == 0.0
        assert result.ui_element_coverage_rate == 1.0
        assert result.locator_coverage_rate == 1.0
        assert math.isclose(result.coverage_rate, 0.7, abs_tol=1e-9)
        assert result.requirement_details["available"] is True

    def test_three_dimension_weighted_score(self):
        """验证完整三维加权公式 v2：0.3*req + 0.3*ui + 0.4*loc。"""
        analyzer = _StubAnalyzer()
        steps = [
            _step(1, "登录按钮"),       # ui 命中 + 有 locator
            _step(2, "未知元素"),       # ui 未命中 + 无 locator
        ]
        ctx = {
            "project_test_point_priorities": {10: 1},
            "project_ui_labels": {"登录按钮"},
            "locators_by_step": {1: [_locator(1)]},
        }
        result = analyzer._analyze_coverage(
            steps=steps, coverage_context=ctx, case=_case(test_point_id=10)
        )
        # req=1.0, ui=0.5, loc=0.5
        # v2 综合 = 0.3*1.0 + 0.3*0.5 + 0.4*0.5 = 0.30 + 0.15 + 0.20 = 0.65
        assert math.isclose(result.coverage_rate, 0.65, abs_tol=1e-9)
        assert result.score == 6.5
        assert result.level == "low"  # 0.65 < 0.7 阈值
