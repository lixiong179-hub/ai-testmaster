"""任务批量执行Mixin - 处理测试任务级别的多用例批量执行。

当测试任务包含多个测试用例时，按顺序执行每个用例，
汇总执行结果并更新任务状态。
"""
import json
from typing import Optional, Dict, Any
from loguru import logger

from app.models.test_case import TestCase
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus, ExecutionError, handle_execution_errors,
)


class TaskBatchExecutorMixin:

    @handle_execution_errors
    async def execute_test_task(
        self,
        task_id: int,
        global_headless: Optional[bool] = None,
        global_record_video: Optional[bool] = None,
        target_env: str = "test",
        skip_init: bool = False,
        execution_mode: str = "smart",
        mobile_device_id: Optional[str] = None,
        use_mcp: Optional[bool] = None
    ) -> Dict[str, Any]:
        """执行测试任务（任务级执行，支持多用例）。

        Args:
            task_id: 测试任务ID
            global_headless: 全局无头模式配置
            global_record_video: 全局视频录制配置
            target_env: 目标环境名称
            skip_init: 是否跳过初始化
            execution_mode: 执行模式
            mobile_device_id: 移动设备ID
            use_mcp: 是否使用MCP

        Returns:
            任务执行摘要
        """
        from app.models.test_task import TestTask, TaskStatus
        from app.models.test_result import TestResult
        from app.models.project import Project

        logger.info(f"开始执行测试任务: {task_id}")

        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ExecutionError(f"测试任务不存在: {task_id}")

        project = self.db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            raise ExecutionError(f"项目不存在: {task.project_id}")

        task.status = TaskStatus.RUNNING
        task.start_time = utcnow()
        self.db.commit()

        task_start_time = utcnow()

        try:
            if self.precondition_service:
                env_config = {}
                raw_web_cfg = getattr(project, 'web_env_configs', None)
                resolved_web_cfg = None
                if raw_web_cfg:
                    if isinstance(raw_web_cfg, dict):
                        resolved_web_cfg = raw_web_cfg
                    elif isinstance(raw_web_cfg, str):
                        try:
                            parsed = json.loads(raw_web_cfg)
                            if isinstance(parsed, dict):
                                resolved_web_cfg = parsed
                            elif isinstance(parsed, str):
                                inner = json.loads(parsed)
                                if isinstance(inner, dict):
                                    resolved_web_cfg = inner
                        except (json.JSONDecodeError, ValueError, TypeError):
                            pass

                if resolved_web_cfg:
                    env_config = resolved_web_cfg.get(target_env, {})
                    if not env_config:
                        available_envs = list(resolved_web_cfg.keys())
                        if available_envs:
                            fallback_env = available_envs[0]
                            env_config = resolved_web_cfg.get(fallback_env, {})
                            logger.warning(f"目标环境 '{target_env}' 不存在，回退到 '{fallback_env}'")
                        else:
                            logger.warning("项目无可用环境配置，使用项目默认配置")

                await self.precondition_service.read_test_object_info(
                    project,
                    env_config=env_config if env_config else None
                )

                headless = global_headless if global_headless is not None else True
                browser = await self.precondition_service.execute_web_precondition(
                    headless=headless,
                    browser_type="chromium",
                    auto_login=(not skip_init)
                )
                if browser:
                    self.browser = browser

                if self.browser and not self.locator_service:
                    from app.services.element_locator_service import ElementLocatorService
                    from app.utils.unified_vision_model import create_vision_model
                    from app.core.config import settings
                    try:
                        vision_model = create_vision_model()
                        effective_use_mcp = (
                            use_mcp if use_mcp is not None
                            else getattr(settings, 'PLAYWRIGHT_MCP_ENABLED', False)
                        )
                        self.locator_service = ElementLocatorService.create_locator_service(
                            db=self.db,
                            browser=self.browser,
                            vision_model=vision_model,
                            use_mcp=effective_use_mcp
                        )
                        logger.info("ElementLocatorService 初始化成功")
                    except Exception as e:
                        logger.warning(f"ElementLocatorService 初始化失败: {e}")

            test_results = self.db.query(TestResult).filter(
                TestResult.task_id == task_id
            ).all()

            if not test_results:
                logger.warning(f"测试任务 {task_id} 没有关联的测试用例")
                task.status = TaskStatus.PENDING
                task.end_time = utcnow()
                self.db.commit()
                return self._get_task_summary(task_id)

            total_cases = len(test_results)
            passed_cases = 0
            failed_cases = 0

            case_ids = [r.case_id for r in test_results if r.case_id]
            case_map = {}
            if case_ids:
                cases = self.db.query(TestCase).filter(
                    TestCase.id.in_(case_ids)
                ).all()
                case_map = {c.id: c for c in cases}

            for test_result in test_results:
                test_case = case_map.get(test_result.case_id)

                if test_case:
                    try:
                        result = await self.execute_test_case(
                            test_case=test_case,
                            project_id=project.id,
                            skip_precondition=False,
                            execution_mode=execution_mode,
                            mobile_device_id=mobile_device_id
                        )

                        if result.status == ExecutionStatus.PASSED:
                            test_result.exec_status = 1
                            passed_cases += 1
                        else:
                            test_result.exec_status = 2
                            failed_cases += 1

                        test_result.exec_time = utcnow()
                        test_result.exec_log = result.actual_result or ""

                    except Exception as e:
                        logger.error(f"用例 {test_result.case_id} 执行失败: {e}")
                        test_result.exec_status = 2
                        test_result.exec_time = utcnow()
                        test_result.error_msg = str(e)
                        failed_cases += 1

                    self.db.commit()

            task.status = TaskStatus.COMPLETED if failed_cases == 0 else TaskStatus.FAILED
            task.end_time = utcnow()
            self.db.commit()

            logger.info(f"测试任务执行完成: {task_id}, 通过: {passed_cases}, 失败: {failed_cases}")

        except Exception as e:
            logger.error(f"测试任务执行失败: {e}")
            from app.models.test_task import TaskStatus
            task.status = TaskStatus.FAILED
            task.end_time = utcnow()
            self.db.commit()
            raise ExecutionError("任务执行失败") from e

        finally:
            if self.precondition_service:
                await self.precondition_service.cleanup()
                logger.info("前置操作服务已清理")

        return self._get_task_summary(task_id)

    def _get_task_summary(self, task_id: int) -> Dict[str, Any]:
        """获取任务执行摘要。"""
        from app.models.test_task import TestTask
        from app.models.test_result import TestResult

        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ExecutionError(f"测试任务不存在: {task_id}")

        results = self.db.query(TestResult).filter(
            TestResult.task_id == task_id
        ).all()

        total = len(results)
        passed = len([r for r in results if r.exec_status == 1])
        failed = len([r for r in results if r.exec_status == 2])

        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "task_id": task.id,
            "task_name": task.task_name,
            "status": str(task.status),
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "pass_rate": f"{pass_rate:.2f}%",
            "start_time": task.start_time.strftime("%Y-%m-%d %H:%M:%S") if task.start_time else None,
            "end_time": task.end_time.strftime("%Y-%m-%d %H:%M:%S") if task.end_time else None,
        }

    def get_task_execution_summary(self, task_id: int) -> Dict[str, Any]:
        """获取任务执行摘要（兼容旧API）。"""
        return self._get_task_summary(task_id)
