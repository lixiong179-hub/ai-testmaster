"""Excel格式规范化预处理Mixin - 合并单元格展开、多步骤拆分、多Sheet合并、列名智能映射。"""
import os
import re
from typing import Dict, Any, List, Optional
from loguru import logger


COLUMN_ALIASES: Dict[str, List[str]] = {
    "title": ["用例描述", "标题", "用例标题", "Test Case", "case_title"],
    "action": ["操作步骤", "步骤描述", "操作", "Step", "step_desc"],
    "expected_result": ["期望结果", "预期结果", "Expected", "expected"],
    "precondition": ["初始条件", "前置条件", "Precondition", "前提条件"],
    "priority": ["优先级", "用例等级", "Priority", "重要程度"],
    "case_type": ["用例类型", "Case Type", "类型"],
    "module": ["所属模块", "所属分组", "Module", "模块"],
    "case_no": ["用例序号", "执行用例ID", "ID", "编号"],
}


class ExcelNormalizeMixin:
    """Excel格式规范化预处理：合并单元格展开、多步骤拆分、多Sheet合并、列名智能映射。"""

    _temp_files: List[str] = []

    def _register_temp_file(self, path: str) -> None:
        self._temp_files.append(path)

    def cleanup_temp_files(self) -> None:
        for path in self._temp_files:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
        self._temp_files.clear()

    def normalize_excel(self, file_path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "detected_format": "unknown",
            "normalization_needed": False,
            "issues": [],
            "column_mapping": {},
            "preview": {"total_rows": 0, "module_distribution": {}},
        }
        try:
            import pandas as pd
            xl = pd.ExcelFile(file_path)
            sheet_names = xl.sheet_names
            if "用例信息" in sheet_names and "测试步骤" in sheet_names:
                result["detected_format"] = "standard"
                return result
            result["detected_format"] = "functional"
            df = pd.read_excel(file_path, sheet_name=0)
            if df.empty:
                result["issues"].append({"type": "empty_file", "suggestion": "Excel文件为空"})
                return result
            df.columns = [str(col).strip() for col in df.columns]
            merged_issues = self._detect_merged_cells(df)
            if merged_issues:
                result["normalization_needed"] = True
                result["issues"].extend(merged_issues)
            multi_step_issues = self._detect_multi_step_cells(df, df.columns.tolist())
            if multi_step_issues:
                result["normalization_needed"] = True
                result["issues"].extend(multi_step_issues)
            if len(sheet_names) > 1:
                result["normalization_needed"] = True
                result["issues"].append({
                    "type": "multi_sheet",
                    "sheet_count": len(sheet_names),
                    "suggestion": f"{len(sheet_names)}个Sheet将合并导入，每个Sheet作为一个模块",
                })
            column_mapping = self._infer_column_mapping(df.columns.tolist())
            result["column_mapping"] = {
                "detected": column_mapping,
                "confidence": self._calc_mapping_confidence(column_mapping, df.columns.tolist()),
            }
            data_rows = df.dropna(how="all")
            result["preview"]["total_rows"] = len(data_rows)
            module_col = next((c for c in ["所属模块", "所属分组", "Module"] if c in df.columns), None)
            if module_col:
                modules = df[module_col].dropna().unique()
                result["preview"]["module_distribution"] = {str(m): 0 for m in modules}
            return result
        except Exception as e:
            logger.error(f"Excel规范化检测失败: {e}")
            result["issues"].append({"type": "error", "suggestion": f"检测失败: {e}"})
            return result

    def apply_normalization(
        self,
        file_path: str,
        column_mapping: Optional[Dict[str, str]] = None,
        normalize_options: Optional[Dict[str, bool]] = None,
    ) -> str:
        import pandas as pd
        import tempfile
        options = normalize_options or {
            "expand_merged_cells": True,
            "split_multi_step": True,
            "merge_sheets": True,
        }
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        if "用例信息" in sheet_names and "测试步骤" in sheet_names:
            return file_path
        dfs: List[pd.DataFrame] = []
        for sheet_name in sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            if df.empty:
                continue
            df.columns = [str(col).strip() for col in df.columns]
            if column_mapping:
                rename_map = {}
                for original_col, standard_name in column_mapping.items():
                    if original_col in df.columns:
                        rename_map[original_col] = standard_name
                if rename_map:
                    df = df.rename(columns=rename_map)
            if options.get("expand_merged_cells", True):
                merged_cols = [
                    issue["column"] for issue in self._detect_merged_cells(df)
                ]
                df = self._expand_merged_cells(df, merged_cols)
            if options.get("split_multi_step", True):
                df = self._split_multi_step_cells(df)
            if len(sheet_names) > 1:
                module_col = next((c for c in ["所属模块", "module"] if c in df.columns), None)
                if module_col is None:
                    df["所属模块"] = sheet_name
            dfs.append(df)
        if not dfs:
            return file_path
        merged_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", prefix="normalized_") as tmp:
            normalized_path = tmp.name
        merged_df.to_excel(normalized_path, index=False, sheet_name="用例数据")
        self._register_temp_file(normalized_path)
        logger.info(f"Excel规范化完成，输出: {normalized_path}")
        return normalized_path

    def _detect_merged_cells(self, df: Any) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        try:
            for col in df.columns:
                null_count = df[col].isna().sum()
                if null_count > 0:
                    first_valid = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                    if first_valid is not None and null_count > len(df) * 0.1:
                        issues.append({
                            "type": "merged_cells",
                            "column": col,
                            "null_count": int(null_count),
                            "suggestion": f"列'{col}'有{null_count}个空值，可能是合并单元格，建议展开填充",
                        })
        except Exception as e:
            logger.debug(f"合并单元格检测异常: {e}")
        return issues

    def _detect_multi_step_cells(self, df: Any, columns: List[str]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        try:
            step_col = next((c for c in ["操作步骤", "步骤描述", "action"] if c in columns), None)
            if step_col is None:
                return issues
            multi_step_pattern = re.compile(r'(?:【\d+】|\[\d+\])')
            for idx, row in df.iterrows():
                val = str(row.get(step_col, ""))
                if multi_step_pattern.search(val) and (val.count("【") + val.count("[")) > 1:
                    issues.append({
                        "type": "multi_step_in_cell",
                        "row": int(idx) + 2,
                        "cell": step_col,
                        "suggestion": f"第{int(idx) + 2}行的操作步骤包含多个步骤编号，建议拆分为独立步骤",
                    })
        except Exception as e:
            logger.debug(f"多步骤检测异常: {e}")
        return issues

    def _expand_merged_cells(self, df: Any, merged_columns: Optional[List[str]] = None) -> Any:
        try:
            cols_to_fill = merged_columns if merged_columns else [
                col for col in df.columns
                if df[col].isna().any() and df[col].isna().sum() > len(df) * 0.1
            ]
            for col in cols_to_fill:
                if col in df.columns and df[col].isna().any():
                    df[col] = df[col].ffill()
            return df
        except Exception as e:
            logger.warning(f"合并单元格展开失败: {e}")
            return df

    def _split_multi_step_cells(self, df: Any) -> Any:
        try:
            import pandas as pd
            step_col = next((c for c in ["操作步骤", "步骤描述", "action"] if c in df.columns), None)
            if step_col is None:
                return df
            expected_col = next((c for c in ["期望结果", "预期结果", "expected_result"] if c in df.columns), None)
            new_rows: List[Dict[str, Any]] = []
            step_pattern = re.compile(r'(?:【(\d+)】|\[(\d+)\])\s*((?:(?!【\d+】|\[\d+\]).)*)', re.DOTALL)
            for _, row in df.iterrows():
                step_val = str(row.get(step_col, ""))
                matches = step_pattern.findall(step_val)
                if len(matches) > 1:
                    for match in matches:
                        new_row = row.to_dict()
                        step_num = match[0] if match[0] else match[1]
                        step_text = match[2].strip()
                        new_row[step_col] = f"【{step_num}】{step_text}"
                        if expected_col and expected_col in new_row:
                            new_row[expected_col] = ""
                        new_rows.append(new_row)
                else:
                    new_rows.append(row.to_dict())
            if new_rows:
                df = pd.DataFrame(new_rows)
            return df
        except Exception as e:
            logger.warning(f"多步骤拆分失败: {e}")
            return df

    def _infer_column_mapping(self, columns: List[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for col in columns:
            col_stripped = col.strip()
            for standard_name, aliases in COLUMN_ALIASES.items():
                if col_stripped in aliases:
                    mapping[col_stripped] = standard_name
                    break
        return mapping

    def _calc_mapping_confidence(self, mapping: Dict[str, str], columns: List[str]) -> float:
        if not columns:
            return 0.0
        required = {"title", "action", "expected_result"}
        mapped = set(mapping.values())
        matched = required & mapped
        return round(len(matched) / len(required), 2)
