"""用例执行编排行为护栏（G-8 B4k：`execute_test_case` 拆分前置测试）。

覆盖前置条件分支（默认执行 / skip 旗标 / mobile 模式 / 失败短路）、
steps_json 解析（list / JSON 串 / 非法串 / 空）、非 dict 步骤跳过、
动作类型非法回退 click、通过/失败计数与两类异常的中断语义。
"""

import json

import pytest

from app.services.test_execution_engine.models import (
    ActionType,
    ExecutionStatus,
    FailureCategory,
    StepExecutionError,
)
from app.services.test_execution_engine.task_executor_mixin._executor import _ExecutorMixin


class _CaseStub:
    def __init__(self, case_id: int = 1, title: str = "用例", case_no: str = "TC-001", steps_json=None):
        self.id = case_id
        self.title = title
        self.case_no = case_no
        self.steps_json = steps_json


class _CaseHarness(_ExecutorMixin):
    """最小宿主：前置条件与单步执行均可打桩。"""

    def __init__(self, precondition_error: Exception | None = None, step_impl=None) -> None:
        self.browser = None
        self.locator_service = None
        self._precondition_error = precondition_error
        self._step_impl = step_impl
        self.precondition_calls: list[int] = []
        self.executed_steps: list[dict] = []

    async def _execute_precondition(self, project_id: int) -> None:
        self.precondition_calls.append(project_id)
        if self._precondition_error is not None:
            raise self._precondition_error

    async def _execute_single_step(self, step_data, action_type, step_result, execution_mode="smart"):
        self.executed_steps.append(step_data)
        if self._step_impl is not None:
            return await self._step_impl(step_data, action_type, step_result)
        step_result.status = ExecutionStatus.PASSED
        return step_result


def _steps(count: int) -> list[dict]:
    return [{"step": i + 1, "action": f"动作{i + 1}", "action_type": "click"} for i in range(count)]


class TestPreconditionBranch:
    async def test_precondition_runs_by_default(self):
        engine = _CaseHarness()

        result = await engine.execute_test_case(_CaseStub(steps_json=_steps(2)), project_id=7)

        assert engine.precondition_calls == [7]
        assert result.status == ExecutionStatus.PASSED
        assert result.passed_steps == 2

    async def test_skip_precondition_flag(self):
        engine = _CaseHarness()

        await engine.execute_test_case(_CaseStub(steps_json=_steps(1)), project_id=7, skip_precondition=True)

        assert engine.precondition_calls == []

    @pytest.mark.parametrize("mode", ["mobile_realtime", "mobile_smart"])
    async def test_mobile_mode_skips_precondition(self, mode):
        engine = _CaseHarness()

        await engine.execute_test_case(_CaseStub(steps_json=_steps(1)), project_id=7, execution_mode=mode)

        assert engine.precondition_calls == []

    async def test_precondition_failure_short_circuits(self):
        engine = _CaseHarness(precondition_error=RuntimeError("登录失败"))

        result = await engine.execute_test_case(_CaseStub(steps_json=_steps(1)), project_id=7)

        assert result.status == ExecutionStatus.FAILED
        assert result.error_message == "Precondition failed: 登录失败"
        assert result.failure_category == FailureCategory.PRECONDITION_FAILURE
        assert engine.executed_steps == []


class TestStepsParsing:
    async def test_empty_steps_auto_passed(self):
        engine = _CaseHarness()

        result = await engine.execute_test_case(_CaseStub(steps_json=[]), project_id=1)

        assert result.status == ExecutionStatus.PASSED
        assert result.error_message == "用例无步骤，自动通过"

    async def test_json_string_steps_parsed(self):
        engine = _CaseHarness()

        result = await engine.execute_test_case(_CaseStub(steps_json=json.dumps(_steps(2))), project_id=1)

        assert result.passed_steps == 2

    async def test_invalid_json_string_treated_as_empty(self):
        engine = _CaseHarness()

        result = await engine.execute_test_case(_CaseStub(steps_json="{not-json"), project_id=1)

        assert result.status == ExecutionStatus.PASSED
        assert result.error_message == "用例无步骤，自动通过"

    async def test_non_dict_step_skipped_but_counted(self):
        engine = _CaseHarness()

        result = await engine.execute_test_case(
            _CaseStub(steps_json=[{"step": 1, "action": "点击", "action_type": "click"}, "oops"]),
            project_id=1,
        )

        assert result.total_steps == 2
        assert result.passed_steps == 1
        assert len(result.steps) == 1

    async def test_invalid_action_type_falls_back_to_click(self):
        engine = _CaseHarness()
        stub = _CaseStub(steps_json=[{"step": 1, "action": "点击", "action_type": "unknown_action"}])

        result = await engine.execute_test_case(stub, project_id=1)

        assert result.steps[0].action_type == ActionType.CLICK


class TestStepOutcomeCounting:
    async def test_failed_step_marks_case_failed(self):
        async def _fail(step_data, action_type, step_result):
            step_result.status = ExecutionStatus.FAILED
            step_result.failure_category = FailureCategory.PRODUCT_BUG
            return step_result

        engine = _CaseHarness(step_impl=_fail)

        result = await engine.execute_test_case(_CaseStub(steps_json=_steps(2)), project_id=1)

        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 2
        assert result.failure_category == FailureCategory.PRODUCT_BUG

    async def test_step_execution_error_breaks_loop(self):
        async def _boom(step_data, action_type, step_result):
            raise StepExecutionError("element not found")

        engine = _CaseHarness(step_impl=_boom)

        result = await engine.execute_test_case(_CaseStub(steps_json=_steps(3)), project_id=1)

        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1
        assert len(engine.executed_steps) == 1
        assert result.failure_category == FailureCategory.LOCATOR_FAILURE
        assert result.steps[0].error_message == "element not found"

    async def test_generic_exception_marked_environment_error(self):
        async def _boom(step_data, action_type, step_result):
            raise RuntimeError("浏览器崩溃")

        engine = _CaseHarness(step_impl=_boom)

        result = await engine.execute_test_case(_CaseStub(steps_json=_steps(2)), project_id=1)

        assert result.failed_steps == 1
        assert result.failure_category == FailureCategory.ENVIRONMENT_ERROR
        assert result.steps[0].status == ExecutionStatus.ERROR
        assert len(engine.executed_steps) == 1
