"""XMind 测试点导入端点模块。

本模块定义 XMind 文件导入 API 端点，支持预览和导入两种模式。

路由前缀: /test-point（由父模块 test_point.py 注册）
标签: 测试点管理

端点概览:
    - POST /import-xmind - 导入 XMind 测试点文件

权限要求: 需要 Bearer 令牌认证

业务说明:
    - 预览模式（preview=true）：仅解析文件返回结果，不写入数据库
    - 导入模式（preview=false）：解析文件并批量写入数据库
    - 文件大小限制：≤10MB
    - 支持格式：.xmind 标准格式（ZIP + XML）
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.test_point import (
    TestPointXmindPreviewItem,
    TestPointXmindPreviewResponse,
    TestPointXmindImportResponse,
)
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_point_mutate import check_project_permission
from app.services.xmind_parser import XmindParser, XmindParseError
from app.services.xmind_case_parser import XmindCaseParser
from app.services.xmind_ai_parser import XmindAIParser
from app.services.xmind_import_service import (
    validate_file,
    save_upload_file,
    filter_valid_points,
    collect_skip_reasons,
    should_treat_as_case_tree,
    handle_case_style_import,
    handle_ai_enhanced_import,
)
from app.utils.ai_client_core import AITimeoutError
from app.crud.test_point import batch_create_test_points
from loguru import logger

router = APIRouter()


@router.post("/import-xmind")
async def import_xmind(
    file: UploadFile = File(..., description="XMind 文件"),
    project_id: int = Form(..., description="项目ID"),
    preview: bool = Form(False, description="是否预览模式"),
    ai_enhance: bool = Form(False, description="是否AI增强模式"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入 XMind 测试点文件。

    支持两种模式:
        - 预览模式（preview=true）：解析文件并返回预览数据，不写入数据库
        - 导入模式（preview=false）：解析文件并批量写入数据库
        - AI增强模式（ai_enhance=true）：使用LLM将路径转换为结构化测试用例

    Args:
        file: 上传的 .xmind 文件。
        project_id: 目标项目 ID。
        preview: 是否预览模式。
        ai_enhance: 是否启用AI增强解析。
        db: 数据库会话。
        current_user: 当前登录用户。

    Returns:
        预览模式返回 TestPointXmindPreviewResponse，
        导入模式返回 TestPointXmindImportResponse。
    """
    check_project_permission(db, project_id, current_user.id)

    validate_file(file)

    tmp_path = await save_upload_file(file)
    try:
        parser = XmindParser()
        parsed_points = parser.parse(tmp_path)
        case_parser = XmindCaseParser()
        parsed_cases = case_parser.parse(tmp_path)

        ai_timeout_occurred = False
        if ai_enhance:
            paths = parser.extract_paths(tmp_path)
            if paths:
                try:
                    ai_parser = XmindAIParser()
                    ai_cases = ai_parser.parse_paths(paths)
                    if ai_cases:
                        return handle_ai_enhanced_import(
                            db=db,
                            project_id=project_id,
                            current_username=current_user.username,
                            ai_cases=ai_cases,
                            preview=preview,
                        )
                except Exception as e:
                    if isinstance(e, AITimeoutError):
                        ai_timeout_occurred = True
                        logger.warning(
                            f"AI增强解析超时，降级到普通解析: {e}"
                        )
                    else:
                        logger.warning(
                            f"AI增强解析失败，降级到普通解析: {e}"
                        )

        if should_treat_as_case_tree(parsed_cases):
            return handle_case_style_import(
                db=db,
                project_id=project_id,
                current_username=current_user.username,
                parsed_cases=parsed_cases,
                preview=preview,
            )

        if not parsed_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="XMind 文件中未找到有效的测试点数据",
            )

        valid_points = filter_valid_points(parsed_points)
        skipped_count = len(parsed_points) - len(valid_points)
        skipped_reasons = collect_skip_reasons(parsed_points)

        if preview:
            return TestPointXmindPreviewResponse(
                preview_mode="test_points",
                total=len(valid_points),
                items=[
                    TestPointXmindPreviewItem(
                        module=p["module"],
                        function=p["function"],
                        point=p["point"],
                        priority=p["priority"],
                    )
                    for p in valid_points
                ],
                case_total=0,
                case_items=[],
                skipped_count=skipped_count,
                skipped_reasons=skipped_reasons,
                ai_timeout=ai_timeout_occurred,
            )

        saved = batch_create_test_points(
            db=db,
            project_id=project_id,
            test_points_data=valid_points,
            created_by=current_user.username,
        )
        logger.info(
            f"XMind 导入完成: project_id={project_id}, "
            f"saved={len(saved)}, skipped={skipped_count}"
        )
        return TestPointXmindImportResponse(
            saved_count=len(saved),
            saved_case_count=0,
            total_parsed=len(parsed_points),
            skipped_count=skipped_count,
            skipped_reasons=skipped_reasons,
            ai_timeout=ai_timeout_occurred,
        )
    except XmindParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
