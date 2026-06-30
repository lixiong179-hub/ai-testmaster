"""
Test Case Generation Service - UI 元素可执行性校验子Mixin
从 validate_mixin.py 拆分：UI 元素名称归一化、收集、命中检测与可执行性问题输出。
"""
import re
from typing import Any, Dict, List, Optional


class TestCaseGenerationUiValidationMixin:
    """UI 元素可执行性校验：检查生成步骤引用的 UI 元素是否在上下文 UI 规格中存在。"""

    _MIN_UI_ELEMENT_HIT_RATE = 0.8
    _UI_ELEMENT_KEYS = frozenset({
        "id",
        "key",
        "name",
        "label",
        "text",
        "title",
        "placeholder",
        "content",
        "value",
        "aria_label",
        "element_name",
        "selector",
    })
    _GENERIC_UI_WORDS = frozenset({
        "按钮",
        "输入框",
        "文本框",
        "链接",
        "页面",
        "弹窗",
        "菜单",
        "选项",
        "入口",
        "控件",
    })

    @staticmethod
    def _normalize_ui_element_name(value: Any) -> str:
        text = str(value or "").strip()
        text = re.sub(r"[\s【】「」\"'`<>《》:：,，。；;、\[\]()（）]", "", text)
        return text.lower()

    @classmethod
    def _collect_ui_element_names(cls, ui_specs: Optional[List[Dict[str, Any]]]) -> set[str]:
        names: set[str] = set()

        def add(value: Any) -> None:
            if not isinstance(value, str):
                return
            normalized = cls._normalize_ui_element_name(value)
            if len(normalized) < 2 or normalized in cls._GENERIC_UI_WORDS:
                return
            names.add(normalized)

        def walk(value: Any, key_hint: Optional[str] = None) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    key_text = str(key).lower()
                    if key_text in cls._UI_ELEMENT_KEYS:
                        add(item)
                    if isinstance(item, (dict, list)):
                        walk(item, key_text)
            elif isinstance(value, list):
                for item in value:
                    walk(item, key_hint)
            elif key_hint in cls._UI_ELEMENT_KEYS:
                add(value)

        for spec_item in ui_specs or []:
            if not isinstance(spec_item, dict):
                continue
            add(spec_item.get("screen_name"))
            walk(spec_item.get("ui_spec"))
        return names

    @classmethod
    def _extract_step_target_elements(cls, step: Dict[str, Any]) -> List[str]:
        candidates: List[str] = []
        explicit = step.get("target_element")
        if explicit:
            candidates.append(str(explicit))

        action = " ".join(
            str(value or "")
            for value in (
                step.get("action"),
                step.get("description"),
                step.get("param"),
            )
        )
        bracket_patterns = [
            r"(?:点击|选择|勾选|切换|按下|长按)\s*[【「《\"']([^】」》\"']{2,40})[】」》\"']",
            r"(?:在|向)\s*[【「《\"']([^】」》\"']{2,40})[】」》\"']\s*(?:输入|填写|键入|录入|选择)",
        ]
        for pattern in bracket_patterns:
            candidates.extend(re.findall(pattern, action))

        result: List[str] = []
        seen = set()
        for item in candidates:
            normalized = cls._normalize_ui_element_name(item)
            if len(normalized) < 2 or normalized in cls._GENERIC_UI_WORDS or normalized in seen:
                continue
            seen.add(normalized)
            result.append(item.strip())
        return result

    @classmethod
    def _ui_element_exists(cls, target: str, element_names: set[str]) -> bool:
        normalized = cls._normalize_ui_element_name(target)
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

    @classmethod
    def _ui_executability_issues(
        cls,
        steps: List[Dict[str, Any]],
        ui_specs: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        element_names = cls._collect_ui_element_names(ui_specs)
        if not element_names:
            return []

        checked = 0
        hit = 0
        missing: List[str] = []
        for step in steps or []:
            targets = cls._extract_step_target_elements(step)
            for target in targets:
                checked += 1
                if cls._ui_element_exists(target, element_names):
                    hit += 1
                else:
                    missing.append(target)

        if checked == 0:
            return []
        hit_rate = hit / checked
        if hit_rate >= cls._MIN_UI_ELEMENT_HIT_RATE:
            return []
        unique_missing = []
        seen = set()
        for item in missing:
            normalized = cls._normalize_ui_element_name(item)
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_missing.append(item)
        missing_text = "、".join(unique_missing[:5])
        return [
            f"UI元素命中率 {hit_rate:.0%} 低于 {cls._MIN_UI_ELEMENT_HIT_RATE:.0%}，未匹配元素: {missing_text}"
        ]
