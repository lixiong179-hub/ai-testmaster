import pytest
from app.services.test_data.response_handler import parse_ai_response, validate_generated_data


class TestParseAiResponse:
    def test_valid_json_list(self):
        content = '[{"name": "test", "value": "1"}]'
        result = parse_ai_response(content)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_valid_json_dict(self):
        content = '{"name": "test", "value": "1"}'
        result = parse_ai_response(content)
        assert isinstance(result, dict)

    def test_json_with_surrounding_text(self):
        content = 'Here is the result: [{"name": "test"}] and some text'
        result = parse_ai_response(content)
        assert isinstance(result, list)

    def test_dict_with_surrounding_text(self):
        content = 'Result: {"name": "test"} end'
        result = parse_ai_response(content)
        assert isinstance(result, dict)

    def test_invalid_content_raises(self):
        with pytest.raises(ValueError, match="无法解析"):
            parse_ai_response("no json here at all")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_ai_response("")

    def test_nested_json(self):
        content = '[{"name": "test", "data": {"key": "value"}}]'
        result = parse_ai_response(content)
        assert result[0]["data"]["key"] == "value"

    def test_json_in_code_block(self):
        content = '```json\n[{"name": "test"}]\n```'
        result = parse_ai_response(content)
        assert isinstance(result, list)


class TestValidateGeneratedData:
    def test_valid_data(self):
        data = [{"name": "test", "age": 25}]
        fields = [{"name": "name", "required": True}, {"name": "age", "required": True}]
        result = validate_generated_data(data, fields)
        assert len(result) == 1

    def test_missing_required_field(self):
        data = [{"age": 25}]
        fields = [{"name": "name", "required": True}]
        with pytest.raises(ValueError, match="必填字段"):
            validate_generated_data(data, fields)

    def test_null_required_field(self):
        data = [{"name": None}]
        fields = [{"name": "name", "required": True}]
        with pytest.raises(ValueError, match="必填字段"):
            validate_generated_data(data, fields)

    def test_optional_field_missing(self):
        data = [{"name": "test"}]
        fields = [{"name": "name", "required": True}, {"name": "email", "required": False}]
        result = validate_generated_data(data, fields)
        assert len(result) == 1

    def test_empty_data(self):
        data = []
        fields = [{"name": "name", "required": True}]
        result = validate_generated_data(data, fields)
        assert len(result) == 0

    def test_multiple_records(self):
        data = [{"name": "a"}, {"name": "b"}]
        fields = [{"name": "name", "required": True}]
        result = validate_generated_data(data, fields)
        assert len(result) == 2

    def test_no_required_fields(self):
        data = [{"name": "test"}]
        fields = [{"name": "name", "required": False}]
        result = validate_generated_data(data, fields)
        assert len(result) == 1
