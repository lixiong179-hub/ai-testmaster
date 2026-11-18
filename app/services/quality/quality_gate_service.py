"""QualityGate 统一校验编排服务。

编排6个独立校验器执行校验，合并结果，支持从 QualityRuleConfig
读取项目级规则覆盖默认值。

合并规则: 取所有校验器中最严重的状态
    rejected > pending_review > warning > passed
"""

from loguru import logger
from sqlalchemy.orm import Session

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationResult,
)
from app.services.quality.validators.case_validator import CaseValidator
from app.services.quality.validators.update_suggestion_validator import UpdateSuggestionValidator
from app.services.quality.validators.import_result_validator import ImportResultValidator
from app.services.quality.validators.material_conflict_validator import MaterialConflictValidator
from app.services.quality.validators.ui_reference_validator import UIReferenceValidator
from app.services.quality.validators.duplication_validator import DuplicationValidator


class QualityGateService:
    """QualityGate 统一校验编排服务。"""

    def __init__(self, db: Session | None = None) -> None:
        """初始化校验器列表。

        Args:
            db: 数据库会话，用于读取项目级规则覆盖
        """
        self.db = db
        self.validators: list[BaseValidator] = [
            CaseValidator(),
            UpdateSuggestionValidator(),
            ImportResultValidator(),
            MaterialConflictValidator(),
            UIReferenceValidator(),
            DuplicationValidator(),
        ]

    def _load_project_rules(self, project_id: int) -> dict:
        """从 QualityRuleConfig 读取项目级规则覆盖。"""
        if self.db is None or project_id is None:
            return {}
        try:
            from app.models.quality_rule_config import QualityRuleConfig

            rows = (
                self.db.query(QualityRuleConfig)
                .filter(
                    QualityRuleConfig.project_id == project_id,
                )
                .all()
            )
            return {row.rule_key: row.rule_value for row in rows}
        except Exception as e:
            logger.warning(f"加载项目 {project_id} 质量规则失败: {e}")
            return {}

    def _build_context(
        self,
        context: dict | None,
        project_rules: dict,
    ) -> dict:
        """将项目级规则覆盖合并到上下文中。"""
        ctx = dict(context or {})
        for key, value in project_rules.items():
            if key not in ctx:
                ctx[key] = value
        return ctx

    def validate(
        self,
        case_data: dict,
        context: dict | None = None,
        project_id: int | None = None,
    ) -> ValidationResult:
        """编排所有校验器执行校验，合并结果。

        Args:
            case_data: 用例数据字典
            context: 上下文信息（如UI规格、已有用例标题等）
            project_id: 项目ID，用于读取项目级规则覆盖

        Returns:
            ValidationResult: 合并后的校验结果
        """
        project_rules: dict = {}
        if project_id is not None:
            project_rules = self._load_project_rules(project_id)

        ctx = self._build_context(context, project_rules)
        results: list[ValidationResult] = []

        for validator in self.validators:
            try:
                result = validator.validate(case_data, context=ctx)
                results.append(result)
            except Exception as e:
                logger.warning(f"校验器 {validator.__class__.__name__} 执行异常: {e}")
                results.append(
                    ValidationResult(
                        status="warning",
                        issues=[],
                    )
                )

        merged = ValidationResult.merge(results)
        return merged

    @staticmethod
    def grade_to_status(grade: str) -> str:
        """将评分等级(A/B/C/D)映射到4档状态。

        A -> passed
        B -> warning
        C -> pending_review
        D -> rejected
        """
        mapping = {
            "A": "passed",
            "B": "warning",
            "C": "pending_review",
            "D": "rejected",
        }
        return mapping.get(grade, "pending_review")

    @staticmethod
    def status_to_grade(status: str) -> str:
        """将4档状态映射回评分等级。"""
        mapping = {
            "passed": "A",
            "warning": "B",
            "pending_review": "C",
            "rejected": "D",
        }
        return mapping.get(status, "C")
