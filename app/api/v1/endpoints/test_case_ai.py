"""测试用例AI生成端点模块（聚合入口）

本模块为AI生成测试用例的聚合入口，将生成端点和Prompt预览端点统一注册到同一路由前缀下。
流式端点在 test_case_ai_stream.py 中定义。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

子模块概览:
    - test_case_ai_helpers: 共享辅助函数
    - test_case_ai_schemas: 请求/响应Pydantic模型
    - test_case_ai_generate: 生成端点（基础/增强/上下文/单条/批量/前置条件）
    - test_case_ai_preview: Prompt预览端点

端点概览:
    - POST /ai-generate                  - AI基础生成测试用例
    - POST /ai-enhanced-generate         - AI增强模式生成
    - POST /generate-context             - 获取AI生成上下文
    - POST /generate-single              - 基于单个测试点生成
    - POST /ai-batch-generate            - AI批量生成（占位）
    - GET  /{case_id}/precondition-steps - 获取前置条件步骤
    - PUT  /{case_id}/precondition-steps - 批量保存前置条件步骤
    - POST /{case_id}/parse-precondition - AI解析前置条件
    - POST /preview-graph-prompt         - 预览Graph Prompt文本

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter

from app.api.v1.endpoints.test_case_ai_generate import router as generate_router
from app.api.v1.endpoints.test_case_ai_preview import router as preview_router

# ── 向后兼容导出：供 test_case_ai_stream.py 及测试文件直接引用 ──
from app.api.v1.endpoints.test_case_ai_helpers import (
    _prepare_test_point,
    _build_ui_specs_text,
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
)
from app.api.v1.endpoints.test_case_ai_schemas import (
    AIGenerateRequest,
    AIGenerateEnhancedRequest,
    GenerateContextRequest,
    SingleGenerateRequest,
    BatchGenerateRequest,
    MAX_FLOW_NODES,
    MAX_FLOW_EDGES,
)
from app.api.v1.endpoints.test_case_ai_preview import (
    PreviewGraphPromptRequest,
    PreviewGraphPromptResponse,
)

__all__ = [
    "_prepare_test_point",
    "_build_ui_specs_text",
    "_build_graph_prompt_data",
    "_build_linear_prompt_data",
    "_format_case_response",
    "AIGenerateRequest",
    "AIGenerateEnhancedRequest",
    "GenerateContextRequest",
    "SingleGenerateRequest",
    "BatchGenerateRequest",
    "MAX_FLOW_NODES",
    "MAX_FLOW_EDGES",
    "PreviewGraphPromptRequest",
    "PreviewGraphPromptResponse",
]

# 主路由：聚合生成端点和预览端点
router = APIRouter()
router.include_router(generate_router)
router.include_router(preview_router)
