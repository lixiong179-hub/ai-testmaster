"""测试数据参数化服务 - 支持${namespace.param}语法的动态参数解析。

本模块实现测试数据的参数化解析能力，支持在测试步骤中使用
${random.phone}、${date.today}等参数语法，在执行时动态解析为
实际值。同一次执行中相同参数值保持一致。

核心类:
    - ParameterContext: 参数化上下文，维护执行级缓存和元信息
    - TestDataParameterizer: 参数化解析器，解析${}语法

核心函数:
    - parse_parameters: 解析参数化文本的便捷函数
    - create_parameter_context: 创建参数化上下文的便捷函数

支持的参数语法:
    - ${random.product_name}: 随机产品线名称
    - ${random.phone}: 随机手机号
    - ${random.email}: 随机邮箱
    - ${random.name}: 随机姓名
    - ${random.company}: 随机公司名
    - ${random.number}: 随机数字
    - ${date.today}: 今天日期
    - ${date.yesterday}: 昨天日期
    - ${date.tomorrow}: 明天日期
    - ${date.now}: 当前日期时间
    - ${date.+N}: N天后日期
    - ${date.-N}: N天前日期
    - ${user.name}: 当前用户名
    - ${user.id}: 当前用户ID
    - ${project.name}: 项目名称
    - ${project.id}: 项目ID
    - ${execution.id}: 执行ID

依赖关系:
    - app.models.test_data: DataType枚举
    - app.services.test_data_generator: TestDataGenerator数据生成器

缓存设计:
    通过ParameterContext.cached_values实现执行级缓存，
    同一execution_id下相同参数表达式只解析一次，
    后续引用直接返回缓存值，确保数据一致性。

容错设计:
    解析失败时保留原始${}表达式不替换，避免生成空值或错误值
    导致测试步骤执行异常。
"""
import re
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger

from app.models.test_data import DataType
from app.services.test_data_generator import TestDataGenerator


@dataclass
class ParameterContext:
    """参数化上下文 - 维护单次执行中的参数缓存和元信息。

    属性:
        execution_id: 执行唯一标识，用于区分不同执行和缓存键前缀。
        user_id: 当前用户ID，用于${user.*}参数解析。
        project_id: 当前项目ID，用于${project.*}参数解析。
        cached_values: 已解析参数的缓存字典，key为"{execution_id}:{param_expr}"。
        execution_timestamp: 执行开始时间戳（固定），用于${execution.timestamp}。

    设计意图:
        同一执行中的所有步骤共享同一个ParameterContext，
        确保相同参数表达式返回相同值。
    """
    execution_id: str  # 执行ID，用于区分不同执行
    user_id: Optional[int] = None  # 用户ID
    project_id: Optional[int] = None  # 项目ID
    cached_values: Dict[str, str] = field(default_factory=dict)  # 缓存的值
    execution_timestamp: str = field(default="")  # 执行时间戳（固定）

    def __post_init__(self):
        """初始化后设置默认执行时间戳。"""
        if not self.execution_timestamp:
            self.execution_timestamp = datetime.now().strftime('%Y%m%d%H%M%S')


class TestDataParameterizer:
    """测试数据参数化解析器 - 解析${namespace.param}语法为实际值。

    职责:
        - 解析${}语法中的参数表达式
        - 按命名空间分发到对应处理器
        - 缓存已解析值确保一致性
        - 解析失败时保留原始表达式

    命名空间处理器:
        - random: 随机数据生成（手机号/邮箱/姓名等）
        - date: 日期时间计算（今天/明天/相对日期等）
        - user: 用户信息（名称/ID/邮箱等）
        - project: 项目信息（名称/ID/编码等）
        - execution: 执行信息（ID/时间戳等）

    使用场景:
        - 测试步骤执行前解析输入值中的参数
        - 前置条件中的动态参数替换
        - 测试数据模板的参数化填充

    使用方式:
        parameterizer = TestDataParameterizer(context)
        result = parameterizer.parse("创建${random.product_name}产品线")
        # result: "创建产品线_20240115_123产品线"
    """

    # 参数语法正则表达式，匹配${...}中的内容
    PARAM_PATTERN = re.compile(r'\$\{([^}]+)\}')

    def __init__(self, context: Optional[ParameterContext] = None):
        """初始化参数化解析器。

        Args:
            context: 参数化上下文，可选。未提供时自动创建默认上下文。
        """
        self.context = context or ParameterContext(execution_id=self._generate_execution_id())
        self.generator = TestDataGenerator()
        # 命名空间到处理器的映射
        self._param_handlers: Dict[str, Callable[[str], str]] = {
            'random': self._handle_random_param,
            'date': self._handle_date_param,
            'user': self._handle_user_param,
            'project': self._handle_project_param,
            'execution': self._handle_execution_param,
        }

    def _generate_execution_id(self) -> str:
        """生成执行ID，格式为EXEC_{时间戳}_{6位随机字符}。

        Returns:
            唯一的执行标识字符串。
        """
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"EXEC_{timestamp}_{random_suffix}"

    def parse(self, text: str) -> str:
        """解析参数化文本，将所有${...}替换为实际值。

        使用正则表达式匹配所有${...}参数，逐个解析并替换。
        解析失败的参数保留原始${}表达式。

        Args:
            text: 包含参数的文本，如"创建${random.product_name}产品线"。

        Returns:
            解析后的文本，所有参数已替换为实际值。

        Example:
            >>> p = TestDataParameterizer()
            >>> p.parse("创建${random.product_name}产品线")
            "创建产品线_20240115_123产品线"
        """
        if not text:
            return text

        def replace_param(match) -> str:
            param_expr = match.group(1)  # 如 "random.product_name"
            return self._resolve_param(param_expr)

        try:
            result = self.PARAM_PATTERN.sub(replace_param, text)
            return result
        except Exception as e:
            logger.error(f"参数化解析失败: text={text}, error={e}")
            return text

    def _resolve_param(self, param_expr: str) -> str:
        """解析单个参数表达式，含缓存检查和命名空间分发。

        解析流程:
            1. 检查缓存，命中则直接返回
            2. 解析命名空间和参数名（以第一个.分隔）
            3. 查找对应命名空间处理器
            4. 执行处理器获取值
            5. 缓存结果并返回

        Args:
            param_expr: 参数表达式，如"random.product_name"。

        Returns:
            解析后的值，解析失败时保留原始${}表达式。
        """
        # 检查缓存，同一次执行中相同参数只解析一次
        cache_key = f"{self.context.execution_id}:{param_expr}"
        if cache_key in self.context.cached_values:
            return self.context.cached_values[cache_key]

        # 解析命名空间和参数名（以第一个.分隔，后续.作为参数名的一部分）
        parts = param_expr.split('.')
        if len(parts) < 2:
            logger.warning(f"无效的参数表达式: {param_expr}")
            return f"${{{param_expr}}}"

        namespace = parts[0]
        param_name = '.'.join(parts[1:])

        # 获取命名空间处理器
        handler = self._param_handlers.get(namespace)
        if not handler:
            logger.warning(f"未知的参数命名空间: {namespace}")
            return f"${{{param_expr}}}"

        # 执行处理器并缓存结果
        try:
            value = handler(param_name)
            self.context.cached_values[cache_key] = value
            return value
        except Exception as e:
            logger.error(f"参数解析失败: {param_expr}, error={e}")
            return f"${{{param_expr}}}"

    def _handle_random_param(self, param_name: str) -> str:
        """处理random命名空间的参数，委托给TestDataGenerator生成。

        支持的参数名:
            product_name/phone/email/name/company/number/address/
            id_card/bank_card/url/boolean/text

        Args:
            param_name: 参数名，如"phone"。

        Returns:
            生成的随机值，未知参数名时保留原始表达式。
        """
        # 缓存逻辑已在_resolve_param中统一处理，这里直接生成值
        generators = {
            'product_name': lambda: self.generator.generate_data(DataType.TEXT, '产品线名称'),
            'phone': lambda: self.generator.generate_data(DataType.PHONE, '手机号'),
            'email': lambda: self.generator.generate_data(DataType.EMAIL, '邮箱'),
            'name': lambda: self.generator.generate_data(DataType.TEXT, '姓名'),
            'company': lambda: self.generator.generate_data(DataType.TEXT, '公司'),
            'number': lambda: self.generator.generate_data(DataType.NUMBER, '数字'),
            'address': lambda: self.generator.generate_data(DataType.TEXT, '地址'),
            'id_card': lambda: self.generator.generate_data(DataType.ID_CARD, '身份证'),
            'bank_card': lambda: self.generator.generate_data(DataType.BANK_CARD, '银行卡'),
            'url': lambda: self.generator.generate_data(DataType.URL, 'URL'),
            'boolean': lambda: self.generator.generate_data(DataType.BOOLEAN, '布尔值'),
            'text': lambda: self.generator.generate_data(DataType.TEXT, '文本'),
        }

        generator = generators.get(param_name)
        if generator:
            return generator()
        else:
            logger.warning(f"未知的 random 参数: {param_name}")
            return f"${{random.{param_name}}}"

    def _handle_date_param(self, param_name: str) -> str:
        """处理date命名空间的参数，支持固定日期和相对日期计算。

        固定日期:
            today/yesterday/tomorrow/now/year/month/day/time/timestamp

        相对日期:
            +N: N天后的日期
            -N: N天前的日期

        Args:
            param_name: 参数名，如"today"、"+7"、"-3"。

        Returns:
            日期字符串，格式为YYYY-MM-DD或YYYY-MM-DD HH:MM:SS。
        """
        now = datetime.now()

        # 处理相对日期，如 +7, -3
        relative_match = re.match(r'([+-])(\d+)', param_name)
        if relative_match:
            sign = relative_match.group(1)
            days = int(relative_match.group(2))
            if sign == '+':
                date = now + timedelta(days=days)
            else:
                date = now - timedelta(days=days)
            return date.strftime('%Y-%m-%d')

        # 处理固定日期
        date_generators = {
            'today': lambda: now.strftime('%Y-%m-%d'),
            'yesterday': lambda: (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            'tomorrow': lambda: (now + timedelta(days=1)).strftime('%Y-%m-%d'),
            'now': lambda: now.strftime('%Y-%m-%d %H:%M:%S'),
            'year': lambda: str(now.year),
            'month': lambda: str(now.month),
            'day': lambda: str(now.day),
            'time': lambda: now.strftime('%H:%M:%S'),
            'timestamp': lambda: str(int(now.timestamp())),
        }

        generator = date_generators.get(param_name)
        if generator:
            return generator()
        else:
            logger.warning(f"未知的 date 参数: {param_name}")
            return f"${{date.{param_name}}}"

    def _handle_user_param(self, param_name: str) -> str:
        """处理user命名空间的参数，返回当前用户信息。

        当上下文中未设置user_id时使用默认值。

        Args:
            param_name: 参数名，如"name"、"id"。

        Returns:
            用户信息字符串。
        """
        user_defaults = {
            'name': '测试用户',
            'id': str(self.context.user_id or '1'),
            'email': 'test@example.com',
            'phone': '13800138000',
        }
        return user_defaults.get(param_name, f"${{user.{param_name}}}")

    def _handle_project_param(self, param_name: str) -> str:
        """处理project命名空间的参数，返回当前项目信息。

        当上下文中未设置project_id时使用默认值。

        Args:
            param_name: 参数名，如"name"、"id"。

        Returns:
            项目信息字符串。
        """
        project_defaults = {
            'name': '测试项目',
            'id': str(self.context.project_id or '1'),
            'code': 'TEST',
        }
        return project_defaults.get(param_name, f"${{project.{param_name}}}")

    def _handle_execution_param(self, param_name: str) -> str:
        """处理execution命名空间的参数，返回当前执行信息。

        Args:
            param_name: 参数名，如"id"、"timestamp"。

        Returns:
            执行信息字符串。
        """
        execution_defaults = {
            'id': self.context.execution_id,
            'timestamp': self.context.execution_timestamp,  # 使用固定的执行时间戳
        }
        return execution_defaults.get(param_name, f"${{execution.{param_name}}}")

    def get_cached_params(self) -> Dict[str, str]:
        """获取所有已缓存的参数值副本。

        Returns:
            缓存字典的浅拷贝。
        """
        return self.context.cached_values.copy()

    def clear_cache(self):
        """清除所有缓存的参数值，用于新的执行周期。"""
        self.context.cached_values.clear()


def parse_parameters(text: str, context: Optional[ParameterContext] = None) -> str:
    """便捷函数 - 解析参数化文本，无需手动创建解析器实例。

    Args:
        text: 包含参数的文本。
        context: 参数化上下文，可选。

    Returns:
        解析后的文本。
    """
    parameterizer = TestDataParameterizer(context)
    return parameterizer.parse(text)


def create_parameter_context(
    execution_id: Optional[str] = None,
    user_id: Optional[int] = None,
    project_id: Optional[int] = None
) -> ParameterContext:
    """便捷函数 - 创建参数化上下文。

    Args:
        execution_id: 执行ID，可选，未提供时自动生成。
        user_id: 用户ID，可选。
        project_id: 项目ID，可选。

    Returns:
        ParameterContext实例。
    """
    return ParameterContext(
        execution_id=execution_id or f"EXEC_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        user_id=user_id,
        project_id=project_id
    )
