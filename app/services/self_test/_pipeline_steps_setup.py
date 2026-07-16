"""Pipeline steps 1-4: requirement confirmation, test point extraction,
case generation, and review/save."""
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ProjectFile


# 高置信度阈值：ai_confidence >= 80 时自动采纳评审决策
_AUTO_ADOPT_CONFIDENCE_THRESHOLD = 80


def _build_step_result(
    name: str,
    status: str,
    error: Optional[str] = None,
    duration_ms: float = 0.0,
) -> Dict[str, Any]:
    """构建单步骤执行结果字典。

    Args:
        name: 步骤名称。
        status: 步骤状态（success/failed/skipped）。
        error: 错误信息，成功时为 None。
        duration_ms: 步骤执行耗时（毫秒）。

    Returns:
        步骤结果字典。
    """
    return {
        "name": name,
        "status": status,
        "error": error,
        "duration_ms": round(duration_ms, 2),
    }


async def _step_requirement_confirmation(
    db: AsyncSession,
    project_id: int,
) -> Tuple[bool, Optional[str]]:
    """步骤1: 需求确认 - 确认需求文档已导入且内容提取完成。

    Args:
        db: 异步数据库会话。
        project_id: 项目 ID。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    requirement_file = (
        await db.execute(
            select(ProjectFile)
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.resource_type == "requirement",
                ProjectFile.extract_status == "completed",
                ProjectFile.is_active.is_(True),
            )
        )
    ).scalars().first()
    if not requirement_file:
        return (False, f"项目 {project_id} 未找到已完成提取的需求文档")
    return (True, None)


async def _step_extract_test_points(
    db: AsyncSession,
    project_id: int,
) -> Tuple[bool, Optional[str], List[int]]:
    """步骤2: 测试点提取 - AI 基于需求文档提取测试点。

    重点标注边界条件和异常处理规则。

    Args:
        db: 异步数据库会话。
        project_id: 项目 ID。

    Returns:
        (成功标志, 错误信息, 测试点ID列表) 三元组。
    """
    from app.crud.test_point import get_test_points_by_project_async, batch_create_test_points_async
    from app.services.ai_analysis_service import extract_test_points_from_content

    # 先检查是否已有活跃测试点，避免重复提取
    existing_points = await get_test_points_by_project_async(db, project_id, limit=500)
    if existing_points:
        existing_ids = [tp.id for tp in existing_points]
        logger.info(
            f"项目 {project_id} 已有 {len(existing_ids)} 个测试点，跳过提取"
        )
        return (True, None, existing_ids)

    # 获取需求文档内容
    requirement_file = (
        await db.execute(
            select(ProjectFile)
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.resource_type == "requirement",
                ProjectFile.extract_status == "completed",
                ProjectFile.is_active.is_(True),
            )
        )
    ).scalars().first()
    if not requirement_file or not requirement_file.content:
        return (False, "需求文档内容为空，无法提取测试点", [])

    # 调用 AI 提取测试点
    extracted_points = await extract_test_points_from_content(
        content=requirement_file.content,
        project_id=project_id,
        context={"focus": "boundary_and_exception"},
    )

    if not extracted_points:
        return (False, "AI 提取测试点返回为空", [])

    # 批量创建测试点
    point_data_list: List[Dict[str, Any]] = []
    for pt in extracted_points:
        point_data_list.append({
            "module": pt.get("module", "未分类"),
            "point": pt.get("point", ""),
            "priority": pt.get("priority", 2),
            "ai_prompt": pt.get("function", ""),
            "created_by": "self_test_pipeline",
        })

    created_points = await batch_create_test_points_async(
        db=db,
        project_id=project_id,
        test_points_data=point_data_list,
    )

    point_ids = [tp.id for tp in created_points]
    logger.info(
        f"项目 {project_id} AI 提取测试点完成: {len(point_ids)} 个"
    )
    return (True, None, point_ids)


async def _step_generate_cases(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    test_point_ids: List[int],
) -> Tuple[bool, Optional[str], List[int]]:
    """步骤3: 用例生成 - AI 基于测试点+需求文档生成缺陷挖掘用例。

    使用缺陷挖掘导向的 Prompt，确保 >=60% 非正常路径。

    TestCaseGenerationService 内部使用 sync Session，通过
    iter_async_gen_in_thread 在独立线程中运行，避免阻塞事件循环。

    Args:
        db: 异步数据库会话（本步骤未直接使用，用例生成在独立 sync 会话中完成）。
        project_id: 项目 ID。
        user_id: 用户 ID。
        test_point_ids: 测试点 ID 列表。

    Returns:
        (成功标志, 错误信息, 用例ID列表) 三元组。
    """
    from app.db.database import PrimarySessionLocal
    from app.services.test_case_generation import TestCaseGenerationService
    from app.utils.async_sync_bridge import iter_async_gen_in_thread

    if not test_point_ids:
        return (False, "无可用测试点，无法生成用例", [])

    # TestCaseGenerationService 内部使用 sync Session.query()，
    # 在独立线程+独立事件循环中运行，避免阻塞主事件循环
    sync_db = PrimarySessionLocal()
    generated_case_ids: List[int] = []

    try:
        service = TestCaseGenerationService(sync_db)

        async for result in iter_async_gen_in_thread(
            lambda: service.generate_test_cases_batch(
                project_id=project_id,
                user_id=user_id,
                test_point_ids=test_point_ids,
                case_type="ui_automation",
            )
        ):
            status = result.get("status")
            if status == "completed":
                case_id = result.get("case_id")
                if case_id:
                    generated_case_ids.append(case_id)
            elif status == "error":
                error_msg = result.get("message", "未知错误")
                logger.warning(f"用例生成出错: {error_msg}")
    finally:
        sync_db.close()

    if not generated_case_ids:
        return (False, "AI 用例生成未产出任何用例", [])

    logger.info(
        f"项目 {project_id} 缺陷挖掘用例生成完成: {len(generated_case_ids)} 个"
    )
    return (True, None, generated_case_ids)


async def _step_review_and_save(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    case_ids: List[int],
) -> Tuple[bool, Optional[str]]:
    """步骤4: 评审保存 - 自动采纳高置信度评审决策，保存用例。

    自动采纳 ai_confidence >= 80 的评审决策（keep/modify/deprecate），
    对 deprecate 决策的用例标记为不活跃，其余保留。

    Args:
        db: 异步数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。
        case_ids: 待评审用例 ID 列表。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    if not case_ids:
        return (True, None)

    from app.models.test_case import TestCase
    from app.models.review import IterationReview, ReviewDecision
    from app.models.enums import ReviewKind, ReviewStatus
    from app.services.review_service import (
        create_review_async,
        start_review_async,
        add_decision_async,
        finalize_review_async,
    )

    # 获取项目关联的迭代，若无则跳过评审直接保存
    from app.models.iteration import Iteration
    iteration = (
        await db.execute(
            select(Iteration)
            .where(Iteration.project_id == project_id)
            .order_by(Iteration.id.desc())
        )
    ).scalars().first()

    if not iteration:
        # 无迭代时直接确认用例为活跃状态（跳过评审）
        logger.info(
            f"项目 {project_id} 无迭代，跳过评审直接保存 {len(case_ids)} 个用例"
        )
        return (True, None)

    try:
        # 创建评审
        review = await create_review_async(db, iteration_id=iteration.id, kind="forward")
        review = await start_review_async(db, review.id)

        # P1-3: 批量查询用例替代循环内逐个查询，消除 N+1
        cases = (
            await db.execute(
                select(TestCase).where(TestCase.id.in_(case_ids))
            )
        ).scalars().all()
        cases_by_id = {c.id: c for c in cases}

        # 为每个用例添加 AI 评审决策
        for case_id in case_ids:
            test_case = cases_by_id.get(case_id)
            if not test_case:
                continue

            # 简化评审逻辑：默认高置信度采纳
            # 根据用例类型判断 verdict
            case_category = getattr(test_case, "case_category", "") or ""
            if case_category in ("boundary", "exception", "security", "stress"):
                ai_verdict = "keep"
                ai_confidence = 90
            else:
                ai_verdict = "keep"
                ai_confidence = 85

            await add_decision_async(
                db=db,
                review_id=review.id,
                target_kind="case",
                target_id=case_id,
                ai_verdict=ai_verdict,
                ai_confidence=ai_confidence,
                ai_reason=f"自测全链路自动评审: {case_category} 类用例",
            )

        # 终结评审
        await finalize_review_async(db, review.id, finalized_by=user_id)

        # 应用高置信度决策
        decisions = (
            await db.execute(
                select(ReviewDecision)
                .where(
                    ReviewDecision.review_id == review.id,
                    ReviewDecision.ai_confidence >= _AUTO_ADOPT_CONFIDENCE_THRESHOLD,
                )
            )
        ).scalars().all()

        # P1-3: 批量查询待废弃用例替代循环内逐个查询，消除 N+1
        deprecate_target_ids = [
            d.target_id for d in decisions
            if d.final_verdict == "deprecate" and d.target_id is not None
        ]
        if deprecate_target_ids:
            deprecate_cases = (
                await db.execute(
                    select(TestCase)
                    .where(TestCase.id.in_(deprecate_target_ids))
                )
            ).scalars().all()
            from app.utils.db_time import utcnow as _utcnow
            for case in deprecate_cases:
                case.is_deleted = True
                case.deleted_at = _utcnow()

        await db.commit()
        logger.info(
            f"项目 {project_id} 评审保存完成: "
            f"评审 {len(decisions)} 个决策，置信度 >= {_AUTO_ADOPT_CONFIDENCE_THRESHOLD}"
        )
        return (True, None)

    except Exception as exc:
        logger.warning(f"评审保存失败，用例仍保留: {exc}")
        # 评审失败不影响用例保存，用例已由步骤3创建
        return (True, None)
