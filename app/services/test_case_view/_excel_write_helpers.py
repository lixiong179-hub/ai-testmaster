"""Excel 导出布局与取数辅助（G-8 B5k 从 `ExcelExportMixin` 拆出）。

两个导出方法原先各自在 try 块里混了「查库取数 / 列定义 / 单元格布局 / 落盘」四件事，
这里只承载前两类中可独立测试的部分，Mixin 侧保留「组织调用 + 落盘 + 异常兜底」。
"""

from collections import OrderedDict
from typing import Any

from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase, TestStep

INFO_HEADERS: tuple[str, ...] = ("用例编号", "用例标题", "所属模块", "前置条件", "预期结果", "优先级", "总步骤数")
INFO_WIDTHS: tuple[float, ...] = (14, 40, 18, 30, 30)
STEP_WRAP_COLUMNS: tuple[int, ...] = (2, 3, 8, 9)

STEP_HEADERS: tuple[str, ...] = (
    "步骤编号",
    "操作步骤",
    "预期结果",
    "业务视图",
    "技术视图",
    "已定位",
    "定位状态",
    "CSS选择器",
    "XPath",
    "元素类型",
)
STEP_COL_WIDTHS: tuple[float, ...] = (10, 30, 30, 10, 10, 10, 12, 24, 24, 14)

FUNCTIONAL_COLUMNS: tuple[str, ...] = (
    "用例序号",
    "优先级",
    "用例描述",
    "初始条件",
    "操作步骤",
    "期望结果",
    "测试结果",
    "测试人",
)
FUNCTIONAL_COL_WIDTHS: tuple[float, ...] = (12, 8, 30, 25, 35, 35, 12, 10)

PRIORITY_MAP: dict[int, str] = {1: "P0", 2: "P2", 3: "P3"}


def _load_locators_by_step(db: Any, step_ids: list[int]) -> dict[int, ElementLocator]:
    """step_id → 定位器；无步骤时跳过查询。"""
    if not step_ids:
        return {}
    rows = db.query(ElementLocator).filter(ElementLocator.step_id.in_(step_ids)).all()
    return {loc.step_id: loc for loc in rows}


def _load_case_with_steps(
    db: Any, test_case_id: int
) -> tuple[TestCase | None, list[TestStep], dict[int, ElementLocator]]:
    """标准格式导出取数：用例 + 有序步骤 + 定位器映射。"""
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.is_deleted.is_(False)).first()
    if not test_case:
        return None, [], {}
    steps = db.query(TestStep).filter(TestStep.test_case_id == test_case_id).order_by(TestStep.step_number).all()
    return test_case, steps, _load_locators_by_step(db, [s.id for s in steps])


def _load_steps_by_case(db: Any, test_cases: list[TestCase]) -> dict[int, list[TestStep]]:
    """一次查出全部步骤并按 case_id 分组（避免 N+1）。"""
    case_ids = [tc.id for tc in test_cases]
    rows = (
        db.query(TestStep)
        .filter(TestStep.test_case_id.in_(case_ids))
        .order_by(TestStep.test_case_id, TestStep.step_number)
        .all()
    )
    steps_by_case: dict[int, list[TestStep]] = {}
    for step in rows:
        steps_by_case.setdefault(step.test_case_id, []).append(step)
    return steps_by_case


def _group_cases_by_module(test_cases: list[TestCase]) -> OrderedDict[str, list[TestCase]]:
    """按模块分组并保持用例原顺序（空模块名归入「默认模块」）。"""
    modules: OrderedDict[str, list[TestCase]] = OrderedDict()
    for tc in test_cases:
        modules.setdefault(tc.module or "默认模块", []).append(tc)
    return modules


def _write_info_sheet(ws: Any, test_case: TestCase, steps: list[TestStep], header_font: Any, header_fill: Any) -> None:
    """Sheet1「用例信息」：表头 + 单行值 + 列宽。"""
    info_values: tuple[Any, ...] = (
        test_case.case_no or "",
        test_case.title or "",
        test_case.module or "",
        test_case.precondition or "",
        test_case.expected_result or "",
        test_case.priority,
        len(steps),
    )
    for col_idx, header in enumerate(INFO_HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
    for col_idx, value in enumerate(info_values, 1):
        ws.cell(row=2, column=col_idx, value=value)
    for col_idx, width in enumerate(INFO_WIDTHS, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width


def _step_row(step: TestStep, locator: ElementLocator | None) -> list[Any]:
    """单步骤行值；定位器缺失时三列留空。"""
    return [
        step.step_number,
        step.action or "",
        step.expected_result or "",
        "是" if step.is_business_view == 1 else "否",
        "是" if step.is_technical_view == 1 else "否",
        "是" if step.has_locator == 1 else "否",
        step.locator_status or "",
        locator.css_selector if locator else "",
        locator.xpath if locator else "",
        locator.element_type if locator else "",
    ]


def _write_steps_sheet(
    ws: Any,
    steps: list[TestStep],
    locators: dict[int, ElementLocator],
    header_font: Any,
    header_fill: Any,
    wrap: Any,
) -> None:
    """Sheet2「测试步骤」：表头 + 逐步骤行 + 长文本列换行 + 列宽。"""
    for col_idx, header in enumerate(STEP_HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
    for row_idx, step in enumerate(steps, 2):
        for col_idx, value in enumerate(_step_row(step, locators.get(step.id)), 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if col_idx in STEP_WRAP_COLUMNS:
                cell.alignment = wrap
    for col_idx, width in enumerate(STEP_COL_WIDTHS, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width


def _write_functional_header(ws: Any, header_font: Any, header_fill: Any, thin_border: Any) -> None:
    """功能用例表头 + 列宽。"""
    for col_idx, col_name in enumerate(FUNCTIONAL_COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = _center_alignment()
    for col_idx, width in enumerate(FUNCTIONAL_COL_WIDTHS, 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width


def _center_alignment() -> Any:
    """表头/序号列居中：复用 openpyxl Alignment，避免在 Mixin 里再引样式类。"""
    from openpyxl.styles import Alignment

    return Alignment(horizontal="center", vertical="center")


def _write_module_title(
    ws: Any, row: int, module_name: str, module_font: Any, module_fill: Any, thin_border: Any
) -> None:
    """模块分组标题行（合并单元格 + 居中 + 全行边框）。"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(FUNCTIONAL_COLUMNS))
    module_cell = ws.cell(row=row, column=1, value=module_name)
    module_cell.font = module_font
    module_cell.fill = module_fill
    module_cell.alignment = _center_alignment()
    for ci in range(1, len(FUNCTIONAL_COLUMNS) + 1):
        ws.cell(row=row, column=ci).border = thin_border


def _write_functional_case_row(
    ws: Any,
    row: int,
    row_data: list[Any],
    thin_border: Any,
    center_alignment: Any,
    wrap_alignment: Any,
) -> None:
    """一行功能用例：序号/优先级居中，其余自动换行。"""
    for col_idx, value in enumerate(row_data, 1):
        cell = ws.cell(row=row, column=col_idx, value=value)
        cell.border = thin_border
        cell.alignment = center_alignment if col_idx in (1, 2) else wrap_alignment


__all__ = [
    "FUNCTIONAL_COLUMNS",
    "INFO_HEADERS",
    "PRIORITY_MAP",
    "_group_cases_by_module",
    "_load_case_with_steps",
    "_load_steps_by_case",
    "_write_functional_case_row",
    "_write_functional_header",
    "_write_info_sheet",
    "_write_module_title",
    "_write_steps_sheet",
]
