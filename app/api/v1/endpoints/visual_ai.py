"""Visual AI 引擎 API 端点（Task 12）。

提供视觉基线管理、图像对比与 Diff 审批的 REST 接口。

端点清单：
    基线管理：
        POST   /projects/{project_id}/visual-ai/baselines           创建基线
        GET    /projects/{project_id}/visual-ai/baselines           列出基线
        GET    /projects/{project_id}/visual-ai/baselines/{id}      查询基线
        PUT    /projects/{project_id}/visual-ai/baselines/{id}      更新基线
        DELETE /projects/{project_id}/visual-ai/baselines/{id}      删除基线

    视觉对比：
        POST   /projects/{project_id}/visual-ai/compare             对比当前截图与基线

    Diff 审批：
        GET    /projects/{project_id}/visual-ai/diffs               列出 Diff
        POST   /projects/{project_id}/visual-ai/diffs/{id}/approve  审批 Diff
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.core.exception._base import create_response
from app.db.database import async_get_db
from app.models.baseline_approval import BaselineApproval, APPROVAL_ACTION_VALUES
from app.models.project import Project
from app.models.user import User
from app.models.visual_baseline import VisualBaseline, MATCH_LEVEL_VALUES
from app.models.visual_diff import VisualDiff, DIFF_STATUS_VALUES
from app.schemas.common import ApiResponse
from app.schemas.visual_ai import (
    ApprovalRequest,
    ApprovalResponse,
    BaselineCreateRequest,
    BaselineListResponse,
    BaselineResponse,
    BaselineUpdateRequest,
    CompareRequest,
    DiffListResponse,
    DiffResponse,
)
from app.services.storage import get_storage
from app.services.visual_ai.baseline_service import BaselineService
from app.services.visual_ai.comparison_engine import ComparisonEngine

router = APIRouter(tags=["Visual AI 视觉回归"])


async def _verify_project_owner(
    db: AsyncSession, project_id: int, user_id: int
) -> None:
    """校验项目归属当前用户，不存在或无权限抛 403。"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == user_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )


def _decode_base64(b64_str: str) -> bytes:
    """解码 base64 字符串为字节流。"""
    try:
        return base64.b64decode(b64_str)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"base64 解码失败: {exc}",
        )


def _check_visual_ai_enabled() -> None:
    """校验 Visual AI 功能是否启用。"""
    if not settings.VISUAL_AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Visual AI 功能未启用",
        )


# ── 基线管理端点 ──


@router.post(
    "/projects/{project_id}/visual-ai/baselines",
    response_model=ApiResponse[BaselineResponse],
    summary="创建视觉基线",
)
async def create_baseline(
    project_id: int,
    body: BaselineCreateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """上传截图创建视觉基线。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    if body.match_level not in MATCH_LEVEL_VALUES:
        raise HTTPException(status_code=400, detail=f"非法 match_level: {body.match_level}")

    image_bytes = _decode_base64(body.image_base64)
    dom_bytes = _decode_base64(body.dom_snapshot_base64) if body.dom_snapshot_base64 else None

    service = BaselineService(db=db, storage=get_storage())
    baseline = await service.create_baseline(
        project_id=project_id,
        name=body.name,
        page_url=body.page_url,
        viewport_width=body.viewport_width,
        viewport_height=body.viewport_height,
        image_bytes=image_bytes,
        match_level=body.match_level,
        test_case_id=body.test_case_id,
        dom_snapshot_bytes=dom_bytes,
        created_by=current_user.id,
    )
    return create_response(data=BaselineResponse.model_validate(baseline.to_dict()).model_dump(), msg="基线创建成功")


@router.get(
    "/projects/{project_id}/visual-ai/baselines",
    response_model=ApiResponse[BaselineListResponse],
    summary="列出视觉基线",
)
async def list_baselines(
    project_id: int,
    status_filter: Optional[str] = Query(None, alias="status", description="基线状态过滤"),
    test_case_id: Optional[int] = Query(None, description="按用例过滤"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """按项目列出视觉基线，支持状态与用例过滤。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    service = BaselineService(db=db, storage=get_storage())
    baselines = await service.list_baselines(
        project_id=project_id,
        status=status_filter,
        test_case_id=test_case_id,
        offset=offset,
        limit=limit,
    )
    items = [BaselineResponse.model_validate(b.to_dict()) for b in baselines]
    data = BaselineListResponse(total=len(items), items=items)
    return create_response(data=data.model_dump(), msg="查询成功")


@router.get(
    "/projects/{project_id}/visual-ai/baselines/{baseline_id}",
    response_model=ApiResponse[BaselineResponse],
    summary="查询视觉基线详情",
)
async def get_baseline(
    project_id: int,
    baseline_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """按 ID 查询视觉基线详情。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    service = BaselineService(db=db, storage=get_storage())
    baseline = await service.get_baseline_by_id(baseline_id)
    if baseline is None or baseline.project_id != project_id:
        raise HTTPException(status_code=404, detail="基线不存在")
    return create_response(data=BaselineResponse.model_validate(baseline.to_dict()).model_dump(), msg="查询成功")


@router.put(
    "/projects/{project_id}/visual-ai/baselines/{baseline_id}",
    response_model=ApiResponse[BaselineResponse],
    summary="更新视觉基线截图",
)
async def update_baseline(
    project_id: int,
    baseline_id: int,
    body: BaselineUpdateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """更新基线截图，旧版本归档，创建新版本。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    image_bytes = _decode_base64(body.image_base64)
    dom_bytes = _decode_base64(body.dom_snapshot_base64) if body.dom_snapshot_base64 else None

    service = BaselineService(db=db, storage=get_storage())
    existing = await service.get_baseline_by_id(baseline_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="基线不存在")

    new_baseline = await service.update_baseline(
        baseline_id=baseline_id,
        new_image_bytes=image_bytes,
        match_level=body.match_level,
        dom_snapshot_bytes=dom_bytes,
    )
    return create_response(data=BaselineResponse.model_validate(new_baseline.to_dict()).model_dump(), msg="基线更新成功")


@router.delete(
    "/projects/{project_id}/visual-ai/baselines/{baseline_id}",
    response_model=ApiResponse[Dict[str, Any]],
    summary="删除视觉基线",
)
async def delete_baseline(
    project_id: int,
    baseline_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """删除基线及其存储文件。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    service = BaselineService(db=db, storage=get_storage())
    existing = await service.get_baseline_by_id(baseline_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="基线不存在")

    deleted = await service.delete_baseline(baseline_id)
    return create_response(data={"deleted": deleted, "baseline_id": baseline_id}, msg="删除成功")


# ── 视觉对比端点 ──


@router.post(
    "/projects/{project_id}/visual-ai/compare",
    response_model=ApiResponse[DiffResponse],
    summary="对比当前截图与基线",
)
async def compare_screenshot(
    project_id: int,
    body: CompareRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """对比当前截图与活跃基线，生成 Diff 记录。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    baseline_service = BaselineService(db=db, storage=get_storage())
    baseline = await baseline_service.get_active_baseline(
        project_id=project_id,
        page_url=body.page_url,
        viewport_width=body.viewport_width,
        viewport_height=body.viewport_height,
    )
    if baseline is None:
        raise HTTPException(status_code=404, detail="未找到活跃基线，请先创建基线")

    baseline_image = await baseline_service.load_baseline_image(baseline.id)
    current_image = _decode_base64(body.current_image_base64)

    engine = ComparisonEngine(
        ai_client=None,
        llm_analysis_threshold=settings.VISUAL_AI_LLM_ANALYSIS_THRESHOLD,
        llm_token_limit=settings.VISUAL_AI_LLM_TOKEN_LIMIT,
    )
    result = await engine.compare(
        baseline_bytes=baseline_image,
        current_bytes=current_image,
        match_level=body.match_level or baseline.match_level,
        enable_llm_analysis=body.enable_llm_analysis,
    )

    # 保存 Diff 图片到存储
    diff_image_key: Optional[str] = None
    diff_image_base64: Optional[str] = None
    if result.diff_image:
        import hashlib

        url_hash = hashlib.md5(body.page_url.encode("utf-8")).hexdigest()[:12]
        diff_image_key = f"visual-ai/diffs/{project_id}/{url_hash}/{baseline.id}_{result.diff_pixel_count}.png"
        storage = get_storage()
        await storage.save(diff_image_key, result.diff_image, content_type="image/png")
        diff_image_base64 = base64.b64encode(result.diff_image).decode("ascii")

    # 自动审批：差异低于阈值时自动通过
    diff_status = "pending"
    if result.diff_percentage < settings.VISUAL_AI_AUTO_APPROVE_THRESHOLD:
        diff_status = "auto_approved"

    # 持久化 Diff 记录
    diff_record = VisualDiff(
        project_id=project_id,
        baseline_id=baseline.id,
        test_case_id=body.test_case_id,
        test_result_id=body.test_result_id,
        current_image_key="",
        diff_image_key=diff_image_key,
        diff_percentage=result.diff_percentage,
        diff_pixel_count=result.diff_pixel_count,
        total_pixel_count=result.total_pixel_count,
        match_level=result.match_level,
        status=diff_status,
        llm_analysis=result.llm_analysis.to_json() if result.llm_analysis else None,
        llm_token_cost=result.total_token_cost,
    )
    db.add(diff_record)
    await db.commit()
    await db.refresh(diff_record)

    response_data = DiffResponse(
        diff_id=diff_record.id,
        baseline_id=baseline.id,
        diff_percentage=result.diff_percentage,
        diff_pixel_count=result.diff_pixel_count,
        total_pixel_count=result.total_pixel_count,
        match_level=result.match_level,
        status=diff_status,
        llm_analysis=result.llm_analysis.to_dict() if result.llm_analysis else None,
        llm_token_cost=result.total_token_cost,
        diff_image_base64=diff_image_base64,
    )
    return create_response(data=response_data.model_dump(), msg="对比完成")


# ── Diff 审批端点 ──


@router.get(
    "/projects/{project_id}/visual-ai/diffs",
    response_model=ApiResponse[DiffListResponse],
    summary="列出视觉差异记录",
)
async def list_diffs(
    project_id: int,
    status_filter: Optional[str] = Query(None, alias="status", description="审批状态过滤"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """按项目列出视觉差异记录。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    stmt = select(VisualDiff).where(VisualDiff.project_id == project_id)
    if status_filter:
        if status_filter not in DIFF_STATUS_VALUES:
            raise HTTPException(status_code=400, detail=f"非法 status: {status_filter}")
        stmt = stmt.where(VisualDiff.status == status_filter)
    stmt = stmt.order_by(VisualDiff.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    diffs = result.scalars().all()

    items = []
    for d in diffs:
        items.append(
            DiffResponse(
                diff_id=d.id,
                baseline_id=d.baseline_id,
                diff_percentage=d.diff_percentage,
                diff_pixel_count=d.diff_pixel_count,
                total_pixel_count=d.total_pixel_count,
                match_level=d.match_level,
                status=d.status,
                llm_token_cost=d.llm_token_cost,
            )
        )
    data = DiffListResponse(total=len(items), items=items)
    return create_response(data=data.model_dump(), msg="查询成功")


@router.post(
    "/projects/{project_id}/visual-ai/diffs/{diff_id}/approve",
    response_model=ApiResponse[ApprovalResponse],
    summary="审批视觉差异",
)
async def approve_diff(
    project_id: int,
    diff_id: int,
    body: ApprovalRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """审批视觉差异记录（approve/reject/update_baseline）。"""
    _check_visual_ai_enabled()
    await _verify_project_owner(db, project_id, current_user.id)

    if body.action not in APPROVAL_ACTION_VALUES:
        raise HTTPException(status_code=400, detail=f"非法 action: {body.action}")

    diff = await db.get(VisualDiff, diff_id)
    if diff is None or diff.project_id != project_id:
        raise HTTPException(status_code=404, detail="Diff 不存在")

    approval = BaselineApproval(
        project_id=project_id,
        diff_id=diff_id,
        baseline_id=diff.baseline_id,
        action=body.action,
        comment=body.comment,
        reviewer_id=current_user.id,
    )
    db.add(approval)

    # 更新 Diff 状态
    if body.action == "approve":
        diff.status = "approved"
    elif body.action == "reject":
        diff.status = "rejected"
    elif body.action == "update_baseline":
        diff.status = "approved"
        # 触发基线更新流程（标记，实际更新需调用 PUT /baselines/{id}）

    await db.commit()
    await db.refresh(approval)

    return create_response(data=ApprovalResponse.model_validate(approval.to_dict()).model_dump(), msg="审批成功")
