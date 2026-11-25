"""B6e 前置护栏：缺陷严重度评估分档 + 全链路单步执行器。

`_assess_defect_severity` 是 12 条 if 的优先级判定链，拆分后必须逐档一致；
`_run_step` 是 9 个 try/except 块收敛后的唯一入口，需覆盖 success / failed /
skipped / 异常四条路径与计时字段。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.self_test._defect_bug import _assess_defect_severity
from app.services.self_test._orchestrator import _merge_defect_counts, _run_step


class TestAssessDefectSeverity:
    @pytest.mark.parametrize(
        ("assertion", "expected_category"),
        [
            ("no_sensitive_data", "security"),
            ("no_xss", "security"),
            ("NO_XSS", "security"),  # failure_type 大小写不敏感
        ],
    )
    def test_p0_security(self, assertion, expected_category):
        assert _assess_defect_severity(assertion) == (1, expected_category)

    @pytest.mark.parametrize("message", ["页面白屏", "500错误", "Internal Server Error", "crash on load"])
    def test_p0_crash_keywords(self, message):
        assert _assess_defect_severity("assertion_failed", error_message=message) == (1, None)

    def test_p1_memory_leak_by_assertion_or_evidence(self):
        assert _assess_defect_severity("memory_leak_suspect") == (2, "response_performance")
        assert _assess_defect_severity("whatever", {"memory_leak_suspect": True}) == (2, "response_performance")

    @pytest.mark.parametrize("status", [500, 502, 503, 504, "5xx"])
    def test_p1_server_error_from_network_failures(self, status):
        evidence = {"network_failures": [{"url": "/api", "status": status}]}
        assert _assess_defect_severity("assertion_failed", evidence) == (2, "response_performance")

    def test_p1_ignores_4xx_network_failures(self):
        evidence = {"network_failures": [{"url": "/api", "status": 404}]}
        assert _assess_defect_severity("assertion_failed", evidence) == (3, None)

    def test_p1_no_network_errors_assertion(self):
        assert _assess_defect_severity("no_network_errors") == (2, "response_performance")

    @pytest.mark.parametrize("message", ["数据不一致", "权限绕过", "Permission Bypass detected"])
    def test_p1_data_and_permission(self, message):
        assert _assess_defect_severity("assertion_failed", error_message=message) == (2, None)

    @pytest.mark.parametrize("failure_type", ["element_not_found", "locator_failure"])
    def test_p1_element_failures_by_type(self, failure_type):
        assert _assess_defect_severity(failure_type) == (2, None)

    @pytest.mark.parametrize("message", ["元素未找到", "定位失败", "stale element reference"])
    def test_p1_element_failures_by_message(self, message):
        assert _assess_defect_severity("assertion_failed", error_message=message) == (2, None)

    @pytest.mark.parametrize(
        ("assertion", "expected_category"),
        [("loading_hidden", "loading_experience"), ("loading_visible", "loading_experience")],
    )
    def test_p2_loading(self, assertion, expected_category):
        assert _assess_defect_severity(assertion) == (3, expected_category)

    def test_p2_response_time(self):
        assert _assess_defect_severity("response_time_lt") == (3, "response_performance")

    def test_p2_rendering(self):
        assert _assess_defect_severity("text_not_empty") == (3, "empty_state")

    @pytest.mark.parametrize("assertion", ["not_visible", "visible", "text_contains", "text_equals", "text_matches"])
    def test_p2_visual_consistency(self, assertion):
        assert _assess_defect_severity(assertion) == (3, "visual_consistency")

    def test_p3_console(self):
        assert _assess_defect_severity("no_console_errors") == (4, "error_feedback")

    @pytest.mark.parametrize("assertion", ["url_contains", "url_equals"])
    def test_p3_url(self, assertion):
        assert _assess_defect_severity(assertion) == (4, None)

    def test_default_is_p2_without_category(self):
        assert _assess_defect_severity("unknown_assertion") == (3, None)

    def test_none_evidence_tolerated(self):
        assert _assess_defect_severity("no_xss", None) == (1, "security")


class TestRunStep:
    @pytest.mark.asyncio
    async def test_success_records_and_returns_tuple(self):
        steps: list[dict] = []
        call = AsyncMock(return_value=(True, None, [1, 2]))
        result = await _run_step(steps, "步骤A", call)
        assert result == (True, None, [1, 2])
        assert steps[0]["name"] == "步骤A"
        assert steps[0]["status"] == "success"
        assert steps[0]["error"] is None
        assert isinstance(steps[0]["duration_ms"], float)

    @pytest.mark.asyncio
    async def test_failed_step_records_error(self):
        steps: list[dict] = []
        result = await _run_step(steps, "步骤B", AsyncMock(return_value=(False, "原因")))
        assert result == (False, "原因")
        assert steps[0]["status"] == "failed"
        assert steps[0]["error"] == "原因"

    @pytest.mark.asyncio
    async def test_skip_reason_avoids_call(self):
        steps: list[dict] = []
        call = AsyncMock()
        assert await _run_step(steps, "步骤C", call, skip_reason="前置缺失") is None
        call.assert_not_awaited()
        assert steps[0]["status"] == "skipped"
        assert steps[0]["error"] == "前置缺失"

    @pytest.mark.asyncio
    async def test_exception_is_captured_not_raised(self):
        steps: list[dict] = []
        assert await _run_step(steps, "步骤D", AsyncMock(side_effect=RuntimeError("boom"))) is None
        assert steps[0]["status"] == "failed"
        assert steps[0]["error"] == "boom"


class TestMergeDefectCounts:
    def test_copies_counts_and_recomputes_total(self):
        summary = {"p0_count": 9, "p1_count": 9, "p2_count": 9, "p3_count": 9, "total_defects": 36}
        _merge_defect_counts(summary, {"p0": 1, "p1": 2, "p2": 3, "p3": 4})
        assert summary == {"p0_count": 1, "p1_count": 2, "p2_count": 3, "p3_count": 4, "total_defects": 10}

    def test_missing_keys_default_to_zero(self):
        summary = {"p0_count": 5, "p1_count": 5, "p2_count": 5, "p3_count": 5, "total_defects": 20}
        _merge_defect_counts(summary, {})
        assert summary["total_defects"] == 0
