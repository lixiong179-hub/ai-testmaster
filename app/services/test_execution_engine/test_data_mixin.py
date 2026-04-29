"""测试数据Mixin - 管理测试执行过程中的数据参数化解析。
"""
import re
from typing import Optional, Dict, Any, List
from loguru import logger


class TestDataMixin:

    def _create_parameterizer(self, test_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, str]]:
        if not test_data:
            return None
        parameterized = {}
        for key, value in test_data.items():
            if isinstance(value, str):
                parameterized[key] = value
            elif isinstance(value, (int, float)):
                parameterized[key] = str(value)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    compound_key = f"{key}.{sub_key}"
                    parameterized[compound_key] = str(sub_value) if not isinstance(sub_value, str) else sub_value
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    indexed_key = f"{key}[{i}]"
                    parameterized[indexed_key] = str(item) if not isinstance(item, str) else item
        return parameterized

    def _generate_step_test_data(
        self,
        step,
        global_test_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, str]]:
        step_test_data = {}

        if global_test_data:
            parameterized = self._create_parameterizer(global_test_data)
            if parameterized:
                step_test_data.update(parameterized)

        if hasattr(step, 'test_data') and step.test_data:
            if isinstance(step.test_data, dict):
                step_parameterized = self._create_parameterizer(step.test_data)
                if step_parameterized:
                    step_test_data.update(step_parameterized)
            elif isinstance(step.test_data, str):
                try:
                    import json
                    parsed = json.loads(step.test_data)
                    if isinstance(parsed, dict):
                        step_parameterized = self._create_parameterizer(parsed)
                        if step_parameterized:
                            step_test_data.update(step_parameterized)
                except (json.JSONDecodeError, ValueError):
                    pass

        return step_test_data if step_test_data else None

    def _substitute_parameters_in_action(
        self,
        action_text: str,
        test_data: Dict[str, str]
    ) -> str:
        if not test_data or not action_text:
            return action_text

        result = action_text

        pattern = r'\{\{(\w+(?:\.\w+)*(?:\[\d+\])*)\}\}'
        matches = re.findall(pattern, action_text)

        for match in matches:
            placeholder = "{{" + match + "}}"
            value = test_data.get(match)
            if value is not None:
                result = result.replace(placeholder, value)
                logger.debug(f"参数替换: {placeholder} -> {value}")
            else:
                parts = match.split('.')
                current = test_data
                found = True
                for part in parts:
                    bracket_match = re.match(r'(\w+)\[(\d+)\]', part)
                    if bracket_match:
                        key = bracket_match.group(1)
                        index = int(bracket_match.group(2))
                        if isinstance(current, dict) and key in current:
                            current = current[key]
                            if isinstance(current, list) and index < len(current):
                                current = current[index]
                            else:
                                found = False
                                break
                        else:
                            found = False
                            break
                    else:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            found = False
                            break

                if found and isinstance(current, str):
                    result = result.replace(placeholder, current)
                    logger.debug(f"嵌套参数替换: {placeholder} -> {current}")

        return result
