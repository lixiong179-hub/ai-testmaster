"""
AI增强模式生成测试用例端点模块

本模块定义AI增强模式生成测试用例的API端点，支持流式和非流式两种生成方式。
增强模式在基础AI生成上增加了更详细的步骤描述和测试数据生成。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /ai-enhanced-generate        - AI增强模式生成（非流式）
    - POST /ai-enhanced-generate/stream - AI增强模式生成（SSE流式）

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 增强模式生成更详细的测试步骤和预期结果
    - 流式模式通过SSE实时推送生成进度
    - 需配置DEEPSEEK_API_KEY环境变量
"""
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.project import Project
from app.models.user import User
from app.api.v1.endpoints.auth import oauth2_scheme
from app.api.v1.endpoints.auth_deps import get_current_user
from app.utils.ai_client import generate_test_case, generate_test_case_enhanced
from app.utils.test_case_helpers import convert_steps_to_response
from app.core.exception import create_response
from app.schemas.test_case import FlowSortDataSchema
from loguru import logger

router = APIRouter()

MAX_FLOW_NODES = 100
MAX_FLOW_EDGES = 200


class AIGenerateEnhancedRequest(BaseModel):
    project_id: int
    description: str
    case_type: Optional[str] = None
    exec_mode: str = "all"
    priority: int = 2
    enhanced_mode: bool = True
    context: Optional[dict] = None
    ui_screen_ids: Optional[List[int]] = None
    mode: Literal['linear', 'graph'] = 'linear'
    flow_sort_data: Optional[FlowSortDataSchema] = None

    @field_validator('case_type')
    @classmethod
    def validate_case_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid_types = ('ui_automation', 'manual', 'api_automation', 'performance', 'security',
                       'functional', 'api_auto', 'UI', 'API')
        if v not in valid_types:
            raise ValueError(f'不支持的用例类型: {v}')
        from app.core.constants import TestCaseType
        return TestCaseType.from_legacy(v).value

    @field_validator('exec_mode')
    @classmethod
    def validate_exec_mode(cls, v: str) -> str:
        valid_modes = ('all', 'ui_auto', 'manual')
        if v not in valid_modes:
            raise ValueError(f'不支持的执行模式: {v}')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError('描述不能为空且至少需要5个字符')
        if len(v) > 10000:
            raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')
        return v.strip()

    @field_validator('flow_sort_data')
    @classmethod
    def validate_flow_sort_data_size(cls, v: Optional[FlowSortDataSchema]) -> Optional[FlowSortDataSchema]:
        if v is None:
            return v
        if len(v.nodes) > MAX_FLOW_NODES:
            raise ValueError(f'nodes数量不能超过{MAX_FLOW_NODES}')
        if len(v.edges) > MAX_FLOW_EDGES:
            raise ValueError(f'edges数量不能超过{MAX_FLOW_EDGES}')
        return v


def _prepare_test_point(context: Dict[str, Any], description: str, priority: int) -> Dict[str, Any]:
    """从上下文中提取或构造测试点信息。"""
    test_points = context.get('test_points', [])
    test_point = context.get('test_point', {}) or context.get('current_test_point', {})
    if not test_point and test_points:
        test_point = test_points[0]
    if not test_point:
        test_point = {
            "module": context.get("module", "未知模块"),
            "function": context.get("function") or context.get("point", ""),
            "point": context.get("point", "未知测试点"),
            "priority": priority,
        }
    return test_point


def _build_ui_specs_text(ui_specs: List[Dict[str, Any]]) -> str:
    """将UI规格列表格式化为Prompt文本。"""
    if not ui_specs:
        return ""
    from app.services.case_generation.ai_prompt_mixin import AIPromptMixin
    spec_parts = []
    for spec_item in ui_specs:
        screen_name = spec_item.get("screen_name", "未命名页面")
        spec = spec_item.get("ui_spec", {})
        if spec:
            spec_parts.append(AIPromptMixin._format_ui_spec_for_prompt(screen_name, spec))
    return "\n\n".join(spec_parts) if spec_parts else ""


def _build_graph_prompt_data(
    flow_sort_data: FlowSortDataSchema,
    context: Dict[str, Any],
    description: str,
    priority: int
) -> Dict[str, Any]:
    """构建流程图模式所需的Prompt数据。"""
    from app.services.case_generation_prompt_builder import PromptBuilder
    from app.services.flow_validation import validate_flow_structure

    nodes_list = [n.model_dump() for n in flow_sort_data.nodes]
    edges_list = [e.model_dump() for e in flow_sort_data.edges]

    # M1B-6: 后端流程结构校验（仅记录，不阻断）
    errors, warnings = validate_flow_structure(nodes_list, edges_list)
    if errors:
        logger.warning(f"流程图校验发现 {len(errors)} 个错误: {errors}")
    if warnings:
        logger.info(f"流程图校验发现 {len(warnings)} 个警告: {warnings}")
    module_info = flow_sort_data.module_info

    test_point = _prepare_test_point(context, description, priority)
    ui_specs = context.get('ui_specs', [])
    ui_specs_text = _build_ui_specs_text(ui_specs)
    test_point_json = json.dumps(test_point, ensure_ascii=False)

    graph_prompt = PromptBuilder.build_graph_prompt(
        nodes=nodes_list,
        edges=edges_list,
        module_info=module_info,
        requirement_content=context.get('requirement_content', ''),
        test_point_json=test_point_json,
        ui_specs_text=ui_specs_text
    )

    logger.info(f"流程图模式：接收到 {len(nodes_list)} 个节点，{len(edges_list)} 条连线")

    return {
        'requirement_content': context.get('requirement_content', ''),
        'ui_description': '',
        'ui_spec': ui_specs[0].get('ui_spec', {}) if ui_specs else {},
        'ui_specs': ui_specs,
        'test_point': test_point,
        'case_type': context.get('case_type'),
        'exec_mode': context.get('exec_mode', 'all'),
        'project_config': context.get('project_config'),
        'graph_prompt': graph_prompt,
        'flow_validation': {'errors': errors, 'warnings': warnings},
    }


def _build_linear_prompt_data(
    context: Dict[str, Any],
    description: str,
    priority: int,
    case_type: Optional[str],
    exec_mode: str
) -> Dict[str, Any]:
    """构建线性模式所需的Prompt数据。"""
    test_point = _prepare_test_point(context, description, priority)
    raw_ui_desc = context.get('ui_description', '')
    ui_specs = context.get('ui_specs', [])

    return {
        'requirement_content': context.get('requirement_content', ''),
        'ui_description': raw_ui_desc,
        'ui_spec': ui_specs[0].get('ui_spec', {}) if ui_specs else {},
        'ui_specs': ui_specs,
        'test_point': test_point,
        'case_type': case_type,
        'exec_mode': exec_mode,
        'project_config': context.get('project_config')
    }


def _format_case_response(
    generated_case: Dict[str, Any],
    project_id: int,
    description: str,
    priority: int,
    case_type: Optional[str]
) -> Dict[str, Any]:
    """格式化生成的测试用例为响应数据。"""
    steps_data = convert_steps_to_response(generated_case.get("steps", []))
    return {
        "id": 0,
        "project_id": project_id,
        "case_no": f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "module": generated_case.get("module", "AI生成"),
        "title": generated_case.get("title", description[:50]),
        "precondition": generated_case.get("precondition", ""),
        "test_data": generated_case.get("test_data", {}),
        "steps": steps_data,
        "expected_result": generated_case.get("expected_result", ""),
        "priority": priority,
        "case_type": generated_case.get("case_type", case_type),
        "generate_status": 1,
        "create_time": datetime.now().isoformat()
    }


@router.post("/ai-enhanced-generate")
async def ai_enhanced_generate(
    request: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI增强模式生成测试用例（非流式）

    使用增强模式AI生成测试用例，生成更详细的步骤描述和测试数据。
    非流式模式等待全部生成完成后一次性返回结果。

    请求参数(AIGenerateEnhancedRequest):
        - project_id: 所属项目ID
        - description: 需求描述
        - requirement_file_id: 需求文件ID（可选）

    响应格式: 生成的测试用例详情

    权限要求: 需要Bearer令牌认证
    """
    project_id = request.project_id
    description = request.description

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if not description or len(description.strip()) < 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="描述不能为空且至少需要5个字符")

    try:
        context = request.context or {}
        logger.info(f"AI生成增强模式 - 接收到的context: {json.dumps(context, ensure_ascii=False, default=str)[:500]}")

        if request.mode == 'graph' and request.flow_sort_data:
            prompt_data = _build_graph_prompt_data(
                flow_sort_data=request.flow_sort_data,
                context=context,
                description=description,
                priority=request.priority
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        elif request.enhanced_mode:
            prompt_data = _build_linear_prompt_data(
                context=context,
                description=description,
                priority=request.priority,
                case_type=request.case_type,
                exec_mode=request.exec_mode
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)

        response_data = _format_case_response(
            generated_case=generated_case,
            project_id=project_id,
            description=description,
            priority=request.priority,
            case_type=request.case_type
        )

        return create_response(data=response_data)
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败")


@router.post("/ai-enhanced-generate/stream")
async def ai_enhanced_generate_stream(
    request: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    AI增强模式生成测试用例（SSE流式）

    以SSE方式流式返回AI增强模式生成的测试用例。
    前端可实时展示生成进度和中间结果。

    请求参数(AIGenerateEnhancedRequest):
        - project_id: 所属项目ID
        - description: 需求描述
        - requirement_file_id: 需求文件ID（可选）

    响应格式: SSE事件流

    权限要求: 需要Bearer令牌认证
    """
    project_id = request.project_id
    description = request.description

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if not description or len(description.strip()) < 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="描述不能为空且至少需要5个字符")

    async def event_generator():
        try:
            yield f"data: {json.dumps({'code': 0, 'message': '开始生成', 'data': {'status': 'started'}}, ensure_ascii=False)}\n\n"

            context = request.context or {}

            if request.mode == 'graph' and request.flow_sort_data:
                yield f"data: {json.dumps({'code': 0, 'message': '构建流程图Prompt...', 'data': {'status': 'building_prompt'}}, ensure_ascii=False)}\n\n"
                prompt_data = _build_graph_prompt_data(
                    flow_sort_data=request.flow_sort_data,
                    context=context,
                    description=description,
                    priority=request.priority
                )
            elif request.enhanced_mode:
                yield f"data: {json.dumps({'code': 0, 'message': '构建增强Prompt...', 'data': {'status': 'building_prompt'}}, ensure_ascii=False)}\n\n"
                prompt_data = _build_linear_prompt_data(
                    context=context,
                    description=description,
                    priority=request.priority,
                    case_type=request.case_type,
                    exec_mode=request.exec_mode
                )
            else:
                yield f"data: {json.dumps({'code': 0, 'message': '基础模式生成中...', 'data': {'status': 'generating'}}, ensure_ascii=False)}\n\n"
                generated_case = await asyncio.to_thread(generate_test_case, description)
                response_data = _format_case_response(
                    generated_case=generated_case,
                    project_id=project_id,
                    description=description,
                    priority=request.priority,
                    case_type=request.case_type
                )
                yield f"data: {json.dumps({'code': 0, 'message': '生成完成', 'data': response_data}, ensure_ascii=False, default=str)}\n\n"
                return

            yield f"data: {json.dumps({'code': 0, 'message': 'AI生成中...', 'data': {'status': 'generating'}}, ensure_ascii=False)}\n\n"
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)

            response_data = _format_case_response(
                generated_case=generated_case,
                project_id=project_id,
                description=description,
                priority=request.priority,
                case_type=request.case_type
            )

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
            "X-Accel-Buffering": "no"
        }
    )
