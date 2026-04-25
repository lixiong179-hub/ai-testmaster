"""测试点提取与导入端点模块

本模块定义测试点的数据提取和导入API端点。
路由前缀: /test-point（由父模块test_point.py注册）

端点概览:
    - POST /extract          - 从需求文件AI提取测试点
    - POST /extract-from-ui  - 从UI原型屏幕提取测试点
    - POST /import-xmind     - 导入XMind测试点文件

所有端点均需要Bearer令牌认证。
"""
import os
import tempfile
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.crud.test_case_mutate import batch_create_test_cases
from app.crud.test_point import batch_create_test_points
from app.db.database import get_db
from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeScreen
from app.models.user import User
from app.schemas.test_point import (
    TestPointExtractFromUiRequest,
    TestPointExtractRequest,
    TestPointXmindImportResponse,
    TestPointXmindPreviewCaseItem,
    TestPointXmindPreviewCaseStep,
    TestPointXmindPreviewItem,
    TestPointXmindPreviewResponse,
)
from app.services.ai_analysis_service import (
    extract_test_points_from_content,
    extract_test_points_from_ui_specs,
)
from app.services.file_content_extractor import FileContentExtractor
from app.services.xmind_case_parser import XmindCaseParser
from app.services.xmind_parser import XmindParseError, XmindParser

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024


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


# ── XMind导入端点 ────────────────────────────────────────


@router.post("/import-xmind")
async def import_xmind(
    file: UploadFile = File(..., description="XMind 文件"),
    project_id: int = Form(..., description="项目ID"),
    preview: bool = Form(False, description="是否预览模式"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入XMind测试点文件，支持预览和导入两种模式。"""
    _check_project_access(db, project_id, current_user.id)
    _validate_file(file)
    tmp_path = await _save_upload_file(file)
    try:
        parser = XmindParser()
        parsed_points = parser.parse(tmp_path)
        case_parser = XmindCaseParser()
        parsed_cases = case_parser.parse(tmp_path)

        if _should_treat_as_case_tree(parsed_cases):
            return _handle_case_style_import(
                db=db, project_id=project_id,
                current_username=current_user.username,
                parsed_cases=parsed_cases, preview=preview,
            )
        if not parsed_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="XMind 文件中未找到有效的测试点数据",
            )
        valid_points = _filter_valid_points(parsed_points)
        skipped_count = len(parsed_points) - len(valid_points)
        skipped_reasons = _collect_skip_reasons(parsed_points)

        if preview:
            return TestPointXmindPreviewResponse(
                preview_mode="test_points", total=len(valid_points),
                items=[
                    TestPointXmindPreviewItem(
                        module=p["module"], function=p["function"],
                        point=p["point"], priority=p["priority"],
                    ) for p in valid_points
                ],
                case_total=0, case_items=[],
                skipped_count=skipped_count, skipped_reasons=skipped_reasons,
            )
        saved = batch_create_test_points(
            db=db, project_id=project_id,
            test_points_data=valid_points, created_by=current_user.username,
        )
        logger.info(
            f"XMind 导入完成: project_id={project_id}, "
            f"saved={len(saved)}, skipped={skipped_count}"
        )
        return TestPointXmindImportResponse(
            saved_count=len(saved), saved_case_count=0,
            total_parsed=len(parsed_points),
            skipped_count=skipped_count, skipped_reasons=skipped_reasons,
        )
    except XmindParseError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── XMind导入辅助函数 ────────────────────────────────────


def _check_project_access(db: Session, project_id: int, user_id: int) -> None:
    """校验用户项目权限，无权限时抛出403。"""
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )


def _validate_file(file: UploadFile) -> None:
    """校验上传文件格式。"""
    if not file.filename or not file.filename.endswith(".xmind"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的 XMind 文件格式，请上传 .xmind 文件",
        )


async def _save_upload_file(file: UploadFile) -> str:
    """将上传文件保存到临时路径，文件过大时抛出400。"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xmind")
    try:
        total_size = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="文件大小超过 10MB 限制",
                )
            tmp.write(chunk)
        tmp.close()
        return tmp.name
    except Exception:
        tmp.close()
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise


def _filter_valid_points(points: List[dict]) -> List[dict]:
    """过滤有效测试点（module和point必须存在）。"""
    return [p for p in points if p.get("module") and p.get("point")]


def _collect_skip_reasons(points: List[dict]) -> List[str]:
    """收集被跳过节点的原因，最多返回20条。"""
    reasons = []
    for p in points:
        if not p.get("module"):
            reasons.append("模块名称为空")
        elif not p.get("point"):
            reasons.append("测试点名称为空")
    return reasons[:20]


def _should_treat_as_case_tree(parsed_cases: list) -> bool:
    """判断XMind是否更接近场景/用例树。"""
    if not parsed_cases:
        return False
    case_like_items = [
        case for case in parsed_cases
        if case.get("source_depth", 0) >= 4
        and case.get("action_count", 0) >= 1
        and case.get("expected_count", 0) >= 1
        and (
            case.get("condition_count", 0) >= 1
            or case.get("ignored_count", 0) >= 1
            or case.get("action_count", 0) >= 2
        )
    ]
    if len(parsed_cases) == 1:
        return len(case_like_items) == 1
    return len(case_like_items) >= 2 and (
        len(case_like_items) / len(parsed_cases)
    ) >= 0.4


def _handle_case_style_import(
    db: Session, project_id: int, current_username: str,
    parsed_cases: list, preview: bool,
):
    """处理更接近测试用例脑图的XMind导入。"""
    point_payloads = [
        {
            "module": c["module"], "function": c["function"],
            "point": c["point"], "priority": c["priority"],
        }
        for c in parsed_cases
    ]

    if preview:
        return TestPointXmindPreviewResponse(
            preview_mode="test_cases", total=len(point_payloads),
            items=[
                TestPointXmindPreviewItem(
                    module=item["module"], function=item["function"],
                    point=item["point"], priority=item["priority"],
                ) for item in point_payloads
            ],
            case_total=len(parsed_cases),
            case_items=[
                TestPointXmindPreviewCaseItem(
                    module=case["module"], function=case["function"],
                    title=case["title"],
                    precondition=case.get("precondition", ""),
                    expected_result=case.get("expected_result", ""),
                    priority=case["priority"],
                    step_count=len(case.get("steps", [])),
                    steps=[
                        TestPointXmindPreviewCaseStep(
                            step_number=index,
                            action=step.get("action", ""),
                            expected_result=step.get("expected_result", ""),
                        )
                        for index, step in enumerate(case.get("steps", []), start=1)
                    ],
                ) for case in parsed_cases
            ],
            skipped_count=0, skipped_reasons=[],
        )

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    point_payloads_for_save = [
        {
            "module": c["module"], "function": c["function"],
            "point": c["point"], "priority": c["priority"],
            "created_by": current_username,
        }
        for c in parsed_cases
    ]
    saved_points = batch_create_test_points(
        db=db, project_id=project_id,
        test_points_data=point_payloads_for_save,
        created_by=current_username, commit=False,
    )
    case_payloads = []
    for index, (case, saved_point) in enumerate(
        zip(parsed_cases, saved_points), start=1
    ):
        case_payloads.append({
            "case_no": f"CASE{project_id}-{timestamp}{index:04d}",
            "project_id": project_id,
            "test_point_id": saved_point.id,
            "module": case["module"], "title": case["title"],
            "precondition": case.get("precondition", ""),
            "steps": case.get("steps", []),
            "expected_result": case.get("expected_result", ""),
            "priority": case["priority"],
            "case_type": case.get("case_type", "manual"),
            "test_category": case.get("case_type", "manual"),
            "generate_status": 1,
        })
    saved_cases = batch_create_test_cases(
        db=db, project_id=project_id,
        test_cases_data=case_payloads, commit=False,
    )
    db.commit()
    for item in saved_points:
        db.refresh(item)
    for item in saved_cases:
        db.refresh(item)
    logger.info(
        "XMind 场景导入完成: project_id={}, saved_points={}, saved_cases={}",
        project_id, len(saved_points), len(saved_cases),
    )
    return TestPointXmindImportResponse(
        saved_count=len(saved_points), saved_case_count=len(saved_cases),
        total_parsed=len(parsed_cases), skipped_count=0, skipped_reasons=[],
    )
