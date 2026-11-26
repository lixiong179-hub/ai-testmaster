"""历史资产文件解析（R2-3：从 `endpoints/_history_asset_parsers.py` 下沉）。

职责：把上传的 Excel / XMind 文件解析为统一的用例字典列表。
无 DB 访问、无 HTTP 依赖，纯函数，便于独立单测与复用。

原私有模块已删除；`app/services/history_asset/` 为同名域包（分类/助手），
本模块与它同域但职责单一（仅解析），故独立成模块而非塞进包内。
"""

from typing import Any

from loguru import logger

from app.services.xmind_parser import XmindParser, XmindParseError


def _cell_text(value: Any, pd) -> str:
    """单元格转文本：空值 / NaN 统一为空串（避免出现字符串 "nan"）。"""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _case_row_to_dict(info_row, pd) -> dict[str, Any]:
    """把「用例信息」sheet 的一行转成用例字典。"""
    row_name = info_row.name
    return {
        "title": _cell_text(info_row.get("用例标题", ""), pd),
        "module": _cell_text(info_row.get("所属模块", ""), pd),
        "precondition": _cell_text(info_row.get("前置条件", ""), pd),
        "expected_result": _cell_text(info_row.get("预期结果", ""), pd),
        "priority": int(info_row.get("优先级", 2)),
        "case_row_index": int(row_name) if not pd.isna(row_name) else 0,
        "steps": [],
    }


def _fallback_case(cases: list[dict[str, Any]], case_idx: int) -> dict[str, Any] | None:
    """用例序号无法精确命中时：越界取首条，其余按序号取。"""
    if not cases:
        return None
    return cases[case_idx] if case_idx < len(cases) else cases[0]


def _attach_steps(cases: list[dict[str, Any]], steps_df, pd) -> None:
    """按「用例序号」把测试步骤挂到对应用例上。"""
    case_by_index = {case["case_row_index"]: case for case in cases}
    for _, step_row in steps_df.iterrows():
        case_idx = int(step_row.get("用例序号", step_row.get("用例行号", 0)))
        target_case = case_by_index.get(case_idx) or _fallback_case(cases, case_idx)
        if not target_case:
            continue
        target_case["steps"].append(
            {
                "step_number": int(step_row.get("步骤编号", 1)),
                "action": str(step_row.get("操作步骤", "")),
                "expected_result": str(step_row.get("预期结果", "")),
            }
        )
    for case in cases:
        case.pop("case_row_index", None)


def _read_dual_sheet(file_path: str, pd) -> list[dict[str, Any]]:
    """双 sheet 版式：用例信息 + 测试步骤。"""
    case_info_df = pd.read_excel(file_path, sheet_name="用例信息")
    steps_df = pd.read_excel(file_path, sheet_name="测试步骤")
    cases = [_case_row_to_dict(info_row, pd) for _, info_row in case_info_df.iterrows()]
    if cases and not steps_df.empty:
        _attach_steps(cases, steps_df, pd)
    return cases


def _module_from_row(row, current_module: str, pd) -> str:
    """空步骤行：首列非数字文本视为模块名。"""
    first_col = row.iloc[0] if len(row) > 0 else None
    if first_col is None or pd.isna(first_col):
        return current_module
    value = str(first_col).strip()
    return value if value and not value.isdigit() else current_module


def _single_row_to_case(row, title: str, module: str, pd) -> dict[str, Any]:
    """单 sheet 版式：一行即一条用例（含单步）。"""
    expected = _cell_text(row.get("期望结果", row.get("预期结果", "")), pd)
    return {
        "title": title,
        "module": module,
        "precondition": _cell_text(row.get("前置条件", ""), pd),
        "expected_result": expected,
        "priority": 2,
        "steps": [
            {
                "action": _cell_text(row.get("操作步骤", row.get("步骤描述", "")), pd),
                "expected_result": expected,
            }
        ],
    }


def _read_single_sheet(file_path: str, pd) -> list[dict[str, Any]]:
    """单 sheet 版式：空步骤行累积模块名，其余行转用例。"""
    df = pd.read_excel(file_path, sheet_name=0)
    cases: list[dict[str, Any]] = []
    current_module = ""
    for _, row in df.iterrows():
        raw_step = row.get("操作步骤", row.get("步骤描述", None))
        if raw_step is None or pd.isna(raw_step) or str(raw_step).strip() == "":
            current_module = _module_from_row(row, current_module, pd)
            continue
        title = _cell_text(row.get("用例描述", row.get("标题", "")), pd)
        if not title:
            continue
        cases.append(_single_row_to_case(row, title, current_module, pd))
    return cases


def _parse_excel_cases(file_path: str) -> list[dict[str, Any]]:
    """解析 Excel 用例文件。

    支持两种版式：
        1) 双 sheet（`用例信息` + `测试步骤`），按「用例序号」关联步骤；
        2) 单 sheet，按「操作步骤」列是否存在自动识别，空步骤行视为模块名。
    解析失败统一抛 `ValueError`（调用方据此返回 400）。
    """
    import pandas as pd

    try:
        xls = pd.ExcelFile(file_path)
        if "用例信息" in xls.sheet_names and "测试步骤" in xls.sheet_names:
            return _read_dual_sheet(file_path, pd)
        return _read_single_sheet(file_path, pd)
    except Exception as e:
        logger.error(f"Excel 解析失败: {e}")
        raise ValueError(f"Excel 解析失败: {e}") from e


def _parse_xmind_cases(file_path: str) -> list[dict[str, Any]]:
    """解析 XMind 用例文件（委托 `XmindParser`），失败抛 `ValueError`。"""
    parser = XmindParser()
    try:
        raw_points = parser.parse(file_path)
    except XmindParseError as e:
        logger.error(f"XMind 解析失败: {e}")
        raise ValueError(f"XMind 解析失败: {e}") from e
    cases: list[dict[str, Any]] = []
    for point in raw_points:
        cases.append(
            {
                "title": point.get("name", ""),
                "module": point.get("module", ""),
                "precondition": "",
                "expected_result": point.get("expected", ""),
                "steps": point.get("steps", []),
            }
        )
    return cases
