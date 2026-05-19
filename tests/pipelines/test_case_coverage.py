import pytest
from app.pipelines.steps._case_coverage import (
    _classify_case_type,
    _check_type_coverage,
    _append_supplement_examples,
)


class TestClassifyCaseType:
    def test_positive_by_category(self):
        assert _classify_case_type({"case_category": "positive"}) == "positive"

    def test_positive_by_chinese_category(self):
        assert _classify_case_type({"case_category": "正向测试"}) == "positive"

    def test_boundary_by_category(self):
        assert _classify_case_type({"case_category": "boundary"}) == "boundary"

    def test_boundary_by_chinese_category(self):
        assert _classify_case_type({"case_category": "边界测试"}) == "boundary"

    def test_negative_by_category(self):
        assert _classify_case_type({"case_category": "negative"}) == "negative"

    def test_negative_by_chinese_category(self):
        assert _classify_case_type({"case_category": "异常测试"}) == "negative"

    def test_positive_by_title_keyword(self):
        assert _classify_case_type({"title": "正常登录测试"}) == "positive"

    def test_boundary_by_title_keyword(self):
        assert _classify_case_type({"title": "边界值测试"}) == "boundary"

    def test_negative_by_title_keyword(self):
        assert _classify_case_type({"title": "异常输入测试"}) == "negative"

    def test_positive_by_step_keyword(self):
        case = {
            "title": "普通操作",
            "steps": [{"action": "正常输入用户名", "expected_result": "成功"}],
        }
        assert _classify_case_type(case) == "positive"

    def test_boundary_by_step_keyword(self):
        case = {
            "title": "普通操作",
            "steps": [{"action": "输入最大值", "expected_result": "边界校验"}],
        }
        assert _classify_case_type(case) == "boundary"

    def test_negative_by_step_keyword(self):
        case = {
            "title": "普通操作",
            "steps": [{"action": "输入错误数据", "expected_result": "异常拦截"}],
        }
        assert _classify_case_type(case) == "negative"

    def test_default_positive(self):
        assert _classify_case_type({"title": "普通操作"}) == "positive"

    def test_empty_case(self):
        assert _classify_case_type({}) == "positive"

    def test_case_type_field(self):
        assert _classify_case_type({"case_type": "positive"}) == "positive"

    def test_exception_keyword(self):
        assert _classify_case_type({"case_category": "exception"}) == "negative"

    def test_happy_keyword(self):
        assert _classify_case_type({"case_category": "happy"}) == "positive"


class TestCheckTypeCoverage:
    def test_all_covered(self):
        cases = [
            {"title": "正常流程", "case_category": "positive"},
            {"title": "边界值", "case_category": "boundary"},
            {"title": "异常测试", "case_category": "negative"},
        ]
        result = _check_type_coverage(cases)
        assert result == []

    def test_missing_boundary(self):
        cases = [
            {"title": "正常流程", "case_category": "positive"},
            {"title": "异常测试", "case_category": "negative"},
        ]
        result = _check_type_coverage(cases)
        assert "boundary" in result

    def test_missing_all(self):
        cases = [{"title": "普通操作"}]
        result = _check_type_coverage(cases)
        assert "boundary" in result
        assert "negative" in result

    def test_empty_cases(self):
        result = _check_type_coverage([])
        assert sorted(result) == ["boundary", "negative", "positive"]


class TestAppendSupplementExamples:
    def test_no_missing_types(self):
        parts = []
        _append_supplement_examples(parts, [])
        assert len(parts) == 0

    def test_missing_negative(self):
        parts = []
        _append_supplement_examples(parts, ["negative"])
        assert any("异常" in p for p in parts)

    def test_missing_boundary(self):
        parts = []
        _append_supplement_examples(parts, ["boundary"])
        assert any("边界" in p for p in parts)

    def test_missing_positive(self):
        parts = []
        _append_supplement_examples(parts, ["positive"])
        assert any("主流程" in p or "正向" in p for p in parts)

    def test_max_two_types(self):
        parts = []
        _append_supplement_examples(parts, ["positive", "boundary", "negative"])
        supplement_count = sum(1 for p in parts if p.startswith("【"))
        assert supplement_count <= 2
