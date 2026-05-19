import pytest
import json
from app.services.xmind_ai_parser._parsing import (
    _parse_ai_response,
    _repair_json_text,
    _extract_case_objects,
    _normalize_case,
)


class TestParseAIResponse:
    def test_valid_json_array(self):
        text = json.dumps([{"title": "用例1"}, {"title": "用例2"}])
        result = _parse_ai_response(text, 2)
        assert result is not None
        assert len(result) == 2

    def test_json_with_code_block(self):
        text = '```json\n[{"title": "用例1"}]\n```'
        result = _parse_ai_response(text, 1)
        assert result is not None
        assert len(result) == 1

    def test_empty_text(self):
        result = _parse_ai_response("", 1)
        assert result is None

    def test_whitespace_only(self):
        result = _parse_ai_response("   ", 1)
        assert result is None

    def test_dict_with_cases_key(self):
        text = json.dumps({"cases": [{"title": "用例1"}]})
        result = _parse_ai_response(text, 1)
        assert result is not None
        assert len(result) == 1

    def test_dict_with_items_key(self):
        text = json.dumps({"items": [{"title": "T"}]})
        result = _parse_ai_response(text, 1)
        assert result is not None

    def test_dict_with_data_key(self):
        text = json.dumps({"data": [{"title": "T"}]})
        result = _parse_ai_response(text, 1)
        assert result is not None

    def test_non_json_text(self):
        result = _parse_ai_response("这不是JSON", 1)
        assert result is None

    def test_count_mismatch_still_returns(self):
        text = json.dumps([{"title": "用例1"}])
        result = _parse_ai_response(text, 5)
        assert result is not None
        assert len(result) == 1

    def test_embedded_json(self):
        text = '一些文字 [{"title": "用例1"}] 一些文字'
        result = _parse_ai_response(text, 1)
        assert result is not None

    def test_non_list_result(self):
        text = json.dumps({"key": "value"})
        result = _parse_ai_response(text, 1)
        assert result is None


class TestRepairJsonText:
    def test_trailing_comma_in_object(self):
        text = '{"key": "value",}'
        result = _repair_json_text(text)
        assert "," not in result[-2:]

    def test_trailing_comma_in_array(self):
        text = '[1, 2, 3,]'
        result = _repair_json_text(text)
        assert ",]" not in result

    def test_missing_comma_between_objects(self):
        text = '{"a": 1}{"b": 2}'
        result = _repair_json_text(text)
        assert "},{" in result

    def test_missing_comma_between_array_and_object(self):
        text = ']{"a": 1}'
        result = _repair_json_text(text)
        assert "],{" in result


class TestExtractCaseObjects:
    def test_with_cases_key(self):
        text = '"cases": [{"title": "T1"}, {"title": "T2"}]'
        result = _extract_case_objects(text)
        assert len(result) == 2

    def test_with_array(self):
        text = '[{"title": "T1"}, {"title": "T2"}]'
        result = _extract_case_objects(text)
        assert len(result) == 2

    def test_no_objects(self):
        text = 'no json here'
        result = _extract_case_objects(text)
        assert result == []

    def test_malformed_object(self):
        text = '{"broken": '
        result = _extract_case_objects(text)
        assert result == []


class TestNormalizeCase:
    def test_normal(self):
        raw = {
            "module": "登录模块",
            "title": "登录验证",
            "precondition": "已注册用户",
            "expected_result": "登录成功",
            "priority": 1,
            "steps": [{"action": "点击登录", "expected_result": "成功"}],
        }
        result = _normalize_case(raw, "默认模块")
        assert result["module"] == "登录模块"
        assert result["title"] == "登录验证"
        assert result["priority"] == 1
        assert len(result["steps"]) == 1

    def test_missing_module_uses_fallback(self):
        raw = {"title": "T", "steps": []}
        result = _normalize_case(raw, "回退模块")
        assert result["module"] == "回退模块"

    def test_empty_module_uses_fallback(self):
        raw = {"module": "", "title": "T", "steps": []}
        result = _normalize_case(raw, "回退模块")
        assert result["module"] == "回退模块"

    def test_invalid_priority_defaults_to_2(self):
        raw = {"title": "T", "priority": 5, "steps": []}
        result = _normalize_case(raw, "M")
        assert result["priority"] == 2

    def test_no_steps_with_expected_result(self):
        raw = {"title": "检查项", "expected_result": "符合预期", "steps": []}
        result = _normalize_case(raw, "M")
        assert len(result["steps"]) == 1
        assert "检查并确认" in result["steps"][0]["action"]

    def test_no_steps_no_expected(self):
        raw = {"title": "T", "steps": []}
        result = _normalize_case(raw, "M")
        assert result["steps"] == []

    def test_step_not_dict_skipped(self):
        raw = {
            "title": "T",
            "steps": ["not a dict", {"action": "有效步骤", "expected_result": "R"}],
        }
        result = _normalize_case(raw, "M")
        assert len(result["steps"]) == 1

    def test_case_type_default(self):
        raw = {"title": "T", "steps": []}
        result = _normalize_case(raw, "M")
        assert result["case_type"] is not None

    def test_point_from_title(self):
        raw = {"title": "测试标题", "steps": [{"action": "A", "expected_result": "E"}]}
        result = _normalize_case(raw, "M")
        assert result["point"] == "测试标题"

    def test_point_from_action_when_no_title(self):
        raw = {"title": "", "steps": [{"action": "操作步骤", "expected_result": "E"}]}
        result = _normalize_case(raw, "M")
        assert result["point"] == "操作步骤"
