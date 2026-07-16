"""测试用例 CRUD 共享工具函数。

本模块存放 test_case_crud 与 test_case_crud_batch 共享的纯工具函数，
包括步骤合并与步骤/测试数据持久化（async 版本）。

迁移说明（P0 服务 async 化）:
    create_steps_and_test_data 改为 async，供 crud 与 batch 端点共享。
"""
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.test_case import TestCaseCreate
from app.models.test_case import TestStep
from app.models.test_data import TestData, DataType, GenerationRule


def merge_test_data_to_steps(test_case: TestCaseCreate) -> list:
    steps_list = [step.model_dump() for step in test_case.steps]
    top_level_test_data = getattr(test_case, 'test_data', None)
    if top_level_test_data and isinstance(top_level_test_data, dict) and steps_list:
        steps_list[0]['test_data'] = top_level_test_data
    return steps_list


async def create_steps_and_test_data(
    test_case: TestCaseCreate, new_test_case_id: int, db: AsyncSession
) -> None:
    """创建用例步骤与关联测试数据（async 版本，供 crud 与 batch 端点共享）。"""
    for i, step_data in enumerate(test_case.steps or []):
        step = TestStep(
            test_case_id=new_test_case_id,
            step_number=i + 1,
            action=step_data.action,
            expected_result=step_data.expected_result if step_data.expected_result else "",
            action_type=step_data.action_type if hasattr(step_data, 'action_type') and step_data.action_type else None,
            input_value=step_data.input_value if hasattr(step_data, 'input_value') and step_data.input_value else None,
            target_element=step_data.target_element if hasattr(step_data, 'target_element') and step_data.target_element else None,
            is_business_view=1,
            is_technical_view=1
        )
        db.add(step)
        await db.flush()

        step_test_data = step_data.test_data if hasattr(step_data, 'test_data') and step_data.test_data else None
        if step_test_data and isinstance(step_test_data, list):
            for j, td in enumerate(step_test_data):
                if not isinstance(td, dict):
                    continue
                field_type_str = td.get('field_type', 'text')
                try:
                    field_type = DataType(field_type_str)
                except ValueError:
                    field_type = DataType.TEXT

                gen_rule_str = td.get('generation_rule', 'custom')
                try:
                    gen_rule = GenerationRule(gen_rule_str)
                except ValueError:
                    gen_rule = GenerationRule.CUSTOM

                enum_values = td.get('enum_values')
                enum_values_str = json.dumps(enum_values, ensure_ascii=False) if enum_values else None

                test_data_record = TestData(
                    step_id=step.id,
                    field_name=td.get('field_name', ''),
                    field_type=field_type,
                    data_value=td.get('data_value', ''),
                    generation_rule=gen_rule,
                    enum_values=enum_values_str,
                    description=td.get('description', ''),
                    is_required=True,
                    sort_order=j
                )
                db.add(test_data_record)
