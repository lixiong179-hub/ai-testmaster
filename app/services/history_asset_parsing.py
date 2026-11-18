"""历史资产文件解析（R2-3：从 `endpoints/_history_asset_parsers.py` 下沉）。

职责：把上传的 Excel / XMind 文件解析为统一的用例字典列表。
无 DB 访问、无 HTTP 依赖，纯函数，便于独立单测与复用。

原私有模块已删除；`app/services/history_asset/` 为同名域包（分类/助手），
本模块与它同域但职责单一（仅解析），故独立成模块而非塞进包内。
"""

from typing import Any

from loguru import logger

from app.services.xmind_parser import XmindParser, XmindParseError


def _parse_excel_cases(file_path: str) -> list[dict[str, Any]]:
    """解析 Excel 用例文件。

    支持两种版式：
        1) 双 sheet（`用例信息` + `测试步骤`），按「用例序号」关联步骤；
        2) 单 sheet，按「操作步骤」列是否存在自动识别，空步骤行视为模块名。
    解析失败统一抛 `ValueError`（调用方据此返回 400）。
    """
    import pandas as pd

    cases: list[dict[str, Any]] = []
    try:
        xls = pd.ExcelFile(file_path)
        if "用例信息" in xls.sheet_names and "测试步骤" in xls.sheet_names:
            case_info_df = pd.read_excel(file_path, sheet_name="用例信息")
            steps_df = pd.read_excel(file_path, sheet_name="测试步骤")
            for _, info_row in case_info_df.iterrows():
                case_data = {
                    "title": str(info_row.get("用例标题", "")),
                    "module": str(info_row.get("所属模块", "")),
                    "precondition": str(info_row.get("前置条件", "")),
                    "expected_result": str(info_row.get("预期结果", "")),
                    "priority": int(info_row.get("优先级", 2)),
                    "case_row_index": int(info_row.name) if not pd.isna(info_row.name) else 0,
                    "steps": [],
                }
                cases.append(case_data)
            if cases and not steps_df.empty:
                case_by_index = {c["case_row_index"]: c for c in cases}
                for _, step_row in steps_df.iterrows():
                    step_data = {
                        "step_number": int(step_row.get("步骤编号", 1)),
                        "action": str(step_row.get("操作步骤", "")),
                        "expected_result": str(step_row.get("预期结果", "")),
                    }
                    case_idx = int(step_row.get("用例序号", step_row.get("用例行号", 0)))
                    target_case = case_by_index.get(case_idx)
                    if target_case is None and cases:
                        target_case = cases[min(case_idx, len(cases) - 1)] if case_idx < len(cases) else cases[0]
                    if target_case:
                        target_case["steps"].append(step_data)
                for c in cases:
                    c.pop("case_row_index", None)
        else:
            df = pd.read_excel(file_path, sheet_name=0)
            current_module = ""
            for _, row in df.iterrows():
                raw_step = row.get("操作步骤", row.get("步骤描述", None))
                first_col = row.iloc[0] if len(row) > 0 else None
                if pd.isna(raw_step) or str(raw_step).strip() == "":
                    if first_col is not None and not pd.isna(first_col):
                        val = str(first_col).strip()
                        if val and not val.isdigit():
                            current_module = val
                    continue
                title = str(row.get("用例描述", row.get("标题", ""))).strip()
                if not title:
                    continue
                cases.append(
                    {
                        "title": title,
                        "module": current_module,
                        "precondition": str(row.get("前置条件", "")).strip(),
                        "expected_result": str(row.get("期望结果", row.get("预期结果", ""))).strip(),
                        "priority": 2,
                        "steps": [
                            {
                                "action": str(row.get("操作步骤", row.get("步骤描述", ""))).strip(),
                                "expected_result": str(row.get("期望结果", row.get("预期结果", ""))).strip(),
                            }
                        ],
                    }
                )
    except Exception as e:
        logger.error(f"Excel 解析失败: {e}")
        raise ValueError(f"Excel 解析失败: {e}") from e
    return cases


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
                "priority": 2,
                "steps": point.get("steps", []),
            }
        )
    return cases
