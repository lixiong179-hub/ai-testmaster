"""XMind 导入业务逻辑服务。

将 XMind 导入的纯业务逻辑从 API 端点层下沉，避免端点文件膨胀。
负责文件校验、保存、测试点过滤、场景树导入处理等。
"""
import os
import tempfile
from datetime import datetime
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.test_point import (
    TestPointXmindPreviewItem,
    TestPointXmindPreviewCaseItem,
    TestPointXmindPreviewCaseStep,
    TestPointXmindPreviewResponse,
    TestPointXmindImportResponse,
)
from app.crud.test_point import batch_create_test_points
from app.crud.test_case_mutate import batch_create_test_cases
from loguru import logger

MAX_FILE_SIZE = 10 * 1024 * 1024


def validate_file(file: UploadFile) -> None:
    """校验上传文件格式和大小。

    Args:
        file: 上传文件对象。

    Raises:
        HTTPException: 文件格式或大小不符合要求时抛出。
    """
    if not file.filename or not file.filename.endswith(".xmind"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的 XMind 文件格式，请上传 .xmind 文件",
        )


async def save_upload_file(file: UploadFile) -> str:
    """将上传文件保存到临时路径。

    Args:
        file: 上传文件对象。

    Returns:
        临时文件路径。

    Raises:
        HTTPException: 文件过大时抛出。
    """
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


def filter_valid_points(points: list) -> list:
    """过滤有效的测试点数据。

    过滤规则:
        - module 必须存在
        - point 必须存在

    说明:
        XMind 中仅有二级节点（function）但没有三级测试点时，
        解析器会产出 point 为空的中间数据。由于测试点模型和预览响应
        都要求 point 为非空字符串，这类数据需要在接口层统一跳过。

    Args:
        points: 解析出的测试点列表。

    Returns:
        有效测试点列表。
    """
    valid = []
    for p in points:
        if not p.get("module"):
            continue
        if not p.get("point"):
            continue
        valid.append(p)
    return valid


def collect_skip_reasons(points: list) -> list:
    """收集被跳过节点的原因。

    Args:
        points: 解析出的测试点列表。

    Returns:
        跳过原因列表（最多20条）。
    """
    reasons = []
    for p in points:
        if not p.get("module"):
            reasons.append("模块名称为空")
        elif not p.get("point"):
            reasons.append("测试点名称为空")
    return reasons[:20]


def should_treat_as_case_tree(parsed_cases: list) -> bool:
    """判断 XMind 是否更接近场景/用例树，而不是普通测试点树。"""
    if not parsed_cases:
        return False
    case_like_items = [
        case
        for case in parsed_cases
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


def handle_case_style_import(
    db: Session,
    project_id: int,
    current_username: str,
    parsed_cases: list,
    preview: bool,
    ai_timeout: bool = False,
):
    """处理更接近测试用例脑图的 XMind 导入。

    Args:
        db: 数据库会话。
        project_id: 目标项目 ID。
        current_username: 当前操作用户名。
        parsed_cases: 解析出的用例列表。
        preview: 是否预览模式。
        ai_timeout: AI增强模式是否因超时而降级。

    Returns:
        TestPointXmindPreviewResponse 或 TestPointXmindImportResponse。
    """
    point_payloads = [
        {
            "module": case["module"],
            "function": case["function"],
            "point": case["point"],
            "priority": case["priority"],
        }
        for case in parsed_cases
    ]

    if preview:
        return TestPointXmindPreviewResponse(
            preview_mode="test_cases",
            total=len(point_payloads),
            items=[
                TestPointXmindPreviewItem(
                    module=item["module"],
                    function=item["function"],
                    point=item["point"],
                    priority=item["priority"],
                )
                for item in point_payloads
            ],
            case_total=len(parsed_cases),
            case_items=[
                TestPointXmindPreviewCaseItem(
                    module=case["module"],
                    function=case["function"],
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
                )
                for case in parsed_cases
            ],
            skipped_count=0,
            skipped_reasons=[],
            ai_timeout=ai_timeout,
        )

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    point_payloads_for_save = [
        {
            "module": case["module"],
            "function": case["function"],
            "point": case["point"],
            "priority": case["priority"],
            "created_by": current_username,
        }
        for case in parsed_cases
    ]
    saved_points = batch_create_test_points(
        db=db,
        project_id=project_id,
        test_points_data=point_payloads_for_save,
        created_by=current_username,
        commit=False,
    )

    case_payloads = []
    for index, (case, saved_point) in enumerate(zip(parsed_cases, saved_points), start=1):
        case_payloads.append(
            {
                "case_no": f"CASE{project_id}-{timestamp}{index:04d}",
                "project_id": project_id,
                "test_point_id": saved_point.id,
                "module": case["module"],
                "title": case["title"],
                "precondition": case.get("precondition", ""),
                "steps": case.get("steps", []),
                "expected_result": case.get("expected_result", ""),
                "priority": case["priority"],
                "case_type": case.get("case_type", "manual"),
                "test_category": case.get("case_type", "manual"),
                "generate_status": 1,
            }
        )
    saved_cases = batch_create_test_cases(
        db=db,
        project_id=project_id,
        test_cases_data=case_payloads,
        commit=False,
    )

    db.commit()
    for item in saved_points:
        db.refresh(item)
    for item in saved_cases:
        db.refresh(item)

    logger.info(
        "XMind 场景导入完成: project_id={}, saved_points={}, saved_cases={}",
        project_id,
        len(saved_points),
        len(saved_cases),
    )
    return TestPointXmindImportResponse(
        saved_count=len(saved_points),
        saved_case_count=len(saved_cases),
        total_parsed=len(parsed_cases),
        skipped_count=0,
        skipped_reasons=[],
        ai_timeout=ai_timeout,
    )


def handle_ai_enhanced_import(
    db: Session,
    project_id: int,
    current_username: str,
    ai_cases: list,
    preview: bool,
):
    """处理 AI 增强模式导入，逻辑复用场景树导入。"""
    return handle_case_style_import(
        db=db,
        project_id=project_id,
        current_username=current_username,
        parsed_cases=ai_cases,
        preview=preview,
    )
