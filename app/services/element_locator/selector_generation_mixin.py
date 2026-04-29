"""选择器生成Mixin - 自动生成CSS和XPath选择器。
"""
import re
from typing import Optional, Dict, Any


class SelectorGenerationMixin:

    MAX_CLASS_COUNT = 2
    MAX_TEXT_LENGTH = 20
    MAX_PLACEHOLDER_LENGTH = 10

    def _sanitize_for_css(self, value: str) -> str:
        if not value:
            return ""
        special_chars = r'([!"#$%&\'()*+,./:;<=>?@[\\\]^`{|}~])'
        return re.sub(special_chars, r'\\\1', value)

    def _sanitize_for_xpath(self, value: str) -> str:
        if not value:
            return ""
        if '"' in value and "'" in value:
            parts = value.split('"')
            return 'concat("' + '", \'"\', "'.join(parts) + '")'
        elif '"' in value:
            return f"'{value}'"
        else:
            return f'"{value}"'

    def _generate_css_selector(self, element_attrs: Dict[str, Any]) -> Optional[str]:
        tag = element_attrs.get("tag", "")
        element_id = element_attrs.get("id")
        data_testid = element_attrs.get("data-testid")
        element_class = element_attrs.get("class")
        element_name = element_attrs.get("name")
        element_type = element_attrs.get("type")
        placeholder = element_attrs.get("placeholder")

        if element_id:
            safe_id = self._sanitize_for_css(element_id)
            return f"#{safe_id}"

        if data_testid:
            safe_testid = self._sanitize_for_css(data_testid)
            return f"[data-testid='{safe_testid}']"

        if element_name:
            safe_name = self._sanitize_for_css(element_name)
            return f"[name='{safe_name}']"

        if element_class:
            classes = element_class.split()[:self.MAX_CLASS_COUNT]
            safe_classes = [self._sanitize_for_css(c) for c in classes]
            class_selector = ".".join(safe_classes)
            safe_tag = self._sanitize_for_css(tag)
            return f"{safe_tag}.{class_selector}"

        if element_type and placeholder:
            safe_tag = self._sanitize_for_css(tag)
            safe_type = self._sanitize_for_css(element_type)
            safe_placeholder = self._sanitize_for_css(placeholder[:self.MAX_PLACEHOLDER_LENGTH])
            return f"{safe_tag}[type='{safe_type}'][placeholder*='{safe_placeholder}']"

        if element_type:
            safe_tag = self._sanitize_for_css(tag)
            safe_type = self._sanitize_for_css(element_type)
            return f"{safe_tag}[type='{safe_type}']"

        safe_tag = self._sanitize_for_css(tag)
        return safe_tag if safe_tag else None

    def _generate_xpath(self, element_attrs: Dict[str, Any]) -> Optional[str]:
        tag = element_attrs.get("tag", "*")
        element_id = element_attrs.get("id")
        element_name = element_attrs.get("name")
        element_text = element_attrs.get("text")

        if element_id:
            safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
            safe_id = self._sanitize_for_xpath(element_id)
            return f"//{safe_tag}[@id={safe_id}]"

        if element_name:
            safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
            safe_name = self._sanitize_for_xpath(element_name)
            return f"//{safe_tag}[@name={safe_name}]"

        if element_text:
            safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
            text = element_text[:self.MAX_TEXT_LENGTH]
            safe_text = self._sanitize_for_xpath(text)
            return f"//{safe_tag}[contains(text(),{safe_text})]"

        safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
        return f"//{safe_tag}"

    @staticmethod
    def _normalize_coordinate(element_info: Dict[str, Any], inplace: bool = False) -> Dict[str, Any]:
        result = element_info if inplace else {}
        for key in ["x", "y", "width", "height"]:
            val = element_info.get(key, 0)
            if val is None:
                val = 0
            if isinstance(val, list):
                val = val[0] if val else 0
            result[key] = val
        return result
