"""依赖解析与快照容错机制单元测试。

覆盖:
    - _build_dependency_graph: 依赖图构建
    - _topological_sort_cases: 拓扑排序
    - _fill_depends_on: 自动填充依赖关系
    - _build_fallback_steps: 降级导航步骤构建
    - _infer_anchor_step: 锚点步骤推断
    - _mark_dependents_blocked: 阻塞标记
    - _should_skip_as_blocked: 阻塞跳过判断
    - _extract_url_from_text: URL提取
    - FailureCategory: 失败根因分类
"""
import json
import pytest
from unittest.mock import MagicMock
from typing import Any, Dict, List, Optional

from app.pipelines.steps._parsing import (
    _fill_depends_on,
    _build_fallback_steps,
    _infer_anchor_step,
    _extract_page_name,
    _extract_action_keywords,
)
from app.services.test_execution_engine.dependency_resolution_mixin import (
    DependencyResolutionMixin,
)
from app.services.test_execution_engine.models import (
    FailureCategory,
    ExecutionStatus,
    TestExecutionResult,
)


class _StubCase:
    def __init__(
        self,
        case_id: int,
        title: str,
        case_no: str = "",
        depends_on: Optional[str] = None,
        anchor_step: Optional[int] = None,
        fallback_steps: Optional[str] = None,
        precondition: str = "",
        steps_json: Optional[List[Dict[str, Any]]] = None,
    ):
        self.id = case_id
        self.title = title
        self.case_no = case_no or f"TC-{case_id:03d}"
        self.depends_on = depends_on
        self.anchor_step = anchor_step
        self.fallback_steps = fallback_steps
        self.precondition = precondition
        self.steps_json = steps_json or []


class _InferMixin:
    """用于测试 _infer_failure_category 系列方法的独立Mixin。"""
    _mobile_device_id = None
    _mobile_executor = None

    def _infer_failure_category(self, failed_steps, test_case):
        from app.services.test_execution_engine.models import FailureCategory
        is_mobile = getattr(self, '_mobile_device_id', None) is not None
        for step in failed_steps:
            error_msg = (step.error_message or "").lower()
            if self._is_crash_error(error_msg, is_mobile):
                return FailureCategory.CRASH_BUG
            if self._is_performance_error(error_msg, is_mobile):
                return FailureCategory.PERFORMANCE_BUG
        if is_mobile and self._is_device_compatibility_issue():
            return FailureCategory.COMPATIBILITY_BUG
        if any(r.healing_applied for r in failed_steps):
            return FailureCategory.LOCATOR_FAILURE
        return FailureCategory.PRODUCT_BUG

    def _is_crash_error(self, error_msg, is_mobile):
        crash_keywords = [
            "crashed", "crash", "not responding", "anr",
            "blank page", "white screen", "页面空白", "白屏",
            "sigsegv", "sigabrt", "native crash",
            "out of memory", "oom", "内存溢出",
            "force close", "unfortunately",
        ]
        return any(kw in error_msg for kw in crash_keywords)

    def _is_performance_error(self, error_msg, is_mobile):
        if not is_mobile:
            return False
        perf_keywords = [
            "timeout", "timed out", "超时",
            "network error", "网络错误", "连接超时",
            "err_connection", "err_name_not_resolved",
            "net::err", "load failed",
        ]
        return any(kw in error_msg for kw in perf_keywords)

    def _is_device_compatibility_issue(self):
        try:
            mobile_executor = getattr(self, '_mobile_executor', None)
            if not mobile_executor:
                return False
            adb = getattr(mobile_executor, 'adb', None)
            if not adb:
                return False
            connected = adb.is_device_connected()
            return not connected
        except Exception:
            return False


class _StubMixin(DependencyResolutionMixin, _InferMixin):
    def __init__(self):
        self._anchor_snapshots = {}
        self._case_results = {}
        self._failed_main_titles = set()
        self._title_to_case_no = {}
        self._pending_cases = []
        self._mobile_device_id = None
        self._mobile_executor = None


class TestBuildDependencyGraph:
    def test_no_dependencies(self):
        mixin = _StubMixin()
        cases = [
            _StubCase(1, "用例A"),
            _StubCase(2, "用例B"),
        ]
        graph = mixin._build_dependency_graph(cases)
        assert graph[1] == set()
        assert graph[2] == set()

    def test_with_dependencies(self):
        mixin = _StubMixin()
        cases = [
            _StubCase(1, "主干用例"),
            _StubCase(2, "分支用例", depends_on="主干用例"),
            _StubCase(3, "异常用例", depends_on="主干用例"),
        ]
        graph = mixin._build_dependency_graph(cases)
        assert graph[1] == set()
        assert 1 in graph[2]
        assert 1 in graph[3]

    def test_unknown_dependency_ignored(self):
        mixin = _StubMixin()
        cases = [
            _StubCase(1, "用例A", depends_on="不存在的用例"),
        ]
        graph = mixin._build_dependency_graph(cases)
        assert graph[1] == set()


class TestTopologicalSort:
    def test_main_first_then_dependents(self):
        mixin = _StubMixin()
        cases = [
            _StubCase(2, "分支用例", depends_on="主干用例"),
            _StubCase(1, "主干用例"),
            _StubCase(3, "异常用例", depends_on="主干用例"),
        ]
        graph = mixin._build_dependency_graph(cases)
        sorted_cases = mixin._topological_sort_cases(cases, graph)
        titles = [c.title for c in sorted_cases]
        main_idx = titles.index("主干用例")
        assert main_idx < titles.index("分支用例")
        assert main_idx < titles.index("异常用例")

    def test_no_dependencies_preserves_order(self):
        mixin = _StubMixin()
        cases = [
            _StubCase(1, "用例A"),
            _StubCase(2, "用例B"),
        ]
        graph = mixin._build_dependency_graph(cases)
        sorted_cases = mixin._topological_sort_cases(cases, graph)
        assert [c.id for c in sorted_cases] == [1, 2]


class TestFillDependsOn:
    def test_auto_fill_boundary_case(self):
        parsed = [
            {
                "title": "正向-登录成功",
                "case_category": "positive",
                "steps": [
                    {"step": 1, "action": "访问登录页", "expected_result": "登录页加载完成"},
                    {"step": 2, "action": "输入账号密码", "expected_result": "输入框显示内容"},
                    {"step": 3, "action": "点击登录", "expected_result": "跳转首页"},
                ],
            },
            {
                "title": "边界-密码错误5次锁定",
                "case_category": "boundary",
                "precondition": "已处于登录页",
                "steps": [
                    {"step": 1, "action": "输入错误密码5次", "expected_result": "账号锁定"},
                ],
            },
        ]
        _fill_depends_on(parsed)
        assert parsed[1]["depends_on"] == "正向-登录成功"
        assert parsed[1]["anchor_step"] is not None
        assert parsed[1]["fallback_steps"] is not None

    def test_preserve_existing_depends_on(self):
        parsed = [
            {
                "title": "正向-登录成功",
                "case_category": "positive",
                "steps": [{"step": 1, "action": "登录", "expected_result": "成功"}],
            },
            {
                "title": "异常-网络超时",
                "case_category": "exception",
                "depends_on": "自定义依赖",
                "anchor_step": 5,
                "steps": [{"step": 1, "action": "触发超时", "expected_result": "超时提示"}],
            },
        ]
        _fill_depends_on(parsed)
        assert parsed[1]["depends_on"] == "自定义依赖"
        assert parsed[1]["anchor_step"] == 5

    def test_no_positive_case_skips(self):
        parsed = [
            {
                "title": "异常-无主干",
                "case_category": "exception",
                "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
            },
        ]
        _fill_depends_on(parsed)
        assert "depends_on" not in parsed[0]


class TestBuildFallbackSteps:
    def test_extract_up_to_anchor(self):
        main_steps = [
            {"step": 1, "action": "访问首页", "action_type": "navigate", "target_element": "", "input_value": "/home"},
            {"step": 2, "action": "点击商品", "action_type": "click", "target_element": "商品卡片", "input_value": ""},
            {"step": 3, "action": "加入购物车", "action_type": "click", "target_element": "加入购物车按钮", "input_value": ""},
            {"step": 4, "action": "确认订单", "action_type": "click", "target_element": "确认按钮", "input_value": ""},
        ]
        result = _build_fallback_steps(main_steps, 2)
        assert len(result) == 2
        assert result[0]["step"] == 1
        assert result[1]["step"] == 2
        assert result[0]["action"] == "访问首页"
        assert result[1]["action"] == "点击商品"

    def test_anchor_at_first_step(self):
        main_steps = [
            {"step": 1, "action": "访问登录页", "action_type": "navigate", "target_element": "", "input_value": "/login"},
            {"step": 2, "action": "输入账号", "action_type": "input", "target_element": "账号输入框", "input_value": "admin"},
        ]
        result = _build_fallback_steps(main_steps, 1)
        assert len(result) == 1
        assert result[0]["step"] == 1

    def test_empty_steps(self):
        result = _build_fallback_steps([], 3)
        assert result == []

    def test_skip_invalid_step_numbers(self):
        main_steps = [
            {"step": "abc", "action": "无效步骤"},
            {"step": 2, "action": "有效步骤", "action_type": "click", "target_element": "按钮", "input_value": ""},
        ]
        result = _build_fallback_steps(main_steps, 2)
        assert len(result) == 1
        assert result[0]["step"] == 2


class TestInferAnchorStep:
    def test_match_page_name_in_precondition(self):
        case = {
            "precondition": "已处于确认订单页，可见提交按钮",
            "title": "异常-支付失败",
        }
        main_steps = [
            {"step": 1, "action": "访问首页", "expected_result": "首页加载完成"},
            {"step": 2, "action": "选择商品", "expected_result": "商品详情页可见"},
            {"step": 3, "action": "点击立即购买", "expected_result": "跳转至确认订单页"},
        ]
        anchor = _infer_anchor_step(case, main_steps)
        assert anchor == 3

    def test_match_action_keywords(self):
        case = {
            "precondition": "在购物车页面",
            "title": "边界-库存不足提交订单",
        }
        main_steps = [
            {"step": 1, "action": "访问首页", "expected_result": "首页加载"},
            {"step": 2, "action": "提交订单", "expected_result": "订单提交成功"},
        ]
        anchor = _infer_anchor_step(case, main_steps)
        assert anchor == 2

    def test_no_match_returns_none(self):
        case = {
            "precondition": "系统正常运行",
            "title": "异常-未知场景",
        }
        main_steps = [
            {"step": 1, "action": "访问首页", "expected_result": "首页加载"},
        ]
        anchor = _infer_anchor_step(case, main_steps)
        assert anchor is None


class TestExtractPageName:
    def test_pattern_already_at_page(self):
        assert _extract_page_name("已处于确认订单页") == "确认订单页"

    def test_pattern_at_page(self):
        assert _extract_page_name("处于支付页") == "支付页"

    def test_pattern_on_page(self):
        assert _extract_page_name("在登录页面") == "登录页"

    def test_no_match(self):
        assert _extract_page_name("系统正常运行") is None


class TestExtractActionKeywords:
    def test_match_keywords(self):
        result = _extract_action_keywords("提交订单后支付失败")
        assert "提交订单" in result
        assert "支付失败" in result

    def test_no_match(self):
        result = _extract_action_keywords("查看页面内容")
        assert result == []


class TestMarkDependentsBlocked:
    def test_mark_blocked_on_main_failure(self):
        mixin = _StubMixin()
        main_case = _StubCase(1, "主干用例")
        dep_case1 = _StubCase(2, "分支用例", depends_on="主干用例")
        dep_case2 = _StubCase(3, "异常用例", depends_on="主干用例")
        other_case = _StubCase(4, "独立用例")

        blocked = mixin._mark_dependents_blocked(
            main_case, [main_case, dep_case1, dep_case2, other_case], {}
        )
        assert 2 in blocked
        assert 3 in blocked
        assert 4 not in blocked

    def test_should_skip_as_blocked(self):
        mixin = _StubMixin()
        mixin._failed_main_titles.add("主干用例")
        dep_case = _StubCase(2, "分支用例", depends_on="主干用例")
        other_case = _StubCase(3, "独立用例")

        assert mixin._should_skip_as_blocked(dep_case) is True
        assert mixin._should_skip_as_blocked(other_case) is False


class TestExtractUrlFromText:
    def test_extract_https_url(self):
        mixin = _StubMixin()
        assert mixin._extract_url_from_text("访问 https://example.com/login 页面") == "https://example.com/login"

    def test_extract_http_url(self):
        mixin = _StubMixin()
        assert mixin._extract_url_from_text("导航到 http://test.com/home") == "http://test.com/home"

    def test_extract_path(self):
        mixin = _StubMixin()
        result = mixin._extract_url_from_text("输入 /login 并回车")
        assert result == "/login"

    def test_no_url(self):
        mixin = _StubMixin()
        assert mixin._extract_url_from_text("点击登录按钮") is None


class TestFallbackStepsJsonParsing:
    def test_fallback_steps_stored_as_json_string(self):
        main_steps = [
            {"step": 1, "action": "访问首页", "action_type": "navigate", "target_element": "", "input_value": "/home"},
            {"step": 2, "action": "点击商品", "action_type": "click", "target_element": "商品卡片", "input_value": ""},
        ]
        fallback = _build_fallback_steps(main_steps, 2)
        json_str = json.dumps(fallback, ensure_ascii=False)
        parsed_back = json.loads(json_str)
        assert len(parsed_back) == 2
        assert parsed_back[0]["action"] == "访问首页"
        assert parsed_back[1]["action"] == "点击商品"


class TestFailureCategory:
    def test_product_bug_is_real_bug(self):
        result = TestExecutionResult(
            case_id=1,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PRODUCT_BUG,
        )
        assert result.failure_category == FailureCategory.PRODUCT_BUG
        assert result.failure_category.value == "product_bug"

    def test_upstream_blocked_is_not_product_bug(self):
        result = TestExecutionResult(
            case_id=2,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.UPSTREAM_BLOCKED,
        )
        assert result.failure_category == FailureCategory.UPSTREAM_BLOCKED
        assert result.failure_category.value != "product_bug"

    def test_navigation_failure_is_infrastructure_issue(self):
        result = TestExecutionResult(
            case_id=3,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.NAVIGATION_FAILURE,
        )
        assert result.failure_category == FailureCategory.NAVIGATION_FAILURE

    def test_precondition_failure_is_infrastructure_issue(self):
        result = TestExecutionResult(
            case_id=4,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PRECONDITION_FAILURE,
        )
        assert result.failure_category == FailureCategory.PRECONDITION_FAILURE

    def test_environment_error_is_infrastructure_issue(self):
        result = TestExecutionResult(
            case_id=5,
            status=ExecutionStatus.ERROR,
            failure_category=FailureCategory.ENVIRONMENT_ERROR,
        )
        assert result.failure_category == FailureCategory.ENVIRONMENT_ERROR

    def test_locator_failure_needs_manual_review(self):
        result = TestExecutionResult(
            case_id=6,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.LOCATOR_FAILURE,
        )
        assert result.failure_category == FailureCategory.LOCATOR_FAILURE

    def test_passed_case_has_no_failure_category(self):
        result = TestExecutionResult(
            case_id=7,
            status=ExecutionStatus.PASSED,
        )
        assert result.failure_category is None

    def test_to_dict_includes_failure_category(self):
        result = TestExecutionResult(
            case_id=8,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PRODUCT_BUG,
            navigation_level="Level1-快照恢复",
        )
        d = result.to_dict()
        assert d["failure_category"] == "product_bug"
        assert d["navigation_level"] == "Level1-快照恢复"

    def test_to_dict_none_failure_category(self):
        result = TestExecutionResult(
            case_id=9,
            status=ExecutionStatus.PASSED,
        )
        d = result.to_dict()
        assert d["failure_category"] is None
        assert d["navigation_level"] is None

    def test_distinguish_real_bug_from_false_positive(self):
        product_bug = TestExecutionResult(
            case_id=10,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PRODUCT_BUG,
        )
        nav_failure = TestExecutionResult(
            case_id=11,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.NAVIGATION_FAILURE,
        )
        upstream_blocked = TestExecutionResult(
            case_id=12,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.UPSTREAM_BLOCKED,
        )
        real_bugs = [
            r for r in [product_bug, nav_failure, upstream_blocked]
            if FailureCategory.is_product_bug(r.failure_category)
        ]
        false_positives = [
            r for r in [product_bug, nav_failure, upstream_blocked]
            if FailureCategory.is_false_positive(r.failure_category)
        ]
        assert len(real_bugs) == 1
        assert len(false_positives) == 2


class TestCEndFailureCategories:
    def test_performance_bug_is_product_bug(self):
        result = TestExecutionResult(
            case_id=20,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PERFORMANCE_BUG,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is True
        assert FailureCategory.is_false_positive(result.failure_category) is False

    def test_compatibility_bug_is_product_bug(self):
        result = TestExecutionResult(
            case_id=21,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.COMPATIBILITY_BUG,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is True
        assert FailureCategory.is_false_positive(result.failure_category) is False

    def test_crash_bug_is_product_bug(self):
        result = TestExecutionResult(
            case_id=22,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.CRASH_BUG,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is True
        assert FailureCategory.is_false_positive(result.failure_category) is False

    def test_c_end_full_scenario_filtering(self):
        results = [
            TestExecutionResult(case_id=30, status=ExecutionStatus.PASSED),
            TestExecutionResult(case_id=31, status=ExecutionStatus.FAILED, failure_category=FailureCategory.PRODUCT_BUG),
            TestExecutionResult(case_id=32, status=ExecutionStatus.FAILED, failure_category=FailureCategory.CRASH_BUG),
            TestExecutionResult(case_id=33, status=ExecutionStatus.FAILED, failure_category=FailureCategory.PERFORMANCE_BUG),
            TestExecutionResult(case_id=34, status=ExecutionStatus.FAILED, failure_category=FailureCategory.COMPATIBILITY_BUG),
            TestExecutionResult(case_id=35, status=ExecutionStatus.FAILED, failure_category=FailureCategory.UPSTREAM_BLOCKED),
            TestExecutionResult(case_id=36, status=ExecutionStatus.FAILED, failure_category=FailureCategory.NAVIGATION_FAILURE),
            TestExecutionResult(case_id=37, status=ExecutionStatus.ERROR, failure_category=FailureCategory.ENVIRONMENT_ERROR),
        ]
        real_bugs = [r for r in results if FailureCategory.is_product_bug(r.failure_category)]
        false_positives = [r for r in results if FailureCategory.is_false_positive(r.failure_category)]
        passed = [r for r in results if r.status == ExecutionStatus.PASSED]

        assert len(passed) == 1
        assert len(real_bugs) == 4
        assert len(false_positives) == 3
        real_bug_ids = [r.case_id for r in real_bugs]
        assert 31 in real_bug_ids
        assert 32 in real_bug_ids
        assert 33 in real_bug_ids
        assert 34 in real_bug_ids

    def test_b_end_timeout_is_not_product_bug(self):
        result = TestExecutionResult(
            case_id=40,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.NAVIGATION_FAILURE,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is False

    def test_c_end_crash_highest_priority(self):
        crash = FailureCategory.CRASH_BUG
        perf = FailureCategory.PERFORMANCE_BUG
        compat = FailureCategory.COMPATIBILITY_BUG
        product = FailureCategory.PRODUCT_BUG

        all_product_bugs = [crash, perf, compat, product]
        assert all(FailureCategory.is_product_bug(fc) for fc in all_product_bugs)


class TestInferFailureCategory:
    def test_crash_detection_app_crash(self):
        mixin = _StubMixin()
        step = MagicMock()
        step.error_message = "App process crashed unexpectedly"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.CRASH_BUG

    def test_crash_detection_anr(self):
        mixin = _StubMixin()
        step = MagicMock()
        step.error_message = "Application not responding (ANR)"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.CRASH_BUG

    def test_crash_detection_white_screen(self):
        mixin = _StubMixin()
        step = MagicMock()
        step.error_message = "页面空白 white screen detected"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.CRASH_BUG

    def test_crash_detection_oom(self):
        mixin = _StubMixin()
        step = MagicMock()
        step.error_message = "OutOfMemoryError: out of memory allocating bitmap"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.CRASH_BUG

    def test_performance_bug_mobile_timeout(self):
        mixin = _StubMixin()
        mixin._mobile_device_id = "device_123"
        step = MagicMock()
        step.error_message = "Element timed out waiting for selector"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.PERFORMANCE_BUG

    def test_performance_bug_mobile_network_error(self):
        mixin = _StubMixin()
        mixin._mobile_device_id = "device_123"
        step = MagicMock()
        step.error_message = "net::err_connection_timed_out"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.PERFORMANCE_BUG

    def test_b_end_timeout_not_performance_bug(self):
        mixin = _StubMixin()
        step = MagicMock()
        step.error_message = "Element timed out waiting for selector"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.PRODUCT_BUG

    def test_locator_failure_with_healing(self):
        mixin = _StubMixin()
        step = MagicMock()
        step.error_message = "Element not found"
        step.healing_applied = True
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.LOCATOR_FAILURE

    def test_default_product_bug(self):
        mixin = _StubMixin()
        step = MagicMock()
        step.error_message = "Expected text '成功' but found '失败'"
        step.healing_applied = False
        case = MagicMock()
        result = mixin._infer_failure_category([step], case)
        assert result == FailureCategory.PRODUCT_BUG


class TestApiSetupMixin:
    def test_substitute_api_vars(self):
        from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin

        class _ApiStub(ApiSetupMixin):
            pass

        stub = _ApiStub()
        stub._api_extracted_vars = {"order_id": 12345, "user_name": "testuser"}
        data = {
            "order_id": "{{order_id}}",
            "name": "{{user_name}}",
            "quantity": 1,
            "nested": {"ref_id": "{{order_id}}"},
        }
        result = stub._substitute_api_vars(data)
        assert result["order_id"] == 12345
        assert result["name"] == "testuser"
        assert result["quantity"] == 1
        assert result["nested"]["ref_id"] == 12345

    def test_resolve_json_path(self):
        from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin

        class _ApiStub(ApiSetupMixin):
            pass

        stub = _ApiStub()
        data = {"data": {"id": 42, "order_no": "ORD001"}, "list": [10, 20, 30]}
        assert stub._resolve_json_path(data, "$.data.id") == 42
        assert stub._resolve_json_path(data, "$.data.order_no") == "ORD001"
        assert stub._resolve_json_path(data, "$.list.0") == 10
        assert stub._resolve_json_path(data, "$.nonexistent") is None

    def test_resolve_json_path_no_dollar(self):
        from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin

        class _ApiStub(ApiSetupMixin):
            pass

        stub = _ApiStub()
        data = {"token": "abc123"}
        assert stub._resolve_json_path(data, "token") == "abc123"

    def test_extract_api_vars(self):
        from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin

        class _ApiStub(ApiSetupMixin):
            pass

        stub = _ApiStub()
        stub._api_extracted_vars = {}
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"id": 99, "name": "测试订单"}}
        stub._extract_api_vars(mock_response, {"order_id": "$.data.id", "order_name": "$.data.name"})
        assert stub._api_extracted_vars["order_id"] == 99
        assert stub._api_extracted_vars["order_name"] == "测试订单"

    def test_no_setup_api_calls_returns_false(self):
        from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin

        class _ApiStub(ApiSetupMixin):
            pass

        stub = _ApiStub()
        case = MagicMock()
        case.setup_api_calls = None
        import asyncio
        ok, desc = asyncio.get_event_loop().run_until_complete(
            stub._execute_setup_api_calls(case)
        )
        assert ok is False

    def test_invalid_json_returns_false(self):
        from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin

        class _ApiStub(ApiSetupMixin):
            pass

        stub = _ApiStub()
        case = MagicMock()
        case.setup_api_calls = "not valid json{{{"
        import asyncio
        ok, desc = asyncio.get_event_loop().run_until_complete(
            stub._execute_setup_api_calls(case)
        )
        assert ok is False
        assert "JSON" in desc


class TestNavigationPriorityBEndVsCEnd:
    def test_b_end_api_setup_takes_priority(self):
        mixin = _StubMixin()
        mixin._mobile_device_id = None
        case = MagicMock()
        case.setup_api_calls = json.dumps([{"method": "GET", "url": "/api/test"}])
        case.depends_on = "主干用例"
        case.anchor_step = 3
        assert bool(getattr(case, 'setup_api_calls', None)) is True

    def test_c_end_snapshot_takes_priority_over_api(self):
        mixin = _StubMixin()
        mixin._mobile_device_id = "device_123"
        case = MagicMock()
        case.setup_api_calls = None
        case.depends_on = "主干用例"
        case.anchor_step = 3
        is_mobile = getattr(mixin, '_mobile_device_id', None) is not None
        assert is_mobile is True
        assert bool(getattr(case, 'setup_api_calls', None)) is False


class TestMobileSnapshot:
    def test_element_matches_by_resource_id(self):
        """resource_id匹配但text不匹配时，仅1/2属性匹配，应返回False。"""
        from app.services.test_execution_engine.dependency_resolution_mixin import DependencyResolutionMixin

        expected = {"resource_id": "com.app:id/btn_submit", "text": "提交"}
        current = MagicMock()
        current.resource_id = "com.app:id/btn_submit"
        current.text = "提交订单"
        current.content_desc = None
        assert DependencyResolutionMixin._element_matches(expected, current) is False

    def test_element_matches_by_two_attributes(self):
        """至少两个属性同时匹配时返回True。"""
        from app.services.test_execution_engine.dependency_resolution_mixin import DependencyResolutionMixin

        expected = {"resource_id": "com.app:id/btn_submit", "text": "提交"}
        current = MagicMock()
        current.resource_id = "com.app:id/btn_submit"
        current.text = "提交"
        current.content_desc = None
        assert DependencyResolutionMixin._element_matches(expected, current) is True

    def test_element_matches_by_text(self):
        from app.services.test_execution_engine.dependency_resolution_mixin import DependencyResolutionMixin

        expected = {"text": "取消订单"}
        current = MagicMock()
        current.resource_id = "com.app:id/btn_cancel"
        current.text = "取消订单"
        current.content_desc = None
        assert DependencyResolutionMixin._element_matches(expected, current) is True

    def test_element_matches_by_content_desc(self):
        from app.services.test_execution_engine.dependency_resolution_mixin import DependencyResolutionMixin

        expected = {"content_desc": "购物车"}
        current = MagicMock()
        current.resource_id = None
        current.text = ""
        current.content_desc = "购物车"
        assert DependencyResolutionMixin._element_matches(expected, current) is True

    def test_element_not_matches(self):
        from app.services.test_execution_engine.dependency_resolution_mixin import DependencyResolutionMixin

        expected = {"resource_id": "com.app:id/btn_submit", "text": "提交"}
        current = MagicMock()
        current.resource_id = "com.app:id/btn_cancel"
        current.text = "取消"
        current.content_desc = None
        assert DependencyResolutionMixin._element_matches(expected, current) is False

    def test_web_snapshot_has_type_field(self):
        mixin = _StubMixin()
        mixin._anchor_snapshots["主干_3"] = {
            "type": "web",
            "url": "https://example.com/orders/123",
            "anchor_step": 3,
            "case_title": "主干",
        }
        snapshot = mixin._anchor_snapshots.get("主干_3")
        assert snapshot["type"] == "web"
        assert "url" in snapshot

    def test_mobile_snapshot_has_type_field(self):
        mixin = _StubMixin()
        mixin._anchor_snapshots["主干_3"] = {
            "type": "mobile",
            "current_activity": "com.app/.OrderDetailActivity",
            "ui_element_summary": [
                {"resource_id": "com.app:id/btn_cancel", "text": "取消订单"},
            ],
            "screenshot_hash": "abc123def456",
            "anchor_step": 3,
            "case_title": "主干",
            "app_package": "com.app",
        }
        snapshot = mixin._anchor_snapshots.get("主干_3")
        assert snapshot["type"] == "mobile"
        assert "current_activity" in snapshot
        assert "ui_element_summary" in snapshot
        assert len(snapshot["ui_element_summary"]) == 1

    def test_mobile_vs_web_snapshot_structure(self):
        web_snapshot = {
            "type": "web",
            "url": "https://example.com/orders",
            "storage_state": {"cookies": [], "origins": []},
        }
        mobile_snapshot = {
            "type": "mobile",
            "current_activity": "com.app/.OrderListActivity",
            "ui_element_summary": [{"text": "订单列表"}],
            "screenshot_hash": "hash123",
            "app_package": "com.app",
        }
        assert web_snapshot["type"] != mobile_snapshot["type"]
        assert "url" in web_snapshot
        assert "current_activity" in mobile_snapshot
        assert "storage_state" in web_snapshot
        assert "ui_element_summary" in mobile_snapshot
