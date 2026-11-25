"""Excel导入Mixin - 标准格式和功能用例格式的Excel导入。"""

import re
import time
from typing import Any

from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.enums import LocatorStatus
from app.services.test_case_view.models import BusinessStepView
from app.services.case_number_service import CaseNumberService

STEP_COLUMN_KEYS: tuple[str, ...] = ("操作步骤", "步骤描述")
MODULE_COLUMN_KEYS: tuple[str, ...] = ("所属模块", "所属分组")
_FUNCTIONAL_PRIORITY_MAP: dict[str, int] = {"P0": 1, "P1": 1, "P2": 2, "P3": 3}
_UI_CASE_TYPE_MARKERS: tuple[str, ...] = ("UI自动化", "功能测试", "UI", "功能")


def _row_text(row: Any, keys: tuple[str, ...]) -> str:
    """按候选列依次取值并 strip（用于兼容多种列名）。"""
    return str(row.get(keys[0], row.get(keys[1], "") if len(keys) > 1 else "")).strip()


def _is_module_header_row(row: Any, pd: Any) -> bool:
    """模块分组标题行：操作步骤列为空（合并单元格常见形态）。"""
    raw_step = row.get(STEP_COLUMN_KEYS[0], row.get(STEP_COLUMN_KEYS[1], None))
    return bool(pd.isna(raw_step) or str(raw_step).strip() == "")


def _module_from_header_row(row: Any, pd: Any) -> str | None:
    """从标题行首列取模块名；纯数字是数据行序号，不视为模块名。"""
    first_col = row.iloc[0] if len(row) > 0 else None
    if first_col is None or pd.isna(first_col):
        return None
    first_val = str(first_col).strip()
    if not first_val or first_val.isdigit():
        return None
    return first_val


def _resolve_row_module(row: Any, current_module: str, pd: Any) -> str:
    """模块名优先取行内列值，回退到最近一次标题行识别的模块。"""
    col_module = row.get(MODULE_COLUMN_KEYS[0], row.get(MODULE_COLUMN_KEYS[1], None))
    if col_module is None or pd.isna(col_module):
        return current_module
    return str(col_module).strip() or current_module


def _functional_priority(priority_text: str) -> int:
    return _FUNCTIONAL_PRIORITY_MAP.get(priority_text.upper(), 2)


def _is_ui_case_type(case_type: str) -> bool:
    return case_type in _UI_CASE_TYPE_MARKERS


class ExcelImportMixin:
    """Excel导入：标准双Sheet格式、第三方功能用例格式。"""

    def import_from_excel(
        self,
        file_path: str,
        project_id: int,
        user_id: int = 1,
        target_device: str | None = None,
        iteration_id: int | None = None,
    ) -> int | None:
        try:
            import pandas as pd

            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"项目不存在: {project_id}")
                return None

            case_info_df = pd.read_excel(file_path, sheet_name="用例信息")
            steps_df = pd.read_excel(file_path, sheet_name="测试步骤")

            if case_info_df.empty or steps_df.empty:
                logger.error("Excel文件格式不正确，缺少必要的数据")
                return None

            case_info = case_info_df.iloc[0]
            original_case_no = str(case_info.get("用例编号", ""))
            case_no = CaseNumberService.generate(project_id, self.db)

            test_case = TestCase(
                project_id=project_id,
                case_no=case_no,
                legacy_case_no=original_case_no if original_case_no else None,
                module=str(case_info.get("所属模块", "默认模块")),
                title=str(case_info.get("用例标题", "未命名用例")),
                precondition=str(case_info.get("前置条件", "")),
                expected_result=str(case_info.get("预期结果", "")),
                priority=int(case_info.get("优先级", 2)),
                case_type="ui_automation",
                target_device=target_device,
                generate_status=1,
                steps_json=[],
            )
            self.db.add(test_case)
            self.db.flush()

            for _, row in steps_df.iterrows():
                step = TestStep(
                    test_case_id=test_case.id,
                    step_number=int(row.get("步骤编号", 1)),
                    action=str(row.get("操作步骤", "")),
                    expected_result=str(row.get("预期结果", "")),
                    is_business_view=1 if str(row.get("业务视图", "是")) == "是" else 0,
                    is_technical_view=1 if str(row.get("技术视图", "是")) == "是" else 0,
                    has_locator=1 if str(row.get("已定位", "否")) == "是" else 0,
                    locator_status=str(row.get("定位状态", LocatorStatus.PENDING.value)),
                )
                self.db.add(step)
                self.db.flush()

                css_val = row.get("CSS选择器", "")
                xpath_val = row.get("XPath", "")
                type_val = row.get("元素类型", "")

                css_selector = str(css_val) if pd.notna(css_val) and css_val != "" else ""
                xpath = str(xpath_val) if pd.notna(xpath_val) and xpath_val != "" else ""
                element_type = str(type_val) if pd.notna(type_val) and type_val != "" else ""

                if css_selector or xpath:
                    locator = ElementLocator(
                        step_id=step.id,
                        css_selector=css_selector if css_selector else None,
                        xpath=xpath if xpath else None,
                        element_type=element_type if element_type else None,
                    )
                    self.db.add(locator)

            self.db.commit()
            logger.info(f"从Excel导入测试用例成功: {test_case.id} (项目: {project_id})")
            return test_case.id
        except Exception as e:
            self.db.rollback()
            logger.error(f"从Excel导入失败: {e}")
            return None

    def import_functional_excel(
        self,
        file_path: str,
        project_id: int,
        module: str = "默认模块",
        target_device: str | None = None,
        iteration_id: int | None = None,
    ) -> list[int]:
        try:
            import pandas as pd

            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"项目不存在: {project_id}")
                return []

            df = pd.read_excel(file_path, sheet_name=0)
            if df.empty:
                logger.error("Excel文件为空")
                return []

            df.columns = [str(col).strip() for col in df.columns]
            imported_cases = []
            current_module = module  # 跟踪当前模块名（从合并行提取）

            for _, row in df.iterrows():
                if _is_module_header_row(row, pd):
                    current_module = _module_from_header_row(row, pd) or current_module
                    continue

                title = _row_text(row, ("用例描述", "标题"))
                if not title:
                    continue

                test_case, steps = self._build_functional_case(
                    row=row,
                    project_id=project_id,
                    title=title,
                    group=_resolve_row_module(row, current_module, pd),
                    target_device=target_device,
                    pd=pd,
                )
                self.db.add(test_case)
                self.db.flush()
                self._add_functional_steps(test_case, steps)
                imported_cases.append(test_case.id)

            self.db.commit()
            logger.info(f"从功能用例Excel导入成功: {len(imported_cases)}条用例")
            return imported_cases
        except Exception as e:
            self.db.rollback()
            logger.error(f"从功能用例Excel导入失败: {e}")
            return []

    def _build_functional_case(
        self,
        row: Any,
        project_id: int,
        title: str,
        group: str,
        target_device: str | None,
        pd: Any,
    ) -> tuple[TestCase, list[BusinessStepView]]:
        """功能用例行 → (TestCase 实体, 业务步骤列表)；编号/优先级/类型的兼容规则集中在此。"""
        case_no = _row_text(row, ("执行用例ID",))
        # 用例序号是模块内序号（1,2,3...），不能作为唯一编号；仅当非纯数字时视为真实编号
        raw_seq = _row_text(row, ("用例序号",))
        if not case_no and raw_seq and not raw_seq.isdigit():
            case_no = raw_seq
        original_case_no = case_no if case_no else None
        case_no = CaseNumberService.generate(project_id, self.db)

        expected = _row_text(row, ("期望结果", "预期结果"))
        steps = self._parse_functional_steps(_row_text(row, ("操作步骤", "步骤描述")), expected)
        case_type = _row_text(row, ("用例类型",)) or "UI自动化"

        test_case = TestCase(
            project_id=project_id,
            case_no=case_no,
            legacy_case_no=original_case_no,
            module=group,
            title=title,
            precondition=_row_text(row, ("初始条件", "前置条件")),
            expected_result=expected.replace("\\n", "\n"),
            priority=_functional_priority(_row_text(row, ("优先级", "用例等级"))),
            case_type="ui_automation" if _is_ui_case_type(case_type) else "api_automation",
            target_device=target_device,
            generate_status=1,
            steps_json=[s.to_dict() for s in steps],
        )
        return test_case, steps

    def _add_functional_steps(self, test_case: TestCase, steps: list[BusinessStepView]) -> None:
        """按顺序落业务视图步骤（技术视图待定位阶段补齐）。"""
        for i, step_info in enumerate(steps, 1):
            self.db.add(
                TestStep(
                    test_case_id=test_case.id,
                    step_number=i,
                    action=step_info.action,
                    expected_result=step_info.expected_result,
                    is_business_view=1,
                    is_technical_view=0,
                    has_locator=0,
                    locator_status=LocatorStatus.PENDING.value,
                )
            )

    def _generate_unique_case_no(self, project_id: int, original_case_no: str) -> str:
        if not original_case_no:
            timestamp = int(time.time())
            return f"TC{project_id}_{timestamp}"

        existing = (
            self.db.query(TestCase).filter(TestCase.case_no == original_case_no, TestCase.is_deleted.is_(False)).first()
        )

        if not existing:
            return original_case_no

        counter = 1
        while True:
            new_case_no = f"{original_case_no}_{project_id}_{counter}"
            existing = (
                self.db.query(TestCase).filter(TestCase.case_no == new_case_no, TestCase.is_deleted.is_(False)).first()
            )
            if not existing:
                logger.info(f"用例编号 '{original_case_no}' 已存在，自动重命名为 '{new_case_no}'")
                return new_case_no
            counter += 1

    def _parse_functional_steps(self, step_desc: str, expected: str) -> list[BusinessStepView]:
        steps = []
        step_pattern = r"(?:【(\d+)】|\[(\d+)\])\s*((?:(?!【\d+】|\[\d+\]).)*)"
        step_matches = re.findall(step_pattern, step_desc, re.DOTALL)
        expected_matches = re.findall(step_pattern, expected, re.DOTALL)

        def _extract_num(m: tuple) -> int:
            return int(m[0]) if m[0] else int(m[1])

        if step_matches:
            expected_dict = {_extract_num(m): m[2].strip() for m in expected_matches}
            for m in step_matches:
                step_num = _extract_num(m)
                action = m[2].strip().replace("\\n", "\n")
                exp = expected_dict.get(step_num, "").replace("\\n", "\n")
                steps.append(BusinessStepView(step_number=step_num, action=action, expected_result=exp))
        else:
            step_lines = [s.strip() for s in re.split(r"\r?\n", step_desc) if s.strip()]
            expected_lines = [s.strip() for s in re.split(r"\r?\n", expected) if s.strip()]
            for i, action in enumerate(step_lines, 1):
                exp = expected_lines[i - 1] if i <= len(expected_lines) else ""
                steps.append(BusinessStepView(step_number=i, action=action, expected_result=exp))

        return steps if steps else [BusinessStepView(1, step_desc, expected)]
