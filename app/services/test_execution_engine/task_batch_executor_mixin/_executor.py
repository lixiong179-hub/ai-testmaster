from typing import Any

from loguru import logger

from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus,
    ExecutionError,
    handle_execution_errors,
    TestExecutionResult,
    FailureCategory,
)
from app.services.test_execution_engine.task_batch_executor_mixin._helpers import (
    _CaseCounts,
    _collect_step_evidence,
    _dedupe_evidence,
    _resolve_target_env_config,
)


class _ExecutorMixin:
    @handle_execution_errors
    async def execute_test_task(
        self,
        task_id: int,
        global_headless: bool | None = None,
        global_record_video: bool | None = None,
        target_env: str = "test",
        skip_init: bool = False,
        execution_mode: str = "smart",
        mobile_device_id: str | None = None,
        use_mcp: bool | None = None,
    ) -> dict[str, Any]:
        logger.info(f"开始执行测试任务: {task_id}")

        task, project = self._load_task_context(task_id)
        self._load_visibility_config(project, task)
        self._mark_task_running(task)

        owns_precondition_service = False
        try:
            owns_precondition_service = await self._prepare_execution_environment(
                project, execution_mode, skip_init, global_headless, target_env, use_mcp
            )

            test_results = self._load_task_results(task_id)
            if not test_results:
                self._complete_empty_task(task)
                return self._get_task_summary(task_id)

            await self._run_case_loop(task, project, test_results, execution_mode, mobile_device_id)
        except Exception as e:
            self._mark_task_failed(task, e)
            raise ExecutionError("任务执行失败") from e
        finally:
            if self.precondition_service and owns_precondition_service:
                await self.precondition_service.cleanup()

        return self._get_task_summary(task_id)

    # ---------- 任务装载与状态流转 ----------

    def _load_task_context(self, task_id: int):
        """加载任务与其所属项目，缺失即报错。"""
        from app.models.test_task import TestTask
        from app.models.project import Project

        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ExecutionError(f"测试任务不存在: {task_id}")

        project = self.db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            raise ExecutionError(f"项目不存在: {task.project_id}")
        return task, project

    def _load_visibility_config(self, project: Any, task: Any) -> None:
        """合并项目级与任务级可见模式配置；失败不阻断，回落 None。"""
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

    def _mark_task_running(self, task: Any) -> None:
        from app.models.test_task import TaskStatus

        task.status = TaskStatus.RUNNING
        task.start_time = utcnow()
        task.error_message = None
        self.db.commit()

    def _mark_task_failed(self, task: Any, error: Exception) -> None:
        """中断时落 FAILED 终态，保持原始错误摘要。"""
        logger.error(f"测试任务执行失败: {error}")
        from app.models.test_task import TaskStatus

        task.status = TaskStatus.FAILED
        task.error_message = f"任务执行异常中断：{error}"
        task.end_time = utcnow()
        self.db.commit()

    def _finalize_task_status(self, task: Any, counts: _CaseCounts) -> None:
        """按失败/阻塞计数决定 COMPLETED / FAILED 并写回原因。"""
        from app.models.test_task import TaskStatus

        task.status = TaskStatus.COMPLETED if counts.failed == 0 and counts.blocked == 0 else TaskStatus.FAILED
        if task.status == TaskStatus.FAILED:
            reasons = []
            if counts.failed:
                reasons.append(f"{counts.failed} 个用例失败")
            if counts.blocked:
                reasons.append(f"{counts.blocked} 个用例阻塞")
            task.error_message = "任务未通过：" + "，".join(reasons)
        else:
            task.error_message = None
        task.end_time = utcnow()
        self.db.commit()

    # ---------- 执行环境准备 ----------

    async def _ensure_precondition_service(self, execution_mode: str) -> bool:
        """按需初始化前置服务；返回是否由本任务创建（决定谁负责 cleanup）。"""
        if self.precondition_service or execution_mode in ("mobile_realtime", "mobile_smart"):
            return False
        from app.services.precondition_service import PreconditionService

        self.precondition_service = PreconditionService()
        await self.precondition_service.initialize()
        return True

    def _ensure_locator_service(self, use_mcp: bool | None) -> None:
        """浏览器就绪且尚未创建时初始化元素定位服务；失败仅告警。"""
        if not self.browser or self.locator_service:
            return
        from app.services.element_locator_service import ElementLocatorService
        from app.utils.unified_vision_model import create_vision_model
        from app.core.config import settings

        try:
            vision_model = create_vision_model()
            effective_use_mcp = use_mcp if use_mcp is not None else getattr(settings, "PLAYWRIGHT_MCP_ENABLED", False)
            self.locator_service = ElementLocatorService.create_locator_service(
                db=self.db, browser=self.browser, vision_model=vision_model, use_mcp=effective_use_mcp
            )
        except Exception as e:
            logger.warning(f"ElementLocatorService 初始化失败: {e}")

    async def _prepare_execution_environment(
        self,
        project: Any,
        execution_mode: str,
        skip_init: bool,
        global_headless: bool | None,
        target_env: str,
        use_mcp: bool | None,
    ) -> bool:
        """初始化前置服务、读取被测对象、启动浏览器并接上定位服务。"""
        owns_service = await self._ensure_precondition_service(execution_mode)
        if not self.precondition_service:
            return owns_service

        env_config = _resolve_target_env_config(getattr(project, "web_env_configs", None), target_env)
        await self.precondition_service.read_test_object_info(project, env_config=env_config if env_config else None)

        headless = global_headless if global_headless is not None else True
        browser = await self.precondition_service.execute_web_precondition(
            headless=headless, browser_type="chromium", auto_login=(not skip_init)
        )
        if browser:
            self.browser = browser
        self._ensure_locator_service(use_mcp)
        return owns_service

    # ---------- 用例执行循环 ----------

    def _load_task_results(self, task_id: int) -> list:
        from app.models.test_result import TestResult

        return self.db.query(TestResult).filter(TestResult.task_id == task_id).all()

    def _complete_empty_task(self, task: Any) -> None:
        """无关联用例时视为空完成，避免前端状态机卡在 running。"""
        logger.warning(f"测试任务 {task.id} 没有关联的测试用例，标记为执行完成")
        from app.models.test_task import TaskStatus

        task.status = TaskStatus.COMPLETED
        task.end_time = utcnow()
        self.db.commit()

    def _init_case_execution_state(self, test_results: list) -> tuple[list, dict]:
        """装载用例、初始化依赖/接口状态并解析执行顺序。"""
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
        result_map: dict[int, Any] = {r.case_id: r for r in test_results if r.case_id}
        return sorted_cases, result_map

    async def _navigate_for_case(self, test_case: Any) -> tuple[str | None, bool]:
        """有依赖时导航到锚点；返回（所用层级, 是否导航失败）。"""
        if not getattr(test_case, "depends_on", None):
            return None, False
        nav_ok, nav_level = await self._navigate_to_dependency_anchor(test_case)
        return (nav_level, False) if nav_ok else (None, True)

    def _mark_case_blocked(self, test_case: Any, test_result: Any) -> None:
        logger.info(f"用例 {test_case.case_no} 因依赖失败标记为 BLOCKED")
        test_result.exec_status = ExecStatus.BLOCKED
        test_result.exec_time = utcnow()
        depends_on_title = getattr(test_case, "depends_on", "") or ""
        test_result.exec_log = (
            f"[上游阻塞] 依赖的主干用例 '{depends_on_title}' 执行失败，本用例无法执行（非产品Bug，需先修复上游）"
        )

    def _apply_case_result(
        self,
        test_case: Any,
        test_result: Any,
        result: TestExecutionResult,
        nav_failed: bool,
        sorted_cases: list,
        counts: _CaseCounts,
    ) -> None:
        """把执行结果映射为用例状态与计数，失败时标记下游阻塞。"""
        if result.status == ExecutionStatus.PASSED:
            test_result.exec_status = ExecStatus.PASSED
            counts.passed += 1
            return

        if nav_failed:
            result.failure_category = FailureCategory.NAVIGATION_FAILURE
            test_result.exec_log = (
                "[导航失败] 依赖导航三级降级均失败，页面可能未到达正确状态，"
                f"失败原因可能是测试基础设施问题而非产品Bug。原始结果: {result.error_message or ''}"
            )
        elif result.failure_category is None:
            result.failure_category = FailureCategory.PRODUCT_BUG
        test_result.exec_status = ExecStatus.FAILED
        counts.failed += 1
        self._mark_dependents_blocked(test_case, sorted_cases, self._case_results)

    async def _run_and_record_case(
        self,
        test_case: Any,
        test_result: Any,
        project: Any,
        sorted_cases: list,
        execution_mode: str,
        mobile_device_id: str | None,
        nav_level_used: str | None,
        nav_failed: bool,
        counts: _CaseCounts,
    ) -> None:
        """执行单条用例并回写状态、日志与缺陷证据。"""
        result = await self.execute_test_case(
            test_case=test_case,
            project_id=project.id,
            skip_precondition=False,
            execution_mode=execution_mode,
            mobile_device_id=mobile_device_id,
        )
        if nav_level_used:
            result.navigation_level = nav_level_used

        self._apply_case_result(test_case, test_result, result, nav_failed, sorted_cases, counts)

        test_result.exec_time = utcnow()
        if not test_result.exec_log:
            test_result.exec_log = result.error_message or ""

        aggregated_evidence = self._aggregate_defect_evidence(result)
        if aggregated_evidence:
            test_result.defect_evidence = aggregated_evidence

        self._case_results[test_case.id] = result
        if not getattr(test_case, "depends_on", None) and result.status == ExecutionStatus.PASSED:
            await self._save_main_flow_snapshots(test_case, self._step_results)

    async def _execute_case_entry(
        self,
        test_case: Any,
        test_result: Any,
        project: Any,
        sorted_cases: list,
        execution_mode: str,
        mobile_device_id: str | None,
        counts: _CaseCounts,
    ) -> None:
        """单条用例入口：阻塞判定 → 依赖导航 → 执行 → 异常兜底。"""
        if self._should_skip_as_blocked(test_case):
            self._mark_case_blocked(test_case, test_result)
            counts.blocked += 1
            return

        nav_level_used, nav_failed = await self._navigate_for_case(test_case)
        try:
            await self._run_and_record_case(
                test_case,
                test_result,
                project,
                sorted_cases,
                execution_mode,
                mobile_device_id,
                nav_level_used,
                nav_failed,
                counts,
            )
        except Exception as e:
            logger.error(f"用例 {test_result.case_id} 执行失败: {e}")
            test_result.exec_status = ExecStatus.FAILED
            test_result.exec_time = utcnow()
            test_result.error_msg = str(e)
            counts.failed += 1
            self._mark_dependents_blocked(test_case, sorted_cases, self._case_results)

    async def _run_case_loop(
        self,
        task: Any,
        project: Any,
        test_results: list,
        execution_mode: str,
        mobile_device_id: str | None,
    ) -> None:
        """遍历用例执行并汇总任务终态。"""
        sorted_cases, result_map = self._init_case_execution_state(test_results)
        counts = _CaseCounts()

        for test_case in sorted_cases:
            test_result = result_map.get(test_case.id)
            if not test_result:
                continue
            await self._execute_case_entry(
                test_case, test_result, project, sorted_cases, execution_mode, mobile_device_id, counts
            )
            self.db.commit()

        self._finalize_task_status(task, counts)
        logger.info(
            f"测试任务执行完成: {task.id}, 通过: {counts.passed}, 失败: {counts.failed}, 阻塞: {counts.blocked}"
        )

    @staticmethod
    def _aggregate_defect_evidence(result: "TestExecutionResult") -> dict[str, Any] | None:
        """聚合步骤级别的 defect_evidence 为用例级别的缺陷证据。

        合并所有步骤的 console_errors、network_failures、uncaught_exceptions，
        对 memory_leak_suspect 取并集。
        """
        if not result or not result.steps:
            return None

        merged = _collect_step_evidence(result.steps)
        if merged is None:
            return None

        # 去重后仅保留非空字段
        deduped = _dedupe_evidence(merged)
        return {k: v for k, v in deduped.items() if v} or None
