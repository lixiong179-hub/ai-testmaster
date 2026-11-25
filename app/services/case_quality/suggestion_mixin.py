"""改进建议Mixin - 基于多维质量评估结果生成改进建议。

综合评分权重调整：
    复杂度 0.3 + 冗余度 0.3 + 覆盖度 0.4（覆盖度内部已按三维度加权）
"""

from loguru import logger

from app.services.case_quality.models import (
    ComplexityScore,
    RedundancyScore,
    CoverageScore,
    QualityReport,
)


def _complexity_suggestions(complexity: ComplexityScore) -> list[str]:
    """复杂度相关建议（验证码 / 缺验证 / 步骤过多 / 复杂度过高）。"""
    suggestions: list[str] = []
    if complexity.has_captcha:
        suggestions.append("用例包含验证码步骤，建议添加验证码自动识别或手动跳过机制")
    if not complexity.has_verification:
        suggestions.append("用例缺少验证步骤，建议添加断言以确认操作结果")
    if complexity.step_count > 6:
        suggestions.append("用例步骤过多，步骤偏多（>6步），建议检查是否混合了多个测试场景，考虑拆分为独立用例")
    if complexity.level == "very_complex":
        suggestions.append("用例复杂度过高，建议简化操作流程或拆分子流程")
    return suggestions


def _redundancy_suggestions(redundancy: RedundancyScore) -> list[str]:
    """冗余度相关建议（相似用例 / 重复步骤 / 冗余等级高）。"""
    suggestions: list[str] = []
    if redundancy.similar_case_count > 0:
        suggestions.append(f"发现 {redundancy.similar_case_count} 个相似用例，建议合并或使用数据驱动方式")
    if redundancy.duplicate_step_count > 0:
        suggestions.append(f"发现 {redundancy.duplicate_step_count} 个重复步骤，建议提取为公共前置条件")
    if redundancy.level == "high":
        suggestions.append("用例冗余度较高，建议重构以减少重复")
    return suggestions


def _requirement_coverage_suggestions(coverage: CoverageScore) -> list[str]:
    """需求覆盖率建议：无测试点数据 / 未关联测试点 / 覆盖率不足。"""
    req_rate = coverage.requirement_coverage_rate
    req_details = coverage.requirement_details
    if req_details.get("project_total_test_points", 0) <= 0:
        return ["项目暂无测试点数据，建议先导入需求并提取测试点"]
    if not req_details.get("has_test_point_link", False):
        return ["用例未关联测试点，建议绑定需求测试点以提升需求覆盖率"]
    if req_rate < 1.0:
        return [f"需求覆盖率为 {req_rate:.0%}，建议补充关联测试点"]
    return []


def _ui_coverage_suggestions(coverage: CoverageScore) -> list[str]:
    """UI 元素覆盖率建议：无原型数据 / 步骤缺 target_element / 命中率偏低。"""
    ui_rate = coverage.ui_element_coverage_rate
    ui_details = coverage.ui_element_details
    if ui_details.get("total_ui_labels", 0) <= 0:
        return ["项目暂无UI原型解析数据，建议上传UI原型图并解析"]
    steps_with_target = ui_details.get("steps_with_target", 0)
    matched_steps = ui_details.get("matched_steps", 0)
    if steps_with_target == 0:
        return ["步骤缺少目标元素描述(target_element)，建议补充以提升UI元素覆盖率"]
    if ui_rate < 0.5:
        return [
            f"UI元素覆盖率仅 {ui_rate:.0%}（{matched_steps}/{steps_with_target} 步骤命中），"
            f"建议检查步骤目标元素与UI原型的一致性"
        ]
    return []


def _locator_suggestions(coverage: CoverageScore) -> list[str]:
    """locator 覆盖建议：缺定位步骤多且覆盖率低 / 综合覆盖率低。"""
    loc_rate = coverage.locator_coverage_rate
    suggestions: list[str] = []
    if coverage.uncovered_elements > 0 and loc_rate < 0.5:
        suggestions.append(
            f"元素定位覆盖率仅 {loc_rate:.0%}，有 {coverage.uncovered_elements} 个步骤缺少定位信息，建议批量录制"
        )
    if coverage.level in ("low", "very_low") and loc_rate < 0.3:
        suggestions.append("综合覆盖率较低，建议优先为核心步骤补充定位信息")
    return suggestions


class SuggestionMixin:
    def _generate_optimization_suggestions(
        self, complexity: ComplexityScore, redundancy: RedundancyScore, coverage: CoverageScore
    ) -> list[str]:
        """基于三维度覆盖率生成改进建议。

        Args:
            complexity: 复杂度评分。
            redundancy: 冗余度评分。
            coverage: 覆盖率评分（含三维度分解）。

        Returns:
            List[str]: 改进建议列表。
        """
        return [
            *_complexity_suggestions(complexity),
            *_redundancy_suggestions(redundancy),
            *_requirement_coverage_suggestions(coverage),
            *_ui_coverage_suggestions(coverage),
            *_locator_suggestions(coverage),
        ]

    async def _generate_ai_suggestions(self, quality_report: QualityReport) -> list[str]:
        """基于AI模型生成优化建议。

        Args:
            quality_report: 质量报告。

        Returns:
            List[str]: AI生成的优化建议列表（最多5条）。
        """
        aiSuggestions: list[str] = []

        try:
            from app.utils.unified_vision_model import get_default_vision_model

            visionModel = get_default_vision_model()

            coverage = quality_report.coverage
            coverageInfo = ""
            if coverage:
                coverageInfo = (
                    f"需求覆盖率: {coverage.requirement_coverage_rate:.0%}, "
                    f"UI元素覆盖率: {coverage.ui_element_coverage_rate:.0%}, "
                    f"定位覆盖率: {coverage.locator_coverage_rate:.0%}, "
                    f"综合覆盖率: {coverage.coverage_rate:.0%}"
                )

            prompt = f"""请分析以下测试用例质量报告，给出优化建议：

复杂度: {quality_report.complexity.level if quality_report.complexity else "unknown"} (得分: {quality_report.complexity.score if quality_report.complexity else 0})
冗余度: {quality_report.redundancy.level if quality_report.redundancy else "unknown"} (得分: {quality_report.redundancy.score if quality_report.redundancy else 0})
覆盖率: {quality_report.coverage.level if quality_report.coverage else "unknown"} (综合得分: {quality_report.coverage.score if quality_report.coverage else 0})
{coverageInfo}

请给出3-5条具体的优化建议，每条建议一行。"""

            response = visionModel.analyze_text("", prompt)
            if response:
                lines = [line.strip() for line in response.split("\n") if line.strip()]
                for line in lines:
                    clean = line.lstrip("0123456789.-) ")
                    if clean:
                        aiSuggestions.append(clean)

        except Exception as e:
            logger.warning(f"AI建议生成失败: {e}")

        return aiSuggestions[:5]

    @staticmethod
    def _calculate_overall_score(
        complexity: ComplexityScore, redundancy: RedundancyScore, coverage: CoverageScore
    ) -> float:
        """计算综合评分。

        权重分配 v2（重校准）：复杂度 0.2 + 冗余度 0.4 + 覆盖度 0.4

        权重设计 rationale：
            - 冗余度高 = 真实浪费（重复用例可合并/数据驱动化），应严格扣分 → 0.4
            - 复杂度高未必是问题（端到端集成用例本就需要多步骤），权重压低 → 0.2
            - 覆盖度是综合三维度的复合指标，保持最高权重 → 0.4

        覆盖度内部已按 requirement(0.3) + ui_element(0.3) + locator(0.4) 加权，
        此处直接使用 coverage.score（0~10）。

        Args:
            complexity: 复杂度评分。
            redundancy: 冗余度评分。
            coverage: 覆盖率评分。

        Returns:
            float: 综合评分 0~100。
        """
        COMPLEXITY_WEIGHT = 0.2
        REDUNDANCY_WEIGHT = 0.4
        COVERAGE_WEIGHT = 0.4

        complexityNormalized = max(0, 10 - complexity.score) / 10
        redundancyNormalized = max(0, 10 - redundancy.score) / 10
        coverageNormalized = coverage.score / 10

        overall = (
            complexityNormalized * COMPLEXITY_WEIGHT
            + redundancyNormalized * REDUNDANCY_WEIGHT
            + coverageNormalized * COVERAGE_WEIGHT
        ) * 100

        return round(overall, 2)
