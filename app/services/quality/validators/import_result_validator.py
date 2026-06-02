"""导入用例格式完整性校验器。

校验从外部导入的用例数据格式完整性:
    - 必须包含 title 字段
    - 必须包含 steps 字段且为列表
    - 每个步骤必须包含 action 和 expected_result
"""
from typing import Dict, List, Optional

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
)


class ImportResultValidator(BaseValidator):
    """导入用例格式完整性校验器。"""

    def validate(
        self,
        case_data: Dict,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """校验导入用例的格式完整性。"""
        issues: List[ValidationIssue] = []

        source = (context or {}).get("source", "")
        if source != "import":
            return ValidationResult(status="passed", issues=[])

        title = (case_data.get("title") or "").strip()
        if not title:
            issues.append(ValidationIssue(
                field="title", message="导入用例缺少标题", severity="rejected",
            ))

        steps = case_data.get("steps")
        if steps is None:
            issues.append(ValidationIssue(
                field="steps", message="导入用例缺少步骤列表", severity="rejected",
            ))
        elif not isinstance(steps, list):
            issues.append(ValidationIssue(
                field="steps", message="导入用例的 steps 必须为列表", severity="rejected",
            ))
        else:
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    issues.append(ValidationIssue(
                        field=f"steps[{i}]",
                        message=f"第{i + 1}步不是有效的字典",
                        severity="rejected",
                    ))
                    continue
                action = (step.get("action") or step.get("description") or "").strip()
                if not action:
                    issues.append(ValidationIssue(
                        field=f"steps[{i}].action",
                        message=f"第{i + 1}步缺少操作描述",
                        severity="rejected",
                    ))
                expected = (step.get("expected_result") or "").strip()
                if not expected:
                    issues.append(ValidationIssue(
                        field=f"steps[{i}].expected_result",
                        message=f"第{i + 1}步缺少预期结果",
                        severity="rejected",
                    ))

        module = (case_data.get("module") or "").strip()
        if not module:
            issues.append(ValidationIssue(
                field="module", message="导入用例缺少模块信息", severity="warning",
            ))

        worst = "passed"
        for issue in issues:
            from app.services.quality.validators.base import Severity
            if Severity[issue.severity].value > Severity[worst].value:
                worst = issue.severity

        return ValidationResult(status=worst, issues=issues)
