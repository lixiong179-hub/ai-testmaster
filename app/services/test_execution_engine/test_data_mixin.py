"""测试数据Mixin - 管理测试执行过程中的数据参数化解析。

负责创建参数化解析器、生成步骤测试数据、替换操作描述中的参数占位符。
与TestDataService和TestDataParameterizer协作完成测试数据的参数化。
"""
from typing import Optional, Dict, Any
from loguru import logger

from app.services.test_data.parameterizer_mixin import TestDataParameterizer
from app.services.test_data_parameterizer import ParameterContext


class TestDataMixin:

    def _create_parameterizer(self, execution_id: int, case_id: int) -> Optional[TestDataParameterizer]:
        """创建参数化解析器。

        Args:
            execution_id: 执行ID
            case_id: 用例ID

        Returns:
            参数化解析器，未启用时返回None
        """
        if not self.enable_test_data_param or not self.test_data_service:
            return None

        context = ParameterContext(
            execution_id=f"EXEC_{execution_id}"
        )
        return TestDataParameterizer(context)

    def _generate_step_test_data(
        self,
        step_id: int,
        parameterizer: Optional[TestDataParameterizer] = None
    ) -> Dict[str, str]:
        """生成步骤的测试数据。

        Args:
            step_id: 步骤ID
            parameterizer: 参数化解析器

        Returns:
            字段名到值的映射
        """
        if not self.enable_test_data_param or not self.test_data_service:
            return {}

        try:
            return self.test_data_service.generate_step_data(step_id, parameterizer)
        except Exception as e:
            logger.warning(f"生成测试数据失败: {e}")
            return {}

    def _substitute_parameters_in_action(
        self,
        action: str,
        test_data: Dict[str, str]
    ) -> str:
        """替换操作描述中的参数占位符。

        支持 ${field_name} 格式的占位符替换。

        Args:
            action: 操作描述
            test_data: 测试数据

        Returns:
            替换后的操作描述
        """
        if not test_data:
            return action

        result = action
        for field_name, value in test_data.items():
            placeholder = f"${{{field_name}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
                logger.info(f"替换参数 {placeholder} -> {value}")

        return result
