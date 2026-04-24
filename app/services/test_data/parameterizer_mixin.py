"""测试数据参数化引擎 - 将测试数据注入测试用例步骤

本模块实现测试数据的参数化功能，支持：
- 变量占位符替换（{{variable}}格式）
- 步骤级参数注入
- 数据驱动测试（多组数据驱动同一步骤）
- 参数类型自动推断
"""
import re
from typing import List, Dict, Any, Optional
from loguru import logger


class TestDataParameterizer:
    """测试数据参数化引擎"""

    # 变量占位符正则表达式：匹配 {{variable}} 格式
    VARIABLE_PATTERN = re.compile(r'\{\{(\w+)\}\}')

    def __init__(self):
        """初始化参数化引擎"""
        pass

    def parameterize_steps(
        self,
        steps: List[Dict[str, Any]],
        test_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        将测试数据注入测试步骤

        Args:
            steps: 原始测试步骤列表
            test_data: 测试数据字典

        Returns:
            参数化后的测试步骤列表
        """
        parameterized_steps = []
        for step in steps:
            parameterized_step = self._parameterize_step(step, test_data)
            parameterized_steps.append(parameterized_step)
        return parameterized_steps

    def _parameterize_step(
        self,
        step: Dict[str, Any],
        test_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        参数化单个步骤

        Args:
            step: 原始测试步骤
            test_data: 测试数据字典

        Returns:
            参数化后的测试步骤
        """
        parameterized = step.copy()

        # 参数化步骤描述
        if "description" in step:
            parameterized["description"] = self._replace_variables(
                step["description"], test_data
            )

        # 参数化操作
        if "action" in step:
            parameterized["action"] = self._replace_variables(
                step["action"], test_data
            )

        # 参数化预期结果
        if "expected_result" in step:
            parameterized["expected_result"] = self._replace_variables(
                step["expected_result"], test_data
            )

        # 参数化输入值
        if "input_value" in step:
            parameterized["input_value"] = self._replace_variables(
                step["input_value"], test_data
            )

        # 参数化定位器
        if "locator" in step:
            parameterized["locator"] = self._replace_variables(
                step["locator"], test_data
            )

        return parameterized

    def _replace_variables(
        self,
        text: str,
        test_data: Dict[str, Any]
    ) -> str:
        """
        替换文本中的变量占位符

        Args:
            text: 包含变量占位符的文本
            test_data: 测试数据字典

        Returns:
            替换后的文本
        """
        if not isinstance(text, str):
            return text

        def replace_match(match):
            var_name = match.group(1)
            if var_name in test_data:
                value = test_data[var_name]
                return str(value) if value is not None else ""
            else:
                logger.warning(f"变量 {var_name} 在测试数据中未找到")
                return match.group(0)  # 保留原始占位符

        return self.VARIABLE_PATTERN.sub(replace_match, text)

    def extract_variables(self, steps: List[Dict[str, Any]]) -> List[str]:
        """
        从测试步骤中提取所有变量名

        Args:
            steps: 测试步骤列表

        Returns:
            变量名列表（去重）
        """
        variables = set()
        for step in steps:
            for key in ["description", "action", "expected_result", "input_value", "locator"]:
                if key in step and isinstance(step[key], str):
                    matches = self.VARIABLE_PATTERN.findall(step[key])
                    variables.update(matches)
        return list(variables)

    def validate_data_completeness(
        self,
        steps: List[Dict[str, Any]],
        test_data: Dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        验证测试数据是否完整覆盖所有变量

        Args:
            steps: 测试步骤列表
            test_data: 测试数据字典

        Returns:
            (是否完整, 缺失变量列表)
        """
        required_vars = self.extract_variables(steps)
        missing_vars = [var for var in required_vars if var not in test_data]
        return len(missing_vars) == 0, missing_vars

    def create_data_driven_steps(
        self,
        steps: List[Dict[str, Any]],
        data_sets: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        创建数据驱动的测试步骤（多组数据）

        Args:
            steps: 原始测试步骤列表
            data_sets: 多组测试数据

        Returns:
            每组数据对应的参数化步骤列表
        """
        result = []
        for i, data in enumerate(data_sets):
            try:
                parameterized = self.parameterize_steps(steps, data)
                result.append(parameterized)
            except Exception as e:
                logger.error(f"参数化第{i+1}组数据失败: {e}")
        return result

    def generate_parameterized_description(
        self,
        description: str,
        test_data: Dict[str, Any]
    ) -> str:
        """
        生成参数化后的描述文本

        Args:
            description: 原始描述
            test_data: 测试数据

        Returns:
            参数化后的描述
        """
        return self._replace_variables(description, test_data)
