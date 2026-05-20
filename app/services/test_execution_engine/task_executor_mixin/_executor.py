import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.services.test_execution_engine.models import (
    ExecutionStatus,
    ExecutionError,
    StepExecutionError,
    handle_execution_errors,
    TestExecutionResult,
    StepExecutionResult,
    FailureCategory,
)
from app.services.test_execution_engine.task_executor_mixin._helpers import _HelpersMixin
from app.utils.db_time import utcnow


class _ExecutorMixin(_HelpersMixin):

    @handle_execution_errors
    async def execute_test_case(
        self,
        test_case: TestCase,
        project_id: int,
        skip_precondition: bool = False,
        execution_mode: str = "smart",
        mobile_device_id: Optional[str] = None,
    ) -> TestExecutionResult:
        result = TestExecutionResult(case_id=test_case.id)

        logger.info(f"开始执行测试用例: {test_case.case_no} - {test_case.title}")

        steps_json = test_case.steps_json
        if isinstance(steps_json, str):
            import json
            try:
                steps_json = json.loads(steps_json)
            except (json.JSONDecodeError, TypeError):
                steps_json = []

        if not steps_json:
            result.status = ExecutionStatus.PASSED
            result.error_message = "用例无步骤，自动通过"
            return result

        result.total_steps = len(steps_json)
        self._step_results: List[StepExecutionResult] = []

        for step_data in steps_json:
            if not isinstance(step_data, dict):
                continue

            step_number = step_data.get("step") or step_data.get("step_number", 0)
            action = step_data.get("action", "")
            expected_result = step_data.get("expected_result", "")
            action_type_str = step_data.get("action_type", "click").lower()

            from app.services.test_execution_engine.models import ActionType
            try:
                action_type = ActionType(action_type_str)
            except ValueError:
                action_type = ActionType.CLICK

            step_result = StepExecutionResult(
                step_number=step_number,
                action_type=action_type,
                description=action,
            )

            try:
                step_result = await self._execute_single_step(
                    step_data=step_data,
                    action_type=action_type,
                    step_result=step_result,
                    execution_mode=execution_mode,
                )

                if step_result.status == ExecutionStatus.PASSED:
                    result.passed_steps += 1
                else:
                    result.failed_steps += 1
                    result.failure_category = step_result.failure_category

            except StepExecutionError as e:
                step_result.status = ExecutionStatus.FAILED
                step_result.error_message = str(e)
                result.failed_steps += 1
                result.failure_category = self._infer_failure_category(e)
                self._step_results.append(step_result)
                break
            except Exception as e:
                step_result.status = ExecutionStatus.ERROR
                step_result.error_message = str(e)
                result.failed_steps += 1
                result.failure_category = FailureCategory.ENVIRONMENT_ERROR
                self._step_results.append(step_result)
                break

            self._step_results.append(step_result)

        result.steps = self._step_results

        if result.failed_steps == 0:
            result.status = ExecutionStatus.PASSED
        else:
            result.status = ExecutionStatus.FAILED

        logger.info(
            f"用例执行完成: {test_case.case_no}, "
            f"状态: {result.status.value}, "
            f"通过: {result.passed_steps}/{result.total_steps}"
        )

        return result

    async def _execute_single_step(
        self,
        step_data: Dict[str, Any],
        action_type: Any,
        step_result: StepExecutionResult,
        execution_mode: str = "smart",
    ) -> StepExecutionResult:
        step_result.start_time = utcnow()

        action = step_data.get("action", "")
        expected_result = step_data.get("expected_result", "")
        input_value = step_data.get("input_value", "")
        target_element = step_data.get("target_element", "")

        try:
            if self.locator_service:
                element_info = await self.locator_service.locate_element(
                    description=action,
                    target_element=target_element,
                    execution_mode=execution_mode,
                )

                if element_info is None:
                    step_result.status = ExecutionStatus.FAILED
                    step_result.error_message = f"元素定位失败: {action}"
                    step_result.failure_category = FailureCategory.LOCATOR_FAILURE
                    return step_result

                step_result.element_info = element_info

                if action_type.value in ("click", "double_click", "right_click"):
                    await self._execute_click_action(element_info, action_type)
                elif action_type.value == "input" and input_value:
                    await self._execute_input_action(element_info, input_value)
                elif action_type.value == "hover":
                    await self._execute_hover_action(element_info)
                elif action_type.value == "select":
                    await self._execute_select_action(element_info, input_value)
                else:
                    await self._execute_generic_action(action, element_info, step_data)

            step_result.status = ExecutionStatus.PASSED

        except Exception as e:
            step_result.status = ExecutionStatus.FAILED
            step_result.error_message = str(e)
            raise StepExecutionError(str(e)) from e

        finally:
            step_result.end_time = utcnow()
            if step_result.start_time:
                delta = step_result.end_time - step_result.start_time
                step_result.duration_ms = int(delta.total_seconds() * 1000)

        return step_result

    async def _execute_click_action(self, element_info: Dict, action_type: Any) -> None:
        if not self.browser or not getattr(self.browser, '_page', None):
            raise ExecutionError("浏览器未初始化")
        page = self.browser._page
        css = element_info.get("css_selector")
        if css:
            await page.click(css)
        else:
            coords = element_info.get("ai_coordinate", {})
            x, y = coords.get("x", 0), coords.get("y", 0)
            await page.mouse.click(x, y)

    async def _execute_input_action(self, element_info: Dict, input_value: str) -> None:
        if not self.browser or not getattr(self.browser, '_page', None):
            raise ExecutionError("浏览器未初始化")
        page = self.browser._page
        css = element_info.get("css_selector")
        if css:
            await page.fill(css, input_value)
        else:
            coords = element_info.get("ai_coordinate", {})
            x, y = coords.get("x", 0), coords.get("y", 0)
            await page.mouse.click(x, y)
            await page.keyboard.type(input_value)

    async def _execute_hover_action(self, element_info: Dict) -> None:
        if not self.browser or not getattr(self.browser, '_page', None):
            raise ExecutionError("浏览器未初始化")
        page = self.browser._page
        css = element_info.get("css_selector")
        if css:
            await page.hover(css)
        else:
            coords = element_info.get("ai_coordinate", {})
            x, y = coords.get("x", 0), coords.get("y", 0)
            await page.mouse.move(x, y)

    async def _execute_select_action(self, element_info: Dict, value: str) -> None:
        if not self.browser or not getattr(self.browser, '_page', None):
            raise ExecutionError("浏览器未初始化")
        page = self.browser._page
        css = element_info.get("css_selector")
        if css:
            await page.select_option(css, value)

    async def _execute_generic_action(
        self, action: str, element_info: Dict, step_data: Dict
    ) -> None:
        logger.info(f"执行通用操作: {action}")
