"""UI元素引用命中率校验器。

校验用例步骤中引用的UI元素在UI原型规格中的命中率，
命中率低于阈值时标记为 pending_review。
"""
import re
from typing import Dict, List, Optional, Set

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
)


class UIReferenceValidator(BaseValidator):
    """UI元素引用命中率校验器。"""

    _UI_ELEMENT_KEYS = frozenset({
        "id", "key", "name", "label", "text", "title",
        "placeholder", "content", "value", "aria_label",
        "element_name", "selector",
    })
    _GENERIC_UI_WORDS = frozenset({
        "按钮", "输入框", "文本框", "链接", "页面",
        "弹窗", "菜单", "选项", "入口", "控件",
    })

    def __init__(self, min_hit_rate: float = 0.8) -> None:
        self.minHitRate = min_hit_rate

    @staticmethod
    def _normalize_ui_name(value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"[\s【】「」\"'`<>《》:：,，。；;、\[\]()（）]", "", text)
        return text.lower()

    def _collect_ui_element_names(
        self,
        ui_specs: Optional[List[Dict]],
    ) -> Set[str]:
        """从UI规格中收集所有元素名称。"""
        names: Set[str] = set()

        def add(value: object) -> None:
            if not isinstance(value, str):
                return
            normalized = self._normalize_ui_name(value)
            if len(normalized) < 2 or normalized in self._GENERIC_UI_WORDS:
                return
            names.add(normalized)

        def walk(value: object, key_hint: Optional[str] = None) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    key_text = str(key).lower()
                    if key_text in self._UI_ELEMENT_KEYS:
                        add(item)
                    if isinstance(item, (dict, list)):
                        walk(item, key_text)
            elif isinstance(value, list):
                for item in value:
                    walk(item, key_hint)
            elif key_hint in self._UI_ELEMENT_KEYS:
                add(value)

        for spec_item in ui_specs or []:
            if not isinstance(spec_item, dict):
                continue
            add(spec_item.get("screen_name"))
            walk(spec_item.get("ui_spec"))
        return names

    def _extract_step_targets(self, step: Dict) -> List[str]:
        """从步骤中提取目标UI元素。"""
        candidates: List[str] = []
        explicit = step.get("target_element")
        if explicit:
            candidates.append(str(explicit))

        action = " ".join(
            str(v or "")
            for v in (
                step.get("action"),
                step.get("description"),
                step.get("param"),
            )
        )
        patterns = [
            r"(?:点击|选择|勾选|切换|按下|长按)\s*[【「《\"']([^】」》\"']{2,40})[】」》\"']",
            r"(?:在|向)\s*[【「《\"']([^】」》\"']{2,40})[】」》\"']\s*(?:输入|填写|键入|录入|选择)",
        ]
        for pattern in patterns:
            candidates.extend(re.findall(pattern, action))

        result: List[str] = []
        seen: Set[str] = set()
        for item in candidates:
            normalized = self._normalize_ui_name(item)
            if len(normalized) < 2 or normalized in self._GENERIC_UI_WORDS or normalized in seen:
                continue
            seen.add(normalized)
            result.append(item.strip())
        return result

    def _ui_element_exists(self, target: str, element_names: Set[str]) -> bool:
        normalized = self._normalize_ui_name(target)
        if not normalized:
            return False
        for element in element_names:
            if normalized == element:
                return True
            if len(normalized) >= 2 and normalized in element:
                return True
            if len(element) >= 2 and element in normalized:
                return True
        return False

    def validate(
        self,
        case_data: Dict,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """校验UI元素引用命中率。"""
        ctx = context or {}
        min_hit_rate = ctx.get("ui_min_hit_rate", self.minHitRate)
        ui_specs = ctx.get("ui_specs") or case_data.get("_context_ui_specs")

        element_names = self._collect_ui_element_names(ui_specs)
        if not element_names:
            return ValidationResult(status="passed", issues=[])

        steps = case_data.get("steps") or []
        checked = 0
        hit = 0
        missing: List[str] = []

        for step in steps:
            targets = self._extract_step_targets(step)
            for target in targets:
                checked += 1
                if self._ui_element_exists(target, element_names):
                    hit += 1
                else:
                    missing.append(target)

        if checked == 0:
            return ValidationResult(status="passed", issues=[])

        hit_rate = hit / checked
        if hit_rate >= min_hit_rate:
            return ValidationResult(status="passed", issues=[])

        unique_missing: List[str] = []
        seen: Set[str] = set()
        for item in missing:
            normalized = self._normalize_ui_name(item)
            if normalized not in seen:
                seen.add(normalized)
                unique_missing.append(item)

        issue = ValidationIssue(
            field="ui_reference",
            message=(
                f"UI元素命中率 {hit_rate:.0%} 低于阈值 {min_hit_rate:.0%}，"
                f"未匹配元素: {'、'.join(unique_missing[:5])}"
            ),
            severity="pending_review",
        )
        return ValidationResult(status="pending_review", issues=[issue])
