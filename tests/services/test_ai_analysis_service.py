import pytest
import json
import os
import tempfile

from app.services.ai_analysis_utils import (
    read_file_content,
    generate_analysis_prompt,
    parse_ai_response,
)


class TestReadFileContent:

    def test_read_existing_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("测试文件内容")
            f.flush()
            result = read_file_content(f.name)
            assert result == "测试文件内容"
        os.unlink(f.name)

    def test_read_nonexistent_file(self):
        result = read_file_content("/nonexistent/path/file.txt")
        assert result == "文件读取失败"

    def test_read_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("")
            f.flush()
            result = read_file_content(f.name)
            assert result == ""
        os.unlink(f.name)

    def test_read_unicode_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("中文内容 🔐 特殊符号 ©")
            f.flush()
            result = read_file_content(f.name)
            assert "🔐" in result
        os.unlink(f.name)

    def test_read_multiline_content(self):
        content = "第一行\n第二行\n第三行"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            result = read_file_content(f.name)
            assert "第一行" in result
            assert "第三行" in result
        os.unlink(f.name)


class TestGenerateAnalysisPrompt:

    def test_prompt_contains_content(self):
        content = "用户登录功能需求"
        prompt = generate_analysis_prompt(content)
        assert "用户登录功能需求" in prompt

    def test_prompt_contains_json_format(self):
        prompt = generate_analysis_prompt("测试需求")
        assert '"module"' in prompt
        assert '"function"' in prompt
        assert '"point"' in prompt
        assert '"priority"' in prompt

    def test_prompt_placeholder_replaced(self):
        prompt = generate_analysis_prompt("替换内容")
        assert "{REQ_CONTENT_PLACEHOLDER}" not in prompt

    def test_empty_content(self):
        prompt = generate_analysis_prompt("")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_rules(self):
        prompt = generate_analysis_prompt("需求")
        assert "优先级" in prompt or "priority" in prompt.lower()


class TestParseAiResponse:

    def test_parse_valid_response(self):
        data = [
            {"module": "用户管理", "function": "登录", "point": "验证登录", "priority": 1},
            {"module": "订单管理", "function": "创建", "point": "创建订单", "priority": 2},
        ]
        result = parse_ai_response(data)
        assert len(result) == 2
        assert result[0]["module"] == "用户管理"
        assert result[0]["priority"] == 1

    def test_parse_empty_list(self):
        result = parse_ai_response([])
        assert result == []

    def test_parse_missing_module_defaults(self):
        data = [{"function": "F", "point": "P", "priority": 2}]
        result = parse_ai_response(data)
        assert result[0]["module"] == "未命名模块"

    def test_parse_missing_function_defaults(self):
        data = [{"module": "M", "point": "P", "priority": 2}]
        result = parse_ai_response(data)
        assert result[0]["function"] == "未命名功能"

    def test_parse_priority_clamped_low(self):
        data = [{"module": "M", "function": "F", "point": "P", "priority": -1}]
        result = parse_ai_response(data)
        assert result[0]["priority"] == 1

    def test_parse_priority_clamped_high(self):
        data = [{"module": "M", "function": "F", "point": "P", "priority": 10}]
        result = parse_ai_response(data)
        assert result[0]["priority"] == 3

    def test_parse_priority_default(self):
        data = [{"module": "M", "function": "F", "point": "P"}]
        result = parse_ai_response(data)
        assert result[0]["priority"] == 2

    def test_parse_empty_point_filtered(self):
        data = [{"module": "M", "function": "F", "point": "", "priority": 1}]
        result = parse_ai_response(data)
        assert len(result) == 0

    def test_parse_ai_prompt_field(self):
        data = [{"module": "M", "function": "F", "point": "P", "priority": 1}]
        result = parse_ai_response(data)
        assert "ai_prompt" in result[0]
        parsed_prompt = json.loads(result[0]["ai_prompt"])
        assert parsed_prompt["module"] == "M"

    def test_parse_exception_returns_empty(self):
        result = parse_ai_response(None)
        assert result == []

    def test_parse_mixed_valid_invalid(self):
        data = [
            {"module": "M", "function": "F", "point": "有效", "priority": 1},
            {"module": "M", "function": "F", "point": "", "priority": 2},
        ]
        result = parse_ai_response(data)
        assert len(result) == 1
        assert result[0]["point"] == "有效"
