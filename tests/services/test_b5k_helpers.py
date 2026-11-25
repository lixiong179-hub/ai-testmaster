"""B5k 拆分件护栏：Excel 校验/规范化/导入的纯函数。

`validate_excel_format`(13)、`apply_normalization`(13)、`import_functional_excel`(12)、
`export_to_excel`(11)、`export_to_functional_excel`(15) 拆分出的判定与查询辅助在此加锁。
"""

from collections import OrderedDict
from types import SimpleNamespace

import pandas as pd

from app.services.test_case_view._excel_write_helpers import (
    PRIORITY_MAP,
    _group_cases_by_module,
    _step_row,
)
from app.services.test_case_view.excel_import_mixin import (
    _functional_priority,
    _is_module_header_row,
    _is_ui_case_type,
    _module_from_header_row,
    _resolve_row_module,
    _row_text,
)
from app.services.test_case_view.excel_normalize_mixin import (
    _apply_column_mapping,
    _fill_module_column,
)
from app.services.test_case_view.excel_validate_mixin import (
    _collect_sheet_errors,
    _missing_required_sheets,
)


class TestMissingRequiredSheets:
    def test_both_present(self):
        assert _missing_required_sheets(["用例信息", "测试步骤"]) == []

    def test_both_missing(self):
        errors = _missing_required_sheets(["Sheet1"])
        assert errors == ["缺少'用例信息'sheet", "缺少'测试步骤'sheet"]

    def test_one_missing(self):
        assert _missing_required_sheets(["用例信息"]) == ["缺少'测试步骤'sheet"]


class TestCollectSheetErrors:
    def test_empty_sheet(self):
        errors = []
        _collect_sheet_errors("用例信息", pd.DataFrame(), ("用例标题",), errors)
        assert errors == ["'用例信息'sheet为空"]

    def test_missing_columns(self):
        errors = []
        _collect_sheet_errors("测试步骤", pd.DataFrame({"步骤编号": [1]}), ("步骤编号", "操作步骤"), errors)
        assert errors == ["'测试步骤'sheet缺少'操作步骤'列"]

    def test_all_present(self):
        errors = []
        df = pd.DataFrame({"步骤编号": [1], "操作步骤": ["a"]})
        _collect_sheet_errors("测试步骤", df, ("步骤编号", "操作步骤"), errors)
        assert errors == []


class TestApplyColumnMapping:
    def test_none_mapping_untouched(self):
        df = pd.DataFrame({"原始列": [1]})
        assert list(_apply_column_mapping(df, None).columns) == ["原始列"]

    def test_renames_only_existing(self):
        df = pd.DataFrame({"原始列": [1], "保留列": [2]})
        out = _apply_column_mapping(df, {"原始列": "标准列", "不存在": "x"})
        assert list(out.columns) == ["标准列", "保留列"]

    def test_no_effective_rename(self):
        df = pd.DataFrame({"a": [1]})
        assert list(_apply_column_mapping(df, {"b": "c"}).columns) == ["a"]


class TestFillModuleColumn:
    def test_single_sheet_untouched(self):
        df = pd.DataFrame({"a": [1]})
        assert "所属模块" not in _fill_module_column(df, "S1", 1).columns

    def test_multi_sheet_fills_sheet_name(self):
        df = pd.DataFrame({"a": [1]})
        assert _fill_module_column(df, "S1", 2)["所属模块"].tolist() == ["S1"]

    def test_multi_sheet_keeps_existing_module(self):
        df = pd.DataFrame({"所属模块": ["已有"]})
        assert _fill_module_column(df, "S1", 3)["所属模块"].tolist() == ["已有"]


class TestRowText:
    def test_primary_key(self):
        row = pd.Series({"用例描述": " 标题 ", "标题": "备选"})
        assert _row_text(row, ("用例描述", "标题")) == "标题"

    def test_fallback_key(self):
        row = pd.Series({"标题": "备选"})
        assert _row_text(row, ("用例描述", "标题")) == "备选"

    def test_missing_returns_empty(self):
        assert _row_text(pd.Series({"x": 1}), ("用例描述",)) == ""


class TestModuleHeaderDetection:
    def test_header_row_detected(self):
        row = pd.Series({"用例序号": "登录模块", "操作步骤": None})
        assert _is_module_header_row(row, pd) is True

    def test_data_row_not_header(self):
        row = pd.Series({"用例序号": 1, "操作步骤": "点击登录"})
        assert _is_module_header_row(row, pd) is False

    def test_module_name_from_header(self):
        assert _module_from_header_row(pd.Series({"用例序号": " 登录模块 "}), pd) == "登录模块"

    def test_numeric_first_column_is_not_module(self):
        assert _module_from_header_row(pd.Series({"用例序号": "12"}), pd) is None

    def test_nan_first_column(self):
        assert _module_from_header_row(pd.Series({"用例序号": None}), pd) is None


class TestResolveRowModule:
    def test_prefers_row_column(self):
        row = pd.Series({"所属模块": " 订单 "})
        assert _resolve_row_module(row, "默认", pd) == "订单"

    def test_falls_back_to_current(self):
        assert _resolve_row_module(pd.Series({"所属模块": None}), "默认", pd) == "默认"

    def test_empty_string_falls_back(self):
        assert _resolve_row_module(pd.Series({"所属模块": "  "}), "默认", pd) == "默认"


class TestImportValueMapping:
    def test_priority(self):
        assert PRIORITY_MAP[2] == "P2"
        assert _functional_priority("p0") == 1
        assert _functional_priority("P2") == 2
        assert _functional_priority("未知") == 2

    def test_case_type(self):
        assert _is_ui_case_type("UI自动化") is True
        assert _is_ui_case_type("功能") is True
        assert _is_ui_case_type("接口自动化") is False


class TestExportHelpers:
    def test_group_cases_by_module_keeps_order(self):
        cases = [
            SimpleNamespace(id=1, module="A"),
            SimpleNamespace(id=2, module=None),
            SimpleNamespace(id=3, module="A"),
        ]
        grouped = _group_cases_by_module(cases)
        assert isinstance(grouped, OrderedDict)
        assert list(grouped) == ["A", "默认模块"]
        assert [c.id for c in grouped["A"]] == [1, 3]

    def test_step_row_with_locator(self):
        step = SimpleNamespace(
            step_number=1,
            action="点击登录",
            expected_result="进入首页",
            is_business_view=1,
            is_technical_view=0,
            has_locator=1,
            locator_status="success",
        )
        locator = SimpleNamespace(css_selector="#login", xpath="//button", element_type="button")
        row = _step_row(step, locator)
        assert row == [1, "点击登录", "进入首页", "是", "否", "是", "success", "#login", "//button", "button"]

    def test_step_row_without_locator(self):
        step = SimpleNamespace(
            step_number=2,
            action=None,
            expected_result=None,
            is_business_view=0,
            is_technical_view=0,
            has_locator=0,
            locator_status=None,
        )
        assert _step_row(step, None) == [2, "", "", "否", "否", "否", "", "", "", ""]
