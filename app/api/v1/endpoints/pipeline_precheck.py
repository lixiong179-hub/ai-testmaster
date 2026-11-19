"""Pipeline 场景4预检端点

提供场景4运行前的预检功能，检查历史用例、测试点、UI页面等前置条件。
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_schemas import Scenario4PrecheckRequest
from app.api.v1.endpoints.pipeline_deps import verify_project_access
from app.core.exception import create_response
from app.schemas.common import ApiResponse

router = APIRouter(tags=["Pipeline管理"])


async def _count(db: Session, stmt) -> int:
    """执行 count 查询并返回标量值（同步执行转入线程池）。"""
    return (await asyncio.to_thread(db.execute, stmt)).scalar() or 0


async def _scalar_one_or_none(db: Session, stmt):
    """执行查询并返回 `scalar_one_or_none()`（同步执行转入线程池）。"""
    return (await asyncio.to_thread(db.execute, stmt)).scalar_one_or_none()


async def _all(db: Session, stmt) -> list:
    """执行查询并返回行列表（同步执行转入线程池）。"""
    return (await asyncio.to_thread(db.execute, stmt)).all()


async def _collect_history_case_stats(db: Session, test_case_model, project_id: int) -> dict:
    """统计历史用例总数、可扫描数及各生命周期分布。"""
    base_filter = (
        test_case_model.project_id == project_id,
        test_case_model.is_deleted.is_(False),
    )

    async def _count_lifecycle(*extra) -> int:
        return await _count(db, select(func.count()).select_from(test_case_model).where(*base_filter, *extra))

    return {
        "total": await _count_lifecycle(),
        "included": await _count_lifecycle(test_case_model.lifecycle_status != "archived"),
        "active": await _count_lifecycle(test_case_model.lifecycle_status == "active"),
        "draft": await _count_lifecycle(test_case_model.lifecycle_status == "draft"),
        "pending_review": await _count_lifecycle(test_case_model.lifecycle_status == "pending_review"),
        "archived": await _count_lifecycle(test_case_model.lifecycle_status == "archived"),
        "deleted": await _count(
            db,
            select(func.count())
            .select_from(test_case_model)
            .where(
                test_case_model.project_id == project_id,
                test_case_model.is_deleted.is_(True),
            ),
        ),
    }


async def _verify_selected_test_points(
    db: Session, test_point_model, project_id: int, point_ids: list[int] | None
) -> int:
    """校验所选测试点均属当前项目，返回选中数。"""
    if not point_ids:
        return 0
    owned_count = await _count(
        db,
        select(func.count())
        .select_from(test_point_model)
        .where(
            test_point_model.id.in_(point_ids),
            test_point_model.project_id == project_id,
        ),
    )
    if owned_count != len(point_ids):
        raise HTTPException(status_code=403, detail="部分测试点不属于当前项目")
    return owned_count


async def _verify_selected_requirement_files(
    db: Session, project_file_model, project_id: int, file_ids: list[int] | None
) -> int:
    """校验所选需求文件均属当前项目且有效，返回选中数。"""
    if not file_ids:
        return 0
    owned_count = await _count(
        db,
        select(func.count())
        .select_from(project_file_model)
        .where(
            project_file_model.id.in_(file_ids),
            project_file_model.project_id == project_id,
            project_file_model.is_active.is_(True),
        ),
    )
    if owned_count != len(file_ids):
        raise HTTPException(status_code=403, detail="部分需求文件不属于当前项目")
    return owned_count


async def _resolve_screen_ids(db: Session, body: Scenario4PrecheckRequest, ui_project_model, screen_model) -> list[int]:
    """解析待检查的屏幕 ID（校验 UI 项目归属并按需回填屏幕列表）。"""
    if body.ui_project_id and not body.screen_ids:
        prototype_project = await _scalar_one_or_none(
            db,
            select(ui_project_model).where(
                ui_project_model.id == body.ui_project_id,
                ui_project_model.project_id == body.project_id,
            ),
        )
        if not prototype_project:
            raise HTTPException(status_code=403, detail="UI原型项目不属于当前项目")
        screens = await _all(
            db,
            select(screen_model.id).where(
                screen_model.prototype_project_id == body.ui_project_id,
            ),
        )
        return [s[0] for s in screens]
    if not body.ui_project_id:
        return []
    return list(body.screen_ids)


async def _verify_screen_ownership(db: Session, screen_model, screen_ids: list[int], ui_project_id: int | None) -> None:
    """校验所选屏幕均属指定 UI 原型项目。"""
    if not screen_ids or not ui_project_id:
        return
    owner_check = await _all(
        db,
        select(screen_model.id).where(
            screen_model.id.in_(screen_ids),
            screen_model.prototype_project_id == ui_project_id,
        ),
    )
    invalid_ids = set(screen_ids) - {s[0] for s in owner_check}
    if invalid_ids:
        raise HTTPException(
            status_code=403,
            detail=f"屏幕 {invalid_ids} 不属于 UI 原型项目 {ui_project_id}",
        )


def _summarize_screens(screens) -> tuple[int, int, int, list[int]]:
    """统计已解析 / 未解析 / 解析失败数量与可用屏幕 ID。"""
    parsed_count = 0
    unparsed_count = 0
    failed_count = 0
    usable_ids: list[int] = []
    for screen in screens:
        if screen.parse_status == "completed":
            parsed_count += 1
            if screen.ui_spec is not None:
                usable_ids.append(screen.id)
        elif screen.parse_status == "failed":
            failed_count += 1
        else:
            unparsed_count += 1
    return parsed_count, unparsed_count, failed_count, usable_ids


def _build_precheck_diagnostics(
    *,
    change_source: str,
    parsed_screen_count: int,
    requirement_files_selected: int,
    unparsed_screen_count: int,
    parse_failed_count: int,
    has_test_points: bool,
) -> tuple[list[str], list[str]]:
    """组装阻断原因与告警文案。"""
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if change_source in ("ui_flow", "mixed") and parsed_screen_count == 0:
        blocking_reasons.append("没有已解析的 UI 页面")
    if change_source in ("requirement", "mixed") and requirement_files_selected == 0:
        blocking_reasons.append("没有已选择的迭代需求文档")
    if unparsed_screen_count > 0:
        warnings.append(f"{unparsed_screen_count} 个页面未解析，已排除")
    if parse_failed_count > 0:
        warnings.append(f"{parse_failed_count} 个页面解析失败，已排除")
    if not has_test_points:
        warnings.append("未选择测试点，场景 4 仍可运行但建议选择以获得更精确的对齐结果")
    return blocking_reasons, warnings


@router.post("/scenario-4/precheck", response_model=ApiResponse)
async def precheck_scenario_4(
    body: Scenario4PrecheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """场景4运行前预检，验证历史用例、测试点、UI页面等前置条件是否满足。"""
    await asyncio.to_thread(verify_project_access, db, body.project_id, current_user)

    from app.models.project import ProjectFile
    from app.models.test_case import TestCase
    from app.models.test_point import TestPoint
    from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen

    blocking_reasons: list[str] = []
    warnings: list[str] = []

    history_stats = await _collect_history_case_stats(db, TestCase, body.project_id)

    test_points_total = await _count(
        db,
        select(func.count())
        .select_from(TestPoint)
        .where(
            TestPoint.project_id == body.project_id,
        ),
    )
    test_points_selected = await _verify_selected_test_points(db, TestPoint, body.project_id, body.test_point_ids)

    requirement_files_selected = await _verify_selected_requirement_files(
        db, ProjectFile, body.project_id, body.requirement_file_ids
    )

    screen_ids_to_check = await _resolve_screen_ids(db, body, UIPrototypeProject, UIPrototypeScreen)
    await _verify_screen_ownership(db, UIPrototypeScreen, screen_ids_to_check, body.ui_project_id)

    selected_screen_count = len(screen_ids_to_check) if screen_ids_to_check else 0
    parsed_screen_count = 0
    unparsed_screen_count = 0
    parse_failed_count = 0
    usable_screen_ids: list[int] = []

    if screen_ids_to_check:
        screens_result = await asyncio.to_thread(
            db.execute,
            select(UIPrototypeScreen).where(
                UIPrototypeScreen.id.in_(screen_ids_to_check),
            ),
        )
        parsed_screen_count, unparsed_screen_count, parse_failed_count, usable_screen_ids = _summarize_screens(
            screens_result.scalars().all()
        )

    if history_stats["included"] == 0:
        blocking_reasons.append("项目下没有可扫描的历史用例（已排除 archived 和已删除用例）")
    change_source = body.change_source or ("requirement" if requirement_files_selected > 0 else "ui_flow")
    recommended_pipeline_scenario = 4 if requirement_files_selected > 0 else 5

    extra_blocking, warnings = _build_precheck_diagnostics(
        change_source=change_source,
        parsed_screen_count=parsed_screen_count,
        requirement_files_selected=requirement_files_selected,
        unparsed_screen_count=unparsed_screen_count,
        parse_failed_count=parse_failed_count,
        has_test_points=bool(body.test_point_ids),
    )
    blocking_reasons.extend(extra_blocking)

    can_run = len(blocking_reasons) == 0

    return create_response(
        data={
            "project_id": body.project_id,
            "history_cases": {
                "total": history_stats["total"],
                "included": history_stats["included"],
                "active": history_stats["active"],
                "draft": history_stats["draft"],
                "pending_review": history_stats["pending_review"],
                "archived": history_stats["archived"],
                "deleted": history_stats["deleted"],
            },
            "test_points": {
                "total": test_points_total,
                "selected": test_points_selected,
            },
            "requirements": {
                "selected": requirement_files_selected,
            },
            "ui": {
                "selected_screen_count": selected_screen_count,
                "parsed_screen_count": parsed_screen_count,
                "unparsed_screen_count": unparsed_screen_count,
                "parse_failed_count": parse_failed_count,
                "usable_screen_ids": usable_screen_ids,
            },
            "can_run": can_run,
            "change_source": change_source,
            "recommended_pipeline_scenario": recommended_pipeline_scenario,
            "context_quality": {
                "has_history_cases": history_stats["included"] > 0,
                "has_requirement": requirement_files_selected > 0,
                "has_test_points": test_points_selected > 0 or test_points_total > 0,
                "has_ui_flow": parsed_screen_count >= 2,
            },
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
        }
    )
