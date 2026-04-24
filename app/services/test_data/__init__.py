"""测试数据生成器 - 基于AI的测试数据生成引擎

本模块整合测试数据生成、参数化和CRUD操作，提供完整的测试数据管理能力。

核心类:
    - TestDataGenerator: 测试数据生成器，组合生成和CRUD能力

核心函数:
    - create_test_data_generator: 工厂函数，创建生成器实例

设计模式:
    采用Mixin组合模式，将不同维度的能力拆分到独立Mixin中:
    - GeneratorMixin: AI数据生成
    - TestDataParameterizer: 参数化引擎
    - TestDataCrudMixin: CRUD操作

依赖关系:
    - app.models.test_data: TestData ORM模型
    - app.utils.ai_client: AI客户端工具
    - app.core.config: 配置管理
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.test_data.constants import (
    DATA_TYPE_STRING,
    DATA_TYPE_NUMBER,
    DATA_TYPE_EMAIL,
    DATA_TYPE_PHONE,
    DATA_TYPE_DATE,
    DATA_TYPE_ENUM,
    DATA_TYPE_BOOLEAN,
    DATA_TYPE_CUSTOM,
)
from app.services.test_data.generator_mixin import GeneratorMixin
from app.services.test_data.parameterizer_mixin import TestDataParameterizer
from app.services.test_data.crud_mixin import TestDataCrudMixin
from app.services.test_data.service_mixin import TestDataServiceMixin


class TestDataGenerator(GeneratorMixin, TestDataCrudMixin):
    """测试数据生成器 - 组合AI生成和CRUD操作的完整数据管理器。

    继承顺序（MRO）:
        GeneratorMixin -> TestDataCrudMixin

        GeneratorMixin提供AI数据生成能力。
        TestDataCrudMixin提供数据库CRUD操作。

    使用场景:
        - 为测试用例生成测试数据
        - 管理测试数据记录
        - 批量生成多种类型的测试数据

    使用方式:
        generator = create_test_data_generator(db)
        data = await generator.generate_test_data(field_definitions, count=5)
        generator.batch_create_data(step_id, data)
    """

    def __init__(self, db: Session):
        """初始化测试数据生成器。

        Args:
            db: 数据库会话。
        """
        GeneratorMixin.__init__(self)
        TestDataCrudMixin.__init__(self, db)


def create_test_data_generator(db: Session) -> TestDataGenerator:
    """工厂函数 - 创建测试数据生成器实例。

    Args:
        db: 数据库会话。

    Returns:
        TestDataGenerator实例。
    """
    return TestDataGenerator(db)


__all__ = [
    "TestDataGenerator",
    "create_test_data_generator",
    "TestDataParameterizer",
    "TestDataCrudMixin",
    "TestDataServiceMixin",
    "DATA_TYPE_STRING",
    "DATA_TYPE_NUMBER",
    "DATA_TYPE_EMAIL",
    "DATA_TYPE_PHONE",
    "DATA_TYPE_DATE",
    "DATA_TYPE_ENUM",
    "DATA_TYPE_BOOLEAN",
    "DATA_TYPE_CUSTOM",
]
