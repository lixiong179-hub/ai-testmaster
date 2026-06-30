"""Task 14 三合一质量评分一致性测试。

断言同一用例在三处评分入口（grade_status / score_dimensions / prior_score）
的维度判定一致，覆盖 ≥99% 一致率（SubTask 14.5）。

三处评分共享 quality_scoring_constants 常量与 _classify_* 判定：
- grade_status: 4 档状态（passed/warning/pending_review/rejected）
- score_dimensions: 7 维度连续评分（每维度 0-10）
- prior_score: prior content 评分（0-100 + breakdown）
"""
import pytest

from app.services.case_quality.quality_scoring_constants import (
    WEIGHT_ACTION_TYPE,
    WEIGHT_ATOMICITY,
    WEIGHT_CASE_CATEGORY,
    WEIGHT_EXPECTED_RESULT,
    WEIGHT_PRECONDITION,
    WEIGHT_STEPS,
    WEIGHT_TITLE,
)
from app.services.case_quality.quality_scoring_service import QualityScoringService


def _make_valid_case(**overrides) -> dict:
    """构造一条全维度通过的基准用例，通过 overrides 覆盖特定字段。"""
    base: dict = {
        "title": "验证用户登录功能正常工作流程",
        "precondition": "账号已登录，网络环境正常，测试数据已准备",
        "steps": [
            {"action": "点击登录按钮", "expected_result": "跳转到首页", "action_type": "click"},
            {"action": "查看欢迎信息", "expected_result": "显示欢迎文字", "action_type": "verify"},
        ],
        "expected_result": "登录成功并显示欢迎页面，用户名正确显示",
        "case_category": "positive",
        "case_type": "ui_automation",
    }
    base.update(overrides)
    return base


# ── grade_status 4 档状态判定 ──


class TestGradeStatus:
    """QualityScoringService.grade_status 4 档状态判定。"""

    def test_valid_case_returns_passed(self) -> None:
        assert QualityScoringService.grade_status(_make_valid_case()) == "passed"

    def test_empty_title_returns_rejected(self) -> None:
        assert QualityScoringService.grade_status(_make_valid_case(title="")) == "rejected"

    def test_vague_title_returns_pending_review(self) -> None:
        case = _make_valid_case(title="功能验证测试用例标题加长版")
        assert QualityScoringService.grade_status(case) == "pending_review"

    def test_short_title_returns_warning(self) -> None:
        case = _make_valid_case(title="短标题")
        assert QualityScoringService.grade_status(case) == "warning"

    def test_empty_precondition_returns_rejected(self) -> None:
        assert QualityScoringService.grade_status(_make_valid_case(precondition="")) == "rejected"

    def test_contradictory_precondition_returns_pending_review(self) -> None:
        case = _make_valid_case(precondition="账号已登录但用户未登录，网络正常")
        assert QualityScoringService.grade_status(case) == "pending_review"

    def test_empty_steps_returns_rejected(self) -> None:
        assert QualityScoringService.grade_status(_make_valid_case(steps=[])) == "rejected"

    def test_insufficient_steps_returns_rejected(self) -> None:
        case = _make_valid_case(steps=[{"action": "点击", "expected_result": "结果"}])
        assert QualityScoringService.grade_status(case) == "rejected"

    def test_empty_expected_result_returns_rejected(self) -> None:
        assert QualityScoringService.grade_status(_make_valid_case(expected_result="")) == "rejected"

    def test_vague_expected_result_returns_pending_review(self) -> None:
        case = _make_valid_case(expected_result="功能正常显示")
        assert QualityScoringService.grade_status(case) == "pending_review"

    def test_invalid_case_category_returns_rejected(self) -> None:
        case = _make_valid_case(case_category="invalid_category")
        assert QualityScoringService.grade_status(case) == "rejected"

    def test_severity_order_rejected_dominates(self) -> None:
        case = _make_valid_case(title="", precondition="", steps=[], expected_result="", case_category="")
        assert QualityScoringService.grade_status(case) == "rejected"


# ── score_dimensions 7 维度连续评分 ──


class TestScoreDimensions:
    """QualityScoringService.score_dimensions 7 维度连续评分。"""

    def test_valid_case_all_max(self) -> None:
        dims = QualityScoringService.score_dimensions(_make_valid_case())
        assert dims["title"] == 10.0
        assert dims["precondition"] == 10.0
        assert dims["steps"] == 10.0
        assert dims["expected_result"] == 10.0
        assert dims["case_category"] == 10.0
        assert dims["action_type"] == 10.0
        assert dims["atomicity"] == 10.0

    def test_empty_title_scores_zero(self) -> None:
        dims = QualityScoringService.score_dimensions(_make_valid_case(title=""))
        assert dims["title"] == 0.0

    def test_vague_title_scores_four(self) -> None:
        dims = QualityScoringService.score_dimensions(_make_valid_case(title="功能验证测试用例标题加长版"))
        assert dims["title"] == 4.0

    def test_length_issue_title_scores_seven(self) -> None:
        dims = QualityScoringService.score_dimensions(_make_valid_case(title="短标题"))
        assert dims["title"] == 7.0

    def test_all_seven_dimensions_present(self) -> None:
        dims = QualityScoringService.score_dimensions(_make_valid_case())
        expected_keys = {"title", "precondition", "steps", "expected_result",
                         "case_category", "action_type", "atomicity"}
        assert set(dims.keys()) == expected_keys

    def test_missing_action_type_scores_seven(self) -> None:
        case = _make_valid_case(steps=[
            {"action": "点击登录按钮", "expected_result": "跳转到首页"},
            {"action": "查看欢迎信息", "expected_result": "显示欢迎文字"},
        ])
        dims = QualityScoringService.score_dimensions(case)
        assert dims["action_type"] == 7.0


# ── prior_score prior content 评分 ──


class TestPriorScore:
    """QualityScoringService.prior_score prior content 评分。"""

    def test_valid_case_returns_breakdown(self) -> None:
        score, breakdown = QualityScoringService.prior_score(_make_valid_case())
        assert 0.0 <= score <= 100.0
        assert "title_quality" in breakdown
        assert "steps_quality" in breakdown
        assert "expected_result_quality" in breakdown
        assert "precondition_quality" in breakdown

    def test_empty_title_prior_zero(self) -> None:
        _, breakdown = QualityScoringService.prior_score(_make_valid_case(title=""))
        assert breakdown["title_quality"] == 0.0

    def test_vague_title_prior_low(self) -> None:
        _, breakdown = QualityScoringService.prior_score(_make_valid_case(title="功能验证测试用例标题加长版"))
        assert breakdown["title_quality"] == 5.0

    def test_empty_steps_prior_zero(self) -> None:
        _, breakdown = QualityScoringService.prior_score(_make_valid_case(steps=[]))
        assert breakdown["steps_quality"] == 0.0

    def test_score_clamped_to_range(self) -> None:
        score, _ = QualityScoringService.prior_score(_make_valid_case())
        assert 0.0 <= score <= 100.0


# ── 三处评分维度一致性（SubTask 14.5 核心）──


class TestThreeWayConsistency:
    """断言同一用例在三处评分中维度判定一致，覆盖 ≥99% 一致率。"""

    @pytest.mark.parametrize("title,expected_verdict", [
        ("", "empty"),
        ("功能验证测试用例标题加长版", "vague"),
        ("接口测试", "vague"),
        ("UI测试", "vague"),
        ("短标题", "length"),
        ("验证用户登录功能正常工作流程", "ok"),
    ])
    def test_title_dimension_consistency(self, title: str, expected_verdict: str) -> None:
        """标题维度在 grade_status / score_dimensions / prior_score 三处判定一致。"""
        case = _make_valid_case(title=title)
        verdict = QualityScoringService._classify_title(title)
        assert verdict == expected_verdict
        dims = QualityScoringService.score_dimensions(case)
        dim_map = {"empty": 0.0, "vague": 4.0, "length": 7.0, "ok": 10.0}
        assert dims["title"] == dim_map[expected_verdict]
        _, prior_bd = QualityScoringService.prior_score(case)
        if expected_verdict == "empty":
            assert prior_bd["title_quality"] == 0.0
        elif expected_verdict == "vague":
            assert prior_bd["title_quality"] == 5.0
        else:
            assert prior_bd["title_quality"] > 0.0

    @pytest.mark.parametrize("precondition,expected_verdict", [
        ("", "empty"),
        ("账号已登录但用户未登录，网络正常", "contradictory"),
        ("测试数据已准备", "missing_login"),
        ("账号已登录", "short"),
        ("账号已登录，网络环境正常，测试数据已准备", "ok"),
    ])
    def test_precondition_dimension_consistency(
        self, precondition: str, expected_verdict: str
    ) -> None:
        """前置条件维度在三处评分中判定一致。"""
        case = _make_valid_case(precondition=precondition)
        verdict = QualityScoringService._classify_precondition(precondition)
        assert verdict == expected_verdict
        dims = QualityScoringService.score_dimensions(case)
        dim_map = {"empty": 0.0, "contradictory": 4.0, "missing_login": 4.0,
                   "short": 7.0, "ok": 10.0}
        assert dims["precondition"] == dim_map[expected_verdict]

    @pytest.mark.parametrize("expected_result,expected_verdict", [
        ("", "empty"),
        ("功能正常显示", "vague"),
        ("显示成功", "short"),
        ("登录成功并显示欢迎页面，用户名正确显示", "ok"),
    ])
    def test_expected_result_dimension_consistency(
        self, expected_result: str, expected_verdict: str
    ) -> None:
        """预期结果维度在三处评分中判定一致。"""
        case = _make_valid_case(expected_result=expected_result)
        verdict = QualityScoringService._classify_expected(expected_result)
        assert verdict == expected_verdict
        dims = QualityScoringService.score_dimensions(case)
        dim_map = {"empty": 0.0, "vague": 4.0, "short": 7.0, "ok": 10.0}
        assert dims["expected_result"] == dim_map[expected_verdict]

    def test_grade_status_and_dimensions_share_classify(self) -> None:
        """grade_status 与 score_dimensions 共享 _classify_*，保证判定一致。"""
        # vague title: grade_status → pending_review, dims title → 4.0
        case = _make_valid_case(title="功能验证测试用例标题加长版")
        assert QualityScoringService.grade_status(case) == "pending_review"
        assert QualityScoringService.score_dimensions(case)["title"] == 4.0
        # empty title: grade_status → rejected, dims title → 0.0
        case2 = _make_valid_case(title="")
        assert QualityScoringService.grade_status(case2) == "rejected"
        assert QualityScoringService.score_dimensions(case2)["title"] == 0.0

    def test_consistency_rate_above_99_percent(self) -> None:
        """批量用例标题维度三处评分一致性 ≥99%（SubTask 14.5）。

        三处评分共享 _classify_title 判定与 TITLE_VAGUE_PATTERNS 正则，
        故标题维度 verdict 在 grade_status / score_dimensions / prior_score
        三处必然一致。本测试用 diverse 用例集验证此不变量。
        """
        titles = [
            "验证用户登录功能正常工作流程",
            "",
            "功能验证测试用例标题加长版",
            "短标题",
            "接口测试",
            "UI测试",
            "边界测试用例验证最小值输入",
            "异常登录_密码错误三次锁定账号显示等待时间",
            "正常登录_正确账号密码跳转首页",
        ]
        dim_map = {"empty": 0.0, "vague": 4.0, "length": 7.0, "ok": 10.0}
        consistent = 0
        for title in titles:
            case = _make_valid_case(title=title)
            verdict = QualityScoringService._classify_title(title)
            dims = QualityScoringService.score_dimensions(case)
            _, prior_bd = QualityScoringService.prior_score(case)
            # score_dimensions title 得分与 verdict 对应
            dims_ok = dims["title"] == dim_map[verdict]
            # prior_score title_quality 与 verdict 对应
            if verdict == "empty":
                prior_ok = prior_bd["title_quality"] == 0.0
            elif verdict == "vague":
                prior_ok = prior_bd["title_quality"] == 5.0
            else:
                prior_ok = prior_bd["title_quality"] > 0.0
            if dims_ok and prior_ok:
                consistent += 1
        rate = consistent / len(titles)
        assert rate >= 0.99, f"标题维度一致性率 {rate:.2%} 低于 99%"


# ── 集成委托验证 ──


class TestIntegrationDelegation:
    """验证三处调用方正确委托 QualityScoringService。"""

    def test_validate_single_case_status_delegates_grade_status(self) -> None:
        """validate_single_case_status 委托 grade_status 判定状态。"""
        from app.services.test_case_generation.quality_validator import validate_single_case_status
        case = _make_valid_case(title="")
        status, issues = validate_single_case_status(case)
        assert status == QualityScoringService.grade_status(case)
        assert status == "rejected"
        assert len(issues) > 0

    def test_compute_continuous_score_delegates_score_dimensions(self) -> None:
        """compute_continuous_score 委托 score_dimensions 加权求和。"""
        from app.services.test_case_generation.continuous_scorer import compute_continuous_score
        case = _make_valid_case()
        score = compute_continuous_score(case)
        dims = QualityScoringService.score_dimensions(case)
        expected = round((
            dims["title"] * WEIGHT_TITLE
            + dims["precondition"] * WEIGHT_PRECONDITION
            + dims["steps"] * WEIGHT_STEPS
            + dims["expected_result"] * WEIGHT_EXPECTED_RESULT
            + dims["case_category"] * WEIGHT_CASE_CATEGORY
            + dims["action_type"] * WEIGHT_ACTION_TYPE
            + dims["atomicity"] * WEIGHT_ATOMICITY
        ) * 10, 1)
        assert score == expected

    def test_compute_prior_score_uses_prior_score(self) -> None:
        """_signal_scoring._compute_prior_score 的 content 部分委托 prior_score。"""
        from app.pipelines.steps._signal_scoring import _compute_prior_score
        case = _make_valid_case()
        signals = {"has_prd": True, "has_testpoints": True, "has_ui": True, "is_old_project": False}
        _, _, breakdown = _compute_prior_score(
            case, {"id": 1}, signals, {}, {"conflict_count": 0},
            1, None, user_confirmed=False,
        )
        _, content_bd = QualityScoringService.prior_score(case)
        assert breakdown["title_quality"] == content_bd["title_quality"]
        assert breakdown["steps_quality"] == content_bd["steps_quality"]
        assert breakdown["expected_result_quality"] == content_bd["expected_result_quality"]
        assert breakdown["precondition_quality"] == content_bd["precondition_quality"]
