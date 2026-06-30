"""用例类型覆盖检测与补充生成 - 向后兼容代理模块。

核心实现已迁移到 app.services.case_quality.coverage_service，本文件仅保留
向后兼容的导入与 _generate_supplemental 适配器，确保 Pipeline 现有调用
（_classify_case_type / _check_type_coverage / _generate_supplemental /
_append_supplement_examples）行为完全不变。

迁移原因：覆盖补全逻辑需同时服务 Pipeline 和批量生成流程，提取为纯函数
消除重复，详见 coverage_service 模块文档。
"""
from typing import Any, Dict, List, Optional

from app.pipelines.context import PipelineContext
from app.services.case_quality.coverage_service import (
    classify_case_type,
    detect_missing_categories,
    append_supplement_examples,
    generate_supplemental_cases,
)

# 向后兼容别名：保持 Pipeline 现有 import 语句不变
_classify_case_type = classify_case_type
_check_type_coverage = detect_missing_categories
_append_supplement_examples = append_supplement_examples


def _generate_supplemental(
    ctx: PipelineContext,
    tp: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    missing_types: List[str],
    existing_titles: List[str],
    has_ui: bool,
) -> Optional[List[Dict[str, Any]]]:
    """Pipeline 适配器：将 ctx 风格入参转换为 coverage_service 纯函数调用。

    行为与迁移前完全一致：缺失为空或生成失败时返回 None，
    成功时返回补充用例列表。
    """
    context: Dict[str, Any] = {
        "prd_content": prd_content,
        "ui_description": ui_description,
        "ui_specs": ui_specs,
        "existing_titles": existing_titles,
        "has_ui": has_ui,
        "iteration_id": ctx.iteration_id,
    }
    result = generate_supplemental_cases(
        missing_categories=missing_types,
        test_point=tp,
        context=context,
        ai_client=ctx.get_ai_client(),
    )
    return result if result else None


__all__ = [
    "_classify_case_type",
    "_check_type_coverage",
    "_append_supplement_examples",
    "_generate_supplemental",
]
