"""测试用例AI生成 - Prompt预览端点模块

本模块定义AI生成测试用例的Prompt预览端点，用于用户在生成前查看提交给AI的完整流程描述。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /preview-graph-prompt - 预览Graph Prompt文本

所有端点均需要Bearer令牌认证。
"""
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.test_case import FlowSortDataSchema


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


router = APIRouter()


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
            history_cases=request.context.get("history_cases"),
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
        raise HTTPException(status_code=500, detail="预览失败")
