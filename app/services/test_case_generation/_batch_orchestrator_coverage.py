"""test_case_generation - 批量生成编排器的类型覆盖补全 Mixin。

从 batch_orchestrator.py 拆分，提供 CoverageEnhancementMixin，负责：
检测候选用例的类型覆盖缺失并补充生成缺失类型的用例。

供 BatchOrchestrator 通过多继承组合使用，依赖宿主类在 __init__ 中
注入 self._ai_generator（提供 _build_ui_description）。
"""
from typing import Any, Dict, List

from loguru import logger


class CoverageEnhancementMixin:
    """类型覆盖补全 Mixin。

    职责：
        _enhance_coverage_for_point: 检测类型覆盖缺失并补充生成缺失类型的用例

    依赖宿主类（BatchOrchestrator）在 __init__ 中注入 self._ai_generator
    （提供 _build_ui_description）。
    """

    # ── 类型覆盖补全（合并自 _coverage_enhancement_mixin） ──
    async def _enhance_coverage_for_point(
        self,
        candidate_cases: List[Dict[str, Any]],
        test_point: Dict[str, Any],
        point_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """检测类型覆盖缺失并补充生成缺失类型的用例。

        并发安全：point_context 已由调用方深拷贝，candidate_cases 为本测试点
        独有，generate_supplemental_cases 为纯函数不修改入参，故无需额外隔离。
        补全失败不影响主流程，仅记录告警并返回原候选列表。
        """
        from app.services.case_quality.coverage_service import (
            detect_missing_categories,
            generate_supplemental_cases,
        )
        from app.services.test_case_generation.ai_generator import _get_openai_client

        missing = detect_missing_categories(candidate_cases)
        if not missing:
            return candidate_cases

        try:
            ui_description = self._ai_generator._build_ui_description(
                point_context.get("ui_descriptions", [])
            )
            has_ui = bool(ui_description and ui_description.strip()) or bool(
                point_context.get("ui_specs", [])
            )
            supplemental_context: Dict[str, Any] = {
                "prd_content": point_context.get("requirement_content", ""),
                "ui_description": ui_description,
                "ui_specs": point_context.get("ui_specs", []),
                "existing_titles": [c.get("title", "") for c in candidate_cases],
                "has_ui": has_ui,
                "iteration_id": None,
            }
            supplemental = generate_supplemental_cases(
                missing_categories=missing,
                test_point=test_point,
                context=supplemental_context,
                ai_client=_get_openai_client(),
            )
            if supplemental:
                logger.info(
                    "批量生成覆盖补全 tp_id={} 补充{}条缺失类型用例: {}",
                    test_point.get("id"), len(supplemental), missing,
                )
                return candidate_cases + supplemental
        except (AttributeError, RuntimeError, ValueError, TypeError) as e:
            logger.warning(
                "批量生成覆盖补全失败 tp_id={} {}: {}",
                test_point.get("id"), type(e).__name__, e,
            )
        return candidate_cases
