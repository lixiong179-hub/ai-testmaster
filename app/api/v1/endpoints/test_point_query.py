"""
测试点查询端点模块

本模块定义测试点的查询API端点，包括列表查询、详情获取和统计信息。

路由前缀: /testPoint（由父模块test_point.py注册）
标签: 测试点管理

端点概览:
    - GET  /list                  - 获取测试点列表（分页）
    - GET  /{test_point_id}       - 获取测试点详情
    - GET  /{test_point_id}/stats - 获取测试点统计信息

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 列表查询支持按项目、需求文件、状态筛选
    - 统计信息包含关联用例数量和覆盖率
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.test_point import (
    TestPointAnalyzeRequest,
    TestPointExtractRequest,
    TestPointResponse,
    TestPointUpdate
)
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.crud.test_point import (
    get_test_points_by_project_and_user,
    get_test_points_count,
    batch_create_test_points
)
from app.services.ai_analysis_service import aio_analysis_service, extract_test_points_from_content
from app.services.file_content_extractor import FileContentExtractor
from fastapi.responses import StreamingResponse
import json
from loguru import logger
from app.models.project import Project, ProjectFile

router = APIRouter()


@router.post("/analyze")
async def analyze_project(
    request: TestPointAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        async def generate_progress() -> Any:
            async for progress in aio_analysis_service.analyze_project(
                db=db,
                project_id=request.project_id,
                user_id=current_user.id
            ):
                yield f"data: {json.dumps(progress)}\n\n"
        return StreamingResponse(
            generate_progress(),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"分析项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分析项目失败: {str(e)}"
        )


@router.get("/list/{project_id}")
async def get_test_points(
    project_id: int,
    module: Optional[str] = Query(None, description="模块名称"),
    priority: Optional[int] = Query(None, ge=1, le=3, description="优先级"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        skip = (page - 1) * page_size
        test_points = get_test_points_by_project_and_user(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            module=module,
            priority=priority,
            skip=skip,
            limit=page_size
        )
        total = get_test_points_count(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            module=module,
            priority=priority
        )
        items = []
        for point in test_points:
            items.append(TestPointResponse(
                id=point.id,
                project_id=point.project_id,
                module=point.module,
                function=point.function,
                point=point.point,
                priority=point.priority,
                ai_prompt=point.ai_prompt,
                create_time=point.create_time
            ))
        return {
            "code": 200,
            "message": "获取成功",
            "data": {
                "total": total,
                "items": items,
                "page": page,
                "page_size": page_size
            }
        }
    except Exception as e:
        logger.error(f"获取测试点列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测试点列表失败: {str(e)}"
        )


@router.get("/detail/{test_point_id}", response_model=TestPointResponse)
async def get_test_point_detail(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.models.project import Project
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
        from app.crud.test_point import get_test_point_by_id
        test_point = get_test_point_by_id(db, test_point_id, project_id)
        if not test_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试点不存在"
            )
        return TestPointResponse(
            id=test_point.id,
            project_id=test_point.project_id,
            module=test_point.module,
            function=test_point.function,
            point=test_point.point,
            priority=test_point.priority,
            ai_prompt=test_point.ai_prompt,
            create_time=test_point.create_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测试点详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测试点详情失败: {str(e)}"
        )


@router.post("/extract")
async def extract_test_points(
    request: TestPointExtractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not request.file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供 file_id",
            )
        file = db.query(ProjectFile).filter(
            ProjectFile.id == request.file_id,
            ProjectFile.is_active == True
        ).first()
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在",
            )
        project = db.query(Project).filter(
            Project.id == file.project_id,
            Project.user_id == current_user.id,
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
        extractor = FileContentExtractor(db)
        result = await extractor.extract_file_content(file, force_refresh=False)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "无法读取文件内容"),
            )
        file_content = result.get("content", "")
        logger.info(f"文件内容提取成功, 长度: {len(file_content)}")
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容为空或无法提取",
            )
        test_points = await extract_test_points_from_content(
            content=file_content,
            project_id=file.project_id,
            user_id=current_user.id,
        )
        logger.info(f"AI提取完成, 测试点数量: {len(test_points)}")
        return {
            "code": 200,
            "message": "测试点提取成功",
            "data": {
                "items": test_points,
                "total": len(test_points),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提取测试点失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提取测试点失败: {str(e)}",
        )
