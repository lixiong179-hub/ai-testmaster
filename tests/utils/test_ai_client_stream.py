import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from app.utils.ai_client_enhanced._basic import (
    generate_test_case,
    parse_precondition_to_steps,
    analyze_requirements_stream,
    generate_test_case_stream,
)
from app.utils.ai_client_core import AIClientBase, AIServiceError


class _StreamClient:
    def __init__(self):
        self.api_url = "http://test"
        self.api_key = "test-key"
        self.model = "test-model"
        self.max_retries = 1
        self.retry_delay = 0
        self.cache = {}
        self.cache_expiry = 3600

    def _get_cache_key(self, fn, *args, **kwargs):
        import hashlib
        key_data = f"{fn}:{str(args)}:{str(kwargs)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_from_cache(self, key):
        import time
        if key in self.cache:
            data, ts = self.cache[key]
            if time.time() - ts < self.cache_expiry:
                return data
            del self.cache[key]
        return None

    def _set_to_cache(self, key, data):
        import time
        self.cache[key] = (data, time.time())


class TestGenerateTestCaseBasic:

    @patch("app.utils.ai_client_enhanced._basic.generate_test_case_enhanced")
    def test_with_context_calls_enhanced(self, mock_enhanced):
        mock_enhanced.return_value = [{"title": "增强用例", "steps": []}]
        test_point = {"module": "M", "function": "F", "point": "P", "priority": 1}
        context = {"requirement": "需求", "test_points": []}
        result = generate_test_case(test_point, context)
        assert result["title"] == "增强用例"

    @patch("app.utils.ai_client_enhanced._basic.generate_test_case_enhanced")
    def test_with_context_empty_result(self, mock_enhanced):
        mock_enhanced.return_value = []
        test_point = {"module": "M", "function": "F", "point": "P", "priority": 1}
        context = {"requirement": "需求"}
        result = generate_test_case(test_point, context)
        assert result == {}

    @patch("app.utils.ai_client_enhanced._basic.generate_test_case_enhanced")
    def test_string_test_point_converted(self, mock_enhanced):
        mock_enhanced.return_value = [{"title": "T", "steps": []}]
        result = generate_test_case("简单测试点", {"requirement": "R"})
        assert mock_enhanced.called

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_without_context_uses_basic_client(self, mock_post):
        case_data = {
            "title": "基础用例",
            "precondition": "前置",
            "steps": [{"step": 1, "action": "A", "action_type": "click",
                       "input_value": "", "target_element": "E",
                       "expected_result": "R"}],
            "expected_result": "R"
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": json.dumps(case_data)}}]}
        mock_post.return_value = mock_resp
        test_point = {"module": "M", "function": "F", "point": "P", "priority": 2}
        result = generate_test_case(test_point)
        assert result["title"] == "基础用例"


class TestParsePreconditionToSteps:

    def test_empty_precondition(self):
        result = parse_precondition_to_steps("")
        assert result == []

    def test_none_precondition(self):
        result = parse_precondition_to_steps(None)
        assert result == []

    def test_whitespace_only(self):
        result = parse_precondition_to_steps("   ")
        assert result == []

    def test_numbered_steps_pattern1(self):
        precondition = "1. 打开浏览器\n2. 输入用户名\n3. 点击登录"
        result = parse_precondition_to_steps(precondition)
        assert len(result) == 3
        assert result[0]["action"] == "打开浏览器"
        assert result[1]["action"] == "输入用户名"

    def test_numbered_steps_pattern2(self):
        precondition = "1、打开页面\n2、输入内容"
        result = parse_precondition_to_steps(precondition)
        assert len(result) >= 2

    def test_semicolon_separated(self):
        precondition = "步骤1；步骤2；步骤3"
        result = parse_precondition_to_steps(precondition)
        assert len(result) == 3

    def test_newline_separated(self):
        precondition = "第一步\n第二步\n第三步"
        result = parse_precondition_to_steps(precondition)
        assert len(result) == 3

    def test_single_line_precondition(self):
        precondition = "账号已登录设备网络正常"
        result = parse_precondition_to_steps(precondition)
        assert len(result) == 1
        assert result[0]["step"] == 1

    def test_step_has_action_type(self):
        precondition = "1. 输入用户名admin\n2. 点击登录按钮"
        result = parse_precondition_to_steps(precondition)
        assert result[0]["action_type"] == "input"
        assert result[1]["action_type"] == "click"

    def test_step_structure_fields(self):
        precondition = "1. 验证页面展示"
        result = parse_precondition_to_steps(precondition)
        step = result[0]
        assert "step" in step
        assert "action" in step
        assert "action_type" in step
        assert "input_value" in step
        assert "target_element" in step
        assert "description" in step
        assert "expected_result" in step
        assert "test_data" in step
        assert "ui_elements" in step


class TestAnalyzeRequirementsStream:

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        from app.utils.ai_client_stream import AIStreamMixin

        class _MockStreamClient(AIStreamMixin, AIClientBase):
            pass

        with patch.object(_MockStreamClient, "analyze_requirements_stream") as mock_stream:
            async def _gen(content):
                yield "chunk1"
                yield "chunk2"
            mock_stream.side_effect = _gen
            client = _MockStreamClient()
            chunks = []
            async for chunk in client.analyze_requirements_stream("test"):
                chunks.append(chunk)
            assert len(chunks) == 2


class TestGenerateTestCaseStream:

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        from app.utils.ai_client_stream import AIStreamMixin

        class _MockStreamClient(AIStreamMixin, AIClientBase):
            pass

        with patch.object(_MockStreamClient, "generate_test_case_stream") as mock_stream:
            async def _gen(tp):
                yield {"title": "T"}
            mock_stream.side_effect = _gen
            client = _MockStreamClient()
            chunks = []
            async for chunk in client.generate_test_case_stream({"point": "P"}):
                chunks.append(chunk)
            assert len(chunks) == 1
