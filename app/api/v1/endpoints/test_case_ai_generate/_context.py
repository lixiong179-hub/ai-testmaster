import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_case_ai_schemas import (
    BatchGenerateRequest,
    GenerateContextRequest,
    SingleGenerateRequest,
)
from app.core.exception import create_response
from app.schemas.common import ApiResponse
from app.db.database import async_get_db, PrimarySessionLocal
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.requirement import Requirement
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

DEFAULT_HISTORY_CASE_LIMIT = 10


def _safe_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _extract_terms(*parts: Any) -> set[str]:
    text = " ".join(str(part or "") for part in parts).lower()
    raw_tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    terms: set[str] = set()
    for token in raw_tokens:
        if len(token) < 2:
            continue
        terms.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 2:
            terms.update(token[i:i + 2] for i in range(len(token) - 1))
    return {term for term in terms if len(term) >= 2}


def _score_terms(terms: set[str], *parts: Any) -> int:
    if not terms:
        return 0
    text = " ".join(_safe_text(part) for part in parts).lower()
    return sum(1 for term in terms if term in text)


def _infer_design_tag(case: TestCase, steps: Any) -> str:
    text = " ".join([
        case.title or "",
        case.summary or "",
        case.expected_result or "",
        _safe_text(steps),
    ])
    if any(keyword in text for keyword in ("空", "为空", "必填", "超长", "最大", "最小", "边界", "长度")):
        return "边界值"
    if any(keyword in text for keyword in ("失败", "错误", "异常", "无权限", "断网", "超时", "锁定")):
        return "异常流程"
    if isinstance(steps, list) and len(steps) >= 5:
        return "组合场景"
    return "常规流程"


def _assess_history_trust(
    case: TestCase,
    current_requirement_ids: set[int],
    current_ui_screen_ids: set[int],
    db: Session,
) -> tuple[str, str]:
    staleness_reasons: list[str] = []

    if case.test_point_id:
        tp = db.query(TestPoint).filter(TestPoint.id == case.test_point_id).first()
        if tp and tp.requirement_id and tp.requirement_id not in current_requirement_ids:
            staleness_reasons.append("requirement_mismatch")
        if tp and tp.requirement_id:
            req = db.query(Requirement).filter(Requirement.id == tp.requirement_id).first()
            if req and isinstance(req.update_time, datetime) and isinstance(case.update_time, datetime):
                if req.update_time > case.update_time:
                    staleness_reasons.append("requirement_newer_than_case")

    if isinstance(case.update_time, datetime):
        now = datetime.now(timezone.utc)
        case_update = case.update_time.replace(tzinfo=timezone.utc) if case.update_time.tzinfo is None else case.update_time
        case_age_days = (now - case_update).days
        if case_age_days > 90:
            staleness_reasons.append("case_older_than_90_days")

    if not case.summary and not case.summary_version:
        staleness_reasons.append("summary_missing")

    if current_ui_screen_ids:
        try:
            case_ui_screen_ids = {s.id for s in case.linked_ui_screens} if case.linked_ui_screens else set()
        except Exception:
            case_ui_screen_ids = set()
        if case_ui_screen_ids and not case_ui_screen_ids.intersection(current_ui_screen_ids):
            staleness_reasons.append("ui_screen_mismatch")

    if staleness_reasons:
        if "requirement_mismatch" in staleness_reasons:
            return "low", "HISTORY_REQUIREMENT_MISMATCH"
        if any(r in staleness_reasons for r in ("requirement_newer_than_case", "case_older_than_90_days")):
            return "medium", "HISTORY_POTENTIALLY_STALE"
        return "medium", ",".join(staleness_reasons)

    return "high", ""


def _summarize_history_case(
    case: TestCase,
    similarity: float | None = None,
    trust_level: str = "high",
    staleness_reason: str = "",
) -> dict[str, Any]:
    steps = case.steps_json or []
    steps_summary = ""
    if isinstance(steps, list) and steps:
        actions = [s.get("action", s.get("description", "")) for s in steps[:3] if isinstance(s, dict)]
        steps_summary = " -> ".join(a for a in actions if a)
    summary = (case.summary or steps_summary or case.expected_result or "")[:150]
    result = {
        "id": case.id,
        "case_no": case.case_no,
        "module": case.module or "",
        "title": case.title,
        "summary": summary,
        "covered_scene": summary,
        "design_tag": _infer_design_tag(case, steps),
        "trust_level": trust_level,
        "staleness_reason": staleness_reason,
    }
    if similarity is not None:
        result["similarity"] = round(similarity, 2)
    return result


@router.post("/generate-context", response_model=ApiResponse)
async def get_generation_context(
    request: GenerateContextRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    project_result = await db.execute(
        select(Project).where(
            Project.id == request.project_id, Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation import TestCaseGenerationService
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    # TestCaseGenerationService 内部使用 sync Session API，需独立 sync 会话
    # 性能优化：将整个 async service 调用放到独立线程，避免 sync_db.query() 阻塞主事件循环
    sync_db = PrimarySessionLocal()
    try:
        service = TestCaseGenerationService(sync_db)
        context = await run_async_coro_in_thread(
            service.get_context_for_generation(
                project_id=request.project_id, user_id=current_user.id,
                requirement_file_ids=request.requirement_file_ids,
                ui_file_ids=request.ui_file_ids,
                ui_screen_ids=request.ui_screen_ids,
                test_point_ids=request.test_point_ids,
                force_refresh=request.force_refresh,
                test_point_page=request.test_point_page,
                test_point_page_size=request.test_point_page_size,
            )
        )
        test_points_count = len(context.get("test_points", []))
        if test_points_count == 0:
            logger.warning(f"项目 {request.project_id} 没有找到测试点")

        service.enrich_context_with_trust_and_scoring(
            context,
            request.project_id,
            history_case_ids=request.history_case_ids,
            history_limit=DEFAULT_HISTORY_CASE_LIMIT,
        )

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
            "history_cases": context.get("history_cases", []),
            "context_stats": context.get("context_stats", {}),
            "evidence_refs": context.get("evidence_refs", {}),
            "message": f"获取成功：{test_points_count}个测试点",
        })
    finally:
        sync_db.close()


@router.post("/generate-single")
async def generate_single_test_case(
    request: SingleGenerateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    project_result = await db.execute(
        select(Project).where(
            Project.id == request.project_id, Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation import TestCaseGenerationService
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    sync_db = PrimarySessionLocal()
    try:
        service = TestCaseGenerationService(sync_db)
        # 性能优化：将 service 调用放到独立线程，避免 sync_db.query() 阻塞事件循环
        context = await run_async_coro_in_thread(
            service.get_context_for_generation(
                project_id=request.project_id, user_id=current_user.id,
                requirement_file_ids=request.requirement_file_ids,
                ui_file_ids=request.ui_file_ids,
                ui_screen_ids=request.ui_screen_ids,
                test_point_ids=[request.test_point_id],
            )
        )
        service.enrich_context_with_trust_and_scoring(context, request.project_id)
        test_points = context.get("test_points", [])
        if not test_points:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"没有找到ID为{request.test_point_id}的测试点",
            )
        test_point = test_points[0]
        try:
            from app.utils.ai_concurrency import ai_generation_slot
            # AI 生成调用受模块级信号量保护，限制跨请求总并发（P-2 修复）
            async with ai_generation_slot():
                generated_case = await run_async_coro_in_thread(
                    service.generate_test_case_for_point(
                        context=context, test_point=test_point,
                        project_id=request.project_id, case_type=request.case_type,
                    )
                )
            saved_case = await run_async_coro_in_thread(
                service._save_test_case(
                    project_id=request.project_id,
                    generated_case=generated_case, test_point=test_point,
                )
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
                "context_stats": context.get("context_stats", {}),
                "evidence_refs": context.get("evidence_refs", {}),
                "warnings": context.get("warnings", []),
                "message": "测试用例生成成功",
            })
        except Exception as e:
            sync_db.rollback()
            logger.error(f"生成测试用例失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成失败"
            )
    finally:
        sync_db.close()


@router.post("/ai-batch-generate")
async def ai_batch_generate_test_cases(
    request: BatchGenerateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="批量生成功能即将上线，请使用 /batch-generate/stream 流式端点或 /generate-single 逐条生成",
    )
