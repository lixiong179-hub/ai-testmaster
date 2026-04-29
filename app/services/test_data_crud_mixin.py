"""测试数据CRUD Mixin - 测试数据的数据库增删改查操作。
"""
import json
from typing import Optional, List, Dict, Any
from loguru import logger
from app.models.test_data import TestData, DataType, GenerationRule
from app.services.test_data_parameterizer import TestDataParameterizer, ParameterContext


class TestDataCrudMixin:
    def create_test_data(
        self,
        step_id: int,
        field_name: str,
        field_type: DataType = DataType.TEXT,
        generation_rule: GenerationRule = GenerationRule.RANDOM,
        data_value: Optional[str] = None,
        rule_config: Optional[Dict[str, Any]] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        enum_values: Optional[List[str]] = None,
        description: Optional[str] = None,
        is_required: bool = True,
        sort_order: int = 0
    ) -> TestData:
        test_data = TestData(
            step_id=step_id,
            field_name=field_name,
            field_type=field_type,
            generation_rule=generation_rule,
            data_value=data_value,
            rule_config=json.dumps(rule_config) if rule_config else None,
            min_length=min_length,
            max_length=max_length,
            min_value=min_value,
            max_value=max_value,
            enum_values=json.dumps(enum_values) if enum_values else None,
            description=description,
            is_required=is_required,
            sort_order=sort_order
        )
        self.db.add(test_data)
        self.db.commit()
        self.db.refresh(test_data)
        logger.info(f"创建测试数据成功: id={test_data.id}, field_name={field_name}")
        return test_data

    def get_test_data(self, test_data_id: int) -> Optional[TestData]:
        return self.db.query(TestData).filter(TestData.id == test_data_id).first()

    def get_test_data_by_step(self, step_id: int) -> List[TestData]:
        return self.db.query(TestData).filter(
            TestData.step_id == step_id
        ).order_by(TestData.sort_order).all()

    def update_test_data(self, test_data_id: int, **kwargs) -> Optional[TestData]:
        test_data = self.get_test_data(test_data_id)
        if not test_data:
            return None
        if 'rule_config' in kwargs and kwargs['rule_config'] is not None:
            kwargs['rule_config'] = json.dumps(kwargs['rule_config'])
        if 'enum_values' in kwargs and kwargs['enum_values'] is not None:
            kwargs['enum_values'] = json.dumps(kwargs['enum_values'])
        for key, value in kwargs.items():
            if hasattr(test_data, key):
                setattr(test_data, key, value)
        self.db.commit()
        self.db.refresh(test_data)
        logger.info(f"更新测试数据成功: id={test_data_id}")
        return test_data

    def delete_test_data(self, test_data_id: int) -> bool:
        test_data = self.get_test_data(test_data_id)
        if not test_data:
            return False
        self.db.delete(test_data)
        self.db.commit()
        logger.info(f"删除测试数据成功: id={test_data_id}")
        return True
