"""测试用例AI生成端点模块

本模块定义AI生成测试用例的全部非流式API端点，包含共享模型和辅助函数。
流式端点在 test_case_ai_stream.py 中定义。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /ai-generate                  - AI基础生成测试用例
    - POST /ai-generate-enhanced         - AI增强模式生成（旧接口）
    - POST /ai-enhanced-generate         - AI增强模式生成（重构版）
    - POST /generate-context             - 获取AI生成上下文
    - POST /generate-single              - 基于单个测试点生成
    - POST /ai-batch-generate            - AI批量生成（占位）
    - GET  /{case_id}/precondition-steps - 获取前置条件步骤
    - PUT  /{case_id}/precondition-steps - 批量保存前置条件步骤
    - POST /{case_id}/parse-precondition - AI解析前置条件

所有端点均需要Bearer令牌认证。
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, field_validator, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.constants import TestCasePriority
from app.core.exception import create_response
from app.db.database import get_db
from app.models.project import Project
from app.models.test_case import TestCase, TestCasePreconditionStep, TestStep
from app.models.user import User
from app.schemas.test_case import (
    FlowSortDataSchema,
    PreconditionStepBatchSave,
    PreconditionStepResponse,
)
from app.utils.ai_client import (
    AIServiceError,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError,
    generate_test_case,
    generate_test_case_enhanced,
    parse_precondition_to_steps,
)
from app.utils.test_case_helpers import build_test_case_response, convert_steps_to_response

router = APIRouter()

MAX_FLOW_NODES = 100
MAX_FLOW_EDGES = 200


# ── 共享辅助函数 ──────────────────────────────────────────


def _map_ai_priority_to_value(priority: str) -> int:
    """将AI返回优先级映射为数据库整数值。"""
    priority_map = {
        "high": TestCasePriority.HIGH.value,
        "medium": TestCasePriority.MEDIUM.value,
        "low": TestCasePriority.LOW.value,
    }
    return priority_map.get(priority, TestCasePriority.MEDIUM.value)


def _prepare_test_point(
    context: Dict[str, Any], description: str, priority: int
) -> Dict[str, Any]:
    """从上下文中提取或构造测试点信息。"""
    test_points = context.get("test_points", [])
    test_point = context.get("test_point", {}) or context.get("current_test_point", {})
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
    from app.services.prompt_builder import format_ui_spec_for_prompt
    spec_parts = []
    for spec_item in ui_specs:
        screen_name = spec_item.get("screen_name", "未命名页面")
        spec = spec_item.get("ui_spec", {})
        if spec:
            spec_parts.append(format_ui_spec_for_prompt(screen_name, spec))
    return "\n\n".join(spec_parts) if spec_parts else ""


def _build_graph_prompt_data(
    flow_sort_data: FlowSortDataSchema,
    context: Dict[str, Any], description: str, priority: int,
) -> Dict[str, Any]:
    """构建流程图模式所需的Prompt数据。"""
    from app.services.prompt_builder import PromptBuilder
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
    ui_specs = context.get("ui_specs", [])
    ui_specs_text = _build_ui_specs_text(ui_specs)
    test_point_json = json.dumps(test_point, ensure_ascii=False)
    graph_prompt = PromptBuilder.build_graph_prompt(
        nodes=nodes_list, edges=edges_list, module_info=module_info,
        requirement_content=context.get("requirement_content", ""),
        test_point_json=test_point_json, ui_specs_text=ui_specs_text,
        history_cases=context.get("history_cases"),
    )
    logger.info(f"流程图模式：接收到 {len(nodes_list)} 个节点，{len(edges_list)} 条连线")
    return {
        "requirement_content": context.get("requirement_content", ""),
        "ui_description": "",
        "ui_spec": ui_specs[0].get("ui_spec", {}) if ui_specs else {},
        "ui_specs": ui_specs, "test_point": test_point,
        "case_type": context.get("case_type"),
        "exec_mode": context.get("exec_mode", "all"),
        "project_config": context.get("project_config"),
        "graph_prompt": graph_prompt,
        "flow_validation": {"errors": errors, "warnings": warnings},
    }


def _build_linear_prompt_data(
    context: Dict[str, Any], description: str, priority: int,
    case_type: Optional[str], exec_mode: str,
) -> Dict[str, Any]:
    """构建线性模式所需的Prompt数据。"""
    test_point = _prepare_test_point(context, description, priority)
    raw_ui_desc = context.get("ui_description", "")
    ui_specs = context.get("ui_specs", [])
    return {
        "requirement_content": context.get("requirement_content", ""),
        "ui_description": raw_ui_desc,
        "ui_spec": ui_specs[0].get("ui_spec", {}) if ui_specs else {},
        "ui_specs": ui_specs, "test_point": test_point,
        "case_type": case_type, "exec_mode": exec_mode,
        "project_config": context.get("project_config"),
        "history_cases": context.get("history_cases"),
    }


def _format_case_response(
    generated_case: Dict[str, Any], project_id: int,
    description: str, priority: int, case_type: Optional[str],
) -> Dict[str, Any]:
    """格式化生成的测试用例为响应数据。"""
    if not isinstance(generated_case, dict):
        raise TypeError(
            f"_format_case_response 期望 generated_case 为 dict，实际类型: {type(generated_case).__name__}"
        )
    steps_data = convert_steps_to_response(generated_case.get("steps", []))
    return {
        "id": 0, "project_id": project_id,
        "case_no": f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "module": generated_case.get("module", "AI生成"),
        "title": generated_case.get("title", description[:50]),
        "precondition": generated_case.get("precondition", ""),
        "test_data": generated_case.get("test_data", {}),
        "steps": steps_data,
        "expected_result": generated_case.get("expected_result", ""),
        "priority": priority,
        "case_type": generated_case.get("case_type", case_type),
        "change_type": generated_case.get("change_type", "added"),
        "parent_case_id": generated_case.get("parent_case_id"),
        "generate_status": 1,
        "create_time": datetime.now().isoformat(),
    }


# ── 请求模型 ──────────────────────────────────────────────


class AIGenerateRequest(BaseModel):
    """AI基础生成请求。"""
    project_id: int
    description: str

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("描述不能为空且至少需要10个字符")
        if len(v) > 10000:
            raise ValueError(f"描述过长({len(v)}字符)，最大允许10000字符")
        return v.strip()


class AIGenerateEnhancedRequest(BaseModel):
    """AI增强模式生成请求。"""
    project_id: int
    description: str
    case_type: Optional[str] = None
    exec_mode: str = "all"
    priority: int = 2
    enhanced_mode: bool = True
    context: Optional[dict] = None
    ui_screen_ids: Optional[List[int]] = None
    mode: Literal["linear", "graph"] = Field(
        default="linear", description="排序模式：linear=线性/graph=流程图"
    )
    flow_sort_data: Optional[FlowSortDataSchema] = Field(
        None, description="流程图排序数据（graph模式必填）"
    )

    @field_validator("case_type")
    @classmethod
    def validate_case_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid_types = (
            "ui_automation", "manual", "api_automation", "performance",
            "security", "functional", "api_auto", "UI", "API",
        )
        if v not in valid_types:
            raise ValueError(f"不支持的用例类型: {v}")
        from app.core.constants import TestCaseType
        return TestCaseType.from_legacy(v).value

    @field_validator("exec_mode")
    @classmethod
    def validate_exec_mode(cls, v: str) -> str:
        valid_modes = ("all", "ui_auto", "manual")
        if v not in valid_modes:
            raise ValueError(f"不支持的执行模式: {v}")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError("描述不能为空且至少需要5个字符")
        if len(v) > 10000:
            raise ValueError(f"描述过长({len(v)}字符)，最大允许10000字符")
        return v.strip()

    @field_validator("flow_sort_data")
    @classmethod
    def validate_flow_sort_data_size(
        cls, v: Optional[FlowSortDataSchema]
    ) -> Optional[FlowSortDataSchema]:
        if v is None:
            return v
        if len(v.nodes) > MAX_FLOW_NODES:
            raise ValueError(f"nodes数量不能超过{MAX_FLOW_NODES}")
        if len(v.edges) > MAX_FLOW_EDGES:
            raise ValueError(f"edges数量不能超过{MAX_FLOW_EDGES}")
        return v


class GenerateContextRequest(BaseModel):
    """获取AI生成上下文请求。"""
    project_id: int
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    test_point_ids: Optional[List[int]] = None
    history_case_ids: Optional[List[int]] = None
    force_refresh: bool = False
    test_point_page: int = 1
    test_point_page_size: int = 100

    @field_validator("requirement_file_ids", "ui_file_ids", "ui_screen_ids", "test_point_ids")
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("项目ID必须大于0")
        return v


class SingleGenerateRequest(BaseModel):
    """基于单个测试点生成请求。"""
    project_id: int
    test_point_id: int
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    force_refresh: bool = False
    case_type: Optional[str] = None

    @field_validator("requirement_file_ids", "ui_file_ids", "ui_screen_ids")
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("项目ID必须大于0")
        return v

    @field_validator("test_point_id")
    @classmethod
    def validate_test_point_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("测试点ID必须大于0")
        return v


class BatchGenerateRequest(BaseModel):
    """AI批量生成请求。"""
    project_id: int
    test_point_ids: Optional[List[int]] = None
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    force_refresh: bool = False
    test_point_page: int = 1
    test_point_page_size: int = 100
    case_type: Optional[str] = None

    @field_validator("test_point_ids", "requirement_file_ids", "ui_file_ids", "ui_screen_ids")
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator("test_point_ids", "requirement_file_ids", "ui_file_ids", "ui_screen_ids")
    @classmethod
    def validate_list_size(cls, v: List[int] | None) -> List[int] | None:
        if v is not None and len(v) > 200:
            raise ValueError(f"列表长度不能超过200，当前: {len(v)}")
        return v

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("项目ID必须大于0")
        return v

    @field_validator("test_point_page")
    @classmethod
    def validate_page(cls, v: int) -> int:
        if v < 1:
            raise ValueError("页码必须大于等于1")
        return v

    @field_validator("test_point_page_size")
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        if v < 1 or v > 500:
            raise ValueError("每页数量必须在1-500之间")
        return v


# ── AI基础生成端点 ────────────────────────────────────────


@router.post("/ai-generate")
async def ai_generate_test_case(
    request_data: AIGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI基础生成测试用例（写入数据库）。"""
    project_id = request_data.project_id
    description = request_data.description
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    try:
        generated_case = generate_test_case(description)
        priority_value = _map_ai_priority_to_value(generated_case.get("priority", "medium"))
        new_test_case = TestCase(
            project_id=project_id, title=generated_case.get("title") or "(无标题)",
            precondition=generated_case.get("precondition", ""),
            expected_result=generated_case.get("expected_result", ""),
            priority=priority_value, module="AI生成",
            case_type=generated_case.get("case_type") or generated_case.get("test_category") or "manual",
            steps_json=generated_case.get("steps", []),
            case_no=f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            generate_status=1,
            test_category=generated_case.get("test_category", None),
        )
        db.add(new_test_case)
        db.flush()
        for i, step in enumerate(generated_case.get("steps", [])):
            action = step.get("action") or step.get("step") or f"步骤{i + 1}"
            expected_result = (
                step.get("expected_result") or step.get("param") or "预期结果正常"
            )
            test_step = TestStep(
                test_case_id=new_test_case.id, step_number=i + 1,
                action=action, expected_result=expected_result,
                action_type=step.get("action_type", ""),
                input_value=step.get("input_value", ""),
                target_element=step.get("target_element", ""),
                is_business_view=1, is_technical_view=1,
            )
            db.add(test_step)
        db.commit()
        db.refresh(new_test_case)
        return create_response(data=build_test_case_response(new_test_case))
    except AIAuthenticationError as e:
        db.rollback()
        logger.error(f"AI认证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI服务认证失败，请检查API密钥"
        )
    except AIRateLimitError as e:
        db.rollback()
        logger.error(f"AI请求频率限制: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AI服务请求频率过高，请稍后重试"
        )
    except AITimeoutError as e:
        db.rollback()
        logger.error(f"AI请求超时: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="AI服务请求超时，请稍后重试"
        )
    except (AIResponseFormatError, AIResponseParseError) as e:
        db.rollback()
        logger.error(f"AI响应错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="AI响应格式错误，请稍后重试"
        )
    except AIServiceError as e:
        db.rollback()
        logger.error(f"AI服务错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI服务暂时不可用"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"AI生成测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败"
        )


# ── AI增强模式生成端点 ────────────────────────────────────


@router.post("/ai-generate-enhanced")
async def ai_generate_test_case_enhanced(
    request_data: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI增强模式生成测试用例（旧接口，不写入数据库）。"""
    project_id = request_data.project_id
    description = request_data.description
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    try:
        context = request_data.context or {}
        logger.info(
            f"AI生成增强模式 - 接收到的context: "
            f"{json.dumps(context, ensure_ascii=False, default=str)[:500]}"
        )
        if request_data.mode == "graph" and request_data.flow_sort_data:
            prompt_data = _build_graph_prompt_data(
                flow_sort_data=request_data.flow_sort_data,
                context=context, description=description,
                priority=request_data.priority,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        elif request_data.enhanced_mode:
            prompt_data = _build_linear_prompt_data(
                context=context, description=description,
                priority=request_data.priority,
                case_type=request_data.case_type,
                exec_mode=request_data.exec_mode,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)
        response_data = _format_case_response(
            generated_case=generated_case, project_id=project_id,
            description=description, priority=request_data.priority,
            case_type=request_data.case_type,
        )
        return create_response(data=response_data)
    except AIAuthenticationError as e:
        db.rollback()
        logger.error(f"AI认证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI服务认证失败，请检查API密钥"
        )
    except AIRateLimitError as e:
        db.rollback()
        logger.error(f"AI请求频率限制: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AI服务请求频率过高，请稍后重试"
        )
    except AITimeoutError as e:
        db.rollback()
        logger.error(f"AI请求超时: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="AI服务请求超时，请稍后重试"
        )
    except (AIResponseFormatError, AIResponseParseError) as e:
        db.rollback()
        logger.error(f"AI响应错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="AI响应格式错误，请稍后重试"
        )
    except AIServiceError as e:
        db.rollback()
        logger.error(f"AI服务错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI服务暂时不可用"
        )
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败"
        )


@router.post("/ai-enhanced-generate")
async def ai_enhanced_generate(
    request: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI增强模式生成测试用例（重构版，不写入数据库）。"""
    project_id = request.project_id
    description = request.description
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if not description or len(description.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="描述不能为空且至少需要5个字符"
        )
    try:
        context = request.context or {}
        logger.info(
            f"AI生成增强模式 - 接收到的context: "
            f"{json.dumps(context, ensure_ascii=False, default=str)[:500]}"
        )
        if request.mode == "graph" and request.flow_sort_data:
            prompt_data = _build_graph_prompt_data(
                flow_sort_data=request.flow_sort_data,
                context=context, description=description,
                priority=request.priority,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        elif request.enhanced_mode:
            prompt_data = _build_linear_prompt_data(
                context=context, description=description,
                priority=request.priority, case_type=request.case_type,
                exec_mode=request.exec_mode,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)
        response_data = _format_case_response(
            generated_case=generated_case, project_id=project_id,
            description=description, priority=request.priority,
            case_type=request.case_type,
        )
        return create_response(data=response_data)
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败"
        )


# ── 上下文与单条生成端点 ─────────────────────────────────


@router.post("/generate-context", response_model=dict)
async def get_generation_context(
    request: GenerateContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取AI生成测试用例的上下文信息。"""
    project = db.query(Project).filter(
        Project.id == request.project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation_service import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    context = await service.get_context_for_generation(
        project_id=request.project_id, user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=request.test_point_ids,
        force_refresh=request.force_refresh,
        test_point_page=request.test_point_page,
        test_point_page_size=request.test_point_page_size,
    )
    test_points_count = len(context.get("test_points", []))
    if test_points_count == 0:
        logger.warning(f"项目 {request.project_id} 没有找到测试点")

    # 查询历史参考用例（仅限本项目、非删除、active状态）
    # None = 前端未指定，自动查全部；[] = 前端明确不选任何用例；有值 = 按指定查询
    history_cases = []
    if request.history_case_ids is None:
        # 自动查全部 active 用例
        cases = db.query(TestCase).filter(
            TestCase.project_id == request.project_id,
            TestCase.is_deleted == False,
            TestCase.lifecycle_status == 'active',
        ).order_by(TestCase.id).all()
    elif len(request.history_case_ids) > 0:
        cases = db.query(TestCase).filter(
            TestCase.id.in_(request.history_case_ids),
            TestCase.project_id == request.project_id,
            TestCase.is_deleted == False,
            TestCase.lifecycle_status == 'active',
        ).all()
    else:
        # [] = 明确不选，不查任何用例
        cases = []

    # 统一摘要格式：每条用例给 title + summary + steps概要，控制单条长度
    for c in cases:
        steps = c.steps_json or []
        steps_summary = ""
        if isinstance(steps, list) and steps:
            # 只取前3步的 action，拼接为一句话
            actions = [s.get("action", s.get("description", "")) for s in steps[:3]]
            steps_summary = " → ".join(a for a in actions if a)
        history_cases.append({
            "id": c.id,
            "case_no": c.case_no,
            "module": c.module or "",
            "title": c.title,
            "summary": (c.summary or steps_summary or "")[:150],
            "expected_result": (c.expected_result or "")[:100],
        })

    project_config = {
        "project_name": project.name,
        "project_type": project.project_type or "web",
    }
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
        "history_cases": history_cases,
        "message": f"获取成功：{test_points_count}个测试点",
    })


@router.post("/generate-single")
async def generate_single_test_case(
    request: SingleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """基于单个测试点AI生成测试用例。"""
    project = db.query(Project).filter(
        Project.id == request.project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation_service import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    context = await service.get_context_for_generation(
        project_id=request.project_id, user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=[request.test_point_id],
    )
    test_points = context.get("test_points", [])
    if not test_points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"没有找到ID为{request.test_point_id}的测试点",
        )
    test_point = test_points[0]
    try:
        generated_case = await service.generate_test_case_for_point(
            context=context, test_point=test_point,
            project_id=request.project_id, case_type=request.case_type,
        )
        saved_case = await service._save_test_case(
            project_id=request.project_id,
            generated_case=generated_case, test_point=test_point,
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
            "message": "测试用例生成成功",
        })
    except Exception as e:
        db.rollback()
        logger.error(f"生成测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成失败"
        )


# ── 批量生成端点（占位） ─────────────────────────────────


@router.post("/ai-batch-generate")
async def ai_batch_generate_test_cases(
    request: BatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI批量生成测试用例（占位，请使用流式端点）。"""
    raise NotImplementedError(
        "批量生成功能暂未实现，请使用 /batch-generate/stream 流式端点"
    )


# ── 前置条件端点 ──────────────────────────────────────────


@router.get("/{case_id}/precondition-steps")
async def get_precondition_steps(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取前置条件步骤列表。"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    steps = db.query(TestCasePreconditionStep).filter(
        TestCasePreconditionStep.test_case_id == case_id
    ).order_by(TestCasePreconditionStep.step_number).all()
    return create_response(data=[PreconditionStepResponse.model_validate(s) for s in steps])


@router.put("/{case_id}/precondition-steps")
async def batch_save_precondition_steps(
    case_id: int,
    request: PreconditionStepBatchSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量保存前置条件步骤（覆盖式保存）。"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    db.query(TestCasePreconditionStep).filter(
        TestCasePreconditionStep.test_case_id == case_id
    ).delete()
    for i, step_data in enumerate(request.steps):
        step = TestCasePreconditionStep(
            test_case_id=case_id,
            step_number=step_data.step_number or (i + 1),
            action=step_data.action,
            expected_result=step_data.expected_result or "",
            action_type=step_data.action_type,
            input_value=step_data.input_value,
            target_element=step_data.target_element,
            has_locator=0, locator_status="pending",
        )
        db.add(step)
    db.commit()
    steps = db.query(TestCasePreconditionStep).filter(
        TestCasePreconditionStep.test_case_id == case_id
    ).order_by(TestCasePreconditionStep.step_number).all()
    return create_response(data=[PreconditionStepResponse.model_validate(s) for s in steps])


@router.post("/{case_id}/parse-precondition")
async def parse_precondition(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI解析前置条件为可执行步骤。"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    if not test_case.precondition:
        return create_response(data=[], msg="前置条件为空，无需解析")
    project_url = ""
    if test_case.project_id:
        proj = db.query(Project).filter(Project.id == test_case.project_id).first()
        if proj:
            project_url = getattr(proj, "test_object_url", "") or ""
    try:
        steps = await parse_precondition_to_steps(
            precondition_text=test_case.precondition, project_url=project_url,
        )
        if steps:
            db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == case_id
            ).delete()
            for i, step_data in enumerate(steps):
                pc_step = TestCasePreconditionStep(
                    test_case_id=case_id,
                    step_number=step_data.get("step_number", i + 1),
                    action=step_data.get("action", ""),
                    expected_result=step_data.get("expected_result", ""),
                    action_type=step_data.get("action_type", ""),
                    input_value=step_data.get("input_value", ""),
                    target_element=step_data.get("target_element", ""),
                    has_locator=0, locator_status="pending",
                )
                db.add(pc_step)
            db.commit()
            saved_steps = db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == case_id
            ).order_by(TestCasePreconditionStep.step_number).all()
            return create_response(
                data=[PreconditionStepResponse.model_validate(s) for s in saved_steps],
                msg=f"解析成功，生成 {len(steps)} 个步骤",
            )
        return create_response(data=[], msg="解析成功，但未生成步骤")
    except Exception as e:
        logger.error(f"AI解析前置条件失败: {e}")
        raise HTTPException(status_code=500, detail="AI解析前置条件失败")


class PreviewGraphPromptRequest(BaseModel):
    """Graph Prompt 预览请求体。"""
    flow_sort_data: FlowSortDataSchema = Field(..., description="流程编排数据")
    context: Dict[str, Any] = Field(default_factory=dict, description="AI生成上下文")


class PreviewGraphPromptResponse(BaseModel):
    """Graph Prompt 预览响应体。"""
    graph_prompt: str = Field(..., description="构建完成的Graph Prompt文本")
    node_count: int = Field(..., description="节点总数")
    edge_count: int = Field(..., description="连线总数")
    main_count: int = Field(..., description="主干节点数")
    branch_count: int = Field(..., description="分支节点数")
    exception_count: int = Field(..., description="异常节点数")
    bypass_count: int = Field(..., description="旁路节点数")
    errors: List[Dict[str, str]] = Field(default_factory=list, description="结构校验错误")
    warnings: List[Dict[str, str]] = Field(default_factory=list, description="结构校验警告")


@router.post("/preview-graph-prompt", response_model=PreviewGraphPromptResponse)
async def preview_graph_prompt(
    request: PreviewGraphPromptRequest,
    current_user: User = Depends(get_current_user),
):
    """预览 Graph Prompt 文本，不实际调用 AI。

    用于用户在生成前查看提交给 AI 的完整流程描述。
    """
    try:
        from app.services.prompt_builder.case_prompt import _build_graph_prompt
        from app.services.flow_validation import validate_flow_structure

        nodes_list = [n.model_dump() for n in request.flow_sort_data.nodes]
        edges_list = [e.model_dump() for e in request.flow_sort_data.edges]
        module_info = request.flow_sort_data.module_info

        raw_errors, raw_warnings = validate_flow_structure(nodes_list, edges_list)

        flow_type_counts = {"main": 0, "branch": 0, "exception": 0, "bypass": 0}
        for node in nodes_list:
            t = node.get("flow_type", "main")
            if t in flow_type_counts:
                flow_type_counts[t] += 1

        graph_prompt = _build_graph_prompt(
            nodes=nodes_list,
            edges=edges_list,
            module_info=module_info,
            requirement_content=request.context.get("requirement_content", ""),
            test_point_json=json.dumps(
                request.context.get("test_point", {}), ensure_ascii=False
            ),
            ui_specs_text=request.context.get("ui_specs_text", ""),
        )

        return PreviewGraphPromptResponse(
            graph_prompt=graph_prompt,
            node_count=len(nodes_list),
            edge_count=len(edges_list),
            main_count=flow_type_counts["main"],
            branch_count=flow_type_counts["branch"],
            exception_count=flow_type_counts["exception"],
            bypass_count=flow_type_counts["bypass"],
            errors=[{"msg": e} for e in raw_errors],
            warnings=[{"msg": w} for w in raw_warnings],
        )
    except Exception as e:
        logger.error(f"预览Graph Prompt失败: {e}")
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")
