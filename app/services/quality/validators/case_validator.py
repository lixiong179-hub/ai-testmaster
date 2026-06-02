"""用例基本格式校验器。

校验维度:
    - 标题长度（8~50字）
    - 步骤数（2~8步）
    - 前置条件非空
    - 预期结果非空
"""
from typing import Dict, List, Optional

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
)


class CaseValidator(BaseValidator):
    """用例基本格式校验器，校验标题、步骤数、前置条件、预期结果。"""

    def __init__(
        self,
        title_min: int = 8,
        title_max: int = 50,
        steps_min: int = 2,
        steps_max: int = 8,
    ) -> None:
        self.titleMin = title_min
        self.titleMax = title_max
        self.stepsMin = steps_min
        self.stepsMax = steps_max

    def validate(
        self,
        case_data: Dict,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """校验用例基本格式。"""
        issues: List[ValidationIssue] = []
        ctx = context or {}

        title_min = ctx.get("title_min", self.titleMin)
        title_max = ctx.get("title_max", self.titleMax)
        steps_min = ctx.get("steps_min", self.stepsMin)
        steps_max = ctx.get("steps_max", self.stepsMax)

        title = (case_data.get("title") or "").strip()
        if not title:
            issues.append(ValidationIssue(
                field="title", message="标题为空", severity="rejected",
            ))
        elif len(title) < title_min:
            issues.append(ValidationIssue(
                field="title",
                message=f"标题过短（{len(title)}字），需≥{title_min}字",
                severity="rejected",
            ))
        elif len(title) > title_max:
            issues.append(ValidationIssue(
                field="title",
                message=f"标题过长（{len(title)}字），需≤{title_max}字",
                severity="warning",
            ))

        steps = case_data.get("steps") or []
        step_count = len(steps)
        if step_count < steps_min:
            issues.append(ValidationIssue(
                field="steps",
                message=f"步骤数不足（{step_count}步），需≥{steps_min}步",
                severity="rejected",
            ))
        elif step_count > steps_max:
            issues.append(ValidationIssue(
                field="steps",
                message=f"步骤数过多（{step_count}步），需≤{steps_max}步",
                severity="warning",
            ))

        precondition = (case_data.get("precondition") or "").strip()
        if not precondition:
            issues.append(ValidationIssue(
                field="precondition", message="前置条件为空", severity="rejected",
            ))

        expected_result = (case_data.get("expected_result") or "").strip()
        if not expected_result:
            issues.append(ValidationIssue(
                field="expected_result", message="预期结果为空", severity="rejected",
            ))

        worst = "passed"
        for issue in issues:
            from app.services.quality.validators.base import Severity
            if Severity[issue.severity].value > Severity[worst].value:
                worst = issue.severity

        return ValidationResult(status=worst, issues=issues)
