"""浏览器缺陷捕获功能单元测试。

覆盖范围：
1. 控制台错误捕获（仅 error 级别）
2. 未捕获异常捕获
3. 网络失败捕获（5xx 响应 + requestfailed）
4. 排除预期 4xx 请求
5. 内存泄漏嫌疑检测
6. defect_evidence 汇总
7. clear_defect_evidence 清空
8. _setup_defect_listeners 注册
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any, Dict

from app.utils.browser_controller_base import BrowserControllerV2, BrowserConfig


# ---------------------------------------------------------------------------
# 辅助：构造 mock 消息对象
# ---------------------------------------------------------------------------

class MockConsoleMessage:
    """模拟 Playwright ConsoleMessage。"""

    def __init__(self, msg_type: str, text: str, url: str = "", line: int = 0):
        self.type = msg_type
        self.text = text
        self.location = {"url": url, "lineNumber": line} if url else None


class MockPageError:
    """模拟 Playwright 页面异常。"""

    def __init__(self, message: str, stack: str = ""):
        self._message = message
        self.stack = stack

    def __str__(self) -> str:
        return self._message


class MockRequest:
    """模拟 Playwright Request。"""

    def __init__(self, url: str, method: str = "GET"):
        self.url = url
        self.method = method


class MockResponse:
    """模拟 Playwright Response。"""

    def __init__(self, status: int, url: str, method: str = "GET"):
        self.status = status
        self.request = MockRequest(url, method)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def browser() -> BrowserControllerV2:
    """创建一个 BrowserControllerV2 实例并模拟已初始化状态。"""
    config = BrowserConfig(headless=True)
    ctrl = BrowserControllerV2(config)
    # 模拟 _page 存在，使监听器可注册
    ctrl._page = MagicMock()
    ctrl._is_initialized = True
    ctrl._defect_listeners_registered = False
    return ctrl


# ---------------------------------------------------------------------------
# 1. 控制台错误捕获
# ---------------------------------------------------------------------------

class TestConsoleErrorCapture:

    def test_capture_error_level_only(self, browser: BrowserControllerV2) -> None:
        """仅收集 type=error 的控制台消息。"""
        msg_error = MockConsoleMessage("error", "Uncaught TypeError: x is not a function", "app.js", 42)
        msg_warning = MockConsoleMessage("warning", "Deprecated API usage")
        msg_log = MockConsoleMessage("log", "Hello world")

        browser._on_console_message(msg_error)
        browser._on_console_message(msg_warning)
        browser._on_console_message(msg_log)

        evidence = browser.get_defect_evidence()
        assert len(evidence["console_errors"]) == 1
        assert evidence["console_errors"][0]["message"] == "Uncaught TypeError: x is not a function"
        assert evidence["console_errors"][0]["type"] == "console_error"
        assert "app.js" in evidence["console_errors"][0]["source"]

    def test_capture_multiple_errors(self, browser: BrowserControllerV2) -> None:
        """收集多条 error 级别日志。"""
        for i in range(3):
            browser._on_console_message(MockConsoleMessage("error", f"Error {i}"))

        evidence = browser.get_defect_evidence()
        assert len(evidence["console_errors"]) == 3

    def test_console_message_exception_handling(self, browser: BrowserControllerV2) -> None:
        """处理控制台消息时异常不应中断流程。"""
        broken_msg = MagicMock()
        broken_msg.type = property(lambda s: (_ for _ in ()).throw(RuntimeError("broken")))
        # 不应抛出异常
        browser._on_console_message(broken_msg)
        evidence = browser.get_defect_evidence()
        assert len(evidence["console_errors"]) == 0


# ---------------------------------------------------------------------------
# 2. 未捕获异常捕获
# ---------------------------------------------------------------------------

class TestUncaughtExceptionCapture:

    def test_capture_page_error(self, browser: BrowserControllerV2) -> None:
        """收集页面未捕获异常。"""
        error = MockPageError("ReferenceError: foo is not defined", "at bar (app.js:10:5)")
        browser._on_page_error(error)

        evidence = browser.get_defect_evidence()
        assert len(evidence["uncaught_exceptions"]) == 1
        assert evidence["uncaught_exceptions"][0]["type"] == "uncaught_exception"
        assert "ReferenceError" in evidence["uncaught_exceptions"][0]["message"]
        assert "app.js" in evidence["uncaught_exceptions"][0]["stack"]

    def test_page_error_no_stack(self, browser: BrowserControllerV2) -> None:
        """无 stack 的异常仍可收集。"""
        error = MockPageError("Unknown error", "")
        browser._on_page_error(error)

        evidence = browser.get_defect_evidence()
        assert len(evidence["uncaught_exceptions"]) == 1
        assert evidence["uncaught_exceptions"][0]["stack"] == ""


# ---------------------------------------------------------------------------
# 3. 网络失败捕获（5xx + requestfailed）
# ---------------------------------------------------------------------------

class TestNetworkFailureCapture:

    def test_capture_5xx_response(self, browser: BrowserControllerV2) -> None:
        """收集 5xx 响应。"""
        response = MockResponse(500, "https://api.example.com/users", "GET")
        browser._on_response(response)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 1
        assert evidence["network_failures"][0]["status"] == 500
        assert evidence["network_failures"][0]["url"] == "https://api.example.com/users"
        assert evidence["network_failures"][0]["method"] == "GET"

    def test_capture_503_response(self, browser: BrowserControllerV2) -> None:
        """收集 503 响应。"""
        response = MockResponse(503, "https://api.example.com/health", "GET")
        browser._on_response(response)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 1
        assert evidence["network_failures"][0]["status"] == 503

    def test_capture_request_failed(self, browser: BrowserControllerV2) -> None:
        """收集请求失败事件（status=0）。"""
        request = MockRequest("https://cdn.example.com/bundle.js", "GET")
        browser._on_request_failed(request)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 1
        assert evidence["network_failures"][0]["status"] == 0
        assert evidence["network_failures"][0]["url"] == "https://cdn.example.com/bundle.js"


# ---------------------------------------------------------------------------
# 4. 排除预期 4xx 请求
# ---------------------------------------------------------------------------

class TestExcludeExpected4xx:

    def test_exclude_401_response(self, browser: BrowserControllerV2) -> None:
        """401 响应不记录为缺陷（登录失败是预期行为）。"""
        response = MockResponse(401, "https://api.example.com/login", "POST")
        browser._on_response(response)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 0

    def test_exclude_403_response(self, browser: BrowserControllerV2) -> None:
        """403 响应不记录为缺陷。"""
        response = MockResponse(403, "https://api.example.com/admin", "GET")
        browser._on_response(response)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 0

    def test_exclude_404_response(self, browser: BrowserControllerV2) -> None:
        """404 响应不记录为缺陷。"""
        response = MockResponse(404, "https://api.example.com/missing", "GET")
        browser._on_response(response)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 0

    def test_include_5xx_but_not_4xx(self, browser: BrowserControllerV2) -> None:
        """5xx 记录，4xx 不记录。"""
        browser._on_response(MockResponse(401, "https://api.example.com/login", "POST"))
        browser._on_response(MockResponse(500, "https://api.example.com/data", "GET"))
        browser._on_response(MockResponse(404, "https://api.example.com/missing", "GET"))

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 1
        assert evidence["network_failures"][0]["status"] == 500


# ---------------------------------------------------------------------------
# 5. 内存泄漏嫌疑检测
# ---------------------------------------------------------------------------

class TestMemoryLeakDetection:

    def test_detect_leak_suspect(self, browser: BrowserControllerV2) -> None:
        """连续 5 步内存增长 > 10MB 标记为泄漏嫌疑。"""
        # 模拟 5 个步骤的内存增长，每步增长 3MB，总计 12MB
        memory_values = [50.0, 53.0, 56.0, 59.0, 62.0]
        for val in memory_values:
            browser._memory_samples.append(val)
        browser._detect_memory_leak()

        evidence = browser.get_defect_evidence()
        assert evidence["memory_leak_suspect"] is not None
        assert evidence["memory_leak_suspect"]["peak_mb"] == 62.0
        assert evidence["memory_leak_suspect"]["growth_mb"] == 12.0
        assert evidence["memory_leak_suspect"]["step_count"] == 5

    def test_no_leak_below_threshold(self, browser: BrowserControllerV2) -> None:
        """增长不足 10MB 不标记泄漏嫌疑。"""
        # 每步增长 1MB，总计 4MB
        memory_values = [50.0, 51.0, 52.0, 53.0, 54.0]
        for val in memory_values:
            browser._memory_samples.append(val)
        browser._detect_memory_leak()

        evidence = browser.get_defect_evidence()
        assert evidence["memory_leak_suspect"] is None

    def test_no_leak_non_monotonic(self, browser: BrowserControllerV2) -> None:
        """非单调增长不标记泄漏嫌疑。"""
        # 有下降趋势
        memory_values = [50.0, 60.0, 55.0, 65.0, 70.0]
        for val in memory_values:
            browser._memory_samples.append(val)
        browser._detect_memory_leak()

        evidence = browser.get_defect_evidence()
        assert evidence["memory_leak_suspect"] is None

    def test_no_leak_insufficient_samples(self, browser: BrowserControllerV2) -> None:
        """样本不足 5 个不检测。"""
        memory_values = [50.0, 60.0, 70.0, 80.0]
        for val in memory_values:
            browser._memory_samples.append(val)
        browser._detect_memory_leak()

        evidence = browser.get_defect_evidence()
        assert evidence["memory_leak_suspect"] is None

    @pytest.mark.asyncio
    async def test_collect_memory_sample_chromium(self, browser: BrowserControllerV2) -> None:
        """Chromium 环境 performance.memory 可用时采集内存。"""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value={
            "usedJSHeapSize": 100 * 1024 * 1024,  # 100MB
            "totalJSHeapSize": 200 * 1024 * 1024,
            "jsHeapSizeLimit": 500 * 1024 * 1024,
        })
        browser._page = mock_page

        await browser.collect_memory_sample()
        assert len(browser._memory_samples) == 1
        assert browser._memory_samples[0] == 100.0

    @pytest.mark.asyncio
    async def test_collect_memory_sample_non_chromium(self, browser: BrowserControllerV2) -> None:
        """非 Chromium 环境 performance.memory 不可用时跳过。"""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=Exception("performance.memory is undefined"))
        browser._page = mock_page

        await browser.collect_memory_sample()
        assert len(browser._memory_samples) == 0

    @pytest.mark.asyncio
    async def test_collect_memory_sample_no_page(self, browser: BrowserControllerV2) -> None:
        """无页面时跳过内存采集。"""
        browser._page = None
        await browser.collect_memory_sample()
        assert len(browser._memory_samples) == 0


# ---------------------------------------------------------------------------
# 6. defect_evidence 汇总
# ---------------------------------------------------------------------------

class TestDefectEvidenceSummary:

    def test_empty_evidence(self, browser: BrowserControllerV2) -> None:
        """初始状态返回空缺陷证据。"""
        evidence = browser.get_defect_evidence()
        assert evidence["console_errors"] == []
        assert evidence["network_failures"] == []
        assert evidence["memory_leak_suspect"] is None
        assert evidence["uncaught_exceptions"] == []

    def test_full_evidence(self, browser: BrowserControllerV2) -> None:
        """收集多种类型缺陷后汇总正确。"""
        browser._on_console_message(MockConsoleMessage("error", "JS Error"))
        browser._on_page_error(MockPageError("Uncaught Error", "stack trace"))
        browser._on_response(MockResponse(500, "https://api.example.com/fail", "GET"))

        evidence = browser.get_defect_evidence()
        assert len(evidence["console_errors"]) == 1
        assert len(evidence["uncaught_exceptions"]) == 1
        assert len(evidence["network_failures"]) == 1
        assert evidence["memory_leak_suspect"] is None

    def test_evidence_returns_copy(self, browser: BrowserControllerV2) -> None:
        """get_defect_evidence 返回副本，修改不影响内部状态。"""
        browser._on_console_message(MockConsoleMessage("error", "Error 1"))
        evidence = browser.get_defect_evidence()
        evidence["console_errors"].append({"type": "fake", "message": "injected"})

        evidence2 = browser.get_defect_evidence()
        assert len(evidence2["console_errors"]) == 1


# ---------------------------------------------------------------------------
# 7. clear_defect_evidence 清空
# ---------------------------------------------------------------------------

class TestClearDefectEvidence:

    def test_clear_resets_collectors(self, browser: BrowserControllerV2) -> None:
        """clear_defect_evidence 清空控制台错误/网络失败/未捕获异常。"""
        browser._on_console_message(MockConsoleMessage("error", "Error"))
        browser._on_page_error(MockPageError("Exception"))
        browser._on_response(MockResponse(500, "https://api.example.com/fail", "GET"))

        browser.clear_defect_evidence()

        evidence = browser.get_defect_evidence()
        assert evidence["console_errors"] == []
        assert evidence["network_failures"] == []
        assert evidence["uncaught_exceptions"] == []

    def test_clear_preserves_memory_samples(self, browser: BrowserControllerV2) -> None:
        """clear_defect_evidence 保留内存样本用于泄漏趋势分析。"""
        browser._memory_samples = [50.0, 55.0, 60.0]
        browser._memory_leak_suspect = {"peak_mb": 60.0, "growth_mb": 10.0, "step_count": 5}

        browser.clear_defect_evidence()

        # 内存样本和泄漏嫌疑应保留
        assert browser._memory_samples == [50.0, 55.0, 60.0]
        assert browser._memory_leak_suspect is not None

    def test_clear_resets_request_start_times(self, browser: BrowserControllerV2) -> None:
        """clear_defect_evidence 清空请求开始时间记录。"""
        browser._request_start_times = {"https://example.com": 12345.0}
        browser.clear_defect_evidence()
        assert len(browser._request_start_times) == 0


# ---------------------------------------------------------------------------
# 8. _setup_defect_listeners 注册
# ---------------------------------------------------------------------------

class TestSetupDefectListeners:

    def test_registers_listeners(self, browser: BrowserControllerV2) -> None:
        """注册四类监听器到 page 对象。"""
        mock_page = MagicMock()
        browser._page = mock_page
        browser._defect_listeners_registered = False

        browser._setup_defect_listeners()

        # 验证注册了 5 个监听器（console, pageerror, response, requestfailed, request）
        assert mock_page.on.call_count == 5
        registered_events = [call.args[0] for call in mock_page.on.call_args_list]
        assert "console" in registered_events
        assert "pageerror" in registered_events
        assert "response" in registered_events
        assert "requestfailed" in registered_events
        assert "request" in registered_events
        assert browser._defect_listeners_registered is True

    def test_skip_if_already_registered(self, browser: BrowserControllerV2) -> None:
        """已注册时跳过重复注册。"""
        mock_page = MagicMock()
        browser._page = mock_page
        browser._defect_listeners_registered = True

        browser._setup_defect_listeners()

        mock_page.on.assert_not_called()

    def test_skip_if_no_page(self, browser: BrowserControllerV2) -> None:
        """无页面时跳过注册。"""
        browser._page = None
        browser._defect_listeners_registered = False

        browser._setup_defect_listeners()

        assert browser._defect_listeners_registered is False

    def test_handles_registration_exception(self, browser: BrowserControllerV2) -> None:
        """注册异常不应中断流程。"""
        mock_page = MagicMock()
        mock_page.on.side_effect = RuntimeError("Page closed")
        browser._page = mock_page
        browser._defect_listeners_registered = False

        browser._setup_defect_listeners()

        assert browser._defect_listeners_registered is False


# ---------------------------------------------------------------------------
# 9. 请求耗时计算
# ---------------------------------------------------------------------------

class TestRequestDurationTracking:

    def test_request_start_time_recorded(self, browser: BrowserControllerV2) -> None:
        """请求开始时间被记录。"""
        request = MockRequest("https://api.example.com/data", "GET")
        browser._on_request_started(request)

        assert "https://api.example.com/data" in browser._request_start_times

    def test_response_duration_calculated(self, browser: BrowserControllerV2) -> None:
        """5xx 响应包含耗时计算。"""
        import time
        url = "https://api.example.com/slow"
        browser._request_start_times[url] = time.monotonic() - 0.5  # 模拟 500ms 前

        response = MockResponse(500, url, "POST")
        browser._on_response(response)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 1
        assert evidence["network_failures"][0]["duration_ms"] > 0

    def test_request_failed_duration_calculated(self, browser: BrowserControllerV2) -> None:
        """请求失败事件包含耗时计算。"""
        import time
        url = "https://cdn.example.com/timeout.js"
        browser._request_start_times[url] = time.monotonic() - 1.0  # 模拟 1000ms 前

        request = MockRequest(url, "GET")
        browser._on_request_failed(request)

        evidence = browser.get_defect_evidence()
        assert len(evidence["network_failures"]) == 1
        assert evidence["network_failures"][0]["duration_ms"] > 0


# ---------------------------------------------------------------------------
# 10. StepExecutorMixin 缺陷集成（mock 测试）
# ---------------------------------------------------------------------------

class TestStepExecutorDefectIntegration:

    def test_clear_browser_defect_evidence(self) -> None:
        """_clear_browser_defect_evidence 正确调用浏览器清空方法。"""
        from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin

        mixin = StepExecutorMixin()
        mock_browser = MagicMock()
        mock_browser.clear_defect_evidence = MagicMock()
        mixin.browser = mock_browser

        mixin._clear_browser_defect_evidence()
        mock_browser.clear_defect_evidence.assert_called_once()

    def test_clear_browser_defect_evidence_no_browser(self) -> None:
        """无浏览器时不报错。"""
        from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin

        mixin = StepExecutorMixin()
        mixin.browser = None
        # 不应抛出异常
        mixin._clear_browser_defect_evidence()

    @pytest.mark.asyncio
    async def test_collect_step_defect_evidence(self) -> None:
        """_collect_step_defect_evidence 正确采集并写入 result。"""
        from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin
        from app.services.test_execution_engine.models import StepExecutionResult, ExecutionStatus

        mixin = StepExecutorMixin()
        mock_browser = MagicMock()
        mock_browser.collect_memory_sample = AsyncMock()
        mock_browser.get_defect_evidence = MagicMock(return_value={
            "console_errors": [{"type": "console_error", "message": "test error", "source": ""}],
            "network_failures": [],
            "memory_leak_suspect": None,
            "uncaught_exceptions": [],
        })
        mixin.browser = mock_browser

        result = StepExecutionResult(step_number=1)
        await mixin._collect_step_defect_evidence(result)

        mock_browser.collect_memory_sample.assert_called_once()
        assert result.defect_evidence is not None
        assert len(result.defect_evidence["console_errors"]) == 1

    @pytest.mark.asyncio
    async def test_collect_step_defect_evidence_empty(self) -> None:
        """无实质缺陷时不写入 defect_evidence。"""
        from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin
        from app.services.test_execution_engine.models import StepExecutionResult

        mixin = StepExecutorMixin()
        mock_browser = MagicMock()
        mock_browser.collect_memory_sample = AsyncMock()
        mock_browser.get_defect_evidence = MagicMock(return_value={
            "console_errors": [],
            "network_failures": [],
            "memory_leak_suspect": None,
            "uncaught_exceptions": [],
        })
        mixin.browser = mock_browser

        result = StepExecutionResult(step_number=1)
        await mixin._collect_step_defect_evidence(result)

        assert result.defect_evidence is None

    @pytest.mark.asyncio
    async def test_collect_step_defect_evidence_passed_with_defect(self) -> None:
        """用例通过但存在隐性缺陷时仍记录 defect_evidence。"""
        from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin
        from app.services.test_execution_engine.models import StepExecutionResult, ExecutionStatus

        mixin = StepExecutorMixin()
        mock_browser = MagicMock()
        mock_browser.collect_memory_sample = AsyncMock()
        mock_browser.get_defect_evidence = MagicMock(return_value={
            "console_errors": [{"type": "console_error", "message": "hidden error", "source": ""}],
            "network_failures": [],
            "memory_leak_suspect": {"peak_mb": 100.0, "growth_mb": 15.0, "step_count": 5},
            "uncaught_exceptions": [],
        })
        mixin.browser = mock_browser

        result = StepExecutionResult(step_number=1, status=ExecutionStatus.PASSED)
        await mixin._collect_step_defect_evidence(result)

        assert result.status == ExecutionStatus.PASSED
        assert result.defect_evidence is not None
        assert result.defect_evidence["memory_leak_suspect"] is not None


# ---------------------------------------------------------------------------
# 11. TestResult 模型 defect_evidence 字段
# ---------------------------------------------------------------------------

class TestTestResultDefectEvidenceField:

    def test_model_has_defect_evidence_column(self) -> None:
        """TestResult 模型包含 defect_evidence 列。"""
        from app.models.test_result import TestResult
        columns = {c.name for c in TestResult.__table__.columns}
        assert "defect_evidence" in columns

    def test_model_defect_evidence_nullable(self) -> None:
        """defect_evidence 列允许 NULL。"""
        from app.models.test_result import TestResult
        col = TestResult.__table__.columns["defect_evidence"]
        assert col.nullable is True


# ---------------------------------------------------------------------------
# 12. StepExecutionResult defect_evidence 字段
# ---------------------------------------------------------------------------

class TestStepExecutionResultDefectEvidence:

    def test_default_none(self) -> None:
        """StepExecutionResult 默认 defect_evidence 为 None。"""
        from app.services.test_execution_engine.models import StepExecutionResult
        result = StepExecutionResult(step_number=1)
        assert result.defect_evidence is None

    def test_assign_evidence(self) -> None:
        """可以赋值 defect_evidence。"""
        from app.services.test_execution_engine.models import StepExecutionResult
        evidence = {
            "console_errors": [{"type": "console_error", "message": "err", "source": ""}],
            "network_failures": [],
            "memory_leak_suspect": None,
            "uncaught_exceptions": [],
        }
        result = StepExecutionResult(step_number=1, defect_evidence=evidence)
        assert result.defect_evidence == evidence
