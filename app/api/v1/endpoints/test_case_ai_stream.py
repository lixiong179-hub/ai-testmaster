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
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_case_ai import (
    AIGenerateEnhancedRequest,
    BatchGenerateRequest,
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
)
from app.db.database import get_db
from app.models.project import Project
from app.models.user import User
from app.services.test_case_generation.quality_validator import validate_single_case
from app.utils.ai_client import generate_test_case, generate_test_case_enhanced

router = APIRouter()


def _filter_valid_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """过滤掉质量校验不通过的用例，记录问题日志。

    流式端点无法像非流式端点那样做重试循环，
    因此采用过滤策略：校验通过的用例正常返回，不通过的丢弃并记录。

    Args:
        cases: AI生成的用例列表

    Returns:
        通过质量校验的用例子集
    """
    valid_cases: List[Dict[str, Any]] = []
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            logger.warning(f"流式端点：第{i + 1}条用例非dict类型，已丢弃")
            continue
        issues = validate_single_case(case)
        if issues:
            issue_text = "; ".join(issues[:3])
            logger.warning(
                f"流式端点：第{i + 1}条用例质量校验不通过，已丢弃: {issue_text}"
            )
        else:
            valid_cases.append(case)
    return valid_cases


# ── AI增强模式流式生成端点 ────────────────────────────────


@router.post("/ai-enhanced-generate/stream")
async def ai_enhanced_generate_stream(
    request: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """AI增强模式生成测试用例（SSE流式）。

    以SSE方式流式返回AI增强模式生成的测试用例，
    前端可实时展示生成进度和中间结果。
    """
    project_id = request.project_id
    description = request.description

    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在"
        )

    if not description or len(description.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="描述不能为空且至少需要5个字符",
        )

    async def event_generator():
        try:
            # 先构建context，提取context_stats和warnings用于首帧推送
            context = dict(request.context or {})
            if request.extra_requirements:
                context["extra_requirements"] = request.extra_requirements
            context_stats = context.get("context_stats", {})
            warnings = context.get("warnings", [])
            evidence_refs = context.get("evidence_refs", {})

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
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)

            cases_list = generated_case if isinstance(generated_case, list) else [generated_case]
            cases_list = [c for c in cases_list if isinstance(c, dict) and c]
            valid_cases = _filter_valid_cases(cases_list)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """流式批量生成测试用例。

    以SSE方式流式返回AI批量生成的测试用例，
    每生成一条用例即推送一条事件，前端可实时展示生成进度。
    """
    project = db.query(Project).filter(
        Project.id == request.project_id, Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )

    from app.services.test_case_generation import TestCaseGenerationService

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
                case_type=request.case_type,
            ):
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

    return StreamingResponse(
        generate_progress(), media_type="text/event-stream"
    )
