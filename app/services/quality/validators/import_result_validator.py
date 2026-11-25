"""导入用例格式完整性校验器。

校验从外部导入的用例数据格式完整性:
    - 必须包含 title 字段
    - 必须包含 steps 字段且为列表
    - 每个步骤必须包含 action 和 expected_result
"""

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
    worst_severity,
)


def _reject(field: str, message: str) -> ValidationIssue:
    return ValidationIssue(field=field, message=message, severity="rejected")


def _check_title(case_data: dict, issues: list[ValidationIssue]) -> None:
    if not (case_data.get("title") or "").strip():
        issues.append(_reject("title", "导入用例缺少标题"))


def _check_step(step: dict, index: int, issues: list[ValidationIssue]) -> None:
    """单步骤：操作描述（action 或 description）与预期结果均必填。"""
    if not (step.get("action") or step.get("description") or "").strip():
        issues.append(_reject(f"steps[{index}].action", f"第{index + 1}步缺少操作描述"))
    if not (step.get("expected_result") or "").strip():
        issues.append(_reject(f"steps[{index}].expected_result", f"第{index + 1}步缺少预期结果"))


def _check_steps(case_data: dict, issues: list[ValidationIssue]) -> None:
    steps = case_data.get("steps")
    if steps is None:
        issues.append(_reject("steps", "导入用例缺少步骤列表"))
        return
    if not isinstance(steps, list):
        issues.append(_reject("steps", "导入用例的 steps 必须为列表"))
        return
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            issues.append(_reject(f"steps[{i}]", f"第{i + 1}步不是有效的字典"))
            continue
        _check_step(step, i, issues)


def _check_module(case_data: dict, issues: list[ValidationIssue]) -> None:
    if not (case_data.get("module") or "").strip():
        issues.append(ValidationIssue(field="module", message="导入用例缺少模块信息", severity="warning"))


class ImportResultValidator(BaseValidator):
    """导入用例格式完整性校验器。"""

    def validate(
        self,
        case_data: dict,
        context: dict | None = None,
    ) -> ValidationResult:
        """校验导入用例的格式完整性。"""
        if (context or {}).get("source", "") != "import":
            return ValidationResult(status="passed", issues=[])

        issues: list[ValidationIssue] = []
        _check_title(case_data, issues)
        _check_steps(case_data, issues)
        _check_module(case_data, issues)
        return ValidationResult(status=worst_severity(issues), issues=issues)
