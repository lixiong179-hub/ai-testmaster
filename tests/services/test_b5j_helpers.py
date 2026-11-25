"""B5j 拆分件护栏：分维度严重度 / 建议分维度构造 / 相似用例文本采集 / TF-IDF 分步。

`grade_status`（17）、`_generate_optimization_suggestions`（16）、`_find_similar_cases`（12）、
`fit_transform`（12）、`analyze_project_quality`（11）、`_classify_steps`（11）拆分后，
对新增的纯函数逐一加锁，并校验 `grade_status` 聚合口径（取最大严重度）不变。
"""

import math
from types import SimpleNamespace

import numpy as np

from app.services.case_quality.analyzer_mixin._project_analyzer import (
    _build_case_text_map,
    _build_quality_distribution,
    _collect_top_issues,
    _empty_project_quality,
)
from app.services.case_quality.quality_scoring_service import (
    QualityScoringService,
    _aux_severity,
    _category_severity,
    _expected_severity,
    _precondition_severity,
    _steps_severity,
    _title_severity,
)
from app.services.case_quality.redundancy_mixin import RedundancyMixin, _cached_text, _steps_text
from app.services.case_quality.suggestion_mixin import (
    _complexity_suggestions,
    _locator_suggestions,
    _redundancy_suggestions,
    _requirement_coverage_suggestions,
    _ui_coverage_suggestions,
)
from app.services.case_quality.tfidf_utils import LightweightTfidfVectorizer, _term_frequencies

REJECTED, PENDING, WARNING = 3, 2, 1


class TestTitleSeverity:
    def test_levels(self):
        assert _title_severity("") == REJECTED
        assert _title_severity("功能测试") == PENDING  # 泛化词 → vague
        assert _title_severity("短") == WARNING  # 低于 TITLE_MIN_LENGTH
        assert _title_severity("登录成功进入首页并展示用户信息") == 0


class TestPreconditionSeverity:
    def test_levels(self):
        assert _precondition_severity("") == REJECTED
        assert _precondition_severity("已打开登录页并准备输入账号密码进行登录操作") == PENDING  # missing_login
        assert _precondition_severity("已登录系统并处于首页，账号具备管理员权限") == 0


class TestStepsSeverity:
    def test_empty_and_insufficient(self):
        assert _steps_severity([], "") == REJECTED
        assert _steps_severity([{"action": "点击登录", "expected_result": "进入首页"}], "") == REJECTED

    def test_content_issue(self):
        steps = [{"action": "点击登录", "expected_result": ""}] * 2
        assert _steps_severity(steps, "") == PENDING

    def test_ok(self):
        steps = [{"action": "点击登录", "expected_result": "进入首页"}] * 2
        assert _steps_severity(steps, "") == 0


class TestStepIssuePredicates:
    def test_fields_missing(self):
        assert QualityScoringService._step_fields_missing({"action": "", "expected_result": "ok"}) is True
        assert QualityScoringService._step_fields_missing({"action": "点击", "expected_result": "ok"}) is False

    def test_description_fallback_for_action(self):
        assert QualityScoringService._step_fields_missing({"description": "点击", "expected_result": "ok"}) is False

    def test_manual_judgment_only_for_ui_automation(self):
        step = {"action": "人工确认提示文案", "expected_result": "提示正确展示"}
        assert QualityScoringService._step_has_content_issue(step, "ui_automation") is True
        assert QualityScoringService._step_has_content_issue(step, "manual") is False

    def test_uncertain_wording(self):
        step = {"action": "点击登录或者注册", "expected_result": "进入下一页"}
        assert QualityScoringService._step_has_content_issue(step, "") is True


class TestExpectedAndCategorySeverity:
    def test_expected(self):
        assert _expected_severity("") == REJECTED
        assert _expected_severity("显示成功") == PENDING  # 过短 → short
        assert _expected_severity("页面跳转到首页并展示当前登录用户名") == 0

    def test_category(self):
        assert _category_severity("") == REJECTED
        assert _category_severity("不存在的分类") == REJECTED
        assert _category_severity("positive") == 0


class TestAuxSeverity:
    def test_empty_case_no_issue(self):
        assert _aux_severity({}, []) == 0

    def test_missing_test_data_is_warning(self):
        steps = [{"action_type": "input", "input_value": ""}] * 2
        assert _aux_severity({"steps": steps}, steps) >= WARNING


class TestGradeStatusAggregation:
    def _valid_case(self):
        return {
            "title": "登录成功进入首页并展示用户信息",
            "precondition": "已登录系统并处于首页，账号具备管理员权限",
            "steps": [
                {"action": "打开登录页", "expected_result": "展示登录表单"},
                {
                    "action": "输入用户名和密码",
                    "expected_result": "输入框显示已填内容",
                    "action_type": "input",
                    "input_value": "admin",
                },
                {"action": "点击登录按钮", "expected_result": "跳转到首页"},
            ],
            "expected_result": "页面跳转到首页并展示当前登录用户名",
            "case_category": "positive",
            "case_type": "manual",
        }

    def test_valid_case_not_rejected(self):
        assert QualityScoringService.grade_status(self._valid_case()) != "rejected"

    def test_empty_case_rejected(self):
        assert QualityScoringService.grade_status({}) == "rejected"

    def test_steps_issue_escalates_to_pending(self):
        case = self._valid_case()
        case["steps"] = [{"action": "点击登录或者注册", "expected_result": "进入下一页"}] * 2
        assert QualityScoringService.grade_status(case) == "pending_review"


class TestProjectAnalyzerHelpers:
    def test_empty_project_quality(self):
        payload = _empty_project_quality(7)
        assert payload["project_id"] == 7
        assert payload["total_cases"] == 0
        assert payload["reports"] == []

    def test_build_case_text_map(self):
        steps_map = {
            1: [SimpleNamespace(action=" 点击 登录 "), SimpleNamespace(action="输入User")],
            2: [],
        }
        assert _build_case_text_map(steps_map) == {1: "点击 登录 输入user", 2: ""}

    def test_quality_distribution(self):
        reports = [
            SimpleNamespace(overall_score=85),
            SimpleNamespace(overall_score=70),
            SimpleNamespace(overall_score=50),
            SimpleNamespace(overall_score=30),
        ]
        assert _build_quality_distribution(reports) == {"excellent": 1, "good": 1, "fair": 1, "poor": 1}

    def test_collect_top_issues(self):
        reports = [
            SimpleNamespace(case_id=1, case_name="A", suggestions=["s1", "s2"]),
            SimpleNamespace(case_id=2, case_name="B", suggestions=[]),
        ]
        issues = _collect_top_issues(reports)
        assert [i["suggestion"] for i in issues] == ["s1", "s2"]
        assert issues[0]["case_id"] == 1


class TestSuggestionBuilders:
    def test_complexity(self):
        complexity = SimpleNamespace(has_captcha=True, has_verification=False, step_count=7, level="very_complex")
        assert len(_complexity_suggestions(complexity)) == 4

    def test_complexity_clean(self):
        complexity = SimpleNamespace(has_captcha=False, has_verification=True, step_count=3, level="simple")
        assert _complexity_suggestions(complexity) == []

    def test_redundancy(self):
        redundancy = SimpleNamespace(similar_case_count=2, duplicate_step_count=1, level="high")
        assert len(_redundancy_suggestions(redundancy)) == 3

    def test_requirement_branches(self):
        no_points = SimpleNamespace(requirement_coverage_rate=0.0, requirement_details={})
        assert "暂无测试点" in _requirement_coverage_suggestions(no_points)[0]

        unlinked = SimpleNamespace(requirement_coverage_rate=0.0, requirement_details={"project_total_test_points": 3})
        assert "未关联测试点" in _requirement_coverage_suggestions(unlinked)[0]

        partial = SimpleNamespace(
            requirement_coverage_rate=0.5,
            requirement_details={"project_total_test_points": 3, "has_test_point_link": True},
        )
        assert "需求覆盖率为 50%" in _requirement_coverage_suggestions(partial)[0]

        full = SimpleNamespace(
            requirement_coverage_rate=1.0,
            requirement_details={"project_total_test_points": 3, "has_test_point_link": True},
        )
        assert _requirement_coverage_suggestions(full) == []

    def test_ui_branches(self):
        no_data = SimpleNamespace(ui_element_coverage_rate=0.0, ui_element_details={})
        assert "暂无UI原型" in _ui_coverage_suggestions(no_data)[0]

        no_target = SimpleNamespace(
            ui_element_coverage_rate=0.0, ui_element_details={"total_ui_labels": 3, "steps_with_target": 0}
        )
        assert "缺少目标元素" in _ui_coverage_suggestions(no_target)[0]

        low = SimpleNamespace(
            ui_element_coverage_rate=0.2,
            ui_element_details={"total_ui_labels": 3, "steps_with_target": 5, "matched_steps": 1},
        )
        assert "UI元素覆盖率仅 20%" in _ui_coverage_suggestions(low)[0]

        good = SimpleNamespace(
            ui_element_coverage_rate=0.9,
            ui_element_details={"total_ui_labels": 3, "steps_with_target": 5, "matched_steps": 5},
        )
        assert _ui_coverage_suggestions(good) == []

    def test_locator_branches(self):
        worst = SimpleNamespace(locator_coverage_rate=0.1, uncovered_elements=3, level="very_low")
        assert len(_locator_suggestions(worst)) == 2

        fine = SimpleNamespace(locator_coverage_rate=0.9, uncovered_elements=0, level="high")
        assert _locator_suggestions(fine) == []


class TestRedundancyTextHelpers:
    def test_steps_text_normalizes(self):
        steps = [SimpleNamespace(action=" 点击 登录 "), SimpleNamespace(action="输入User")]
        assert _steps_text(steps) == "点击 登录 输入user"

    def test_cached_text(self):
        case = SimpleNamespace(id=1)
        assert _cached_text(case, {1: "文本"}) == "文本"
        assert _cached_text(case, {2: "文本"}) is None
        assert _cached_text(case, None) is None

    def test_collect_candidate_texts_skips_self_and_empty(self):
        fake_self = SimpleNamespace(
            db=SimpleNamespace(query=lambda *a, **k: SimpleNamespace(filter=lambda *x: SimpleNamespace(all=lambda: [])))
        )
        target = SimpleNamespace(id=1)
        cases = [SimpleNamespace(id=1), SimpleNamespace(id=2), SimpleNamespace(id=3)]
        texts, picked = RedundancyMixin._collect_candidate_texts(fake_self, target, cases, {2: "有文本", 3: ""})
        assert texts == ["有文本"]
        assert [c.id for c in picked] == [2]


class TestTfidfSteps:
    def test_term_frequencies(self):
        assert _term_frequencies(["a", "a", "b"]) == {"a": 2, "b": 1}

    def test_prune_keeps_top_by_discrimination(self):
        vectorizer = LightweightTfidfVectorizer(maxFeatures=2)
        pruned = vectorizer._prune_terms({"a": 1, "b": 2, "c": 3}, n_docs=3)
        assert len(pruned) == 2

    def test_prune_noop_without_limit(self):
        vectorizer = LightweightTfidfVectorizer(maxFeatures=None)
        counts = {"a": 1, "b": 2}
        assert vectorizer._prune_terms(counts, n_docs=3) == counts

    def test_build_term_doc_count_dedupes_within_doc(self):
        assert LightweightTfidfVectorizer._build_term_doc_count([["a", "a", "b"], ["a"]]) == {"a": 2, "b": 1}

    def test_fit_transform_shape_and_normalization(self):
        vectorizer = LightweightTfidfVectorizer(maxFeatures=10)
        matrix = vectorizer.fit_transform(["登录页面输入用户名", "登录页面点击登录按钮"])
        assert matrix.shape[0] == 2
        norms = np.linalg.norm(matrix, axis=1)
        assert np.allclose(norms, 1.0)

    def test_fit_transform_empty_documents(self):
        assert LightweightTfidfVectorizer().fit_transform([]).shape == (0, 0)

    def test_compute_idf_smoothing(self):
        vectorizer = LightweightTfidfVectorizer()
        vectorizer.vocabulary_ = {"a": 0}
        idf = vectorizer._compute_idf({"a": 1}, n_docs=2)
        assert math.isclose(idf[0], math.log(3 / 2) + 1)
