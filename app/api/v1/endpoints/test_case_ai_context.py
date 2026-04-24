"""
AI单条/上下文生成测试用例端点模块

本模块定义AI生成测试用例的上下文获取和单条生成API端点。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /generate-context - 获取AI生成上下文信息
    - POST /generate-single  - 基于单个测试点生成测试用例

权限要求: 所有端点需要Bearer令牌认证
"""
from typing import Optional, List, Any
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


class GenerateContextRequest(BaseModel):
    project_id: int
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    test_point_ids: Optional[List[int]] = None
    force_refresh: bool = False
    test_point_page: int = 1
    test_point_page_size: int = 100

    @field_validator('requirement_file_ids', 'ui_file_ids', 'ui_screen_ids', 'test_point_ids')
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('项目ID必须大于0')
        return v


class SingleGenerateRequest(BaseModel):
    project_id: int
    test_point_id: int
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    force_refresh: bool = False
    case_type: Optional[str] = None

    @field_validator('requirement_file_ids', 'ui_file_ids', 'ui_screen_ids')
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('项目ID必须大于0')
        return v

    @field_validator('test_point_id')
    @classmethod
    def validate_test_point_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('测试点ID必须大于0')
        return v


@router.post("/generate-context", response_model=dict)
async def get_generation_context(
    request: GenerateContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """获取AI生成测试用例的上下文信息"""
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    from app.services.test_case_generation_service import TestCaseGenerationService

    service = TestCaseGenerationService(db)
    context = await service.get_context_for_generation(
        project_id=request.project_id,
        user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=request.test_point_ids,
        force_refresh=request.force_refresh,
        test_point_page=request.test_point_page,
        test_point_page_size=request.test_point_page_size
    )

    test_points_count = len(context.get("test_points", []))
    if test_points_count == 0:
        logger.warning(f"项目 {request.project_id} 没有找到测试点")

    project_config = {
        "project_name": project.name,
        "project_type": project.project_type or "web"
    }

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
        "message": f"获取成功：{test_points_count}个测试点"
    })


@router.post("/generate-single")
async def generate_single_test_case(
    request: SingleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """基于单个测试点AI生成测试用例"""
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    from app.services.test_case_generation_service import TestCaseGenerationService

    service = TestCaseGenerationService(db)

    context = await service.get_context_for_generation(
        project_id=request.project_id,
        user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=[request.test_point_id]
    )

    test_points = context.get("test_points", [])
    if not test_points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"没有找到ID为{request.test_point_id}的测试点"
        )

    test_point = test_points[0]

    try:
        generated_case = await service.generate_test_case_for_point(
            context=context,
            test_point=test_point,
            project_id=request.project_id,
            case_type=request.case_type
        )

        saved_case = await service._save_test_case(
            project_id=request.project_id,
            generated_case=generated_case,
            test_point=test_point
        )

        steps_data = []
        for step in generated_case.get("steps", []):
            steps_data.append({
                "step": step.get("step", "步骤"),
                "action": step.get("action", "执行"),
                "param": step.get("param", "")
            })

        return create_response(data={
            "id": saved_case.id,
            "project_id": saved_case.project_id,
            "case_no": saved_case.case_no,
            "module": saved_case.module,
            "title": saved_case.title,
            "precondition": saved_case.precondition,
            "test_data": generated_case.get("test_data", {}),
            "steps": steps_data,
            "expected_result": saved_case.expected_result,
            "priority": saved_case.priority,
            "case_type": saved_case.case_type,
            "generate_status": saved_case.generate_status,
            "test_point_id": test_point.get("id"),
            "message": "测试用例生成成功"
        })

    except Exception as e:
        db.rollback()
        logger.error(f"生成测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成失败"
        )
