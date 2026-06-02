"""资料冲突校验器。

校验需求文档与UI原型描述之间的不一致:
    - 需求描述与UI元素描述冲突
    - 需求中的功能点在UI原型中无对应界面
"""
from typing import Dict, List, Optional

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
)


class MaterialConflictValidator(BaseValidator):
    """资料冲突校验器，检测需求与UI描述不一致。"""

    def validate(
        self,
        case_data: Dict,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """校验资料冲突。"""
        issues: List[ValidationIssue] = []
        ctx = context or {}

        requirement_keywords = ctx.get("requirement_keywords") or set()
        ui_screen_names = ctx.get("ui_screen_names") or set()

        if not requirement_keywords or not ui_screen_names:
            return ValidationResult(status="passed", issues=[])

        case_title = (case_data.get("title") or "").strip()
        case_steps = case_data.get("steps") or []
        case_text = case_title
        for step in case_steps:
            action = step.get("action") or step.get("description") or ""
            case_text += f" {action}"

        case_text_lower = case_text.lower()

        referenced_req_keywords: List[str] = []
        for kw in requirement_keywords:
            if isinstance(kw, str) and kw.lower() in case_text_lower:
                referenced_req_keywords.append(kw)

        referenced_ui_screens: List[str] = []
        for screen in ui_screen_names:
            if isinstance(screen, str) and screen.lower() in case_text_lower:
                referenced_ui_screens.append(screen)

        if referenced_req_keywords and not referenced_ui_screens:
            issues.append(ValidationIssue(
                field="material_conflict",
                message=(
                    f"用例引用了需求关键词 {referenced_req_keywords[:3]} "
                    f"但未匹配到任何UI界面名称，可能存在资料冲突"
                ),
                severity="pending_review",
            ))

        if referenced_ui_screens and not referenced_req_keywords:
            issues.append(ValidationIssue(
                field="material_conflict",
                message=(
                    f"用例引用了UI界面 {referenced_ui_screens[:3]} "
                    f"但未匹配到任何需求关键词，可能存在资料冲突"
                ),
                severity="warning",
            ))

        worst = "passed"
        for issue in issues:
            from app.services.quality.validators.base import Severity
            if Severity[issue.severity].value > Severity[worst].value:
                worst = issue.severity

        return ValidationResult(status=worst, issues=issues)
