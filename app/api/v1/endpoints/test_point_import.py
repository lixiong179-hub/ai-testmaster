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
from app.core.config import settings
from app.utils.ai_client_core import (
    AIAuthenticationError,
    AIPermissionError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
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

    logger.info(f"XMind导入请求: project_id={project_id}, preview={preview}, ai_enhance={ai_enhance}")

    tmp_path = await save_upload_file(file)
    try:
        parser = XmindParser()
        if ai_enhance:
            all_paths = parser.extract_paths(tmp_path)
            if not all_paths:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AI增强模式失败：XMind文件未提取到有效路径，请检查文件内容后重试",
                )
            total_paths = len(all_paths)
            # 预览模式只采样前 N 条路径给 AI，加速预览体验
            if preview:
                sample_size = settings.XMIND_AI_PREVIEW_SAMPLE
                paths = all_paths[:sample_size]
                logger.info(f"AI预览采样: {len(paths)}/{total_paths} 条路径")
            else:
                paths = all_paths
            try:
                ai_parser = XmindAIParser()
                ai_cases = ai_parser.parse_paths(paths)
            except AITimeoutError as e:
                logger.error(f"AI增强解析超时: {e}")
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail="AI增强解析超时，请稍后重试或关闭AI增强模式使用普通导入",
                )
            except AIAuthenticationError as e:
                logger.error(f"AI增强解析认证失败: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="AI服务认证失败，请联系管理员检查 API Key 配置",
                )
            except AIRateLimitError as e:
                logger.warning(f"AI增强解析触发限流: {e}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="AI服务请求过于频繁，请稍后重试",
                )
            except AIPermissionError as e:
                logger.error(f"AI增强解析权限不足: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="AI服务权限不足，请联系管理员",
                )
            except AIServiceError as e:
                # 其他已知 AI 业务异常：暴露语义化 message，不暴露原始 exc
                logger.error(f"AI增强解析失败({e.error_code}): {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI增强解析失败：{e.message}，请稍后重试或关闭AI增强模式使用普通导入",
                )
            except Exception as e:
                # 未知异常仅写日志，给前端返回通用文案，避免泄漏内部细节
                logger.exception(f"AI增强解析发生未知错误: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="AI增强解析发生未知错误，请稍后重试或关闭AI增强模式使用普通导入",
                )
            if not ai_cases:
                logger.warning("AI增强解析返回空结果")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="AI增强解析返回空结果，请检查文件内容或关闭AI增强模式使用普通导入",
                )
            return handle_ai_enhanced_import(
                db=db,
                project_id=project_id,
                current_username=current_user.username,
                ai_cases=ai_cases,
                preview=preview,
                ai_timeout=False,
                total_paths=total_paths,
            )

        parsed_points = parser.parse(tmp_path)
        case_parser = XmindCaseParser()
        parsed_cases = case_parser.parse(tmp_path)

        if should_treat_as_case_tree(parsed_cases):
            return handle_case_style_import(
                db=db,
                project_id=project_id,
                current_username=current_user.username,
                parsed_cases=parsed_cases,
                preview=preview,
                ai_timeout=False,
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
                        function=p.get("function", ""),
                        point=p["point"],
                        priority=p["priority"],
                        precondition="",
                    )
                    for p in valid_points
                ],
                case_total=0,
                case_items=[],
                skipped_count=skipped_count,
                skipped_reasons=skipped_reasons,
                ai_timeout=False,
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
            ai_timeout=False,
        )
    except XmindParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
