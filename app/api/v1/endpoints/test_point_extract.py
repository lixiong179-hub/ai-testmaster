"""测试点提取端点模块

本模块定义测试点的数据提取API端点。
路由前缀: /test-point（由父模块test_point.py注册）

端点概览:
    - POST /extract          - 从需求文件AI提取测试点
    - POST /extract-from-ui  - 从UI原型屏幕提取测试点

XMind导入端点已迁移至 test_point_import.py。
所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeScreen
from app.models.user import User
from app.schemas.test_point import (
    TestPointExtractFromUiRequest,
    TestPointExtractRequest,
)
from app.services.ai_analysis_service import (
    extract_test_points_from_content,
    extract_test_points_from_ui_specs,
)
from app.services.file_content_extractor import FileContentExtractor

router = APIRouter()


# ── 文件提取端点 ──────────────────────────────────────────


@router.post("/extract")
async def extract_test_points(
    request: TestPointExtractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从需求文件内容中AI提取测试点。"""
    try:
        if not request.file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="请提供 file_id"
            )
        file = db.query(ProjectFile).filter(
            ProjectFile.id == request.file_id, ProjectFile.is_active == True  # noqa: E712
        ).first()
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在"
            )
        project = db.query(Project).filter(
            Project.id == file.project_id, Project.user_id == current_user.id,
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
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
                status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容为空或无法提取"
            )
        test_points = await extract_test_points_from_content(
            content=file_content, project_id=file.project_id, user_id=current_user.id,
        )
        logger.info(f"AI提取完成, 测试点数量: {len(test_points)}")
        return {
            "code": 200, "message": "测试点提取成功",
            "data": {"items": test_points, "total": len(test_points)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提取测试点失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="提取测试点失败"
        )


# ── UI原型提取端点 ────────────────────────────────────────


@router.post("/extract-from-ui")
async def extract_test_points_from_ui(
    request: TestPointExtractFromUiRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从UI原型屏幕提取测试点（三维策略：页面 x 可交互元素 x 流程边）。"""
    try:
        project = db.query(Project).filter(
            Project.id == request.project_id, Project.user_id == current_user.id,
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )
        screen_count = (
            db.query(UIPrototypeScreen)
            .filter(
                UIPrototypeScreen.id.in_(request.ui_screen_ids),
                UIPrototypeScreen.project_id == request.project_id,
            )
            .count()
        )
        if screen_count != len(request.ui_screen_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="部分屏幕ID不存在或不属于当前项目",
            )
        pending_screens = (
            db.query(UIPrototypeScreen)
            .filter(
                UIPrototypeScreen.id.in_(request.ui_screen_ids),
                UIPrototypeScreen.parse_status != "completed",
            )
            .all()
        )
        if pending_screens:
            pending_names = [s.screen_name for s in pending_screens]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"以下屏幕尚未完成AI解析: {', '.join(pending_names)}，请先解析后再提取测试点",
            )
        test_points = await extract_test_points_from_ui_specs(
            screen_ids=request.ui_screen_ids, project_id=request.project_id, db=db,
        )
        logger.info(f"从UI原型提取测试点完成, 数量: {len(test_points)}")
        return {
            "code": 200, "message": "从UI原型提取测试点成功",
            "data": {"items": test_points, "total": len(test_points)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从UI原型提取测试点失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="从UI原型提取测试点失败",
        )
