
"""参数处理器Mixin - 提供各命名空间参数处理能力的 Mixin。"""
import re
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Callable

from app.models.test_data import DataType
from app.services.test_data_generator import TestDataGenerator
from loguru import logger


class ParameterHandlerMixin:
    """参数处理器Mixin。

    提供各命名空间的参数处理方法:
        - _handle_random_param: 随机数据生成
        - _handle_date_param: 日期时间计算
        - _handle_user_param: 用户信息
        - _handle_project_param: 项目信息
        - _handle_execution_param: 执行信息
    """

    generator: TestDataGenerator

    def _generate_execution_id(self) -> str:
        """生成执行ID。"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"EXEC_{timestamp}_{random_suffix}"

    def _handle_random_param(self, param_name: str) -> str:
        """处理random命名空间的参数。"""
        generators: Dict[str, Callable[[], str]] = {
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
        """处理date命名空间的参数。"""
        now = datetime.now()

        relative_match = re.match(r'([+-])(\d+)', param_name)
        if relative_match:
            sign = relative_match.group(1)
            days = int(relative_match.group(2))
            if sign == '+':
                date = now + timedelta(days=days)
            else:
                date = now - timedelta(days=days)
            return date.strftime('%Y-%m-%d')

        date_generators: Dict[str, Callable[[], str]] = {
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
        """处理user命名空间的参数。"""
        user_id = getattr(self.context, 'user_id', None)
        user_defaults: Dict[str, str] = {
            'name': '测试用户',
            'id': str(user_id or '1'),
            'email': 'test@example.com',
            'phone': '13800138000',
        }
        return user_defaults.get(param_name, f"${{user.{param_name}}}")

    def _handle_project_param(self, param_name: str) -> str:
        """处理project命名空间的参数。"""
        project_id = getattr(self.context, 'project_id', None)
        project_defaults: Dict[str, str] = {
            'name': '测试项目',
            'id': str(project_id or '1'),
            'code': 'TEST',
        }
        return project_defaults.get(param_name, f"${{project.{param_name}}}")

    def _handle_execution_param(self, param_name: str) -> str:
        """处理execution命名空间的参数。"""
        execution_defaults: Dict[str, str] = {
            'id': self.context.execution_id,
            'timestamp': self.context.execution_timestamp,
        }
        return execution_defaults.get(param_name, f"${{execution.{param_name}}}")
