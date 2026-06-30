"""Test Data Service - 兼容代理模块

所有实现已迁移到 test_data/ 子包，本文件仅保留向后兼容的导入。
"""
from sqlalchemy.orm import Session
from app.services.test_data_crud_mixin import TestDataCrudMixin
from app.services.test_data_gen_service_mixin import TestDataGenServiceMixin
from app.services.test_data.service_mixin import TestDataServiceMixin
from app.services.test_data_generator import TestDataGenerator


class TestDataService(TestDataCrudMixin, TestDataGenServiceMixin, TestDataServiceMixin):
    """测试数据服务 - 组合CRUD、生成和业务逻辑能力"""

    __test__ = False

    def __init__(self, db: Session):
        """初始化测试数据服务"""
        self.db = db
        self.generator = TestDataGenerator()


__all__ = ["TestDataService", "TestDataServiceMixin"]
