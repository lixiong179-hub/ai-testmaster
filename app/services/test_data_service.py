"""Test Data Service - 兼容代理模块

所有实现已迁移到 test_data/ 子包，本文件仅保留向后兼容的导入。
"""
from typing import Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.test_data_crud_mixin import TestDataCrudMixin
from app.services.test_data_gen_service_mixin import TestDataGenServiceMixin
from app.services.test_data.service_mixin import TestDataServiceMixin
from app.services.test_data_async_mixin import TestDataAsyncMixin
from app.services.test_data_generator import TestDataGenerator


class TestDataService(TestDataCrudMixin, TestDataGenServiceMixin, TestDataServiceMixin, TestDataAsyncMixin):
    """测试数据服务 - 组合CRUD、生成和业务逻辑能力

    hybrid 模式：sync 端点用 sync 方法（TestDataCrudMixin），
    async 端点用 async 方法（TestDataAsyncMixin，方法名带 _async 后缀）。
    """

    __test__ = False

    def __init__(self, db: Union[Session, AsyncSession]) -> None:
        """初始化测试数据服务。

        Args:
            db: 数据库会话，sync 端点传 Session，async 端点传 AsyncSession。
        """
        self.db = db
        self.generator = TestDataGenerator()


__all__ = ["TestDataService", "TestDataServiceMixin"]
