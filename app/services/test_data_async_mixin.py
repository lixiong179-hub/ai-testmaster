"""测试数据异步桥接 Mixin（R2-1 阶段三：会话层单范式收敛）。

单范式后，异步端点注入的是**同步** ``Session``（``Depends(get_db)``），
因此本 Mixin 不再"用 AsyncSession 重写一遍 SQL"，只保留 ``*_async`` 方法名
做向后兼容：每个方法把同名同步实现（``TestDataCrudMixin`` /
``TestDataGenServiceMixin``）丢进工作线程执行，避免阻塞事件循环。

约定（R2-1 阶段三）：
    - 禁止在本文件出现 ``await self.db.xxx(...)``／``select()`` 等异步 DB 代码；
    - 新增能力请先扩展同步 Mixin，再在此追加一行 ``asyncio.to_thread`` 桥接；
    - ``self.db`` 必须是同步 ``Session``。
"""
import asyncio
from typing import Any

from app.models.test_data import TestData, DataType, GenerationRule


class TestDataAsyncMixin:
    """``*_async`` 方法 = 同步实现 + ``asyncio.to_thread``（要求 ``self.db`` 为 Session）。"""

    async def create_test_data_async(
        self,
        step_id: int,
        field_name: str,
        field_type: DataType = DataType.TEXT,
        generation_rule: GenerationRule = GenerationRule.RANDOM,
        data_value: str | None = None,
        rule_config: dict[str, Any] | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        min_value: int | None = None,
        max_value: int | None = None,
        enum_values: list[str] | None = None,
        description: str | None = None,
        is_required: bool = True,
        sort_order: int = 0,
    ) -> TestData:
        """创建测试数据（异步桥接）。"""
        return await asyncio.to_thread(
            self.create_test_data,
            step_id=step_id,
            field_name=field_name,
            field_type=field_type,
            generation_rule=generation_rule,
            data_value=data_value,
            rule_config=rule_config,
            min_length=min_length,
            max_length=max_length,
            min_value=min_value,
            max_value=max_value,
            enum_values=enum_values,
            description=description,
            is_required=is_required,
            sort_order=sort_order,
        )

    async def get_test_data_async(self, test_data_id: int) -> TestData | None:
        """获取单条测试数据（异步桥接）。"""
        return await asyncio.to_thread(self.get_test_data, test_data_id)

    async def get_test_data_by_step_async(self, step_id: int) -> list[TestData]:
        """获取步骤的所有测试数据（异步桥接）。"""
        return await asyncio.to_thread(self.get_test_data_by_step, step_id)

    async def update_test_data_async(self, test_data_id: int, **kwargs) -> TestData | None:
        """更新测试数据（异步桥接）。"""
        return await asyncio.to_thread(self.update_test_data, test_data_id, **kwargs)

    async def delete_test_data_async(self, test_data_id: int) -> bool:
        """删除测试数据（异步桥接）。"""
        return await asyncio.to_thread(self.delete_test_data, test_data_id)

    async def generate_step_data_async(
        self,
        step_id: int,
        parameterizer: Any | None = None,
    ) -> dict[str, str]:
        """生成步骤的测试数据（异步桥接）。"""
        return await asyncio.to_thread(self.generate_step_data, step_id, parameterizer)

    async def auto_generate_for_step_async(
        self, step_id: int, action_description: str
    ) -> list[TestData]:
        """根据操作描述自动推断生成测试数据（异步桥接）。"""
        return await asyncio.to_thread(self.auto_generate_for_step, step_id, action_description)
