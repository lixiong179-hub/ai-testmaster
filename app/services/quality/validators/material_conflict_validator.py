"""资料冲突校验器。

校验需求文档与UI原型描述之间的不一致:
    - 需求描述与UI元素描述冲突
    - 需求中的功能点在UI原型中无对应界面
"""

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
    worst_severity,
)


def _build_case_text(case_data: dict) -> str:
    """用例标题 + 各步骤动作/描述，拼成用于关键词匹配的小写文本。"""
    text = (case_data.get("title") or "").strip()
    for step in case_data.get("steps") or []:
        text += f" {step.get('action') or step.get('description') or ''}"
    return text.lower()


def _match_terms(text: str, candidates: object) -> list[str]:
    """返回在 text 中出现的候选词（忽略非字符串项）。"""
    return [item for item in candidates or [] if isinstance(item, str) and item.lower() in text]


def _build_conflict_issues(referenced_req: list[str], referenced_ui: list[str]) -> list[ValidationIssue]:
    """单向命中即视为资料冲突：只提需求不提界面 → pending_review，反之仅 warning。"""
    issues: list[ValidationIssue] = []
    if referenced_req and not referenced_ui:
        issues.append(
            ValidationIssue(
                field="material_conflict",
                message=f"用例引用了需求关键词 {referenced_req[:3]} 但未匹配到任何UI界面名称，可能存在资料冲突",
                severity="pending_review",
            )
        )
    if referenced_ui and not referenced_req:
        issues.append(
            ValidationIssue(
                field="material_conflict",
                message=f"用例引用了UI界面 {referenced_ui[:3]} 但未匹配到任何需求关键词，可能存在资料冲突",
                severity="warning",
            )
        )
    return issues


class MaterialConflictValidator(BaseValidator):
    """资料冲突校验器，检测需求与UI描述不一致。"""

    def validate(
        self,
        case_data: dict,
        context: dict | None = None,
    ) -> ValidationResult:
        """校验资料冲突。"""
        ctx = context or {}
        requirement_keywords = ctx.get("requirement_keywords") or set()
        ui_screen_names = ctx.get("ui_screen_names") or set()
        if not requirement_keywords or not ui_screen_names:
            return ValidationResult(status="passed", issues=[])

        case_text = _build_case_text(case_data)
        issues = _build_conflict_issues(
            _match_terms(case_text, requirement_keywords),
            _match_terms(case_text, ui_screen_names),
        )
        return ValidationResult(status=worst_severity(issues), issues=issues)
