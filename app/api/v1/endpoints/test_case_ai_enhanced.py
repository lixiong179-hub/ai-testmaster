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
from typing import Optional, List
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
from loguru import logger

router = APIRouter()


class AIGenerateEnhancedRequest(BaseModel):
    project_id: int
    description: str
    case_type: Optional[str] = None
    exec_mode: str = "all"
    priority: int = 2
    enhanced_mode: bool = True
    context: Optional[dict] = None
    ui_screen_ids: Optional[List[int]] = None

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

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if not description or len(description.strip()) < 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="描述不能为空且至少需要5个字符")

    try:
        context = request.context or {}
        logger.info(f"AI生成增强模式 - 接收到的context: {json.dumps(context, ensure_ascii=False, default=str)[:500]}")

        if request.enhanced_mode:
            test_points = context.get('test_points', [])
            test_point = context.get('test_point', {}) or context.get('current_test_point', {})
            logger.info(f"AI生成增强模式 - 解析后的test_point: {test_point}")
            if not test_point and test_points:
                test_point = test_points[0]
            if not test_point:
                test_point = {
                    'module': 'AI生成',
                    'function': '测试场景',
                    'point': description,
                    'priority': request.priority
                }

            raw_ui_desc = context.get('ui_description', '')
            ui_specs = context.get('ui_specs', [])

            generated_case = await asyncio.to_thread(generate_test_case_enhanced, {
                'requirement_content': context.get('requirement_content', ''),
                'ui_description': raw_ui_desc,
                'ui_spec': ui_specs[0].get('ui_spec', {}) if ui_specs else {},
                'ui_specs': ui_specs,
                'test_point': test_point,
                'case_type': request.case_type,
                'exec_mode': request.exec_mode,
                'project_config': context.get('project_config')
            })
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)

        priority_value = request.priority
        steps_data = convert_steps_to_response(generated_case.get("steps", []))

        return create_response(data={
            "id": 0,
            "project_id": project_id,
            "case_no": f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "module": generated_case.get("module", "AI生成"),
            "title": generated_case.get("title", description[:50]),
            "precondition": generated_case.get("precondition", ""),
            "test_data": generated_case.get("test_data", {}),
            "steps": steps_data,
            "expected_result": generated_case.get("expected_result", ""),
            "priority": priority_value,
            "case_type": generated_case.get("case_type", request_data.case_type),
            "generate_status": 1,
            "create_time": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI生成失败: {str(e)}")


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
