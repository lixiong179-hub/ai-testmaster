"""改进建议Mixin - 基于质量评估结果生成改进建议。
"""
from typing import Dict, Any, List, Optional
from loguru import logger

from app.services.case_quality.models import (
    ComplexityScore, RedundancyScore, CoverageScore, QualityReport,
)


class SuggestionMixin:

    def _generate_optimization_suggestions(
        self,
        complexity: ComplexityScore,
        redundancy: RedundancyScore,
        coverage: CoverageScore
    ) -> List[str]:
        suggestions = []

        if complexity.has_captcha:
            suggestions.append("用例包含验证码步骤，建议添加验证码自动识别或手动跳过机制")

        if not complexity.has_verification:
            suggestions.append("用例缺少验证步骤，建议添加断言以确认操作结果")

        if complexity.step_count > 10:
            suggestions.append("用例步骤过多，建议拆分为多个独立用例以提高可维护性")

        if complexity.level == "very_complex":
            suggestions.append("用例复杂度过高，建议简化操作流程或拆分子流程")

        if redundancy.similar_case_count > 0:
            suggestions.append(f"发现 {redundancy.similar_case_count} 个相似用例，建议合并或使用数据驱动方式")

        if redundancy.duplicate_step_count > 0:
            suggestions.append(f"发现 {redundancy.duplicate_step_count} 个重复步骤，建议提取为公共前置条件")

        if redundancy.level == "high":
            suggestions.append("用例冗余度较高，建议重构以减少重复")

        if coverage.coverage_rate < 0.5:
            suggestions.append(f"元素定位覆盖率仅 {coverage.coverage_rate:.0%}，建议补充元素定位信息")

        if coverage.uncovered_elements > 0:
            suggestions.append(f"有 {coverage.uncovered_elements} 个步骤缺少定位信息，建议批量录制")

        if coverage.level in ("low", "very_low"):
            suggestions.append("覆盖率较低，建议优先为核心步骤补充定位信息")

        return suggestions

    async def _generate_ai_suggestions(
        self,
        quality_report: QualityReport
    ) -> List[str]:
        ai_suggestions = []

        try:
            from app.utils.unified_vision_model import get_default_vision_model
            vision_model = get_default_vision_model()

            prompt = f"""请分析以下测试用例质量报告，给出优化建议：

复杂度: {quality_report.complexity.level if quality_report.complexity else 'unknown'} (得分: {quality_report.complexity.score if quality_report.complexity else 0})
冗余度: {quality_report.redundancy.level if quality_report.redundancy else 'unknown'} (得分: {quality_report.redundancy.score if quality_report.redundancy else 0})
覆盖率: {quality_report.coverage.level if quality_report.coverage else 'unknown'} (得分: {quality_report.coverage.score if quality_report.coverage else 0})

请给出3-5条具体的优化建议，每条建议一行。"""

            response = vision_model.analyze_text("", prompt)
            if response:
                lines = [line.strip() for line in response.split('\n') if line.strip()]
                for line in lines:
                    clean = line.lstrip('0123456789.-) ')
                    if clean:
                        ai_suggestions.append(clean)

        except Exception as e:
            logger.warning(f"AI建议生成失败: {e}")

        return ai_suggestions[:5]

    @staticmethod
    def _calculate_overall_score(
        complexity: ComplexityScore,
        redundancy: RedundancyScore,
        coverage: CoverageScore
    ) -> float:
        complexity_weight = 0.3
        redundancy_weight = 0.3
        coverage_weight = 0.4

        complexity_normalized = max(0, 10 - complexity.score) / 10
        redundancy_normalized = max(0, 10 - redundancy.score) / 10
        coverage_normalized = coverage.score / 10

        overall = (
            complexity_normalized * complexity_weight
            + redundancy_normalized * redundancy_weight
            + coverage_normalized * coverage_weight
        ) * 100

        return round(overall, 2)
