"""测试数据异步 CRUD 与生成 Mixin。

从 sync 版本（TestDataCrudMixin / TestDataGenServiceMixin）镜像出 async 方法，
供 async 端点直接调用，消除 db.run_sync 线程池桥接开销。

设计要点：
    - 与 sync mixin 共存（hybrid 模式），sync 端点继续用 sync 方法；
    - async 方法使用 AsyncSession + select()/await db.execute()；
    - generate_value 等纯计算方法复用 sync 版本，不重复实现；
    - 方法名加 _async 后缀避免与 sync 方法冲突。

使用方式：
    async def endpoint(..., db: AsyncSession):
        service = TestDataService(db)  # db 为 AsyncSession
        result = await service.create_test_data_async(...)
"""
import json
from typing import Optional, List, Dict, Any

from loguru import logger
from sqlalchemy import select

from app.models.test_data import TestData, DataType, GenerationRule


class TestDataAsyncMixin:
    """测试数据异步操作 Mixin，供 TestDataService 继承。

    要求 self.db 为 AsyncSession 实例。
    generate_value 等纯计算方法复用 sync 版本（TestDataGenServiceMixin）。
    """

    async def create_test_data_async(
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
        sort_order: int = 0,
    ) -> TestData:
        """创建测试数据（异步版本）。"""
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
            sort_order=sort_order,
        )
        self.db.add(test_data)
        await self.db.commit()
        await self.db.refresh(test_data)
        logger.info(f"创建测试数据成功: id={test_data.id}, field_name={field_name}")
        return test_data

    async def get_test_data_async(self, test_data_id: int) -> Optional[TestData]:
        """获取单条测试数据（异步版本）。"""
        result = await self.db.execute(
            select(TestData).where(TestData.id == test_data_id)
        )
        return result.scalars().first()

    async def get_test_data_by_step_async(self, step_id: int) -> List[TestData]:
        """获取步骤的所有测试数据（异步版本）。"""
        result = await self.db.execute(
            select(TestData)
            .where(TestData.step_id == step_id)
            .order_by(TestData.sort_order)
        )
        return result.scalars().all()

    async def update_test_data_async(
        self, test_data_id: int, **kwargs
    ) -> Optional[TestData]:
        """更新测试数据（异步版本）。"""
        test_data = await self.get_test_data_async(test_data_id)
        if not test_data:
            return None
        if "rule_config" in kwargs and kwargs["rule_config"] is not None:
            kwargs["rule_config"] = json.dumps(kwargs["rule_config"])
        if "enum_values" in kwargs and kwargs["enum_values"] is not None:
            kwargs["enum_values"] = json.dumps(kwargs["enum_values"])
        for key, value in kwargs.items():
            if hasattr(test_data, key):
                setattr(test_data, key, value)
        await self.db.commit()
        await self.db.refresh(test_data)
        logger.info(f"更新测试数据成功: id={test_data_id}")
        return test_data

    async def delete_test_data_async(self, test_data_id: int) -> bool:
        """删除测试数据（异步版本）。"""
        test_data = await self.get_test_data_async(test_data_id)
        if not test_data:
            return False
        await self.db.delete(test_data)
        await self.db.commit()
        logger.info(f"删除测试数据成功: id={test_data_id}")
        return True

    async def generate_step_data_async(
        self,
        step_id: int,
        parameterizer: Optional[Any] = None,
    ) -> Dict[str, str]:
        """生成步骤的测试数据（异步版本）。

        generate_value 为纯计算方法（TestDataGenServiceMixin），直接复用。
        """
        test_data_list = await self.get_test_data_by_step_async(step_id)
        result: Dict[str, str] = {}
        for test_data in test_data_list:
            value = self.generate_value(test_data)
            if parameterizer:
                value = parameterizer.parse(value)
            result[test_data.field_name] = value
        return result

    async def auto_generate_for_step_async(
        self, step_id: int, action_description: str
    ) -> List[TestData]:
        """根据操作描述自动推断生成测试数据（异步版本）。"""
        created_list: List[TestData] = []
        if "产品线" in action_description or "产品" in action_description:
            test_data = await self.create_test_data_async(
                step_id=step_id,
                field_name="product_name",
                field_type=DataType.TEXT,
                generation_rule=GenerationRule.RANDOM,
                description="产品线名称",
                is_required=True,
            )
            created_list.append(test_data)
        if "输入" in action_description or "填写" in action_description:
            test_data = await self.create_test_data_async(
                step_id=step_id,
                field_name="input_value",
                field_type=DataType.TEXT,
                generation_rule=GenerationRule.RANDOM,
                description="输入值",
                is_required=True,
            )
            created_list.append(test_data)
        if "选择" in action_description:
            test_data = await self.create_test_data_async(
                step_id=step_id,
                field_name="select_value",
                field_type=DataType.ENUM,
                generation_rule=GenerationRule.RANDOM,
                enum_values=["选项1", "选项2", "选项3"],
                description="选择值",
                is_required=True,
            )
            created_list.append(test_data)
        if "日期" in action_description or "时间" in action_description:
            test_data = await self.create_test_data_async(
                step_id=step_id,
                field_name="date_value",
                field_type=DataType.DATE,
                generation_rule=GenerationRule.RANDOM,
                description="日期",
                is_required=True,
            )
            created_list.append(test_data)
        logger.info(
            f"自动推断生成测试数据: step_id={step_id}, count={len(created_list)}"
        )
        return created_list
