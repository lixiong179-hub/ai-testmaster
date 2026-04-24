"""Excel导出Mixin - 标准格式和功能用例格式的Excel导出。"""
from typing import List
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator


class ExcelExportMixin:
    """Excel导出：标准双Sheet格式、第三方功能用例格式。"""

    def export_to_excel(self, test_case_id: int, file_path: str) -> bool:
        try:
            import pandas as pd

            test_case = self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
            if not test_case:
                logger.warning(f"测试用例不存在: {test_case_id}")
                return False

            steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case_id
            ).order_by(TestStep.step_number).all()

            step_ids = [s.id for s in steps]
            locators = {}
            if step_ids:
                locator_list = self.db.query(ElementLocator).filter(
                    ElementLocator.step_id.in_(step_ids)
                ).all()
                locators = {l.step_id: l for l in locator_list}

            data = []
            for step in steps:
                locator = locators.get(step.id)
                row = {
                    "步骤编号": step.step_number,
                    "操作步骤": step.action,
                    "预期结果": step.expected_result,
                    "业务视图": "是" if step.is_business_view == 1 else "否",
                    "技术视图": "是" if step.is_technical_view == 1 else "否",
                    "已定位": "是" if step.has_locator == 1 else "否",
                    "定位状态": step.locator_status,
                    "CSS选择器": locator.css_selector if locator else "",
                    "XPath": locator.xpath if locator else "",
                    "元素类型": locator.element_type if locator else "",
                }
                data.append(row)

            df = pd.DataFrame(data)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='测试步骤', index=False)
                case_info = pd.DataFrame([{
                    "用例编号": test_case.case_no,
                    "用例标题": test_case.title,
                    "所属模块": test_case.module,
                    "前置条件": test_case.precondition or "",
                    "预期结果": test_case.expected_result or "",
                    "优先级": test_case.priority,
                    "总步骤数": len(steps)
                }])
                case_info.to_excel(writer, sheet_name='用例信息', index=False)

            logger.info(f"测试用例 {test_case_id} 导出Excel成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            return False

    def export_to_functional_excel(self, test_case_ids: List[int], file_path: str) -> bool:
        try:
            import pandas as pd

            test_cases = self.db.query(TestCase).filter(
                TestCase.id.in_(test_case_ids)
            ).all()

            if not test_cases:
                logger.warning(f"未找到测试用例: {test_case_ids}")
                return False

            data = []
            for tc in test_cases:
                steps = self.db.query(TestStep).filter(
                    TestStep.test_case_id == tc.id
                ).order_by(TestStep.step_number).all()

                step_desc = self._build_functional_steps(steps)
                expected = self._build_functional_expected(steps)

                priority_map = {1: 'P0', 2: 'P1', 3: 'P2', 4: 'P3'}
                priority = priority_map.get(tc.priority, 'P2')
                case_type = 'UI自动化' if tc.case_type in ('ui_automation', 'UI', '功能', '功能测试', 'functional') else 'API自动化'

                row = {
                    "标题": tc.title,
                    "执行用例ID": tc.case_no,
                    "所属模块": tc.module or "默认模块",
                    "前置条件": tc.precondition or "",
                    "步骤描述": step_desc,
                    "预期结果": expected or tc.expected_result or "",
                    "用例类型": case_type,
                    "用例等级": priority,
                    "用例执行": ""
                }
                data.append(row)

            df = pd.DataFrame(data)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='测试用例', index=False)

            logger.info(f"导出功能用例Excel成功: {file_path}, 共{len(data)}条用例")
            return True
        except Exception as e:
            logger.error(f"导出功能用例Excel失败: {e}")
            return False

    def _build_functional_steps(self, steps: List[TestStep]) -> str:
        if not steps:
            return ""
        return "\n".join(f"【{s.step_number}】{s.action}" for s in steps)

    def _build_functional_expected(self, steps: List[TestStep]) -> str:
        if not steps:
            return ""
        return "\n".join(f"【{s.step_number}】{s.expected_result}" for s in steps if s.expected_result)
