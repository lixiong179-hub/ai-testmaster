"""Pipeline 场景4预检端点

提供场景4运行前的预检功能，检查历史用例、测试点、UI页面等前置条件。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_schemas import Scenario4PrecheckRequest
from app.api.v1.endpoints.pipeline_deps import verify_project_access
from app.core.exception import create_response

router = APIRouter(tags=["Pipeline管理"])


@router.post("/scenario-4/precheck", response_model=dict)
async def precheck_scenario_4(
    body: Scenario4PrecheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """场景4运行前预检，验证历史用例、测试点、UI页面等前置条件是否满足。"""
    verify_project_access(db, body.project_id, current_user)

    from app.models.test_case import TestCase
    from app.models.test_point import TestPoint
    from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen

    blocking_reasons: list[str] = []
    warnings: list[str] = []

    history_cases_total = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == body.project_id,
            TestCase.is_deleted.is_(False),
        )
        .count()
    )
    history_cases_included = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == body.project_id,
            TestCase.lifecycle_status != "archived",
            TestCase.is_deleted.is_(False),
        )
        .count()
    )
    history_cases_active = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == body.project_id,
            TestCase.lifecycle_status == "active",
            TestCase.is_deleted.is_(False),
        )
        .count()
    )
    history_cases_draft = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == body.project_id,
            TestCase.lifecycle_status == "draft",
            TestCase.is_deleted.is_(False),
        )
        .count()
    )
    history_cases_pending_review = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == body.project_id,
            TestCase.lifecycle_status == "pending_review",
            TestCase.is_deleted.is_(False),
        )
        .count()
    )
    history_cases_archived = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == body.project_id,
            TestCase.lifecycle_status == "archived",
            TestCase.is_deleted.is_(False),
        )
        .count()
    )
    history_cases_deleted = (
        db.query(TestCase)
        .filter(TestCase.project_id == body.project_id, TestCase.is_deleted == True)
        .count()
    )

    test_points_total = (
        db.query(TestPoint)
        .filter(TestPoint.project_id == body.project_id)
        .count()
    )
    test_points_selected = 0
    if body.test_point_ids:
        owned_count = (
            db.query(TestPoint)
            .filter(
                TestPoint.id.in_(body.test_point_ids),
                TestPoint.project_id == body.project_id,
            )
            .count()
        )
        if owned_count != len(body.test_point_ids):
            raise HTTPException(
                status_code=403,
                detail="部分测试点不属于当前项目",
            )
        test_points_selected = owned_count

    screen_ids_to_check = body.screen_ids
    if body.ui_project_id and not body.screen_ids:
        if body.ui_project_id:
            prototype_project = (
                db.query(UIPrototypeProject)
                .filter(
                    UIPrototypeProject.id == body.ui_project_id,
                    UIPrototypeProject.project_id == body.project_id,
                )
                .first()
            )
            if not prototype_project:
                raise HTTPException(
                    status_code=403,
                    detail="UI原型项目不属于当前项目",
                )
            screens = (
                db.query(UIPrototypeScreen)
                .filter(
                    UIPrototypeScreen.prototype_project_id == body.ui_project_id,
                )
                .all()
            )
            screen_ids_to_check = [s.id for s in screens]
        else:
            screen_ids_to_check = []

    if screen_ids_to_check and body.ui_project_id:
        owner_check = (
                db.query(UIPrototypeScreen)
                .filter(
                    UIPrototypeScreen.id.in_(screen_ids_to_check),
                    UIPrototypeScreen.prototype_project_id == body.ui_project_id,
                )
                .all()
            )
        valid_ids = {s.id for s in owner_check}
        invalid_ids = set(screen_ids_to_check) - valid_ids
        if invalid_ids:
            raise HTTPException(
                status_code=403,
                detail=f"屏幕 {invalid_ids} 不属于 UI 原型项目 {body.ui_project_id}",
            )

    selected_screen_count = len(screen_ids_to_check) if screen_ids_to_check else 0
    parsed_screen_count = 0
    unparsed_screen_count = 0
    parse_failed_count = 0
    usable_screen_ids: list[int] = []

    if screen_ids_to_check:
        for sid in screen_ids_to_check:
            screen = (
                db.query(UIPrototypeScreen)
                .filter(UIPrototypeScreen.id == sid)
                .first()
            )
            if not screen:
                continue
            if screen.parse_status == "completed":
                parsed_screen_count += 1
                if screen.ui_spec is not None:
                    usable_screen_ids.append(sid)
            elif screen.parse_status in ("failed",):
                parse_failed_count += 1
            else:
                unparsed_screen_count += 1

    if history_cases_included == 0:
        blocking_reasons.append("项目下没有可扫描的历史用例（已排除 archived 和已删除用例）")
    if parsed_screen_count == 0:
        blocking_reasons.append("没有已解析的 UI 页面")
    if unparsed_screen_count > 0:
        warnings.append(f"{unparsed_screen_count} 个页面未解析，已排除")
    if parse_failed_count > 0:
        warnings.append(f"{parse_failed_count} 个页面解析失败，已排除")
    if not body.test_point_ids:
        warnings.append("未选择测试点，场景 4 仍可运行但建议选择以获得更精确的对齐结果")

    can_run = len(blocking_reasons) == 0

    return create_response(data={
        "project_id": body.project_id,
        "history_cases": {
            "total": history_cases_total,
            "included": history_cases_included,
            "active": history_cases_active,
            "draft": history_cases_draft,
            "pending_review": history_cases_pending_review,
            "archived": history_cases_archived,
            "deleted": history_cases_deleted,
        },
        "test_points": {
            "total": test_points_total,
            "selected": test_points_selected,
        },
        "ui": {
            "selected_screen_count": selected_screen_count,
            "parsed_screen_count": parsed_screen_count,
            "unparsed_screen_count": unparsed_screen_count,
            "parse_failed_count": parse_failed_count,
            "usable_screen_ids": usable_screen_ids,
        },
        "can_run": can_run,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
    })
