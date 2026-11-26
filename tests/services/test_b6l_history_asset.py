"""B6l 护栏：历史资产 Excel 解析与用例分类。"""

import pandas as pd
import pytest

from app.services.history_asset_classification import (
    _classify_history_cases,
    _title_similarity,
)
from app.services.history_asset_parsing import _parse_excel_cases


def write_excel(path, sheets: dict[str, list[dict]]):
    with pd.ExcelWriter(path) as writer:
        for sheet_name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False)
    return str(path)


class TestTitleSimilarity:
    def test_empty_title_returns_zero(self):
        assert _title_similarity("", "登录") == 0.0

    def test_case_insensitive_exact_match(self):
        assert _title_similarity("Login Page", "login page") == 1.0

    def test_partial_overlap(self):
        assert _title_similarity("abcd", "ab") == pytest.approx(0.5)

    def test_whitespace_only_title_returns_zero(self):
        assert _title_similarity("   ", "x") == 0.0


class TestParseExcelDualSheet:
    def test_cases_and_steps_are_joined(self, tmp_path):
        path = write_excel(
            tmp_path / "dual.xlsx",
            {
                "用例信息": [
                    {
                        "用例标题": "登录成功",
                        "所属模块": "登录",
                        "前置条件": "已注册",
                        "预期结果": "进入首页",
                        "优先级": 1,
                    },
                    {"用例标题": "密码错误", "所属模块": "登录", "前置条件": "", "预期结果": "提示错误", "优先级": 2},
                ],
                "测试步骤": [
                    {"用例序号": 0, "步骤编号": 1, "操作步骤": "输入账号", "预期结果": "输入成功"},
                    {"用例序号": 1, "步骤编号": 1, "操作步骤": "输入错误密码", "预期结果": "提示错误"},
                ],
            },
        )

        cases = _parse_excel_cases(path)

        assert [c["title"] for c in cases] == ["登录成功", "密码错误"]
        assert cases[0]["steps"][0]["action"] == "输入账号"
        assert cases[0]["priority"] == 1
        assert "case_row_index" not in cases[0]

    def test_out_of_range_step_index_falls_back_to_first_case(self, tmp_path):
        path = write_excel(
            tmp_path / "fallback.xlsx",
            {
                "用例信息": [{"用例标题": "唯一用例", "预期结果": "ok"}],
                "测试步骤": [{"用例序号": 99, "步骤编号": 1, "操作步骤": "输入", "预期结果": "ok"}],
            },
        )

        cases = _parse_excel_cases(path)

        assert len(cases) == 1
        assert cases[0]["steps"][0]["action"] == "输入"

    def test_missing_step_index_defaults_to_first_case(self, tmp_path):
        path = write_excel(
            tmp_path / "noindex.xlsx",
            {
                "用例信息": [{"用例标题": "A", "预期结果": "ok"}, {"用例标题": "B", "预期结果": "ok"}],
                "测试步骤": [{"步骤编号": 1, "操作步骤": "点击", "预期结果": "ok"}],
            },
        )

        cases = _parse_excel_cases(path)

        assert cases[0]["steps"][0]["action"] == "点击"
        assert cases[1]["steps"] == []


class TestParseExcelSingleSheet:
    def test_module_rows_and_steps(self, tmp_path):
        path = write_excel(
            tmp_path / "single.xlsx",
            {
                "Sheet1": [
                    {"模块": "登录", "用例描述": None, "操作步骤": None, "期望结果": None},
                    {"模块": None, "用例描述": "登录成功", "操作步骤": "输入账号", "期望结果": "进入首页"},
                    {"模块": None, "用例描述": "密码错误", "操作步骤": "输入错密码", "期望结果": "提示错误"},
                ]
            },
        )

        cases = _parse_excel_cases(path)

        assert [c["title"] for c in cases] == ["登录成功", "密码错误"]
        assert all(c["module"] == "登录" for c in cases)
        assert cases[0]["steps"][0]["action"] == "输入账号"
        assert cases[0]["priority"] == 2

    def test_numeric_first_column_is_not_module(self, tmp_path):
        path = write_excel(
            tmp_path / "numeric.xlsx",
            {
                "Sheet1": [
                    {"序号": 1, "用例描述": None, "操作步骤": None, "期望结果": None},
                    {"序号": 2, "用例描述": "用例A", "操作步骤": "点击", "期望结果": "ok"},
                ]
            },
        )

        cases = _parse_excel_cases(path)

        assert cases[0]["module"] == ""

    def test_empty_title_is_skipped(self, tmp_path):
        path = write_excel(
            tmp_path / "notitle.xlsx",
            {
                "Sheet1": [
                    {"用例描述": None, "操作步骤": "点击", "期望结果": "ok"},
                    {"用例描述": "用例A", "操作步骤": "点击", "期望结果": "ok"},
                ]
            },
        )

        cases = _parse_excel_cases(path)

        assert len(cases) == 1

    def test_step_description_column_fallback(self, tmp_path):
        path = write_excel(
            tmp_path / "stepdesc.xlsx",
            {
                "Sheet1": [
                    {"用例描述": "用例A", "步骤描述": "打开页面", "预期结果": "加载完成"},
                ]
            },
        )

        cases = _parse_excel_cases(path)

        assert cases[0]["steps"][0]["action"] == "打开页面"
        assert cases[0]["expected_result"] == "加载完成"

    def test_invalid_file_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError, match="Excel 解析失败"):
            _parse_excel_cases(str(tmp_path / "missing.xlsx"))


def case(title, steps=None, expected="ok"):
    return {"title": title, "steps": steps or [{"action": "a"}], "expected_result": expected}


class TestClassifyHistoryCases:
    def test_identical_case_is_reused(self):
        history = [case("登录成功")]
        system = [{**case("登录成功"), "case_id": 5}]

        items = _classify_history_cases(history, system, [])

        assert len(items) == 1
        assert items[0].classification == "REUSE_CASE"
        assert items[0].confidence == 1.0
        assert items[0].matched_system_case_id == 5
        assert items[0].suggested_case is None

    def test_step_count_difference_marks_update(self):
        history = [case("登录成功", steps=[{"action": "a"}, {"action": "b"}])]
        system = [{**case("登录成功", steps=[{"action": "a"}]), "case_id": 5}]

        items = _classify_history_cases(history, system, [])

        assert items[0].classification == "UPDATE_CASE"
        assert set(items[0].diff_fields) == {"steps"}

    def test_expected_result_difference_marks_update(self):
        history = [case("登录成功", expected="进入首页")]
        system = [{**case("登录成功", expected="进入主页"), "case_id": 5}]

        items = _classify_history_cases(history, system, [])

        assert items[0].classification == "UPDATE_CASE"
        assert set(items[0].diff_fields) == {"expected_result"}

    def test_partial_title_match_marks_update(self):
        history = [case("abcd")]
        system = [{**case("ab"), "case_id": 7}]

        items = _classify_history_cases(history, system, [])

        assert items[0].classification == "UPDATE_CASE"
        assert items[0].diff_fields == {"title": {"old": "ab", "new": "abcd"}}
        assert items[0].confidence == pytest.approx(0.5)

    def test_keyword_match_marks_new_case(self):
        items = _classify_history_cases([case("登录功能校验")], [], ["登录", "支付", "下单", "退款"])

        assert items[0].classification == "NEW_CASE"
        assert items[0].confidence == 0.7
        assert "登录" in items[0].reason

    def test_keyword_mismatch_requires_confirmation(self):
        items = _classify_history_cases([case("登录功能校验")], [], ["支付"])

        assert items[0].classification == "CONFIRM_REQUIRED"
        assert items[0].confidence == 0.4

    def test_no_keywords_marks_new_case(self):
        items = _classify_history_cases([case("登录功能校验")], [], [])

        assert items[0].classification == "NEW_CASE"
        assert items[0].confidence == 0.6

    def test_unmatched_system_cases_are_deprecated(self):
        history = [case("登录成功")]
        system = [
            {**case("登录成功"), "case_id": 5},
            {"title": "历史遗留用例", "case_id": 9},
        ]

        items = _classify_history_cases(history, system, [])

        deprecated = [item for item in items if item.classification == "DEPRECATED_CASE"]
        assert len(deprecated) == 1
        assert deprecated[0].client_id == "sys_case_9"
        assert deprecated[0].matched_system_case_id == 9

    def test_empty_history_deprecates_all_system_cases(self):
        system = [{"title": "A", "case_id": 1}, {"title": "B", "case_id": 2}]

        items = _classify_history_cases([], system, [])

        assert {item.client_id for item in items} == {"sys_case_1", "sys_case_2"}
        assert all(item.classification == "DEPRECATED_CASE" for item in items)

    def test_system_case_without_id_is_not_deprecated(self):
        items = _classify_history_cases([], [{"title": "无ID用例"}], [])

        assert items == []
