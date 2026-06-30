"""Defect-discovery self-test pipeline orchestrator.

通过 shim 模块引用调用 _step_* 和 _notify_pipeline_summary，使
@patch("app.services.self_test_service._step_*") 等装饰器仍能生效：
patch 替换的是 shim 模块属性，运行时 _stm._step_* 从 shim 查找得到被 patch 版本。
"""
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.services.self_test._pipeline_steps_setup import _build_step_result


async def run_defect_discovery_self_test(
    db: Session,
    project_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """执行缺陷挖掘导向的自测全链路，返回执行摘要。

    全链路包含 9 个步骤，每个步骤失败时记录错误并继续（不中断全链路），
    最终汇总通知。步骤间通过 project_id 关联。

    步骤流程:
        1. 需求确认: 确认需求文档已导入且内容提取完成
        2. 测试点提取: AI 基于需求文档提取测试点（重点标注边界条件和异常处理规则）
        3. 用例生成: AI 基于测试点+需求文档生成缺陷挖掘用例（>=60% 非正常路径）
        4. 评审保存: 自动采纳高置信度评审决策，保存用例
        5. 任务创建: 创建测试任务
        6. 执行: 启动 Playwright 执行（含浏览器环境缺陷捕获）
        7. 严重度评估: 自动评估缺陷严重度，P0/P1 立即通知
        8. 报告生成: 生成以缺陷为中心的测试报告
        9. 数据清理: 清理临时数据

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。

    Returns:
        执行摘要字典，结构如下:
        {
            "project_id": int,
            "success": bool,
            "steps": [{"name": str, "status": str, "error": str|None, "duration_ms": float}],
            "defect_summary": {"p0_count": int, "p1_count": int, "p2_count": int, "p3_count": int, "total_defects": int},
            "report_id": int|None,
            "task_id": int|None,
        }
    """
    # 通过 shim 模块引用调用 _step_* 和 _notify_pipeline_summary，
    # 使 @patch("app.services.self_test_service._step_*") 装饰器生效。
    from app.services import self_test_service as _stm

    steps: List[Dict[str, Any]] = []
    task_id: Optional[int] = None
    report_id: Optional[int] = None
    defect_summary: Dict[str, int] = {"p0_count": 0, "p1_count": 0, "p2_count": 0, "p3_count": 0, "total_defects": 0}

    # 中间状态，步骤间传递
    test_point_ids: List[int] = []
    case_ids: List[int] = []

    logger.info(f"开始缺陷挖掘全链路自测: project_id={project_id}, user_id={user_id}")

    # --- 步骤 1: 需求确认 ---
    step_start = time.monotonic()
    try:
        ok, err = await _stm._step_requirement_confirmation(db, project_id)
        steps.append(_build_step_result(
            "需求确认", "success" if ok else "failed", err,
            (time.monotonic() - step_start) * 1000,
        ))
    except Exception as exc:
        steps.append(_build_step_result(
            "需求确认", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 2: 测试点提取 ---
    step_start = time.monotonic()
    try:
        ok, err, test_point_ids = await _stm._step_extract_test_points(db, project_id)
        steps.append(_build_step_result(
            "测试点提取", "success" if ok else "failed", err,
            (time.monotonic() - step_start) * 1000,
        ))
    except Exception as exc:
        steps.append(_build_step_result(
            "测试点提取", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 3: 用例生成 ---
    step_start = time.monotonic()
    try:
        if not test_point_ids:
            steps.append(_build_step_result(
                "用例生成", "skipped", "前置步骤未产出测试点",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, case_ids = await _stm._step_generate_cases(
                db, project_id, user_id, test_point_ids,
            )
            steps.append(_build_step_result(
                "用例生成", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "用例生成", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 4: 评审保存 ---
    step_start = time.monotonic()
    try:
        if not case_ids:
            steps.append(_build_step_result(
                "评审保存", "skipped", "前置步骤未产出用例",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err = await _stm._step_review_and_save(db, project_id, user_id, case_ids)
            steps.append(_build_step_result(
                "评审保存", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "评审保存", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 5: 任务创建 ---
    step_start = time.monotonic()
    try:
        if not case_ids:
            steps.append(_build_step_result(
                "任务创建", "skipped", "前置步骤未产出用例",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, task_id = await _stm._step_create_task(db, project_id, user_id, case_ids)
            steps.append(_build_step_result(
                "任务创建", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "任务创建", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 6: 执行 ---
    step_start = time.monotonic()
    try:
        if not task_id:
            steps.append(_build_step_result(
                "执行", "skipped", "前置步骤未创建任务",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err = await _stm._step_execute(db, project_id, task_id)
            steps.append(_build_step_result(
                "执行", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "执行", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 7: 严重度评估 ---
    step_start = time.monotonic()
    try:
        if not task_id:
            steps.append(_build_step_result(
                "严重度评估", "skipped", "前置步骤未创建任务",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, defect_counts = await _stm._step_assess_severity(db, project_id, task_id)
            steps.append(_build_step_result(
                "严重度评估", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
            # 汇总缺陷统计
            defect_summary["p0_count"] = defect_counts.get("p0", 0)
            defect_summary["p1_count"] = defect_counts.get("p1", 0)
            defect_summary["p2_count"] = defect_counts.get("p2", 0)
            defect_summary["p3_count"] = defect_counts.get("p3", 0)
            defect_summary["total_defects"] = sum(defect_summary.values())
    except Exception as exc:
        steps.append(_build_step_result(
            "严重度评估", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 8: 报告生成 ---
    step_start = time.monotonic()
    try:
        if not task_id:
            steps.append(_build_step_result(
                "报告生成", "skipped", "前置步骤未创建任务",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, report_id = await _stm._step_generate_report(
                db, project_id, task_id, user_id,
            )
            steps.append(_build_step_result(
                "报告生成", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "报告生成", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 9: 数据清理 ---
    step_start = time.monotonic()
    try:
        ok, err = await _stm._step_cleanup(db, project_id)
        steps.append(_build_step_result(
            "数据清理", "success" if ok else "failed", err,
            (time.monotonic() - step_start) * 1000,
        ))
    except Exception as exc:
        steps.append(_build_step_result(
            "数据清理", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 汇总通知 ---
    await _stm._notify_pipeline_summary(db, project_id, steps, defect_summary, report_id)

    # 全链路完成判定：即使部分步骤失败也算完成（不中断）
    success = all(s["status"] != "failed" for s in steps)

    result = {
        "project_id": project_id,
        "success": success,
        "steps": steps,
        "defect_summary": defect_summary,
        "report_id": report_id,
        "task_id": task_id,
    }

    logger.info(
        f"缺陷挖掘全链路自测完成: project_id={project_id}, "
        f"success={success}, defects={defect_summary}, "
        f"task_id={task_id}, report_id={report_id}"
    )

    return result


async def _notify_pipeline_summary(
    db: Session,
    project_id: int,
    steps: List[Dict[str, Any]],
    defect_summary: Dict[str, int],
    report_id: Optional[int],
) -> None:
    """全链路执行完成后，通过 WebSocket 推送缺陷发现摘要通知。

    通知包含：执行步骤摘要、缺陷发现数（P0-P3）、报告链接。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        steps: 步骤执行结果列表。
        defect_summary: 缺陷统计字典。
        report_id: 报告 ID（可能为 None）。
    """
    from app.core.websocket import manager as ws_manager

    try:
        step_summary = [
            {"name": s["name"], "status": s["status"]}
            for s in steps
        ]
        message = {
            "type": "defect_discovery_pipeline_summary",
            "project_id": project_id,
            "step_summary": step_summary,
            "defect_summary": defect_summary,
            "report_id": report_id,
            "report_link": f"/report/{report_id}" if report_id else None,
        }
        await ws_manager.broadcast(str(project_id), message)
        logger.info(
            f"缺陷挖掘全链路摘要通知已推送: project_id={project_id}"
        )
    except Exception as exc:
        logger.warning(f"全链路摘要 WebSocket 通知失败: {exc}")
