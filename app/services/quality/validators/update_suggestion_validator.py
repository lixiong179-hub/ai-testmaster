"""更新建议校验器。

校验 UPDATE_CASE 类型操作的:
    - diff_fields 非空
    - history_case_id 存在
"""
from typing import Dict, List, Optional

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
)


class UpdateSuggestionValidator(BaseValidator):
    """更新建议校验器，校验 UPDATE_CASE 操作的 diff_fields 和 history_case_id。"""

    def validate(
        self,
        case_data: Dict,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """校验更新建议的完整性和合法性。"""
        issues: List[ValidationIssue] = []
        ctx = context or {}

        change_type = case_data.get("change_type") or case_data.get("ai_change_type") or ""
        if change_type.upper() != "UPDATE_CASE":
            return ValidationResult(status="passed", issues=[])

        diff_fields = case_data.get("diff_fields")
        if not diff_fields:
            issues.append(ValidationIssue(
                field="diff_fields",
                message="UPDATE_CASE 操作的 diff_fields 不能为空",
                severity="rejected",
            ))
        elif isinstance(diff_fields, (list, dict)) and len(diff_fields) == 0:
            issues.append(ValidationIssue(
                field="diff_fields",
                message="UPDATE_CASE 操作的 diff_fields 不能为空列表",
                severity="rejected",
            ))

        history_case_id = case_data.get("history_case_id")
        existing_ids = ctx.get("existing_case_ids") or set()
        if not history_case_id:
            issues.append(ValidationIssue(
                field="history_case_id",
                message="UPDATE_CASE 操作必须指定 history_case_id",
                severity="rejected",
            ))
        elif existing_ids and history_case_id not in existing_ids:
            issues.append(ValidationIssue(
                field="history_case_id",
                message=f"history_case_id={history_case_id} 在项目中不存在",
                severity="rejected",
            ))

        worst = "passed"
        for issue in issues:
            from app.services.quality.validators.base import Severity
            if Severity[issue.severity].value > Severity[worst].value:
                worst = issue.severity

        return ValidationResult(status=worst, issues=issues)
