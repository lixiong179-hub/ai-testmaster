"""统一 Prompt 构建器包 - 合并所有 Prompt 构建逻辑为单一入口。

本包将项目中分散的 3 处 Prompt 构建逻辑统一合并：
1. case_generation_prompt_builder - 流程图/线性模式用例生成
2. test_case_generation.ai_prompt_builder - 测试用例 AI 生成
3. test_data.prompt_builder - 测试数据生成

同时整合 UI Spec 格式化函数和 UI 解析 Prompt 常量。

对外形态:
    builder = PromptBuilder()
    builder.for_test_case(mode='graph'|'linear') \\
        .with_requirement(req) \\
        .with_ui_specs(specs) \\
        .with_test_points(points) \\
        .with_flow(nodes, edges) \\
        .build() -> Dict[str, Any]

    builder.for_test_data() \\
        .with_case(case) \\
        .build() -> str
"""
from app.services.prompt_builder.builder import PromptBuilder
from app.services.prompt_builder.constants import (
    SINGLE_IMAGE_PROMPT,
    MULTI_IMAGE_FLOW_PROMPT,
    BATCH_SUMMARY_PROMPT,
    TEXT_STRUCTURE_PROMPT,
)
from app.services.prompt_builder.ui_spec_formatter import (
    format_ui_spec_for_prompt,
    format_ui_specs_list,
)
from app.services.prompt_builder.helpers import _safe_int, _find_main_step, _infer_condition, _render_flow_meta_hint, _group_edges_by_source

__all__ = [
    'PromptBuilder',
    'SINGLE_IMAGE_PROMPT',
    'MULTI_IMAGE_FLOW_PROMPT',
    'BATCH_SUMMARY_PROMPT',
    'TEXT_STRUCTURE_PROMPT',
    'format_ui_spec_for_prompt',
    'format_ui_specs_list',
]
