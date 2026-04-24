"""
测试用例AI生成端点模块

本模块定义AI生成测试用例的API端点，包括基础生成和增强模式生成。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /ai-generate         - AI生成测试用例
    - POST /ai-generate-enhanced - AI增强模式生成测试用例

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - AI生成调用DeepSeek API，需配置DEEPSEEK_API_KEY
    - 增强模式支持上下文注入（需求内容/UI描述/测试点）
"""
from typing import Optional, List, Literal
from datetime import datetime
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator, Field
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.utils.ai_client import (
    generate_test_case,
    generate_test_case_enhanced,
    AIServiceError,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError
)
from app.utils.test_case_helpers import convert_steps_to_response
from app.utils.test_case_helpers import build_test_case_response
from app.core.exception import create_response
from app.core.constants import TestCasePriority
from app.schemas.test_case import FlowSortDataSchema
from loguru import logger

router = APIRouter()


def _map_ai_priority_to_value(priority: str) -> int:
    """将AI返回优先级映射为数据库整数值（保持兼容默认中优先级）。"""
    priority_map = {
        "high": TestCasePriority.HIGH.value,
        "medium": TestCasePriority.MEDIUM.value,
        "low": TestCasePriority.LOW.value,
    }
    return priority_map.get(priority, TestCasePriority.MEDIUM.value)


class AIGenerateRequest(BaseModel):
    project_id: int
    description: str

    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('描述不能为空且至少需要10个字符')
        if len(v) > 10000:
            raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')
        return v.strip()


@router.post("/ai-generate")
async def ai_generate_test_case(
    request_data: AIGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI生成测试用例"""
    project_id = request_data.project_id
    description = request_data.description

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    try:
        generated_case = generate_test_case(description)

        priority_value = _map_ai_priority_to_value(generated_case["priority"])

        new_test_case = TestCase(
            project_id=project_id,
            title=generated_case["title"],
            precondition=generated_case.get("precondition", ""),
            expected_result=generated_case.get("expected_result", ""),
            priority=priority_value,
            module="AI生成",
            case_type=generated_case.get("case_type") or generated_case.get("test_category") or "manual",
            steps_json=generated_case.get("steps", []),
            case_no=f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            generate_status=1,
            test_category=generated_case.get("test_category", None)
        )

        db.add(new_test_case)
        db.flush()

        for i, step in enumerate(generated_case.get("steps", [])):
            if "action" in step:
                action = step["action"]
            elif "step" in step:
                action = step["step"]
            else:
                action = f"步骤{i + 1}"

            if "expected_result" in step:
                expected_result = step["expected_result"]
            elif "param" in step:
                expected_result = step["param"]
            else:
                expected_result = "预期结果正常"

            test_step = TestStep(
                test_case_id=new_test_case.id,
                step_number=i + 1,
                action=action,
                expected_result=expected_result,
                action_type=step.get("action_type", ""),
                input_value=step.get("input_value", ""),
                target_element=step.get("target_element", ""),
                is_business_view=1,
                is_technical_view=1
            )
            db.add(test_step)

        db.commit()
        db.refresh(new_test_case)

        return create_response(data=build_test_case_response(new_test_case))
    except AIAuthenticationError as e:
        db.rollback()
        logger.error(f"AI认证失败: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI服务认证失败，请检查API密钥")
    except AIRateLimitError as e:
        db.rollback()
        logger.error(f"AI请求频率限制: {e}")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AI服务请求频率过高，请稍后重试")
    except AITimeoutError as e:
        db.rollback()
        logger.error(f"AI请求超时: {e}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="AI服务请求超时，请稍后重试")
    except (AIResponseFormatError, AIResponseParseError) as e:
        db.rollback()
        logger.error(f"AI响应错误: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI响应格式错误，请稍后重试")
    except AIServiceError as e:
        db.rollback()
        logger.error(f"AI服务错误: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI服务暂时不可用")
    except Exception as e:
        db.rollback()
        logger.error(f"AI生成测试用例失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败")


class AIGenerateEnhancedRequest(BaseModel):
    project_id: int
    description: str
    case_type: Optional[str] = None
    exec_mode: str = "all"
    priority: int = 2
    enhanced_mode: bool = True
    context: Optional[dict] = None
    ui_screen_ids: Optional[List[int]] = None
    mode: Literal['linear', 'graph'] = Field(default='linear', description="排序模式：linear=线性/graph=流程图")
    flow_sort_data: Optional[FlowSortDataSchema] = Field(None, description="流程图排序数据（graph模式必填）")

    @field_validator('case_type')
    @classmethod
    def validate_case_type(cls, v):
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
    def validate_exec_mode(cls, v):
        valid_modes = ('all', 'ui_auto', 'manual')
        if v not in valid_modes:
            raise ValueError(f'不支持的执行模式: {v}')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 5:
            raise ValueError('描述不能为空且至少需要5个字符')
        if len(v) > 10000:
            raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')
        return v.strip()


@router.post("/ai-generate-enhanced")
async def ai_generate_test_case_enhanced(
    request_data: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI增强模式生成测试用例"""
    project_id = request_data.project_id
    description = request_data.description

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    try:
        context = request_data.context or {}
        logger.info(f"AI生成增强模式 - 接收到的context: {json.dumps(context, ensure_ascii=False, default=str)[:500]}")

        if request_data.enhanced_mode:
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
                    'priority': request_data.priority
                }

            raw_ui_desc = context.get('ui_description', '')
            ui_specs = context.get('ui_specs', [])

            ai_context = {
                'requirement_content': context.get('requirement_content', ''),
                'ui_description': raw_ui_desc,
                'ui_spec': ui_specs[0].get('ui_spec', {}) if ui_specs else {},
                'ui_specs': ui_specs,
                'test_point': test_point,
                'case_type': request_data.case_type,
                'exec_mode': request_data.exec_mode,
                'project_config': context.get('project_config')
            }

            if request_data.mode == 'graph' and request_data.flow_sort_data:
                from app.services.case_generation_prompt_builder import PromptBuilder

                logger.info(
                    f"AI生成增强模式 - graph模式: "
                    f"nodes={len(request_data.flow_sort_data.nodes)}, "
                    f"edges={len(request_data.flow_sort_data.edges)}"
                )

                ui_specs_text = ""
                if ui_specs:
                    ui_specs_parts = []
                    for idx, spec in enumerate(ui_specs, 1):
                        spec_data = spec.get('ui_spec', {})
                        ui_specs_parts.append(
                            f"屏幕 {idx}: {json.dumps(spec_data, ensure_ascii=False, default=str)}"
                        )
                    ui_specs_text = "\n".join(ui_specs_parts)

                graph_prompt = PromptBuilder.build_graph_prompt(
                    nodes=[n.model_dump() for n in request_data.flow_sort_data.nodes],
                    edges=[e.model_dump() for e in request_data.flow_sort_data.edges],
                    module_info=request_data.flow_sort_data.module_info,
                    requirement_content=context.get('requirement_content', ''),
                    test_point_json=json.dumps(test_point, ensure_ascii=False),
                    ui_specs_text=ui_specs_text
                )
                ai_context['graph_prompt'] = graph_prompt
                logger.info(f"AI生成增强模式 - graph_prompt长度: {len(graph_prompt)}字符")

            generated_case = await asyncio.to_thread(generate_test_case_enhanced, ai_context)
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)

        priority_value = request_data.priority

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI生成失败"
        )
