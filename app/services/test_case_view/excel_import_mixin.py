"""Excel导入Mixin - 标准格式和功能用例格式的Excel导入。"""
import re
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.enums import LocatorStatus
from app.services.test_case_view.models import BusinessStepView


class ExcelImportMixin:
    """Excel导入：标准双Sheet格式、第三方功能用例格式。"""

    def import_from_excel(self, file_path: str, project_id: int, user_id: int = 1) -> Optional[int]:
        try:
            import pandas as pd

            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"项目不存在: {project_id}")
                return None

            case_info_df = pd.read_excel(file_path, sheet_name='用例信息')
            steps_df = pd.read_excel(file_path, sheet_name='测试步骤')

            if case_info_df.empty or steps_df.empty:
                logger.error("Excel文件格式不正确，缺少必要的数据")
                return None

            case_info = case_info_df.iloc[0]
            original_case_no = str(case_info.get('用例编号', ''))
            case_no = self._generate_unique_case_no(project_id, original_case_no)

            test_case = TestCase(
                project_id=project_id,
                case_no=case_no,
                module=str(case_info.get('所属模块', '默认模块')),
                title=str(case_info.get('用例标题', '未命名用例')),
                precondition=str(case_info.get('前置条件', '')),
                expected_result=str(case_info.get('预期结果', '')),
                priority=int(case_info.get('优先级', 2)),
                case_type="ui_automation",
                generate_status=1,
                steps_json=[]
            )
            self.db.add(test_case)
            self.db.flush()

            for _, row in steps_df.iterrows():
                step = TestStep(
                    test_case_id=test_case.id,
                    step_number=int(row.get('步骤编号', 1)),
                    action=str(row.get('操作步骤', '')),
                    expected_result=str(row.get('预期结果', '')),
                    is_business_view=1 if str(row.get('业务视图', '是')) == '是' else 0,
                    is_technical_view=1 if str(row.get('技术视图', '是')) == '是' else 0,
                    has_locator=1 if str(row.get('已定位', '否')) == '是' else 0,
                    locator_status=str(row.get('定位状态', LocatorStatus.PENDING.value))
                )
                self.db.add(step)
                self.db.flush()

                css_val = row.get('CSS选择器', '')
                xpath_val = row.get('XPath', '')
                type_val = row.get('元素类型', '')

                css_selector = str(css_val) if pd.notna(css_val) and css_val != '' else ''
                xpath = str(xpath_val) if pd.notna(xpath_val) and xpath_val != '' else ''
                element_type = str(type_val) if pd.notna(type_val) and type_val != '' else ''

                if css_selector or xpath:
                    locator = ElementLocator(
                        step_id=step.id,
                        css_selector=css_selector if css_selector else None,
                        xpath=xpath if xpath else None,
                        element_type=element_type if element_type else None
                    )
                    self.db.add(locator)

            self.db.commit()
            logger.info(f"从Excel导入测试用例成功: {test_case.id} (项目: {project_id})")
            return test_case.id
        except Exception as e:
            self.db.rollback()
            logger.error(f"从Excel导入失败: {e}")
            return None

    def import_functional_excel(self, file_path: str, project_id: int, module: str = "默认模块") -> Optional[int]:
        try:
            import pandas as pd

            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"项目不存在: {project_id}")
                return None

            df = pd.read_excel(file_path, sheet_name=0)
            if df.empty:
                logger.error("Excel文件为空")
                return None

            df.columns = [str(col).strip() for col in df.columns]
            imported_cases = []

            for _, row in df.iterrows():
                title = str(row.get('标题', '')).strip()
                if not title:
                    continue

                case_no = str(row.get('执行用例ID', '')).strip()
                if not case_no:
                    case_no = f"TC{project_id}_{int(datetime.now().timestamp())}"

                case_no = self._generate_unique_case_no(project_id, case_no)

                group = str(row.get('所属模块', row.get('所属分组', module))).strip()
                precondition = str(row.get('前置条件', '')).strip()
                step_desc = str(row.get('步骤描述', '')).strip()
                expected = str(row.get('预期结果', '')).strip()
                case_type = str(row.get('用例类型', 'UI自动化')).strip()
                priority_str = str(row.get('用例等级', 'P2')).strip()

                priority_map = {'P0': 1, 'P1': 2, 'P2': 3, 'P3': 4}
                priority = priority_map.get(priority_str.upper(), 2)

                steps = self._parse_functional_steps(step_desc, expected)

                test_case = TestCase(
                    project_id=project_id,
                    case_no=case_no,
                    module=group,
                    title=title,
                    precondition=precondition,
                    expected_result=expected.replace('\\n', '\n'),
                    priority=priority,
                    case_type="ui_automation" if case_type in ('UI自动化', '功能测试', 'UI', '功能') else "api_automation",
                    generate_status=1,
                    steps_json=[s.to_dict() for s in steps]
                )
                self.db.add(test_case)
                self.db.flush()

                for i, step_info in enumerate(steps, 1):
                    step = TestStep(
                        test_case_id=test_case.id,
                        step_number=i,
                        action=step_info.action,
                        expected_result=step_info.expected_result,
                        is_business_view=1,
                        is_technical_view=0,
                        has_locator=0,
                        locator_status=LocatorStatus.PENDING.value
                    )
                    self.db.add(step)

                imported_cases.append(test_case.id)

            self.db.commit()
            logger.info(f"从功能用例Excel导入成功: {len(imported_cases)}条用例")
            return imported_cases[0] if imported_cases else None
        except Exception as e:
            self.db.rollback()
            logger.error(f"从功能用例Excel导入失败: {e}")
            return None

    def _generate_unique_case_no(self, project_id: int, original_case_no: str) -> str:
        if not original_case_no:
            timestamp = int(time.time())
            return f"TC{project_id}_{timestamp}"

        existing = self.db.query(TestCase).filter(
            TestCase.case_no == original_case_no
        ).first()

        if not existing:
            return original_case_no

        counter = 1
        while True:
            new_case_no = f"{original_case_no}_{project_id}_{counter}"
            existing = self.db.query(TestCase).filter(
                TestCase.case_no == new_case_no
            ).first()
            if not existing:
                logger.info(f"用例编号 '{original_case_no}' 已存在，自动重命名为 '{new_case_no}'")
                return new_case_no
            counter += 1

    def _parse_functional_steps(self, step_desc: str, expected: str) -> List[BusinessStepView]:
        steps = []
        step_pattern = r'【(\d+)】([^【]*?)(?=【\d+】|$)'
        step_matches = re.findall(step_pattern, step_desc, re.DOTALL)
        expected_matches = re.findall(step_pattern, expected, re.DOTALL)

        if step_matches:
            expected_dict = {int(m[0]): m[1].strip() for m in expected_matches}
            for num, action in step_matches:
                step_num = int(num)
                action = action.strip().replace('\\n', '\n')
                exp = expected_dict.get(step_num, '').replace('\\n', '\n')
                steps.append(BusinessStepView(step_number=step_num, action=action, expected_result=exp))
        else:
            step_lines = [s.strip() for s in re.split(r'\r?\n', step_desc) if s.strip()]
            expected_lines = [s.strip() for s in re.split(r'\r?\n', expected) if s.strip()]
            for i, action in enumerate(step_lines, 1):
                exp = expected_lines[i-1] if i <= len(expected_lines) else ''
                steps.append(BusinessStepView(step_number=i, action=action, expected_result=exp))

        return steps if steps else [BusinessStepView(1, step_desc, expected)]
