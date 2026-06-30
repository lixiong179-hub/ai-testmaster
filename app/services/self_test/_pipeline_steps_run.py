"""Pipeline steps 5-9: task creation, execution, severity assessment,
report generation, and cleanup."""
import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.project import Project
from app.services.self_test._defect_bug import (
    _assess_defect_severity,
    _auto_create_defect_bug,
    _notify_critical_defect_bug,
)


async def _step_create_task(
    db: Session,
    project_id: int,
    user_id: int,
    case_ids: List[int],
) -> Tuple[bool, Optional[str], Optional[int]]:
    """步骤5: 任务创建 - 创建测试任务，将所有活跃用例加入任务。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。
        case_ids: 用例 ID 列表。

    Returns:
        (成功标志, 错误信息, 任务ID) 三元组。
    """
    from app.crud.test_task import create_test_task
    from app.models.test_case import TestCase

    if not case_ids:
        return (False, "无可用用例，无法创建任务", None)

    # 过滤出活跃用例
    active_cases = (
        db.query(TestCase)
        .filter(
            TestCase.id.in_(case_ids),
            TestCase.is_deleted.is_(False),
            TestCase.project_id == project_id,
        )
        .all()
    )
    active_case_ids = [tc.id for tc in active_cases]

    if not active_case_ids:
        return (False, "过滤后无活跃用例，无法创建任务", None)

    task = create_test_task(
        db=db,
        task_name=f"缺陷挖掘自测任务-{time.strftime('%Y%m%d_%H%M%S')}",
        project_id=project_id,
        case_ids=active_case_ids,
        executor_id=user_id,
    )

    logger.info(
        f"项目 {project_id} 测试任务创建完成: task_id={task.id}, "
        f"用例数={len(active_case_ids)}"
    )
    return (True, None, task.id)


async def _step_execute(
    db: Session,
    project_id: int,
    task_id: int,
) -> Tuple[bool, Optional[str]]:
    """步骤6: 执行 - 启动 Playwright 执行（含浏览器环境缺陷捕获）。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    from app.services.test_execution_engine import TestExecutionEngineV2
    from app.services.precondition_service import PreconditionService
    from app.services.element_locator_service import ElementLocatorService

    try:
        precondition_service = PreconditionService()
        await precondition_service.initialize()
    except Exception as exc:
        logger.warning(f"前置条件服务初始化失败，继续执行: {exc}")
        precondition_service = None

    locator_service = ElementLocatorService(db)

    engine = TestExecutionEngineV2(
        db=db,
        precondition_service=precondition_service,
        locator_service=locator_service,
        enable_ai_recognition=True,
        enable_test_data_param=True,
    )

    try:
        result = await engine.execute_test_task(
            task_id=task_id,
            global_headless=True,
            global_record_video=False,
            execution_mode="smart",
        )
        logger.info(
            f"项目 {project_id} 任务 {task_id} 执行完成: {result}"
        )
        return (True, None)
    except Exception as exc:
        logger.error(f"任务执行失败: {exc}")
        return (False, f"任务执行失败: {exc}")


async def _step_assess_severity(
    db: Session,
    project_id: int,
    task_id: int,
) -> Tuple[bool, Optional[str], Dict[str, int]]:
    """步骤7: 严重度评估 - 遍历执行结果，评估缺陷严重度，P0/P1 立即通知。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。

    Returns:
        (成功标志, 错误信息, 缺陷统计) 三元组。
        缺陷统计格式: {"p0": int, "p1": int, "p2": int, "p3": int}
    """
    from app.models.test_result import TestResult
    from app.models.enums import ExecStatus

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return (False, f"项目 {project_id} 不存在", {"p0": 0, "p1": 0, "p2": 0, "p3": 0})

    # 查询任务下所有失败和阻塞的测试结果
    test_results = (
        db.query(TestResult)
        .filter(
            TestResult.project_id == project_id,
            TestResult.task_id == task_id,
            TestResult.exec_status.in_([ExecStatus.FAILED, ExecStatus.BLOCKED]),
        )
        .all()
    )

    defect_counts: Dict[str, int] = {"p0": 0, "p1": 0, "p2": 0, "p3": 0}

    for result in test_results:
        # 从错误信息中提取失败类型
        failure_type = "execution_failure"
        error_msg = result.error_msg or ""

        # 尝试从 exec_log 中提取断言类型
        if result.exec_log:
            log_lower = result.exec_log.lower()
            for assertion in (
                "no_sensitive_data", "no_xss", "loading_hidden",
                "no_console_errors", "no_network_errors", "text_not_empty",
                "response_time_lt", "memory_leak_suspect",
            ):
                if assertion in log_lower:
                    failure_type = assertion
                    break

        # 评估严重度
        severity, _ux_category = _assess_defect_severity(
            failure_type=failure_type,
            defect_evidence=result.defect_evidence,
            error_message=error_msg,
        )

        # 创建 Bug 记录
        step_desc = f"用例 {result.case_no} 执行失败"
        bug = _auto_create_defect_bug(
            db=db,
            project=project,
            failure_type=failure_type,
            error_message=error_msg,
            defect_evidence=result.defect_evidence,
            test_case_id=result.case_id,
            test_result_id=result.id,
            step_description=step_desc,
        )

        if bug:
            severity_key = f"p{severity - 1}" if 1 <= severity <= 4 else "p2"
            defect_counts[severity_key] = defect_counts.get(severity_key, 0) + 1

            # P0/P1 缺陷立即通知
            if severity <= 2:
                await _notify_critical_defect_bug(bug, project)

    logger.info(
        f"项目 {project_id} 任务 {task_id} 严重度评估完成: {defect_counts}"
    )
    return (True, None, defect_counts)


async def _step_generate_report(
    db: Session,
    project_id: int,
    task_id: int,
    user_id: int,
) -> Tuple[bool, Optional[str], Optional[int]]:
    """步骤8: 报告生成 - 生成以缺陷为中心的测试报告。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。
        user_id: 用户 ID。

    Returns:
        (成功标志, 错误信息, 报告ID) 三元组。
    """
    from app.services.report_service import ReportService

    try:
        report = ReportService.generate_report(
            db=db,
            project_id=project_id,
            test_task_id=task_id,
            name=f"缺陷挖掘报告-{time.strftime('%Y%m%d_%H%M%S')}",
            description="自测全链路缺陷挖掘导向测试报告",
            user_id=user_id,
        )
        logger.info(
            f"项目 {project_id} 缺陷挖掘报告生成完成: report_id={report.id}"
        )
        return (True, None, report.id)
    except Exception as exc:
        logger.error(f"报告生成失败: {exc}")
        return (False, f"报告生成失败: {exc}", None)


async def _step_cleanup(
    db: Session,
    project_id: int,
) -> Tuple[bool, Optional[str]]:
    """步骤9: 数据清理 - 清理临时数据（测试点草稿、未保存的生成批次等）。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    from app.models.test_point import TestPoint
    from app.models.enums import TestPointStatus

    try:
        # 清理草稿状态的测试点
        draft_points = (
            db.query(TestPoint)
            .filter(
                TestPoint.project_id == project_id,
                TestPoint.status == TestPointStatus.DRAFT.value,
            )
            .all()
        )
        for point in draft_points:
            db.delete(point)

        # 清理未完成的生成批次
        from app.models.generation_batch import GenerationBatch
        pending_batches = (
            db.query(GenerationBatch)
            .filter(
                GenerationBatch.project_id == project_id,
                GenerationBatch.status.in_(["created", "processing"]),
            )
            .all()
        )
        for batch in pending_batches:
            batch.status = "cancelled"

        db.commit()
        logger.info(
            f"项目 {project_id} 数据清理完成: "
            f"删除 {len(draft_points)} 个草稿测试点, "
            f"取消 {len(pending_batches)} 个未完成批次"
        )
        return (True, None)
    except Exception as exc:
        logger.warning(f"数据清理失败: {exc}")
        return (False, f"数据清理失败: {exc}")
