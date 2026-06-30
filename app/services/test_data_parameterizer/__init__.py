
"""参数化解析器 - 解析${namespace.param}语法为实际值。"""
import re
from typing import Dict, Callable, Optional
from loguru import logger

from app.services.test_data_generator import TestDataGenerator
from app.services.test_data_parameterizer.context import ParameterContext
from app.services.test_data_parameterizer.handlers import ParameterHandlerMixin


class TestDataParameterizer(ParameterHandlerMixin):
    """测试数据参数化解析器。

    职责:
        - 解析${}语法中的参数表达式
        - 按命名空间分发到对应处理器
        - 缓存已解析值确保一致性
        - 解析失败时保留原始表达式
    """

    __test__ = False

    PARAM_PATTERN = re.compile(r'\$\{([^}]+)\}')

    def __init__(self, context: Optional[ParameterContext] = None) -> None:
        self.context = context or ParameterContext(execution_id=self._generate_execution_id())
        self.generator = TestDataGenerator()
        self._param_handlers: Dict[str, Callable[[str], str]] = {
            'random': self._handle_random_param,
            'date': self._handle_date_param,
            'user': self._handle_user_param,
            'project': self._handle_project_param,
            'execution': self._handle_execution_param,
        }

    def parse(self, text: str) -> str:
        """解析参数化文本，将所有${...}替换为实际值。"""
        if not text:
            return text

        def replace_param(match) -> str:
            param_expr = match.group(1)
            return self._resolve_param(param_expr)

        try:
            result = self.PARAM_PATTERN.sub(replace_param, text)
            return result
        except Exception as e:
            logger.error(f"参数化解析失败: text={text}, error={e}")
            return text

    def _resolve_param(self, param_expr: str) -> str:
        """解析单个参数表达式，含缓存检查和命名空间分发。"""
        cache_key = f"{self.context.execution_id}:{param_expr}"
        if cache_key in self.context.cached_values:
            return self.context.cached_values[cache_key]

        parts = param_expr.split('.')
        if len(parts) < 2:
            logger.warning(f"无效的参数表达式: {param_expr}")
            return f"${{{param_expr}}}"

        namespace = parts[0]
        param_name = '.'.join(parts[1:])

        handler = self._param_handlers.get(namespace)
        if not handler:
            logger.warning(f"未知的参数命名空间: {namespace}")
            return f"${{{param_expr}}}"

        try:
            value = handler(param_name)
            self.context.cached_values[cache_key] = value
            return value
        except Exception as e:
            logger.error(f"参数解析失败: {param_expr}, error={e}")
            return f"${{{param_expr}}}"

    def get_cached_params(self) -> Dict[str, str]:
        """获取所有已缓存的参数值副本。"""
        return self.context.cached_values.copy()

    def clear_cache(self) -> None:
        """清除所有缓存的参数值。"""
        self.context.cached_values.clear()


def parse_parameters(text: str, context: Optional[ParameterContext] = None) -> str:
    """便捷函数 - 解析参数化文本。"""
    parameterizer = TestDataParameterizer(context)
    return parameterizer.parse(text)


def create_parameter_context(
    execution_id: Optional[str] = None,
    user_id: Optional[int] = None,
    project_id: Optional[int] = None
) -> ParameterContext:
    """便捷函数 - 创建参数化上下文。"""
    from datetime import datetime
    return ParameterContext(
        execution_id=execution_id or f"EXEC_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        user_id=user_id,
        project_id=project_id
    )
