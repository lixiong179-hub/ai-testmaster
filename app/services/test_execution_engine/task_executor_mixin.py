"""任务执行编排Mixin - 编排测试用例的完整执行流程。
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep, TestCaseExecution
from app.models.project import Project
from app.services.precondition_service import PreconditionService
from app.services.element_locator_service import ElementLocatorService
from app.utils.browser_controller_v2 import BrowserControllerV2, create_browser_controller_v2
from app.utils.unified_vision_model import UnifiedVisionModel, get_default_vision_model
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus, ActionType, ExecutionMode, StepExecutionError,
    StepExecutionResult, TestExecutionResult, handle_execution_errors,
)


class TaskExecutorMixin:

    @handle_execution_errors
    async def execute_test_task(
        self,
        test_case_id: int,
        execution_mode: str = "smart",
        project_id: Optional[int] = None,
        target_env: str = "test",
        test_data: Optional[Dict[str, Any]] = None,
        skip_precondition: bool = False
    ) -> TestExecutionResult:
        logger.info(f"开始执行测试用例 {test_case_id}, 模式={execution_mode}")

        test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not test_case:
            raise StepExecutionError(f"测试用例不存在: {test_case_id}")

        execution_record = TestCaseExecution(
            test_case_id=test_case_id,
            status="running",
            started_at=utcnow(),
        )
        self.db.add(execution_record)
        self.db.commit()
        self.db.refresh(execution_record)

        result = TestExecutionResult(
            execution_id=execution_record.id,
            test_case_id=test_case_id,
            status=ExecutionStatus.RUNNING,
            start_time=utcnow()
        )

        try:
            if not skip_precondition and project_id:
                await self._execute_precondition(project_id, target_env)

            if not self.browser:
                self.browser = create_browser_controller_v2()
                await self.browser.initialize()

            steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case_id
            ).order_by(TestStep.step_number).all()

            if not steps:
                result.status = ExecutionStatus.PASSED
                result.actual_result = "无测试步骤"
                logger.info(f"测试用例 {test_case_id} 无步骤，直接通过")
                return result

            precondition_steps = self.db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == test_case_id
            ).order_by(TestCasePreconditionStep.step_number).all()

            for pc_step in precondition_steps:
                pc_result = await self._execute_precondition_step(pc_step)
                if pc_result.status == ExecutionStatus.FAILED:
                    logger.warning(f"前置条件步骤 {pc_step.step_number} 执行失败，继续执行测试步骤")

            for step in steps:
                step_result = await self._execute_step(step, execution_mode, test_data)
                result.step_results.append(step_result)

                if step_result.status == ExecutionStatus.FAILED:
                    if self.enable_self_healing:
                        try:
                            action_info = self._parse_step_action(step.action)
                            healed = await self._execute_with_self_healing(step, action_info, StepExecutionError(step_result.error_message or ""))
                            if healed:
                                step_result.status = ExecutionStatus.PASSED
                                step_result.ai_analysis = (step_result.ai_analysis or "") + " [自愈成功]"
                        except Exception as e:
                            logger.warning(f"自愈失败: {e}")

                if step_result.screenshot:
                    try:
                        import base64
                        screenshot_b64 = base64.b64encode(step_result.screenshot).decode('utf-8')
                        step_result.screenshot = None
                        step_result.element_locator = step_result.element_locator or {}
                        step_result.element_locator["screenshot_base64"] = screenshot_b64[:100] + "..."
                    except Exception:
                        step_result.screenshot = None

            passed_count = sum(1 for r in result.step_results if r.status == ExecutionStatus.PASSED)
            failed_count = sum(1 for r in result.step_results if r.status == ExecutionStatus.FAILED)

            if failed_count == 0:
                result.status = ExecutionStatus.PASSED
            else:
                result.status = ExecutionStatus.FAILED

            result.end_time = utcnow()
            result.duration_ms = int((result.end_time - result.start_time).total_seconds() * 1000)
            result.actual_result = self._generate_execution_summary()

            execution_record.status = result.status.value
            execution_record.completed_at = result.end_time
            execution_record.actual_result = result.actual_result
            self.db.commit()

            logger.info(f"测试用例 {test_case_id} 执行完成: {result.status.value}")

        except Exception as e:
            result.status = ExecutionStatus.ERROR
            result.end_time = utcnow()
            result.duration_ms = int((result.end_time - result.start_time).total_seconds() * 1000)
            result.error_message = str(e)

            execution_record.status = "error"
            execution_record.completed_at = result.end_time
            execution_record.actual_result = str(e)
            self.db.commit()

            logger.error(f"测试用例 {test_case_id} 执行异常: {e}")

        return result

    async def _execute_step(
        self,
        step: TestStep,
        execution_mode: str,
        test_data: Optional[Dict[str, Any]] = None
    ) -> StepExecutionResult:
        logger.info(f"执行步骤 {step.step_number}: {step.action[:50]}...")

        start_time = utcnow()
        result = StepExecutionResult(
            step_number=step.step_number,
            action=step.action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time
        )

        try:
            step_test_data = self._generate_step_test_data(step, test_data)
            action_with_data = self._substitute_parameters_in_action(
                step.action, step_test_data or {}
            )

            if execution_mode in (ExecutionMode.MOBILE_REALTIME.value, ExecutionMode.MOBILE_SMART.value):
                await self._execute_mobile_step(step, action_with_data, execution_mode, result)
            else:
                action_info = self._parse_step_action(action_with_data)
                action_type = action_info.get("type", ActionType.CLICK)

                if step_test_data and action_type == ActionType.INPUT:
                    for field_name, value in step_test_data.items():
                        if field_name in action_with_data.lower():
                            action_info["input_value"] = value
                            break

                locator_record = None
                if self.locator_service and step.id:
                    from app.models.element_locator import ElementLocator
                    locator_record = self.db.query(ElementLocator).filter(
                        ElementLocator.step_id == step.id
                    ).first()

                if locator_record and execution_mode in (ExecutionMode.PREPROCESS.value, ExecutionMode.SMART.value):
                    try:
                        await self._execute_action_directly(action_type, action_info, locator_record, step_test_data)
                        result.status = ExecutionStatus.PASSED
                        result.element_locator = {
                            "css_selector": locator_record.css_selector,
                            "source": locator_record.source
                        }
                    except Exception as e:
                        logger.warning(f"预存定位执行失败: {e}")
                        await self._execute_action_by_type(action_type, action_info, step.id, step_test_data)
                else:
                    await self._execute_action_by_type(action_type, action_info, step.id, step_test_data)

                result.status = ExecutionStatus.PASSED

            await asyncio.sleep(1)

            if self.browser:
                result.screenshot = await self.browser.take_screenshot()

            if execution_mode == ExecutionMode.REALTIME.value and self.locator_service:
                try:
                    element_info = await self.locator_service.smart_locate_element(step.action)
                    if element_info:
                        await self._save_realtime_locator(step, element_info)
                except Exception as e:
                    logger.debug(f"保存实时定位信息失败: {e}")

            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            result.end_time = end_time
            result.duration_ms = duration

        except Exception as e:
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            result.status = ExecutionStatus.FAILED
            result.end_time = end_time
            result.duration_ms = duration
            result.error_message = str(e)

            if self.browser:
                try:
                    result.screenshot = await self.browser.take_screenshot()
                except Exception:
                    pass

            logger.error(f"步骤 {step.step_number} 执行失败: {e}")

        return result

    def _get_task_summary(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        execution = self.db.query(TestCaseExecution).filter(
            TestCaseExecution.test_case_id == test_case_id
        ).order_by(TestCaseExecution.id.desc()).first()

        if not execution:
            return None

        return {
            "execution_id": execution.id,
            "test_case_id": test_case_id,
            "status": execution.status,
            "start_time": execution.started_at.isoformat() if execution.started_at else None,
            "end_time": execution.completed_at.isoformat() if execution.completed_at else None,
            "actual_result": execution.actual_result
        }

    async def get_task_execution_summary(self, test_case_id: int) -> Optional[Dict[str, Any]]:
        return self._get_task_summary(test_case_id)

    async def get_execution_history(self, test_case_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        executions = self.db.query(TestCaseExecution).filter(
            TestCaseExecution.test_case_id == test_case_id
        ).order_by(TestCaseExecution.id.desc()).limit(limit).all()

        return [
            {
                "execution_id": ex.id,
                "status": ex.status,
                "start_time": ex.started_at.isoformat() if ex.started_at else None,
                "end_time": ex.completed_at.isoformat() if ex.completed_at else None,
                "actual_result": ex.actual_result
            }
            for ex in executions
        ]
