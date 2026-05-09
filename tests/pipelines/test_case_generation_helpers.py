"""T12 test_data 校验 + T2 CaseGeneration 辅助函数 单元测试

覆盖:
    - T12: _validate_test_data — dict 类型校验、键校验、子值类型校验
    - T2: _classify_case_type — 显式字段优先、标题关键词 fallback、步骤内容级匹配、默认正向
    - T6: _dedup_cases_global — 跨测试点 Jaccard 去重
"""
import pytest

from app.pipelines.steps.case_generation import (
    _validate_test_data,
    _classify_case_type,
)


# ── T12: _validate_test_data ──


class TestValidateTestData:
    def test_missing_test_data_key(self):
        """无 test_data 字段 → 自动设为空对象。"""
        case = {"title": "测试用例"}
        _validate_test_data(case)
        assert case["test_data"] == {}

    def test_valid_structure(self):
        """合法 test_data → 不修改。"""
        case = {
            "title": "测试",
            "test_data": {
                "normal": {"input": "值"},
                "boundary": {"input": "边界值"},
            },
        }
        _validate_test_data(case)
        assert case["test_data"]["normal"] == {"input": "值"}
        assert case["test_data"]["boundary"] == {"input": "边界值"}

    def test_non_dict_test_data(self):
        """test_data 非 dict → 重置为 {}。"""
        case = {"title": "测试", "test_data": "invalid_string"}
        _validate_test_data(case)
        assert case["test_data"] == {}

    def test_list_test_data(self):
        """test_data 为 list → 重置为 {}。"""
        case = {"title": "测试", "test_data": [1, 2, 3]}
        _validate_test_data(case)
        assert case["test_data"] == {}

    def test_missing_valid_keys(self):
        """test_data 有内容但缺少 normal/boundary/abnormal 键 → 保留原值 + warning。"""
        case = {"title": "测试", "test_data": {"other_key": {"val": 1}}}
        _validate_test_data(case)
        # 保留原值，不重置
        assert "other_key" in case["test_data"]

    def test_empty_dict_test_data(self):
        """空 dict test_data → 不修改。"""
        case = {"title": "测试", "test_data": {}}
        _validate_test_data(case)
        assert case["test_data"] == {}

    def test_sub_value_not_dict(self):
        """test_data 子键值非 dict → 重置为 {}。"""
        case = {
            "title": "测试",
            "test_data": {
                "normal": "not_a_dict",
                "boundary": {"valid": True},
            },
        }
        _validate_test_data(case)
        assert case["test_data"]["normal"] == {}
        assert case["test_data"]["boundary"] == {"valid": True}

    def test_all_three_keys(self):
        """包含 normal/boundary/abnormal 全部三个键 → 合法。"""
        case = {
            "title": "测试",
            "test_data": {
                "normal": {"a": 1},
                "boundary": {"b": 2},
                "abnormal": {"c": 3},
            },
        }
        _validate_test_data(case)
        assert len(case["test_data"]) == 3

    def test_none_test_data(self):
        """test_data 为 None → 重置为 {}。"""
        case = {"title": "测试", "test_data": None}
        _validate_test_data(case)
        assert case["test_data"] == {}

    def test_integer_test_data(self):
        """test_data 为 int → 重置为 {}。"""
        case = {"title": "测试", "test_data": 42}
        _validate_test_data(case)
        assert case["test_data"] == {}


# ── T2/T7: _classify_case_type ──


class TestClassifyCaseType:
    # 步骤1: 显式字段优先
    def test_case_category_boundary(self):
        case = {"title": "普通标题", "case_category": "boundary_test"}
        assert _classify_case_type(case) == "boundary"

    def test_case_type_negative(self):
        case = {"title": "普通标题", "case_type": "negative"}
        assert _classify_case_type(case) == "negative"

    def test_case_category_positive(self):
        case = {"title": "普通标题", "case_category": "正向测试"}
        assert _classify_case_type(case) == "positive"

    # 步骤2: 标题关键词 fallback
    def test_title_boundary_keyword(self):
        case = {"title": "边界值测试输入框最大长度"}
        assert _classify_case_type(case) == "boundary"

    def test_title_negative_keyword(self):
        case = {"title": "异常场景网络断开时提交表单"}
        assert _classify_case_type(case) == "negative"

    def test_title_positive_keyword(self):
        case = {"title": "正常登录流程验证"}
        assert _classify_case_type(case) == "positive"

    # 步骤3: 步骤内容级匹配
    def test_steps_content_boundary(self):
        case = {
            "title": "输入框测试",
            "steps": [
                {"action": "输入边界值", "expected_result": "提示超出范围"},
            ],
        }
        assert _classify_case_type(case) == "boundary"

    def test_steps_content_negative(self):
        case = {
            "title": "表单提交测试",
            "steps": [
                {"action": "断开网络后提交", "expected_result": "异常提示"},
            ],
        }
        assert _classify_case_type(case) == "negative"

    # 步骤4: 默认正向
    def test_default_positive(self):
        case = {"title": "用户管理操作"}
        assert _classify_case_type(case) == "positive"

    def test_empty_case(self):
        case = {}
        assert _classify_case_type(case) == "positive"

    # 显式字段优先于标题关键词
    def test_explicit_overrides_title(self):
        """case_category=boundary 但标题含"正常" → 仍为 boundary。"""
        case = {"title": "正常流程测试", "case_category": "boundary"}
        assert _classify_case_type(case) == "boundary"
