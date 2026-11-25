"""Excel导出Mixin - 标准格式和功能用例格式的Excel导出。"""

from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.services.test_case_view._excel_write_helpers import (
    PRIORITY_MAP,
    _group_cases_by_module,
    _load_case_with_steps,
    _load_steps_by_case,
    _write_functional_case_row,
    _write_functional_header,
    _write_info_sheet,
    _write_module_title,
    _write_steps_sheet,
)


class ExcelExportMixin:
    """Excel导出：标准双Sheet格式、第三方功能用例格式。"""

    def export_to_excel(self, test_case_id: int, file_path: str) -> bool:
        """导出单条用例为标准双 Sheet Excel（用例信息 + 测试步骤），纯 openpyxl 实现。"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill

            test_case, steps, locators = _load_case_with_steps(self.db, test_case_id)
            if not test_case:
                logger.warning(f"测试用例不存在: {test_case_id}")
                return False

            wb = Workbook()
            header_font = Font(bold=True)
            header_fill = PatternFill(start_color="D9D2E9", end_color="D9D2E9", fill_type="solid")

            ws_info = wb.active
            ws_info.title = "用例信息"
            _write_info_sheet(ws_info, test_case, steps, header_font, header_fill)

            ws_steps = wb.create_sheet(title="测试步骤")
            wrap = Alignment(wrap_text=True, vertical="top")
            _write_steps_sheet(ws_steps, steps, locators, header_font, header_fill, wrap)

            wb.save(file_path)
            logger.info(f"测试用例 {test_case_id} 导出Excel成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出Excel失败: {e}", exc_info=True)
            return False

    def export_to_functional_excel(self, test_case_ids: list[int], file_path: str) -> bool:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

            if not test_case_ids:
                logger.warning("未提供测试用例ID列表")
                return False

            test_cases = (
                self.db.query(TestCase).filter(TestCase.id.in_(test_case_ids), TestCase.is_deleted.is_(False)).all()
            )
            if not test_cases:
                logger.warning(f"未找到测试用例: {test_case_ids}")
                return False

            # 按调用方传入的 ID 顺序排列，保证导出顺序稳定
            id_order = {tid: idx for idx, tid in enumerate(test_case_ids)}
            test_cases.sort(key=lambda tc: id_order.get(tc.id, 0))

            wb = Workbook()
            ws = wb.active
            ws.title = "测试用例"

            # 样式定义
            header_font = Font(bold=True, size=11)
            header_fill = PatternFill(start_color="D9D2E9", end_color="D9D2E9", fill_type="solid")
            module_font = Font(bold=True, size=11)
            module_fill = PatternFill(start_color="E8E0F0", end_color="E8E0F0", fill_type="solid")
            thin_border = Border(
                left=Side(style="thin"),
                right=Side(style="thin"),
                top=Side(style="thin"),
                bottom=Side(style="thin"),
            )
            wrap_alignment = Alignment(wrap_text=True, vertical="top")
            center_alignment = Alignment(horizontal="center", vertical="top")

            _write_functional_header(ws, header_font, header_fill, thin_border)

            current_row = 2
            # 批量查询所有步骤，避免 N+1
            steps_by_case = _load_steps_by_case(self.db, test_cases)

            for module_name, cases in _group_cases_by_module(test_cases).items():
                _write_module_title(ws, current_row, module_name, module_font, module_fill, thin_border)
                current_row += 1

                for seq, tc in enumerate(cases, 1):
                    row_data = self._build_functional_row_data(seq, tc, steps_by_case.get(tc.id, []))
                    _write_functional_case_row(ws, current_row, row_data, thin_border, center_alignment, wrap_alignment)
                    current_row += 1

            wb.save(file_path)
            logger.info(f"导出功能用例Excel成功: {file_path}, 共{len(test_cases)}条用例")
            return True
        except Exception as e:
            logger.error(f"导出功能用例Excel失败: {e}")
            return False

    def _build_functional_row_data(self, seq: int, test_case: TestCase, steps: list[TestStep]) -> list:
        """一行功能用例的取值（期望结果为空时回退用例级 expected_result）。"""
        expected = self._build_functional_expected(steps) or test_case.expected_result or ""
        return [
            seq,
            PRIORITY_MAP.get(test_case.priority, "P2"),
            test_case.title or "",
            test_case.precondition or "",
            self._build_functional_steps(steps),
            expected,
            "",
            "",
        ]

    def _build_functional_steps(self, steps: list[TestStep]) -> str:
        if not steps:
            return ""
        return "\n".join(f"[{s.step_number}] {s.action}" for s in steps)

    def _build_functional_expected(self, steps: list[TestStep]) -> str:
        if not steps:
            return ""
        items = []
        for s in steps:
            if s.expected_result:
                items.append(f"[{s.step_number}] {s.expected_result}")
        return "\n".join(items)
