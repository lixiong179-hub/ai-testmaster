"""Defect-discovery self-test pipeline orchestrator.

通过 shim 模块引用调用 _step_* 和 _notify_pipeline_summary，使
@patch("app.services.self_test_service._step_*") 等装饰器仍能生效：
patch 替换的是 shim 模块属性，运行时 _stm._step_* 从 shim 查找得到被 patch 版本。
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.self_test._pipeline_steps_setup import _build_step_result


def _elapsed_ms(step_start: float) -> float:
    return (time.monotonic() - step_start) * 1000


async def _run_step(
    steps: list[dict[str, Any]],
    name: str,
    call: Callable[[], Awaitable[tuple]],
    skip_reason: str | None = None,
) -> tuple | None:
    """执行单个链路步骤并入账：前置不满足记 skipped，异常记 failed 且不中断后续。

    返回被调用步骤的原始元组（`(ok, err, ...)`），跳过或异常时返回 None——
    调用方据此决定是否采纳 `result[2]` 这类产出，语义与原先的「赋值只发生在成功返回」一致。
    """
    step_start = time.monotonic()
    if skip_reason:
        steps.append(_build_step_result(name, "skipped", skip_reason, _elapsed_ms(step_start)))
        return None
    try:
        result = await call()
    except Exception as exc:  # noqa: BLE001 - 单步异常不应中断全链路
        steps.append(_build_step_result(name, "failed", str(exc), _elapsed_ms(step_start)))
        return None
    ok, err = result[0], result[1]
    steps.append(_build_step_result(name, "success" if ok else "failed", err, _elapsed_ms(step_start)))
    return result


async def run_defect_discovery_self_test(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> dict[str, Any]:
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

    steps: list[dict[str, Any]] = []
    task_id: int | None = None
    report_id: int | None = None
    defect_summary: dict[str, int] = {"p0_count": 0, "p1_count": 0, "p2_count": 0, "p3_count": 0, "total_defects": 0}

    # 中间状态，步骤间传递
    test_point_ids: list[int] = []
    case_ids: list[int] = []

    logger.info(f"开始缺陷挖掘全链路自测: project_id={project_id}, user_id={user_id}")

    # --- 步骤 1: 需求确认 ---
    await _run_step(
        steps,
        "需求确认",
        lambda: _stm._step_requirement_confirmation(db, project_id),
    )

    # --- 步骤 2: 测试点提取 ---
    result = await _run_step(
        steps,
        "测试点提取",
        lambda: _stm._step_extract_test_points(db, project_id),
    )
    if result:
        test_point_ids = result[2]

    # --- 步骤 3: 用例生成 ---
    result = await _run_step(
        steps,
        "用例生成",
        lambda: _stm._step_generate_cases(db, project_id, user_id, test_point_ids),
        skip_reason=None if test_point_ids else "前置步骤未产出测试点",
    )
    if result:
        case_ids = result[2]

    # --- 步骤 4: 评审保存 ---
    await _run_step(
        steps,
        "评审保存",
        lambda: _stm._step_review_and_save(db, project_id, user_id, case_ids),
        skip_reason=None if case_ids else "前置步骤未产出用例",
    )

    # --- 步骤 5: 任务创建 ---
    result = await _run_step(
        steps,
        "任务创建",
        lambda: _stm._step_create_task(db, project_id, user_id, case_ids),
        skip_reason=None if case_ids else "前置步骤未产出用例",
    )
    if result:
        task_id = result[2]

    # --- 步骤 6: 执行 ---
    await _run_step(
        steps,
        "执行",
        lambda: _stm._step_execute(db, project_id, task_id),
        skip_reason=None if task_id else "前置步骤未创建任务",
    )

    # --- 步骤 7: 严重度评估 ---
    result = await _run_step(
        steps,
        "严重度评估",
        lambda: _stm._step_assess_severity(db, project_id, task_id),
        skip_reason=None if task_id else "前置步骤未创建任务",
    )
    if result:
        _merge_defect_counts(defect_summary, result[2])

    # --- 步骤 8: 报告生成 ---
    result = await _run_step(
        steps,
        "报告生成",
        lambda: _stm._step_generate_report(db, project_id, task_id, user_id),
        skip_reason=None if task_id else "前置步骤未创建任务",
    )
    if result:
        report_id = result[2]

    # --- 步骤 9: 数据清理 ---
    await _run_step(
        steps,
        "数据清理",
        lambda: _stm._step_cleanup(db, project_id),
    )

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


def _merge_defect_counts(defect_summary: dict[str, int], defect_counts: dict[str, int]) -> None:
    """把步骤 7 的缺陷计数并入摘要（p0-p3 覆盖写入，总数按四档重算）。"""
    defect_summary["p0_count"] = defect_counts.get("p0", 0)
    defect_summary["p1_count"] = defect_counts.get("p1", 0)
    defect_summary["p2_count"] = defect_counts.get("p2", 0)
    defect_summary["p3_count"] = defect_counts.get("p3", 0)
    # 只累加四档，避免把残留的 total_defects 再计入（原实现依赖初始值为 0）
    defect_summary["total_defects"] = sum(
        defect_summary[key] for key in ("p0_count", "p1_count", "p2_count", "p3_count")
    )


async def _notify_pipeline_summary(
    db: AsyncSession,
    project_id: int,
    steps: list[dict[str, Any]],
    defect_summary: dict[str, int],
    report_id: int | None,
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
        step_summary = [{"name": s["name"], "status": s["status"]} for s in steps]
        message = {
            "type": "defect_discovery_pipeline_summary",
            "project_id": project_id,
            "step_summary": step_summary,
            "defect_summary": defect_summary,
            "report_id": report_id,
            "report_link": f"/report/{report_id}" if report_id else None,
        }
        await ws_manager.broadcast(str(project_id), message)
        logger.info(f"缺陷挖掘全链路摘要通知已推送: project_id={project_id}")
    except Exception as exc:
        logger.warning(f"全链路摘要 WebSocket 通知失败: {exc}")
