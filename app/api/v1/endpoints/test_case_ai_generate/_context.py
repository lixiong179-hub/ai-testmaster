from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_case_ai_schemas import (
    BatchGenerateRequest,
    GenerateContextRequest,
    SingleGenerateRequest,
)
from app.core.exception import create_response
from app.db.database import get_db
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.user import User

router = APIRouter()


@router.post("/generate-context", response_model=dict)
async def get_generation_context(
    request: GenerateContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    project = db.query(Project).filter(
        Project.id == request.project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    context = await service.get_context_for_generation(
        project_id=request.project_id, user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=request.test_point_ids,
        force_refresh=request.force_refresh,
        test_point_page=request.test_point_page,
        test_point_page_size=request.test_point_page_size,
    )
    test_points_count = len(context.get("test_points", []))
    if test_points_count == 0:
        logger.warning(f"项目 {request.project_id} 没有找到测试点")

    history_cases = []
    if request.history_case_ids is None:
        cases = db.query(TestCase).filter(
            TestCase.project_id == request.project_id,
            TestCase.is_deleted.is_(False),
            TestCase.lifecycle_status != 'archived',
        ).order_by(TestCase.id).all()
    elif len(request.history_case_ids) > 0:
        cases = db.query(TestCase).filter(
            TestCase.id.in_(request.history_case_ids),
            TestCase.project_id == request.project_id,
            TestCase.is_deleted.is_(False),
            TestCase.lifecycle_status != 'archived',
        ).all()
    else:
        cases = []

    for c in cases:
        steps = c.steps_json or []
        steps_summary = ""
        if isinstance(steps, list) and steps:
            actions = [s.get("action", s.get("description", "")) for s in steps[:3]]
            steps_summary = " → ".join(a for a in actions if a)
        history_cases.append({
            "id": c.id,
            "case_no": c.case_no,
            "module": c.module or "",
            "title": c.title,
            "summary": (c.summary or steps_summary or "")[:150],
            "expected_result": (c.expected_result or "")[:100],
        })

    project_config = {
        "project_name": project.name,
        "project_type": project.project_type or "web",
    }

    has_explicit_history = request.history_case_ids is not None and len(request.history_case_ids) > 0
    has_explicit_test_points = request.test_point_ids and len(request.test_point_ids) > 0
    if has_explicit_history and not has_explicit_test_points:
        context["test_points"] = []
        test_points_count = 0
        logger.info(f"项目 {request.project_id}: 历史用例查漏补缺模式，跳过测试点自动加载")

    return create_response(data={
        "requirement_content": context.get("requirement_content", ""),
        "requirement_length": len(context.get("requirement_content", "")),
        "ui_descriptions": context.get("ui_descriptions", []),
        "ui_specs": context.get("ui_specs", []),
        "ui_count": len(context.get("ui_descriptions", [])),
        "test_points": context.get("test_points", []),
        "test_point_count": test_points_count,
        "files_used": context.get("files_used", []),
        "warnings": context.get("warnings", []),
        "pagination": context.get("pagination", None),
        "project_config": project_config,
        "history_cases": history_cases,
        "message": f"获取成功：{test_points_count}个测试点",
    })


@router.post("/generate-single")
async def generate_single_test_case(
    request: SingleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    project = db.query(Project).filter(
        Project.id == request.project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    context = await service.get_context_for_generation(
        project_id=request.project_id, user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=[request.test_point_id],
    )
    test_points = context.get("test_points", [])
    if not test_points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"没有找到ID为{request.test_point_id}的测试点",
        )
    test_point = test_points[0]
    try:
        generated_case = await service.generate_test_case_for_point(
            context=context, test_point=test_point,
            project_id=request.project_id, case_type=request.case_type,
        )
        saved_case = await service._save_test_case(
            project_id=request.project_id,
            generated_case=generated_case, test_point=test_point,
        )
        steps_data = [
            {
                "step": step.get("step", "步骤"),
                "action": step.get("action", "执行"),
                "param": step.get("param", ""),
            }
            for step in generated_case.get("steps", [])
        ]
        return create_response(data={
            "id": saved_case.id, "project_id": saved_case.project_id,
            "case_no": saved_case.case_no, "module": saved_case.module,
            "title": saved_case.title, "precondition": saved_case.precondition,
            "test_data": generated_case.get("test_data", {}),
            "steps": steps_data, "expected_result": saved_case.expected_result,
            "priority": saved_case.priority, "case_type": saved_case.case_type,
            "generate_status": saved_case.generate_status,
            "test_point_id": test_point.get("id"),
            "message": "测试用例生成成功",
        })
    except Exception as e:
        db.rollback()
        logger.error(f"生成测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成失败"
        )


@router.post("/ai-batch-generate")
async def ai_batch_generate_test_cases(
    request: BatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="批量生成功能即将上线，请使用 /batch-generate/stream 流式端点或 /generate-single 逐条生成",
    )
