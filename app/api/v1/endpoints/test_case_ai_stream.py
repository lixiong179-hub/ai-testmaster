"""测试用例AI流式生成端点模块

本模块定义AI生成测试用例的流式API端点（SSE）。
非流式端点和共享模型/辅助函数在 test_case_ai.py 中定义。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /ai-enhanced-generate/stream - AI增强模式流式生成
    - POST /batch-generate/stream       - 流式批量生成测试用例

所有端点均需要Bearer令牌认证。
"""
import asyncio
import json
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_case_ai import (
    AIGenerateEnhancedRequest,
    BatchGenerateRequest,
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
)
from app.db.database import PrimarySessionLocal, async_get_db
from app.models.project import Project
from app.models.user import User
from app.services.case_quality.quality_feedback_loop import (
    build_quality_feedback_text,
    run_quality_feedback_loop,
)
from app.utils.ai_client import generate_test_case, generate_test_case_enhanced

router = APIRouter()


async def _run_quality_feedback_for_cases(
    cases: List[Dict[str, Any]],
    regen_fn: Any,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """对用例列表执行质量反馈闭环，返回通过用例与重生成事件。

    替代原直接丢弃策略：低质量用例经最多 3 轮重生成修复，只 rejected
    阻断，pending_review/warning 保留（历史避坑：质量门禁分级阻断）。

    Args:
        cases: AI 首轮生成的用例列表。
        regen_fn: 重生成 async 函数，接收 extra_context dict，返回新用例。

    Returns:
        (通过用例列表, 重生成事件列表)。事件含 round/status/issues_count/case_title。
    """
    final_cases: List[Dict[str, Any]] = []
    regen_events: List[Dict[str, Any]] = []

    for case in cases:
        if not isinstance(case, dict):
            continue
        case_title = case.get("title", "")

        def on_round(
            round_idx: int, rst_status: str, issues: List[str],
            _title: str = case_title,
        ) -> None:
            regen_events.append({
                "round": round_idx, "status": rst_status,
                "issues_count": len(issues), "case_title": _title,
            })

        case, rst_status, _ = await run_quality_feedback_loop(
            case, regen_fn, build_quality_feedback_text, on_round=on_round,
        )
        if rst_status == "rejected":
            logger.warning(
                f"流式端点：用例经反馈闭环仍rejected已丢弃: {case.get('title', '')}"
            )
        else:
            final_cases.append(case)

    return final_cases, regen_events


# ── AI增强模式流式生成端点 ────────────────────────────────


@router.post("/ai-enhanced-generate/stream")
async def ai_enhanced_generate_stream(
    request: AIGenerateEnhancedRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """AI增强模式生成测试用例（SSE流式）。

    以SSE方式流式返回AI增强模式生成的测试用例，
    前端可实时展示生成进度和中间结果。
    """
    project_id = request.project_id
    description = request.description

    def _check_project(sync_db: Session) -> Project:
        project = sync_db.query(Project).filter(
            Project.id == project_id, Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在"
            )
        return project

    await db.run_sync(_check_project)

    if not description or len(description.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="描述不能为空且至少需要5个字符",
        )

    async def event_generator():
        stream_db = PrimarySessionLocal()
        try:
            # 先构建context，提取context_stats和warnings用于首帧推送
            context = dict(request.context or {})
            if request.extra_requirements:
                context["extra_requirements"] = request.extra_requirements
            context_stats = context.get("context_stats", {})
            warnings = context.get("warnings", [])
            evidence_refs = context.get("evidence_refs", {})

            # 构建审计增强 metadata：使用独立 sync session，避免跨 greenlet 访问
            ai_metadata: Dict[str, Any] = {
                "db": stream_db,
                "scenario_type": context.get("scenario_type"),
                "generation_strategy": context.get("generation_strategy"),
            }
            batch_id = context.get("generation_batch_id")
            if batch_id is not None:
                ai_metadata["generation_batch_id"] = int(batch_id)

            yield f"data: {json.dumps({'code': 0, 'message': '开始生成', 'data': {'status': 'started', 'context_stats': context_stats, 'warnings': warnings, 'evidence_refs': evidence_refs}}, ensure_ascii=False)}\n\n"

            if request.mode == "graph" and request.flow_sort_data:
                yield f"data: {json.dumps({'code': 0, 'message': '构建流程图Prompt...', 'data': {'status': 'building_prompt'}}, ensure_ascii=False)}\n\n"
                prompt_data = _build_graph_prompt_data(
                    flow_sort_data=request.flow_sort_data,
                    context=context, description=description,
                    priority=request.priority,
                    case_type=request.case_type,
                )
            elif request.enhanced_mode:
                yield f"data: {json.dumps({'code': 0, 'message': '构建增强Prompt...', 'data': {'status': 'building_prompt'}}, ensure_ascii=False)}\n\n"
                prompt_data = _build_linear_prompt_data(
                    context=context, description=description,
                    priority=request.priority,
                    case_type=request.case_type,
                    exec_mode=request.exec_mode,
                )
            else:
                yield f"data: {json.dumps({'code': 0, 'message': '基础模式生成中...', 'data': {'status': 'generating'}}, ensure_ascii=False)}\n\n"
                generated_case = await asyncio.to_thread(generate_test_case, description)
                response_data = _format_case_response(
                    generated_case=generated_case, project_id=project_id,
                    description=description, priority=request.priority,
                    case_type=request.case_type,
                )
                yield f"data: {json.dumps({'code': 0, 'message': '生成完成', 'data': response_data}, ensure_ascii=False, default=str)}\n\n"
                return

            yield f"data: {json.dumps({'code': 0, 'message': 'AI生成中...', 'data': {'status': 'generating'}}, ensure_ascii=False)}\n\n"
            generated_case = await asyncio.to_thread(
                generate_test_case_enhanced, prompt_data, ai_metadata,
            )

            cases_list = generated_case if isinstance(generated_case, list) else [generated_case]
            cases_list = [c for c in cases_list if isinstance(c, dict) and c]

            # Task 15: 流式端点接入 3 轮反馈闭环，低质量用例重生成而非直接丢弃
            async def _regen_case(extra_ctx: Dict[str, Any]) -> Any:
                new_prompt_data = dict(prompt_data)
                if extra_ctx.get("quality_feedback"):
                    new_prompt_data["quality_feedback"] = extra_ctx["quality_feedback"]
                if extra_ctx.get("quality_signals"):
                    new_prompt_data["quality_signals"] = extra_ctx["quality_signals"]
                result = await asyncio.to_thread(
                    generate_test_case_enhanced, new_prompt_data, ai_metadata,
                )
                if isinstance(result, list) and result and isinstance(result[0], dict):
                    return result[0]
                if isinstance(result, dict):
                    return result
                return None

            valid_cases, regen_events = await _run_quality_feedback_for_cases(
                cases_list, _regen_case,
            )

            # Task 15.3: 推送重生成进度事件（仅重生成轮次，首轮不推送）
            for event in regen_events:
                if event.get("round", 0) > 0:
                    regen_msg = json.dumps(
                        {'code': 0, 'message': f'重生成第{event["round"]}轮',
                         'data': {'status': 'regen', **event}},
                        ensure_ascii=False,
                    )
                    yield f"data: {regen_msg}\n\n"

            if not valid_cases:
                fail_msg = json.dumps(
                    {'code': 1, 'message': '生成的用例均未通过质量校验，请调整描述后重试', 'data': None},
                    ensure_ascii=False,
                )
                yield f"data: {fail_msg}\n\n"
                return
            response_data = [
                _format_case_response(
                    generated_case=case_item, project_id=project_id,
                    description=description, priority=request.priority,
                    case_type=request.case_type,
                )
                for case_item in valid_cases
            ]

            yield f"data: {json.dumps({'code': 0, 'message': '生成完成', 'data': response_data}, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            logger.error(f"AI增强模式流式生成失败: {e}")
            yield f"data: {json.dumps({'code': 500, 'message': f'生成失败: {str(e)}', 'data': None}, ensure_ascii=False)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 流式批量生成端点 ─────────────────────────────────────


@router.post("/batch-generate/stream")
async def batch_generate_test_cases_stream(
    request: BatchGenerateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """流式批量生成测试用例。

    以SSE方式流式返回AI批量生成的测试用例，
    每生成一条用例即推送一条事件，前端可实时展示生成进度。
    """
    def _check_project(sync_db: Session) -> None:
        project = sync_db.query(Project).filter(
            Project.id == request.project_id, Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

    await db.run_sync(_check_project)

    from app.services.test_case_generation import TestCaseGenerationService
    from app.utils.async_sync_bridge import iter_async_gen_in_thread

    async def generate_progress() -> Any:
        stream_db = PrimarySessionLocal()
        try:
            service = TestCaseGenerationService(stream_db)
            try:
                # 性能优化：将 async generator 放到独立线程执行，
                # 避免 service 内部 sync_db.query() 阻塞主事件循环。
                # 通过队列桥接，主事件循环仍能并发处理其他请求。
                def _agen_factory():
                    return service.generate_test_cases_batch(
                        project_id=request.project_id,
                        user_id=current_user.id,
                        test_point_ids=request.test_point_ids,
                        requirement_file_ids=request.requirement_file_ids,
                        ui_file_ids=request.ui_file_ids,
                        ui_screen_ids=request.ui_screen_ids,
                        test_point_page=request.test_point_page,
                        test_point_page_size=request.test_point_page_size,
                        case_type=request.case_type,
                    )

                async for progress in iter_async_gen_in_thread(_agen_factory):
                    yield f"data: {json.dumps(progress)}\n\n"
            except Exception as e:
                logger.error(f"批量生成测试用例失败: {e}")
                error_progress = {
                    "progress": 100,
                    "message": f"生成失败: {str(e)}",
                    "status": "error",
                }
                yield f"data: {json.dumps(error_progress)}\n\n"
            finally:
                yield "data: [DONE]\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        generate_progress(), media_type="text/event-stream"
    )
