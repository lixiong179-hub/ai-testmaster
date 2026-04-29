"""
AI批量生成测试用例端点模块

本模块定义AI批量生成测试用例的API端点，支持基于需求文件一次性生成多条测试用例。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /ai-batch-generate - AI批量生成测试用例

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 批量生成基于需求文件内容，调用AI模型解析需求后生成多条用例
    - 生成过程中逐条创建用例，部分失败不影响已生成的用例
    - 需配置DEEPSEEK_API_KEY环境变量
"""
from typing import Optional, List, Any
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


class BatchGenerateRequest(BaseModel):
    project_id: int
    test_point_ids: Optional[List[int]] = None
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    force_refresh: bool = False
    test_point_page: int = 1
    test_point_page_size: int = 100
    case_type: Optional[str] = None

    @field_validator('test_point_ids', 'requirement_file_ids', 'ui_file_ids', 'ui_screen_ids')
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator('test_point_ids', 'requirement_file_ids', 'ui_file_ids', 'ui_screen_ids')
    @classmethod
    def validate_list_size(cls, v: List[int] | None) -> List[int] | None:
        if v is not None and len(v) > 200:
            raise ValueError(f'列表长度不能超过200，当前: {len(v)}')
        return v

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('项目ID必须大于0')
        return v

    @field_validator('test_point_page')
    @classmethod
    def validate_page(cls, v: int) -> int:
        if v < 1:
            raise ValueError('页码必须大于等于1')
        return v

    @field_validator('test_point_page_size')
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        if v < 1 or v > 500:
            raise ValueError('每页数量必须在1-500之间')
        return v


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


@router.post("/ai-batch-generate")
async def ai_batch_generate_test_cases(
    request: BatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI批量生成测试用例

    基于需求文件内容，调用AI模型一次性生成多条测试用例。
    逐条创建用例记录，部分失败不影响已成功的记录。

    请求参数(BatchGenerateRequest):
        - project_id: 所属项目ID
        - requirement_file_ids: 需求文件ID列表
        - description: 需求描述（可选，补充说明）

    响应格式:
        - total: 生成总数
        - success_count: 成功数量
        - fail_count: 失败数量
        - cases: 生成的用例列表

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 404: 项目或需求文件不存在
        HTTPException 500: AI服务异常
    """
    raise NotImplementedError("批量生成功能暂未实现，请使用 /batch-generate/stream 流式端点")


@router.post("/batch-generate/stream")
async def batch_generate_test_cases_stream(
    request: BatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    流式批量生成测试用例

    以SSE（Server-Sent Events）方式流式返回AI批量生成的测试用例。
    每生成一条用例即推送一条事件，前端可实时展示生成进度。

    请求参数(BatchGenerateRequest):
        - project_id: 所属项目ID
        - test_point_id: 测试点ID

    响应格式: SSE事件流，每条事件包含一条生成的用例数据

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 403: 无权限操作此项目
    """
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

    async def generate_progress() -> Any:
        service = TestCaseGenerationService(db)
        try:
            async for progress in service.generate_test_cases_batch(
                project_id=request.project_id,
                user_id=current_user.id,
                test_point_ids=request.test_point_ids,
                requirement_file_ids=request.requirement_file_ids,
                ui_file_ids=request.ui_file_ids,
                ui_screen_ids=request.ui_screen_ids,
                test_point_page=request.test_point_page,
                test_point_page_size=request.test_point_page_size,
                case_type=request.case_type
            ):
                yield f"data: {json.dumps(progress)}\n\n"
        except Exception as e:
            logger.error(f"批量生成测试用例失败: {e}")
            error_progress = {"progress": 100, "message": f"生成失败: {str(e)}", "status": "error"}
            yield f"data: {json.dumps(error_progress)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream"
    )


@router.post("/generate-context", response_model=dict)
async def get_generation_context(
    request: GenerateContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
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
            detail=f"生成失败: {str(e)}"
        )
