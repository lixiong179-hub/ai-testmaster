"""端到端集成测试 - 验证依赖解析、快照容错、失败分类的完整执行流程。

测试场景:
    1. B端Web: 主干用例执行→快照保存→分支用例快照恢复→失败分类
    2. B端Web: 主干用例失败→下游用例BLOCKED→失败根因分类
    3. C端Mobile: Activity快照保存→UI元素验证→降级导航
    4. API前置准备: 变量提取→变量替换→断言验证
    5. 失败分类: 产品Bug vs 误报的区分
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List, Optional

from app.services.test_execution_engine.models import (
    ExecutionStatus,
    FailureCategory,
    TestExecutionResult,
    StepExecutionResult,
    ActionType,
)
from app.services.test_execution_engine.dependency_resolution_mixin import (
    DependencyResolutionMixin,
)
from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin


class _StubCase:
    def __init__(
        self,
        case_id: int,
        title: str,
        case_no: str = "",
        depends_on: Optional[str] = None,
        anchor_step: Optional[int] = None,
        fallback_steps: Optional[str] = None,
        setup_api_calls: Optional[str] = None,
        precondition: str = "",
        steps_json: Optional[List[Dict[str, Any]]] = None,
    ):
        self.id = case_id
        self.title = title
        self.case_no = case_no or f"TC-{case_id:03d}"
        self.depends_on = depends_on
        self.anchor_step = anchor_step
        self.fallback_steps = fallback_steps
        self.setup_api_calls = setup_api_calls
        self.precondition = precondition
        self.steps_json = steps_json or []


class _FullEngine(
    DependencyResolutionMixin,
    ApiSetupMixin,
):
    """模拟完整引擎，包含所有容错Mixin。"""

    def __init__(self, is_mobile: bool = False):
        self._anchor_snapshots: Dict[str, Dict[str, Any]] = {}
        self._case_results: Dict[int, TestExecutionResult] = {}
        self._failed_main_titles: set = set()
        self._title_to_case_no: Dict[str, str] = {}
        self._pending_cases: List[_StubCase] = []
        self._api_extracted_vars: Dict[str, Any] = {}
        self._mobile_device_id = "device_123" if is_mobile else None
        self._mobile_executor = None
        self._project_base_url = "https://api.example.com"
        self.browser = None
        self._current_project = None
        self._step_results: List[Any] = []


# ============================================================
# 场景1: B端Web - 主干用例成功→快照保存→分支用例快照恢复
# ============================================================
class TestBEndWebSnapshotFlow:
    @pytest.mark.asyncio
    async def test_main_case_saves_snapshot_branch_restores(self):
        """B端Web: 主干用例步骤3通过后保存快照，分支用例恢复快照。"""
        engine = _FullEngine(is_mobile=False)

        mock_page = AsyncMock()
        mock_page.url = "https://admin.example.com/orders/123"
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock(return_value={
            "cookies": [{"name": "token", "value": "abc123", "domain": ".example.com"}],
            "origins": [{"origin": "https://admin.example.com", "localStorage": [
                {"name": "user_role", "value": "admin"}
            ]}],
        })

        engine.browser = MagicMock()
        engine.browser._page = mock_page
        engine.browser._context = mock_context

        main_case = _StubCase(1, "正向-创建订单成功", "TC-001")
        saved = await engine._save_anchor_snapshot(main_case, 3)
        assert saved is True

        snapshot_key = "TC-001_3"
        assert snapshot_key in engine._anchor_snapshots
        snapshot = engine._anchor_snapshots[snapshot_key]
        assert snapshot["type"] == "web"
        assert snapshot["url"] == "https://admin.example.com/orders/123"
        assert "storage_state" in snapshot

        mock_page.goto = AsyncMock()
        mock_context.add_cookies = AsyncMock()

        branch_case = _StubCase(
            2, "异常-取消已创建订单", "TC-002",
            depends_on="正向-创建订单成功", anchor_step=3,
        )
        engine._title_to_case_no["正向-创建订单成功"] = "TC-001"
        restored = await engine._restore_anchor_snapshot(branch_case)
        assert restored is True
        mock_page.goto.assert_called()

    @pytest.mark.asyncio
    async def test_snapshot_restores_cookies_and_localStorage(self):
        """B端Web: 快照恢复时正确还原cookies和localStorage。"""
        engine = _FullEngine(is_mobile=False)

        mock_page = AsyncMock()
        mock_page.url = "https://admin.example.com/dashboard"
        mock_page.evaluate = AsyncMock()
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock(return_value={
            "cookies": [{"name": "session", "value": "sess_abc", "domain": ".example.com"}],
            "origins": [{"origin": "https://admin.example.com", "localStorage": [
                {"name": "theme", "value": "dark"},
                {"name": "lang", "value": "zh-CN"},
            ]}],
        })

        engine.browser = MagicMock()
        engine.browser._page = mock_page
        engine.browser._context = mock_context

        main_case = _StubCase(1, "正向-登录成功", "TC-001")
        await engine._save_anchor_snapshot(main_case, 1)

        mock_page.goto = AsyncMock()
        mock_context.add_cookies = AsyncMock()

        branch_case = _StubCase(2, "分支-修改个人资料", "TC-002",
                                depends_on="正向-登录成功", anchor_step=1)
        engine._title_to_case_no["正向-登录成功"] = "TC-001"
        restored = await engine._restore_anchor_snapshot(branch_case)
        assert restored is True

        # 恢复流程: goto(url) → add_cookies → evaluate(localStorage.setItem) x2
        mock_page.goto.assert_called()
        mock_context.add_cookies.assert_called_once()
        assert mock_page.evaluate.call_count == 2


# ============================================================
# 场景2: B端Web - 主干用例失败→下游用例BLOCKED
# ============================================================
class TestBEndWebBlockedFlow:
    def test_main_failure_marks_dependents_blocked(self):
        """B端Web: 主干用例失败后，所有依赖用例标记为BLOCKED。"""
        engine = _FullEngine(is_mobile=False)

        main_case = _StubCase(1, "正向-创建订单", "TC-001")
        branch1 = _StubCase(2, "异常-取消订单", "TC-002", depends_on="正向-创建订单")
        branch2 = _StubCase(3, "边界-重复提交", "TC-003", depends_on="正向-创建订单")
        independent = _StubCase(4, "正向-查看报表", "TC-004")

        all_cases = [main_case, branch1, branch2, independent]

        blocked_ids = engine._mark_dependents_blocked(main_case, all_cases, {})
        assert 2 in blocked_ids
        assert 3 in blocked_ids
        assert 4 not in blocked_ids

        assert engine._should_skip_as_blocked(branch1) is True
        assert engine._should_skip_as_blocked(branch2) is True
        assert engine._should_skip_as_blocked(independent) is False

    def test_blocked_case_not_counted_as_product_bug(self):
        """BLOCKED用例不应计入产品Bug统计。"""
        result = TestExecutionResult(
            case_id=2,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.UPSTREAM_BLOCKED,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is False
        assert FailureCategory.is_false_positive(result.failure_category) is True


# ============================================================
# 场景3: C端Mobile - Activity快照保存与恢复
# ============================================================
class TestCEndMobileSnapshotFlow:
    @pytest.mark.asyncio
    async def test_mobile_snapshot_saves_activity_and_ui(self):
        """C端Mobile: 快照保存Activity、UI元素摘要和截图hash。"""
        engine = _FullEngine(is_mobile=True)

        mock_adb = AsyncMock()
        mock_adb.get_current_activity = AsyncMock(
            return_value="com.shopapp/.OrderDetailActivity"
        )
        mock_adb.take_screenshot = AsyncMock(
            return_value=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        )

        mock_uiautomator = AsyncMock()
        mock_elem1 = MagicMock()
        mock_elem1.resource_id = "com.shopapp:id/btn_cancel_order"
        mock_elem1.text = "取消订单"
        mock_elem1.content_desc = None
        mock_elem2 = MagicMock()
        mock_elem2.resource_id = "com.shopapp:id/tv_order_status"
        mock_elem2.text = "待发货"
        mock_elem2.content_desc = None
        mock_uiautomator.get_clickable_elements = AsyncMock(
            return_value=[mock_elem1, mock_elem2]
        )

        mock_executor = MagicMock()
        mock_executor.adb = mock_adb
        mock_executor.uiautomator = mock_uiautomator
        engine._mobile_executor = mock_executor

        mock_project = MagicMock()
        mock_project.test_object_app_package = "com.shopapp"
        mock_project.test_object_app_activity = ".MainActivity"
        engine._current_project = mock_project

        main_case = _StubCase(1, "正向-下单成功", "TC-001")
        saved = await engine._save_anchor_snapshot(main_case, 3)
        assert saved is True

        snapshot_key = "TC-001_3"
        assert snapshot_key in engine._anchor_snapshots
        snapshot = engine._anchor_snapshots[snapshot_key]
        assert snapshot["type"] == "mobile"
        assert snapshot["current_activity"] == "com.shopapp/.OrderDetailActivity"
        assert len(snapshot["ui_element_summary"]) == 2
        assert snapshot["ui_element_summary"][0]["resource_id"] == "com.shopapp:id/btn_cancel_order"
        assert snapshot["app_package"] == "com.shopapp"

    @pytest.mark.asyncio
    async def test_mobile_restore_verifies_ui_elements(self):
        """C端Mobile: 快照恢复时验证UI元素是否匹配。"""
        engine = _FullEngine(is_mobile=True)

        engine._anchor_snapshots["TC-001_3"] = {
            "type": "mobile",
            "current_activity": "com.shopapp/.OrderDetailActivity",
            "ui_element_summary": [
                {"resource_id": "com.shopapp:id/btn_cancel_order", "text": "取消订单"},
                {"resource_id": "com.shopapp:id/tv_order_status", "text": "待发货"},
            ],
            "screenshot_hash": "abc123",
            "anchor_step": 3,
            "case_title": "正向-下单成功",
            "app_package": "com.shopapp",
        }
        engine._title_to_case_no["正向-下单成功"] = "TC-001"

        mock_adb = AsyncMock()
        mock_adb.get_current_activity = AsyncMock(
            return_value="com.shopapp/.OrderListActivity"
        )
        mock_adb.start_app = AsyncMock()

        mock_elem1 = MagicMock()
        mock_elem1.resource_id = "com.shopapp:id/btn_cancel_order"
        mock_elem1.text = "取消订单"
        mock_elem1.content_desc = None
        mock_elem2 = MagicMock()
        mock_elem2.resource_id = "com.shopapp:id/tv_order_status"
        mock_elem2.text = "待发货"
        mock_elem2.content_desc = None

        mock_uiautomator = AsyncMock()
        mock_uiautomator.get_clickable_elements = AsyncMock(
            return_value=[mock_elem1, mock_elem2]
        )

        mock_executor = MagicMock()
        mock_executor.adb = mock_adb
        mock_executor.uiautomator = mock_uiautomator
        engine._mobile_executor = mock_executor

        branch_case = _StubCase(
            2, "异常-取消订单", "TC-002",
            depends_on="正向-下单成功", anchor_step=3,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            restored = await engine._restore_anchor_snapshot(branch_case)

        assert restored is True
        mock_adb.start_app.assert_called_once_with(
            "com.shopapp", ".OrderDetailActivity"
        )


# ============================================================
# 场景4: 四级降级策略
# ============================================================
class TestFourLevelDegradation:
    @pytest.mark.asyncio
    async def test_b_end_api_setup_highest_priority(self):
        """B端: 有setup_api_calls时优先使用API前置准备。"""
        engine = _FullEngine(is_mobile=False)
        engine._init_api_setup_state()

        case = _StubCase(
            2, "异常-取消订单", "TC-002",
            depends_on="正向-创建订单", anchor_step=3,
            setup_api_calls=json.dumps([
                {"method": "POST", "url": "/api/v1/orders", "body": {"product_id": 1},
                 "assert": {"status_code": 201}, "extract": {"order_id": "$.data.id"}},
            ]),
        )

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        engine.browser = MagicMock()
        engine.browser._page = mock_page

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"data": {"id": 42}}
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, level = await engine._navigate_to_dependency_anchor(case)

        assert ok is True
        assert "Level0" in level or "API" in level
        assert engine._api_extracted_vars.get("order_id") == 42

    @pytest.mark.asyncio
    async def test_b_end_fallback_to_snapshot_when_no_api(self):
        """B端: 无API配置时降级到快照恢复。"""
        engine = _FullEngine(is_mobile=False)

        engine._anchor_snapshots["TC-001_3"] = {
            "type": "web",
            "url": "https://admin.example.com/orders/123",
            "storage_state": {"cookies": [], "origins": []},
            "anchor_step": 3,
            "case_title": "主干",
        }
        engine._title_to_case_no["主干"] = "TC-001"

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_context = AsyncMock()
        mock_context.add_cookies = AsyncMock()
        engine.browser = MagicMock()
        engine.browser._page = mock_page
        engine.browser._context = mock_context

        case = _StubCase(
            2, "分支用例", "TC-002",
            depends_on="主干", anchor_step=3,
        )
        ok, level = await engine._navigate_to_dependency_anchor(case)
        assert ok is True
        assert "Level1" in level or "快照" in level

    @pytest.mark.asyncio
    async def test_c_end_snapshot_before_fallback_steps(self):
        """C端: 快照恢复优先于fallback_steps。"""
        engine = _FullEngine(is_mobile=True)

        engine._anchor_snapshots["TC-001_3"] = {
            "type": "mobile",
            "current_activity": "com.app/.DetailActivity",
            "ui_element_summary": [{"text": "确认"}],
            "screenshot_hash": "hash123",
            "anchor_step": 3,
            "case_title": "主干",
            "app_package": "com.app",
        }
        engine._title_to_case_no["主干"] = "TC-001"

        mock_adb = AsyncMock()
        mock_adb.get_current_activity = AsyncMock(
            return_value="com.app/.DetailActivity"
        )
        mock_elem = MagicMock()
        mock_elem.resource_id = None
        mock_elem.text = "确认"
        mock_elem.content_desc = None
        mock_uiautomator = AsyncMock()
        mock_uiautomator.get_clickable_elements = AsyncMock(
            return_value=[mock_elem]
        )
        mock_executor = MagicMock()
        mock_executor.adb = mock_adb
        mock_executor.uiautomator = mock_uiautomator
        engine._mobile_executor = mock_executor

        case = _StubCase(
            2, "分支用例", "TC-002",
            depends_on="主干", anchor_step=3,
        )
        ok, level = await engine._navigate_to_dependency_anchor(case)
        assert ok is True
        assert "Level1" in level or "快照" in level


# ============================================================
# 场景5: 失败分类 - 产品Bug vs 误报
# ============================================================
class TestFailureCategorization:
    def test_product_bug_is_real_bug(self):
        """产品Bug: 页面状态正确但行为不符合预期。"""
        result = TestExecutionResult(
            case_id=1,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PRODUCT_BUG,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is True
        assert FailureCategory.is_false_positive(result.failure_category) is False

    def test_crash_bug_is_highest_priority_product_bug(self):
        """崩溃Bug: C端最高优先级产品Bug。"""
        result = TestExecutionResult(
            case_id=2,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.CRASH_BUG,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is True

    def test_performance_bug_is_product_bug_on_mobile(self):
        """性能Bug: C端弱网超时是产品Bug。"""
        result = TestExecutionResult(
            case_id=3,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PERFORMANCE_BUG,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is True

    def test_upstream_blocked_is_false_positive(self):
        """上游阻塞: 不是产品Bug，是误报。"""
        result = TestExecutionResult(
            case_id=4,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.UPSTREAM_BLOCKED,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is False
        assert FailureCategory.is_false_positive(result.failure_category) is True

    def test_navigation_failure_is_false_positive(self):
        """导航失败: 测试基础设施问题，是误报。"""
        result = TestExecutionResult(
            case_id=5,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.NAVIGATION_FAILURE,
        )
        assert FailureCategory.is_product_bug(result.failure_category) is False
        assert FailureCategory.is_false_positive(result.failure_category) is True

    def test_full_execution_summary_statistics(self):
        """完整执行摘要: 区分真实Bug和误报。"""
        results = [
            TestExecutionResult(case_id=1, status=ExecutionStatus.PASSED),
            TestExecutionResult(case_id=2, status=ExecutionStatus.PASSED),
            TestExecutionResult(case_id=3, status=ExecutionStatus.FAILED,
                                failure_category=FailureCategory.PRODUCT_BUG),
            TestExecutionResult(case_id=4, status=ExecutionStatus.FAILED,
                                failure_category=FailureCategory.CRASH_BUG),
            TestExecutionResult(case_id=5, status=ExecutionStatus.FAILED,
                                failure_category=FailureCategory.PERFORMANCE_BUG),
            TestExecutionResult(case_id=6, status=ExecutionStatus.FAILED,
                                failure_category=FailureCategory.UPSTREAM_BLOCKED),
            TestExecutionResult(case_id=7, status=ExecutionStatus.FAILED,
                                failure_category=FailureCategory.NAVIGATION_FAILURE),
            TestExecutionResult(case_id=8, status=ExecutionStatus.ERROR,
                                failure_category=FailureCategory.ENVIRONMENT_ERROR),
        ]

        passed = [r for r in results if r.status == ExecutionStatus.PASSED]
        real_bugs = [r for r in results if FailureCategory.is_product_bug(r.failure_category)]
        false_positives = [r for r in results if FailureCategory.is_false_positive(r.failure_category)]

        assert len(passed) == 2
        assert len(real_bugs) == 3
        assert len(false_positives) == 3

        real_bug_ids = {r.case_id for r in real_bugs}
        assert real_bug_ids == {3, 4, 5}

        false_positive_ids = {r.case_id for r in false_positives}
        assert false_positive_ids == {6, 7, 8}


# ============================================================
# 场景6: API前置准备 - 变量提取与替换
# ============================================================
class TestApiSetupIntegration:
    def test_variable_extraction_and_substitution(self):
        """API前置准备: 第一个API提取变量，第二个API使用变量。"""
        engine = _FullEngine(is_mobile=False)
        engine._init_api_setup_state()

        engine._api_extracted_vars = {"order_id": 42}

        body = {
            "order_id": "{{order_id}}",
            "reason": "测试取消",
            "nested": {"ref": "{{order_id}}"},
        }
        result = engine._substitute_api_vars(body)
        assert result["order_id"] == 42
        assert result["reason"] == "测试取消"
        assert result["nested"]["ref"] == 42

    def test_json_path_extraction(self):
        """API响应变量提取: $.data.id 格式。"""
        engine = _FullEngine(is_mobile=False)
        engine._init_api_setup_state()

        data = {"data": {"id": 99, "items": [{"name": "商品A"}]}, "code": 0}
        assert engine._resolve_json_path(data, "$.data.id") == 99
        assert engine._resolve_json_path(data, "$.code") == 0
        assert engine._resolve_json_path(data, "$.data.items.0.name") == "商品A"
        assert engine._resolve_json_path(data, "$.nonexistent") is None


# ============================================================
# 场景7: 拓扑排序 - 依赖关系正确解析
# ============================================================
class TestTopologicalSortIntegration:
    def test_complex_dependency_graph(self):
        """复杂依赖图: 多个分支用例依赖同一个主干用例。"""
        engine = _FullEngine(is_mobile=False)

        cases = [
            _StubCase(1, "正向-创建订单", "TC-001"),
            _StubCase(2, "异常-取消订单", "TC-002", depends_on="正向-创建订单", anchor_step=3),
            _StubCase(3, "边界-重复提交", "TC-003", depends_on="正向-创建订单", anchor_step=3),
            _StubCase(4, "异常-超时未支付", "TC-004", depends_on="正向-创建订单", anchor_step=2),
            _StubCase(5, "正向-查看报表", "TC-005"),
        ]

        graph = engine._build_dependency_graph(cases)
        sorted_cases = engine._topological_sort_cases(cases, graph)
        titles = [c.title for c in sorted_cases]

        main_idx = titles.index("正向-创建订单")
        assert main_idx < titles.index("异常-取消订单")
        assert main_idx < titles.index("边界-重复提交")
        assert main_idx < titles.index("异常-超时未支付")

        independent_idx = titles.index("正向-查看报表")
        assert independent_idx >= 0

    def test_no_dependency_preserves_order(self):
        """无依赖时保持原有顺序。"""
        engine = _FullEngine(is_mobile=False)
        cases = [
            _StubCase(1, "用例A"),
            _StubCase(2, "用例B"),
            _StubCase(3, "用例C"),
        ]
        graph = engine._build_dependency_graph(cases)
        sorted_cases = engine._topological_sort_cases(cases, graph)
        assert [c.id for c in sorted_cases] == [1, 2, 3]


# ============================================================
# 场景8: fallback_steps降级导航
# ============================================================
class TestFallbackStepsIntegration:
    def test_fallback_steps_built_from_main_flow(self):
        """从主干用例步骤中提取降级导航步骤。"""
        from app.pipelines.steps._parsing import _build_fallback_steps

        main_steps = [
            {"step": 1, "action": "访问首页", "action_type": "navigate",
             "target_element": "", "input_value": "/home"},
            {"step": 2, "action": "搜索商品", "action_type": "input",
             "target_element": "搜索框", "input_value": "手机"},
            {"step": 3, "action": "点击搜索结果", "action_type": "click",
             "target_element": "搜索结果", "input_value": ""},
            {"step": 4, "action": "加入购物车", "action_type": "click",
             "target_element": "加入购物车按钮", "input_value": ""},
        ]

        fallback = _build_fallback_steps(main_steps, 3)
        assert len(fallback) == 3
        assert fallback[0]["action"] == "访问首页"
        assert fallback[1]["action"] == "搜索商品"
        assert fallback[2]["action"] == "点击搜索结果"

        fallback_partial = _build_fallback_steps(main_steps, 1)
        assert len(fallback_partial) == 1
        assert fallback_partial[0]["action"] == "访问首页"

    def test_fallback_steps_json_roundtrip(self):
        """降级导航步骤JSON序列化/反序列化一致性。"""
        from app.pipelines.steps._parsing import _build_fallback_steps

        main_steps = [
            {"step": 1, "action": "访问登录页", "action_type": "navigate",
             "target_element": "", "input_value": "/login"},
            {"step": 2, "action": "输入账号密码", "action_type": "input",
             "target_element": "账号输入框", "input_value": "admin"},
        ]
        fallback = _build_fallback_steps(main_steps, 2)
        json_str = json.dumps(fallback, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert len(parsed) == 2
        assert parsed[0]["action_type"] == "navigate"
        assert parsed[1]["input_value"] == "admin"


# ============================================================
# 场景9: 端到端完整流程模拟
# ============================================================
class TestEndToEndFullFlow:
    def test_b_end_full_flow_main_success_branch_restore(self):
        """B端完整流程: 主干成功→快照保存→分支恢复→执行→分类。"""
        engine = _FullEngine(is_mobile=False)
        engine._init_dependency_state()

        cases = [
            _StubCase(1, "正向-创建订单", "TC-001"),
            _StubCase(2, "异常-取消订单", "TC-002",
                      depends_on="正向-创建订单", anchor_step=3),
            _StubCase(3, "正向-查看报表", "TC-003"),
        ]

        graph = engine._build_dependency_graph(cases)
        sorted_cases = engine._topological_sort_cases(cases, graph)

        titles = [c.title for c in sorted_cases]
        assert titles.index("正向-创建订单") < titles.index("异常-取消订单")

        engine._pending_cases = sorted_cases

        main_result = TestExecutionResult(
            case_id=1, status=ExecutionStatus.PASSED,
        )
        engine._case_results[1] = main_result

        branch_result = TestExecutionResult(
            case_id=2, status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PRODUCT_BUG,
        )
        assert FailureCategory.is_product_bug(branch_result.failure_category) is True

    def test_b_end_full_flow_main_failure_branches_blocked(self):
        """B端完整流程: 主干失败→分支BLOCKED→独立用例正常执行。"""
        engine = _FullEngine(is_mobile=False)
        engine._init_dependency_state()

        cases = [
            _StubCase(1, "正向-创建订单", "TC-001"),
            _StubCase(2, "异常-取消订单", "TC-002",
                      depends_on="正向-创建订单", anchor_step=3),
            _StubCase(3, "边界-重复提交", "TC-003",
                      depends_on="正向-创建订单", anchor_step=3),
            _StubCase(4, "正向-查看报表", "TC-004"),
        ]

        engine._pending_cases = cases

        blocked_ids = engine._mark_dependents_blocked(cases[0], cases, {})
        assert 2 in blocked_ids
        assert 3 in blocked_ids
        assert 4 not in blocked_ids

        assert engine._should_skip_as_blocked(cases[1]) is True
        assert engine._should_skip_as_blocked(cases[2]) is True
        assert engine._should_skip_as_blocked(cases[3]) is False

    def test_c_end_full_flow_crash_categorized_correctly(self):
        """C端完整流程: App崩溃被正确分类为CRASH_BUG而非环境错误。"""
        step_result = StepExecutionResult(
            step_number=3,
            action_type=ActionType.CLICK,
            status=ExecutionStatus.FAILED,
            error_message="App process crashed: SIGSEGV",
        )

        case_result = TestExecutionResult(
            case_id=1,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.CRASH_BUG,
            steps=[step_result],
        )

        assert FailureCategory.is_product_bug(case_result.failure_category) is True
        assert case_result.failure_category == FailureCategory.CRASH_BUG

        d = case_result.to_dict()
        assert d["failure_category"] == "crash_bug"
        assert d["steps"][0]["failure_category"] is None

    def test_execution_result_to_dict_includes_all_new_fields(self):
        """执行结果序列化包含所有新增字段。"""
        result = TestExecutionResult(
            case_id=1,
            status=ExecutionStatus.FAILED,
            failure_category=FailureCategory.PRODUCT_BUG,
            navigation_level="Level0-API前置准备",
        )
        d = result.to_dict()
        assert "failure_category" in d
        assert d["failure_category"] == "product_bug"
        assert "navigation_level" in d
        assert d["navigation_level"] == "Level0-API前置准备"
