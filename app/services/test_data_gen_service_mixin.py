"""测试数据生成服务Mixin - 批量生成和保存测试数据。
"""
import json
from typing import Optional, List, Dict, Any
from loguru import logger
from app.models.test_data import TestData, DataType, GenerationRule
from app.services.test_data_gen_constants import DataConstraints
from app.services.test_data_parameterizer import TestDataParameterizer, ParameterContext


class TestDataGenServiceMixin:
    def generate_value(self, test_data: TestData) -> str:
        constraints = DataConstraints(
            min_length=test_data.min_length,
            max_length=test_data.max_length,
            min_value=test_data.min_value,
            max_value=test_data.max_value,
            enum_values=json.loads(test_data.enum_values) if test_data.enum_values else None
        )
        rule_config = json.loads(test_data.rule_config) if test_data.rule_config else None
        return self.generator.generate_data(
            field_type=test_data.field_type,
            field_name=test_data.field_name,
            generation_rule=test_data.generation_rule,
            constraints=constraints,
            rule_config=rule_config
        )

    def generate_step_data(
        self,
        step_id: int,
        parameterizer: Optional[TestDataParameterizer] = None
    ) -> Dict[str, str]:
        test_data_list = self.get_test_data_by_step(step_id)
        result = {}
        for test_data in test_data_list:
            value = self.generate_value(test_data)
            if parameterizer:
                value = parameterizer.parse(value)
            result[test_data.field_name] = value
        return result

    def generate_case_data(
        self,
        case_id: int,
        context: Optional[ParameterContext] = None
    ) -> Dict[int, Dict[str, str]]:
        from app.models.test_case import TestCase
        test_case = self.db.query(TestCase).filter(TestCase.id == case_id).first()
        if not test_case:
            logger.warning(f"测试用例不存在: {case_id}")
            return {}
        parameterizer = TestDataParameterizer(context) if context else None
        result = {}
        for step in test_case.test_steps:
            step_data = self.generate_step_data(step.id, parameterizer)
            if step_data:
                result[step.id] = step_data
        return result

    def batch_create_test_data(
        self,
        step_id: int,
        data_list: List[Dict[str, Any]]
    ) -> List[TestData]:
        created_list = []
        for data_config in data_list:
            try:
                test_data = self.create_test_data(step_id=step_id, **data_config)
                created_list.append(test_data)
            except Exception as e:
                logger.error(f"批量创建测试数据失败: {data_config}, error={e}")
        return created_list

    def copy_test_data(self, source_step_id: int, target_step_id: int) -> int:
        source_data_list = self.get_test_data_by_step(source_step_id)
        copied_count = 0
        for source_data in source_data_list:
            try:
                self.create_test_data(
                    step_id=target_step_id,
                    field_name=source_data.field_name,
                    field_type=source_data.field_type,
                    generation_rule=source_data.generation_rule,
                    data_value=source_data.data_value,
                    rule_config=source_data.rule_config,
                    min_length=source_data.min_length,
                    max_length=source_data.max_length,
                    min_value=source_data.min_value,
                    max_value=source_data.max_value,
                    enum_values=source_data.enum_values,
                    description=source_data.description,
                    is_required=source_data.is_required,
                    sort_order=source_data.sort_order
                )
                copied_count += 1
            except Exception as e:
                logger.error(f"复制测试数据失败: {source_data.id}, error={e}")
        logger.info(f"复制测试数据完成: {copied_count} 条")
        return copied_count

    def auto_generate_for_step(
        self,
        step_id: int,
        action_description: str
    ) -> List[TestData]:
        created_list = []
        if "产品线" in action_description or "产品" in action_description:
            test_data = self.create_test_data(
                step_id=step_id,
                field_name="product_name",
                field_type=DataType.TEXT,
                generation_rule=GenerationRule.RANDOM,
                description="产品线名称",
                is_required=True
            )
            created_list.append(test_data)
        if "输入" in action_description or "填写" in action_description:
            test_data = self.create_test_data(
                step_id=step_id,
                field_name="input_value",
                field_type=DataType.TEXT,
                generation_rule=GenerationRule.RANDOM,
                description="输入值",
                is_required=True
            )
            created_list.append(test_data)
        if "选择" in action_description:
            test_data = self.create_test_data(
                step_id=step_id,
                field_name="select_value",
                field_type=DataType.ENUM,
                generation_rule=GenerationRule.RANDOM,
                enum_values=["选项1", "选项2", "选项3"],
                description="选择值",
                is_required=True
            )
            created_list.append(test_data)
        if "日期" in action_description or "时间" in action_description:
            test_data = self.create_test_data(
                step_id=step_id,
                field_name="date_value",
                field_type=DataType.DATE,
                generation_rule=GenerationRule.RANDOM,
                description="日期",
                is_required=True
            )
            created_list.append(test_data)
        logger.info(f"自动推断生成测试数据: step_id={step_id}, count={len(created_list)}")
        return created_list
