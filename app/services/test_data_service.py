"""
测试数据服务

提供测试数据的CRUD操作和生成管理
集成到测试执行流程
"""
import json
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from app.models.test_data import TestData, DataType, GenerationRule
from app.models.test_case import TestStep
from app.services.test_data_generator import TestDataGenerator, DataConstraints
from app.services.test_data_parameterizer import TestDataParameterizer, ParameterContext


class TestDataService:
    """
    测试数据服务

    功能：
    - 测试数据的增删改查
    - 根据步骤生成测试数据
    - 参数化解析
    - 批量生成
    """

    def __init__(self, db: Session):
        """
        初始化测试数据服务

        Args:
            db: 数据库会话
        """
        self.db = db
        self.generator = TestDataGenerator()

    # ============================================================================
    # CRUD 操作
    # ============================================================================

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
        """
        创建测试数据

        Args:
            step_id: 步骤ID
            field_name: 字段名称
            field_type: 字段类型
            generation_rule: 生成规则
            data_value: 数据值（自定义规则时使用）
            rule_config: 规则配置
            min_length: 最小长度
            max_length: 最大长度
            min_value: 最小值
            max_value: 最大值
            enum_values: 枚举值列表
            description: 描述
            is_required: 是否必填
            sort_order: 排序顺序

        Returns:
            创建的测试数据
        """
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
        """获取单个测试数据"""
        return self.db.query(TestData).filter(TestData.id == test_data_id).first()

    def get_test_data_by_step(self, step_id: int) -> List[TestData]:
        """获取步骤的所有测试数据"""
        return self.db.query(TestData).filter(
            TestData.step_id == step_id
        ).order_by(TestData.sort_order).all()

    def update_test_data(
        self,
        test_data_id: int,
        **kwargs
    ) -> Optional[TestData]:
        """
        更新测试数据

        Args:
            test_data_id: 测试数据ID
            **kwargs: 要更新的字段

        Returns:
            更新后的测试数据
        """
        test_data = self.get_test_data(test_data_id)
        if not test_data:
            return None

        # 处理JSON字段
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
        """删除测试数据"""
        test_data = self.get_test_data(test_data_id)
        if not test_data:
            return False

        self.db.delete(test_data)
        self.db.commit()

        logger.info(f"删除测试数据成功: id={test_data_id}")
        return True

    # ============================================================================
    # 数据生成
    # ============================================================================

    def generate_value(self, test_data: TestData) -> str:
        """
        根据测试数据配置生成值

        Args:
            test_data: 测试数据

        Returns:
            生成的值
        """
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
        """
        生成步骤的所有测试数据

        Args:
            step_id: 步骤ID
            parameterizer: 参数化解析器（可选）

        Returns:
            字段名到值的映射
        """
        test_data_list = self.get_test_data_by_step(step_id)
        result = {}

        for test_data in test_data_list:
            # 生成值
            value = self.generate_value(test_data)

            # 如果提供了参数化解析器，进行参数化解析
            if parameterizer:
                value = parameterizer.parse(value)

            result[test_data.field_name] = value

        return result

    def generate_case_data(
        self,
        case_id: int,
        context: Optional[ParameterContext] = None
    ) -> Dict[int, Dict[str, str]]:
        """
        生成测试用例的所有步骤数据

        Args:
            case_id: 测试用例ID
            context: 参数化上下文

        Returns:
            步骤ID到字段数据的映射
        """
        from app.models.test_case import TestCase

        test_case = self.db.query(TestCase).filter(TestCase.id == case_id).first()
        if not test_case:
            logger.warning(f"测试用例不存在: {case_id}")
            return {}

        # 创建参数化解析器
        parameterizer = TestDataParameterizer(context) if context else None

        result = {}
        for step in test_case.test_steps:
            step_data = self.generate_step_data(step.id, parameterizer)
            if step_data:
                result[step.id] = step_data

        return result

    # ============================================================================
    # 批量操作
    # ============================================================================

    def batch_create_test_data(
        self,
        step_id: int,
        data_list: List[Dict[str, Any]]
    ) -> List[TestData]:
        """
        批量创建测试数据

        Args:
            step_id: 步骤ID
            data_list: 数据配置列表

        Returns:
            创建的测试数据列表
        """
        created_list = []
        for data_config in data_list:
            try:
                test_data = self.create_test_data(
                    step_id=step_id,
                    **data_config
                )
                created_list.append(test_data)
            except Exception as e:
                logger.error(f"批量创建测试数据失败: {data_config}, error={e}")

        return created_list

    def copy_test_data(
        self,
        source_step_id: int,
        target_step_id: int
    ) -> int:
        """
        复制测试数据到另一个步骤

        Args:
            source_step_id: 源步骤ID
            target_step_id: 目标步骤ID

        Returns:
            复制的数量
        """
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

    # ============================================================================
    # 智能生成
    # ============================================================================

    def auto_generate_for_step(
        self,
        step_id: int,
        action_description: str
    ) -> List[TestData]:
        """
        根据操作描述自动推断并生成测试数据

        Args:
            step_id: 步骤ID
            action_description: 操作描述

        Returns:
            生成的测试数据列表
        """
        created_list = []

        # 根据操作描述智能推断需要的字段
        if "产品线" in action_description or "产品" in action_description:
            # 创建产品线相关数据
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
            # 创建输入相关数据
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
            # 创建选择相关数据
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
            # 创建日期相关数据
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
