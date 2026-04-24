"""测试数据CRUD Mixin - 测试数据的增删改查操作

本模块实现测试数据的CRUD操作，包括：
- 测试数据记录的增删改查
- 数据版本管理
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from app.models.test_data import TestData


class TestDataCrudMixin:
    """测试数据CRUD操作Mixin"""

    def __init__(self, db: Session):
        """
        初始化CRUD操作

        Args:
            db: 数据库会话
        """
        self.db = db

    def create_data(
        self,
        step_id: int,
        field_name: str,
        field_type: str = "text",
        data_value: Optional[str] = None,
        generation_rule: str = "random",
        description: Optional[str] = None
    ) -> TestData:
        """
        创建测试数据

        Args:
            step_id: 步骤ID
            field_name: 字段名称
            field_type: 字段类型
            data_value: 数据值
            generation_rule: 生成规则
            description: 描述

        Returns:
            创建的测试数据
        """
        data = TestData(
            step_id=step_id,
            field_name=field_name,
            field_type=field_type,
            data_value=data_value,
            generation_rule=generation_rule,
            description=description
        )
        self.db.add(data)
        self.db.commit()
        self.db.refresh(data)
        logger.info(f"创建测试数据: {field_name} (ID: {data.id})")
        return data

    def get_data(self, data_id: int) -> Optional[TestData]:
        """
        获取测试数据

        Args:
            data_id: 数据ID

        Returns:
            测试数据对象或None
        """
        return self.db.query(TestData).filter(TestData.id == data_id).first()

    def get_data_by_step(self, step_id: int) -> List[TestData]:
        """
        获取步骤的所有测试数据

        Args:
            step_id: 步骤ID

        Returns:
            测试数据列表
        """
        return self.db.query(TestData).filter(TestData.step_id == step_id).all()

    def update_data(
        self,
        data_id: int,
        field_name: Optional[str] = None,
        field_type: Optional[str] = None,
        data_value: Optional[str] = None,
        generation_rule: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[TestData]:
        """
        更新测试数据

        Args:
            data_id: 数据ID
            field_name: 新字段名称
            field_type: 新字段类型
            data_value: 新数据值
            generation_rule: 新生成规则
            description: 新描述

        Returns:
            更新后的测试数据或None
        """
        data = self.get_data(data_id)
        if not data:
            return None

        if field_name is not None:
            data.field_name = field_name
        if field_type is not None:
            data.field_type = field_type
        if data_value is not None:
            data.data_value = data_value
        if generation_rule is not None:
            data.generation_rule = generation_rule
        if description is not None:
            data.description = description

        self.db.commit()
        self.db.refresh(data)
        logger.info(f"更新测试数据: {data.field_name} (ID: {data.id})")
        return data

    def delete_data(self, data_id: int) -> bool:
        """
        删除测试数据

        Args:
            data_id: 数据ID

        Returns:
            是否删除成功
        """
        data = self.get_data(data_id)
        if not data:
            return False

        self.db.delete(data)
        self.db.commit()
        logger.info(f"删除测试数据: {data.field_name} (ID: {data.id})")
        return True

    def batch_create_data(
        self,
        step_id: int,
        data_list: List[Dict[str, Any]]
    ) -> List[TestData]:
        """
        批量创建测试数据

        Args:
            step_id: 步骤ID
            data_list: 数据列表

        Returns:
            创建的测试数据列表
        """
        created = []
        for item in data_list:
            data = TestData(
                step_id=step_id,
                field_name=item.get("field_name", ""),
                field_type=item.get("field_type", "text"),
                data_value=item.get("data_value"),
                generation_rule=item.get("generation_rule", "random"),
                description=item.get("description")
            )
            self.db.add(data)
            created.append(data)

        self.db.commit()
        for data in created:
            self.db.refresh(data)

        logger.info(f"批量创建 {len(created)} 条测试数据到步骤 {step_id}")
        return created
