import pytest
from app.services.ai_analysis_service._extract import _ExtractMixin


class TestBuildExtractPrompt:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_basic_prompt(self):
        prompt = self.mixin._build_extract_prompt("需求内容测试")
        assert "需求内容测试" in prompt
        assert "JSON" in prompt

    def test_prompt_with_context(self):
        prompt = self.mixin._build_extract_prompt(
            "需求内容",
            context={"extra_instructions": "重点关注登录模块"},
        )
        assert "重点关注登录模块" in prompt

    def test_prompt_without_context(self):
        prompt = self.mixin._build_extract_prompt("需求内容", context=None)
        assert "额外要求" not in prompt

    def test_prompt_with_empty_context(self):
        prompt = self.mixin._build_extract_prompt("需求内容", context={})
        assert "额外要求" not in prompt


class TestBuildUiExtractContent:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_basic_ui_specs(self):
        specs = [
            {
                "screen_name": "登录页",
                "ui_spec": {
                    "elements": [
                        {"text": "用户名", "type": "input"},
                        {"text": "密码", "type": "input"},
                    ]
                },
            }
        ]
        content = self.mixin._build_ui_extract_content(specs)
        assert "登录页" in content
        assert "用户名" in content
        assert "密码" in content

    def test_empty_ui_specs(self):
        content = self.mixin._build_ui_extract_content([])
        assert content == ""

    def test_no_text_elements(self):
        specs = [
            {
                "screen_name": "页面",
                "ui_spec": {
                    "elements": [
                        {"text": "", "type": "button"},
                    ]
                },
            }
        ]
        content = self.mixin._build_ui_extract_content(specs)
        assert "页面" in content

    def test_missing_ui_spec(self):
        specs = [{"screen_name": "页面"}]
        content = self.mixin._build_ui_extract_content(specs)
        assert "页面" in content


class TestBuildUiExtractPrompt:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_contains_ui_content(self):
        prompt = self.mixin._build_ui_extract_prompt("UI设计信息内容")
        assert "UI设计信息内容" in prompt
        assert "JSON" in prompt


class TestParseTestPointsResponse:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_valid_json_list(self):
        content = '[{"module": "登录", "point": "验证登录"}]'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_key(self):
        content = '{"test_points": [{"module": "登录", "point": "验证"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_data_key(self):
        content = '{"data": [{"module": "登录"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_items_key(self):
        content = '{"items": [{"module": "登录"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_points_key(self):
        content = '{"points": [{"module": "登录"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_invalid_json_with_array(self):
        content = '结果如下：[{"module": "登录"}] 结束'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_empty_content(self):
        result = self.mixin._parse_test_points_response("")
        assert result == []

    def test_completely_invalid(self):
        result = self.mixin._parse_test_points_response("no json at all")
        assert result == []

    def test_plain_dict_without_known_key(self):
        content = '{"module": "登录", "point": "验证"}'
        result = self.mixin._parse_test_points_response(content)
        assert isinstance(result, (list, dict))
