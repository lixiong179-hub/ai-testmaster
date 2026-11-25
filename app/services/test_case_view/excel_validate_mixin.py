"""Excel验证Mixin - 标准格式和功能用例格式的Excel验证。"""

from typing import Any

from loguru import logger

INFO_SHEET = "用例信息"
STEP_SHEET = "测试步骤"
INFO_REQUIRED_COLUMN = "用例标题"
STEP_REQUIRED_COLUMNS: tuple[str, ...] = ("步骤编号", "操作步骤", "预期结果")


def _missing_required_sheets(sheet_names: list[str]) -> list[str]:
    """标准格式必备的两个 sheet。"""
    return [f"缺少'{name}'sheet" for name in (INFO_SHEET, STEP_SHEET) if name not in sheet_names]


def _collect_sheet_errors(label: str, df: Any, required_columns: tuple[str, ...], errors: list[str]) -> None:
    """sheet 空表/缺列检查，结果追加到 errors。"""
    if df.empty:
        errors.append(f"'{label}'sheet为空")
        return
    for col in required_columns:
        if col not in df.columns:
            errors.append(f"'{label}'sheet缺少'{col}'列")


class ExcelValidateMixin:
    """Excel格式验证：标准双Sheet格式、第三方功能用例格式。"""

    def validate_excel_format(self, file_path: str) -> dict[str, Any]:
        result = {"valid": False, "errors": [], "warnings": []}
        try:
            import os

            import pandas as pd

            if not os.path.exists(file_path):
                result["errors"].append("文件不存在")
                return result

            sheet_names = pd.ExcelFile(file_path).sheet_names
            result["errors"].extend(_missing_required_sheets(sheet_names))
            if result["errors"]:
                return result

            case_info_df = pd.read_excel(file_path, sheet_name="用例信息")
            steps_df = pd.read_excel(file_path, sheet_name="测试步骤")
            _collect_sheet_errors("用例信息", case_info_df, (INFO_REQUIRED_COLUMN,), result["errors"])
            _collect_sheet_errors("测试步骤", steps_df, STEP_REQUIRED_COLUMNS, result["errors"])

            if not result["errors"]:
                result["valid"] = True
                result["case_count"] = len(case_info_df)
                result["step_count"] = len(steps_df)

            return result
        except Exception as e:
            logger.error(f"验证失败: {e}")
            result["errors"].append("验证失败")
            return result

    def validate_functional_excel(self, file_path: str) -> dict[str, Any]:
        result = {"valid": False, "errors": [], "warnings": [], "format_type": "functional"}
        try:
            import pandas as pd
            import os

            if not os.path.exists(file_path):
                result["errors"].append("文件不存在")
                return result

            df = pd.read_excel(file_path, sheet_name=0)
            if df.empty:
                result["errors"].append("Excel文件为空")
                return result

            df.columns = [str(col).strip() for col in df.columns]

            required_pairs = [
                (["用例描述", "标题"], "用例描述/标题"),
                (["操作步骤", "步骤描述"], "操作步骤/步骤描述"),
                (["期望结果", "预期结果"], "期望结果/预期结果"),
            ]
            for aliases, label in required_pairs:
                if not any(a in df.columns for a in aliases):
                    result["errors"].append(f"缺少必要列: '{label}'")

            optional_pairs = [
                (["用例序号", "执行用例ID"], "用例序号/执行用例ID"),
                (["所属模块"], "所属模块"),
                (["初始条件", "前置条件"], "初始条件/前置条件"),
                (["优先级", "用例等级"], "优先级/用例等级"),
            ]
            for aliases, label in optional_pairs:
                if not any(a in df.columns for a in aliases):
                    result["warnings"].append(f"缺少可选列: '{label}'")

            if not result["errors"]:
                result["valid"] = True
                # 过滤掉模块分组标题行（操作步骤/步骤描述列为空的行）
                step_col = next((c for c in ["操作步骤", "步骤描述"] if c in df.columns), None)
                if step_col:
                    data_rows = df[df[step_col].notna() & (df[step_col].astype(str).str.strip() != "")]
                    result["case_count"] = len(data_rows)
                else:
                    result["case_count"] = len(df)

            return result
        except Exception as e:
            logger.error(f"验证失败: {e}")
            result["errors"].append("验证失败")
            return result
