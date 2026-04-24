"""任务执行编排Mixin - 编排测试用例的完整执行流程。

核心方法:
    - execute_test_case: 单个测试用例执行入口
    - _generate_execution_summary: 生成执行摘要
    - get_execution_history: 获取执行历史
"""
from typing import Optional, Dict, Any, List
from loguru import logger

from app.models.test_case import (
    TestCase,
    TestCasePreconditionStep,
    TestCaseExecution,
    TestStep,
)
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus, handle_execution_errors,
    TestExecutionResult,
)


class TaskExecutorMixin:

    @handle_execution_errors
    async def execute_test_case(
        self,
        test_case: TestCase,
        project_id: int,
        skip_precondition: bool = False,
        execution_id: Optional[int] = None,
        execution_mode: str = "smart",
        mobile_device_id: Optional[str] = None
    ) -> TestExecutionResult:
        """执行测试用例。

        Args:
            test_case: 测试用例
            project_id: 项目ID
            skip_precondition: 是否跳过前置条件
            execution_id: 执行ID（用于参数化上下文）
            execution_mode: 执行模式
            mobile_device_id: 移动设备ID
        """
        logger.info(f"开始执行测试用例: {test_case.case_no} - {test_case.title}")

        start_time = utcnow()
        self._step_results = []
        if mobile_device_id:
            self._mobile_device_id = mobile_device_id

        execution = TestCaseExecution(
            test_case_id=test_case.id,
            status=ExecutionStatus.RUNNING.value,
            started_at=start_time
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        self._current_execution = execution

        if execution_id is None:
            execution_id = execution.id
        self.parameterizer = self._create_parameterizer(execution_id, test_case.id)

        try:
            if not skip_precondition and self.precondition_service:
                login_valid = await self._check_precondition_status()
                if login_valid and self.precondition_service.is_browser_ready:
                    logger.info("登录状态有效，跳过前置条件（登录）")
                else:
                    logger.info("登录状态无效或浏览器未启动，执行前置条件（登录）")
                    await self._execute_precondition(project_id)

            precondition_steps = self.db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == test_case.id
            ).order_by(TestCasePreconditionStep.step_number).all()

            all_passed = True
            if precondition_steps:
                logger.info(f"开始执行 {len(precondition_steps)} 个前置条件步骤")
                for pc_step in precondition_steps:
                    step_result = await self._execute_precondition_step(pc_step)
                    self._step_results.append(step_result)
                    if step_result.status != ExecutionStatus.PASSED:
                        logger.warning(f"前置条件步骤 {pc_step.step_number} 失败，跳过用例执行")
                        all_passed = False
                        break
                else:
                    logger.info("所有前置条件步骤执行成功")

            test_steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case.id
            ).order_by(TestStep.step_number).all()

            if all_passed:
                for step in test_steps:
                    step_result = await self._execute_step(step, execution_mode=execution_mode)
                    self._step_results.append(step_result)
                    if step_result.status != ExecutionStatus.PASSED:
                        all_passed = False
                        if step_result.status == ExecutionStatus.FAILED:
                            logger.warning(f"步骤 {step.step_number} 失败，跳过后续步骤")
                            break
            else:
                logger.warning("前置条件步骤失败，跳过测试步骤执行")

            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            final_status = ExecutionStatus.PASSED if all_passed else ExecutionStatus.FAILED

            execution.status = final_status.value
            execution.completed_at = end_time
            execution.actual_result = self._generate_execution_summary()
            self.db.commit()

            healing_summary = self.get_self_healing_summary()
            if healing_summary["self_healing_attempts"] > 0:
                logger.info(
                    f"自愈摘要 | 尝试: {healing_summary['self_healing_attempts']} | "
                    f"成功: {healing_summary['self_healing_successes']} | "
                    f"成功率: {healing_summary['self_healing_success_rate']:.1%}"
                )

            result = TestExecutionResult(
                execution_id=execution.id,
                test_case_id=test_case.id,
                status=final_status,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration,
                step_results=self._step_results,
                actual_result=execution.actual_result
            )
            logger.info(f"测试用例执行完成: {test_case.case_no}, 状态: {final_status.value}")
            return result

        except Exception as e:
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)
            execution.status = ExecutionStatus.ERROR.value
            execution.completed_at = end_time
            execution.actual_result = "执行错误"
            self.db.commit()
            logger.error(f"测试用例执行错误: {test_case.case_no}, 错误: {e}")
            return TestExecutionResult(
                execution_id=execution.id,
                test_case_id=test_case.id,
                status=ExecutionStatus.ERROR,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration,
                step_results=self._step_results,
                error_message=str(e)
            )

    def _generate_execution_summary(self) -> str:
        """生成执行摘要。"""
        total = len(self._step_results)
        passed = sum(1 for r in self._step_results if r.status == ExecutionStatus.PASSED)
        failed = sum(1 for r in self._step_results if r.status == ExecutionStatus.FAILED)
        summary = f"执行完成: 总计{total}步, 通过{passed}步, 失败{failed}步"
        if failed > 0:
            failed_steps = [r for r in self._step_results if r.status == ExecutionStatus.FAILED]
            summary += f"\n失败步骤: " + ", ".join([f"第{r.step_number}步" for r in failed_steps])
        return summary

    def get_execution_history(
        self,
        test_case_id: Optional[int] = None,
        limit: int = 10
    ) -> List[TestCaseExecution]:
        """获取执行历史。"""
        query = self.db.query(TestCaseExecution)
        if test_case_id:
            query = query.filter(TestCaseExecution.test_case_id == test_case_id)
        return query.order_by(TestCaseExecution.create_time.desc()).limit(limit).all()
