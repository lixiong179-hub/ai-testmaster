import json
from typing import Optional, Dict, Any, List
from loguru import logger

from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus, ExecutionError, handle_execution_errors,
    TestExecutionResult, FailureCategory,
)


class _ExecutorMixin:

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

        from app.services.visibility_config import VisibilityConfigService
        from app.services.visibility_config.merger import VisibilityConfigMerger
        try:
            vis_service = VisibilityConfigService()
            project_config = vis_service.get_project_config(self.db, project.id)
            task_config = vis_service.get_task_config(task)
            self._visibility_config = VisibilityConfigMerger.merge(project_config, task_config)
        except Exception as e:
            logger.warning("可见模式配置加载失败，使用默认配置: {}", e)
            self._visibility_config = None

        task.status = TaskStatus.RUNNING
        task.start_time = utcnow()
        self.db.commit()

        owns_precondition_service = False

        try:
            if (
                not self.precondition_service
                and execution_mode not in ("mobile_realtime", "mobile_smart")
            ):
                from app.services.precondition_service import PreconditionService
                self.precondition_service = PreconditionService()
                await self.precondition_service.initialize()
                owns_precondition_service = True

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

                await self.precondition_service.read_test_object_info(project, env_config=env_config if env_config else None)

                headless = global_headless if global_headless is not None else True
                browser = await self.precondition_service.execute_web_precondition(
                    headless=headless, browser_type="chromium", auto_login=(not skip_init)
                )
                if browser:
                    self.browser = browser

                if self.browser and not self.locator_service:
                    from app.services.element_locator_service import ElementLocatorService
                    from app.utils.unified_vision_model import create_vision_model
                    from app.core.config import settings
                    try:
                        vision_model = create_vision_model()
                        effective_use_mcp = use_mcp if use_mcp is not None else getattr(settings, 'PLAYWRIGHT_MCP_ENABLED', False)
                        self.locator_service = ElementLocatorService.create_locator_service(
                            db=self.db, browser=self.browser, vision_model=vision_model, use_mcp=effective_use_mcp
                        )
                    except Exception as e:
                        logger.warning(f"ElementLocatorService 初始化失败: {e}")

            test_results = self.db.query(TestResult).filter(TestResult.task_id == task_id).all()

            if not test_results:
                # 任务已执行但无关联用例（如 AI 生成失败降级为 0 用例），
                # 视为空完成而非回退到 PENDING：PENDING 会让前端状态机无法切换
                # 出 running，且语义上任务已走完执行流程。前端 refreshStatus 仅识别
                # 执行完成/执行失败/已停止，"等待执行" 会导致页面卡在"测试进行中"。
                logger.warning(f"测试任务 {task_id} 没有关联的测试用例，标记为执行完成")
                task.status = TaskStatus.COMPLETED
                task.end_time = utcnow()
                self.db.commit()
                return self._get_task_summary(task_id)

            passed_cases = 0
            failed_cases = 0
            blocked_cases = 0

            case_ids = [r.case_id for r in test_results if r.case_id]
            case_map = {}
            if case_ids:
                cases = self.db.query(TestCase).filter(TestCase.id.in_(case_ids), TestCase.is_deleted.is_(False)).all()
                case_map = {c.id: c for c in cases}

            self._init_dependency_state()
            sorted_cases = self._resolve_execution_order(list(case_map.values()))
            self._init_api_setup_state()
            self._pending_cases = sorted_cases
            self._anchor_step_index = self._build_anchor_step_index(sorted_cases)

            result_map: Dict[int, TestResult] = {r.case_id: r for r in test_results if r.case_id}

            for test_case in sorted_cases:
                test_result = result_map.get(test_case.id)
                if not test_result:
                    continue

                if self._should_skip_as_blocked(test_case):
                    logger.info(f"用例 {test_case.case_no} 因依赖失败标记为 BLOCKED")
                    test_result.exec_status = ExecStatus.BLOCKED
                    test_result.exec_time = utcnow()
                    depends_on_title = getattr(test_case, 'depends_on', '') or ''
                    test_result.exec_log = f"[上游阻塞] 依赖的主干用例 '{depends_on_title}' 执行失败，本用例无法执行（非产品Bug，需先修复上游）"
                    blocked_cases += 1
                    self.db.commit()
                    continue

                depends_on = getattr(test_case, 'depends_on', None)
                nav_level_used: Optional[str] = None
                nav_failed = False
                if depends_on:
                    nav_ok, nav_level = await self._navigate_to_dependency_anchor(test_case)
                    if nav_ok:
                        nav_level_used = nav_level
                    else:
                        nav_failed = True

                try:
                    result = await self.execute_test_case(
                        test_case=test_case, project_id=project.id,
                        skip_precondition=False, execution_mode=execution_mode,
                        mobile_device_id=mobile_device_id
                    )

                    if nav_level_used:
                        result.navigation_level = nav_level_used

                    if result.status == ExecutionStatus.PASSED:
                        test_result.exec_status = ExecStatus.PASSED
                        passed_cases += 1
                    else:
                        if nav_failed:
                            result.failure_category = FailureCategory.NAVIGATION_FAILURE
                            test_result.exec_log = f"[导航失败] 依赖导航三级降级均失败，页面可能未到达正确状态，失败原因可能是测试基础设施问题而非产品Bug。原始结果: {result.error_message or ''}"
                        elif result.failure_category is None:
                            result.failure_category = FailureCategory.PRODUCT_BUG
                        test_result.exec_status = ExecStatus.FAILED
                        failed_cases += 1
                        self._mark_dependents_blocked(test_case, sorted_cases, self._case_results)

                    test_result.exec_time = utcnow()
                    if not test_result.exec_log:
                        test_result.exec_log = result.error_message or ""

                    # 聚合步骤级别的 defect_evidence 写入 TestResult
                    aggregated_evidence = self._aggregate_defect_evidence(result)
                    if aggregated_evidence:
                        test_result.defect_evidence = aggregated_evidence

                    self._case_results[test_case.id] = result

                    if not depends_on and result.status == ExecutionStatus.PASSED:
                        await self._save_main_flow_snapshots(test_case, self._step_results)

                except Exception as e:
                    logger.error(f"用例 {test_result.case_id} 执行失败: {e}")
                    test_result.exec_status = ExecStatus.FAILED
                    test_result.exec_time = utcnow()
                    test_result.error_msg = str(e)
                    failed_cases += 1
                    self._mark_dependents_blocked(test_case, sorted_cases, self._case_results)

                self.db.commit()

            task.status = TaskStatus.COMPLETED if failed_cases == 0 and blocked_cases == 0 else TaskStatus.FAILED
            task.end_time = utcnow()
            self.db.commit()

            logger.info(f"测试任务执行完成: {task_id}, 通过: {passed_cases}, 失败: {failed_cases}, 阻塞: {blocked_cases}")

        except Exception as e:
            logger.error(f"测试任务执行失败: {e}")
            from app.models.test_task import TaskStatus
            task.status = TaskStatus.FAILED
            task.end_time = utcnow()
            self.db.commit()
            raise ExecutionError("任务执行失败") from e

        finally:
            if self.precondition_service and owns_precondition_service:
                await self.precondition_service.cleanup()

        return self._get_task_summary(task_id)

    @staticmethod
    def _aggregate_defect_evidence(result: "TestExecutionResult") -> Optional[Dict[str, Any]]:
        """聚合步骤级别的 defect_evidence 为用例级别的缺陷证据。

        合并所有步骤的 console_errors、network_failures、uncaught_exceptions，
        对 memory_leak_suspect 取并集。
        """
        if not result or not result.steps:
            return None

        merged: Dict[str, list] = {
            "console_errors": [],
            "network_failures": [],
            "uncaught_exceptions": [],
            "memory_leak_suspect": [],
        }
        has_evidence = False

        for step in result.steps:
            evidence = getattr(step, 'defect_evidence', None)
            if not evidence or not isinstance(evidence, dict):
                continue
            has_evidence = True
            for key in ("console_errors", "network_failures", "uncaught_exceptions"):
                items = evidence.get(key)
                if isinstance(items, list):
                    merged[key].extend(items)
            leak = evidence.get("memory_leak_suspect")
            if isinstance(leak, list):
                merged["memory_leak_suspect"].extend(leak)

        if not has_evidence:
            return None

        # 去重：对列表中的字典转为 tuple 去重
        for key in merged:
            seen = set()
            unique = []
            for item in merged[key]:
                if isinstance(item, dict):
                    ident = tuple(sorted(item.items()))
                else:
                    ident = str(item)
                if ident not in seen:
                    seen.add(ident)
                    unique.append(item)
            merged[key] = unique

        # 仅保留非空字段
        return {k: v for k, v in merged.items() if v} or None
