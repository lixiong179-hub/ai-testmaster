from typing import Any

from loguru import logger

from app.services.xmind_parser import XmindParser, XmindParseError


def _parse_excel_cases(file_path: str) -> list[dict[str, Any]]:
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
                cases.append({
                    "title": title,
                    "module": current_module,
                    "precondition": str(row.get("前置条件", "")).strip(),
                    "expected_result": str(row.get("期望结果", row.get("预期结果", ""))).strip(),
                    "priority": 2,
                    "steps": [{
                        "action": str(row.get("操作步骤", row.get("步骤描述", ""))).strip(),
                        "expected_result": str(row.get("期望结果", row.get("预期结果", ""))).strip(),
                    }],
                })
    except Exception as e:
        logger.error(f"Excel 解析失败: {e}")
        raise ValueError(f"Excel 解析失败: {e}") from e
    return cases


def _parse_xmind_cases(file_path: str) -> list[dict[str, Any]]:
    parser = XmindParser()
    try:
        raw_points = parser.parse(file_path)
    except XmindParseError as e:
        logger.error(f"XMind 解析失败: {e}")
        raise ValueError(f"XMind 解析失败: {e}") from e
    cases: list[dict[str, Any]] = []
    for point in raw_points:
        cases.append({
            "title": point.get("name", ""),
            "module": point.get("module", ""),
            "precondition": "",
            "expected_result": point.get("expected", ""),
            "priority": 2,
            "steps": point.get("steps", []),
        })
    return cases
