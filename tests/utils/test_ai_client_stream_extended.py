import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.utils.ai_client_stream._analyze import _AnalyzeStreamMixin
from app.utils.ai_client_stream._generate import _GenerateStreamMixin
from app.utils.ai_client_stream import AIStreamMixin


class TestParseStreamTestPoints:
    def setup_method(self):
        self.mixin = _AnalyzeStreamMixin()
        self.mixin.api_key = "test_key"
        self.mixin.model = "test_model"
        self.mixin.api_url = "http://test/api"
        self.mixin.max_retries = 1
        self.mixin.retry_delay = 0

    def test_parse_valid_json_array(self):
        content = json.dumps([{"module": "M1", "function": "F1", "point": "P1", "priority": 1}])
        result = self.mixin._parse_stream_test_points(content)
        assert result is not None
        assert len(result) == 1

    def test_parse_json_in_markdown_code_block(self):
        content = '```json\n[{"module": "M1", "function": "F1", "point": "P1", "priority": 1}]\n```'
        result = self.mixin._parse_stream_test_points(content)
        assert result is not None

    def test_parse_json_in_plain_code_block(self):
        content = '```\n[{"module": "M1", "function": "F1", "point": "P1", "priority": 1}]\n```'
        result = self.mixin._parse_stream_test_points(content)
        assert result is not None

    def test_parse_json_array_in_text(self):
        content = 'Here are the results: [{"module": "M1", "function": "F1", "point": "P1", "priority": 1}]'
        result = self.mixin._parse_stream_test_points(content)
        assert result is not None

    def test_parse_invalid_content(self):
        content = "no json at all"
        result = self.mixin._parse_stream_test_points(content)
        assert result is None

    def test_parse_empty_content(self):
        result = self.mixin._parse_stream_test_points("")
        assert result is None

    def test_parse_broken_json_with_fix(self):
        content = '[{"module": "M1", "point": "P1", priority: 1}]'
        result = self.mixin._parse_stream_test_points(content)
        assert result is None or isinstance(result, list)


class TestAnalyzeRequirementsStream:
    @pytest.mark.asyncio
    async def test_analyze_success(self):
        mixin = _AnalyzeStreamMixin()
        mixin.api_key = "test_key"
        mixin.model = "test_model"
        mixin.api_url = "http://test/api"
        mixin.max_retries = 1
        mixin.retry_delay = 0

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(
            return_value=[
                b'data: {"choices": [{"delta": {"content": "[{\\"module\\": \\"M1\\", \\"point\\": \\"P1\\", \\"priority\\": 1}]"}}]\n'
            ]
        )

        results = []
        with patch("requests.post", return_value=mock_response):
            async for item in mixin.analyze_requirements_stream("test content"):
                results.append(item)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_analyze_request_error(self):
        mixin = _AnalyzeStreamMixin()
        mixin.api_key = "test_key"
        mixin.model = "test_model"
        mixin.api_url = "http://test/api"
        mixin.max_retries = 1
        mixin.retry_delay = 0

        import requests
        with patch("requests.post", side_effect=requests.RequestException("connection error")):
            results = []
            async for item in mixin.analyze_requirements_stream("test content"):
                results.append(item)
            assert any(r.get("error") for r in results)


class TestGenerateTestCaseStream:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        mixin = _GenerateStreamMixin()
        mixin.api_key = "test_key"
        mixin.model = "test_model"
        mixin.api_url = "http://test/api"
        mixin.max_retries = 1
        mixin.retry_delay = 0

        case_json = json.dumps({
            "title": "测试用例",
            "precondition": "前置条件",
            "steps": [{"step": 1, "action": "操作"}],
            "expected_result": "预期结果",
            "case_type": "UI",
        })

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(
            return_value=[
                b'data: {"choices": [{"delta": {"content": "' + case_json.encode() + b'"}}]\n'
            ]
        )

        results = []
        with patch("requests.post", return_value=mock_response):
            async for item in mixin.generate_test_case_stream({"module": "M1", "point": "P1"}):
                results.append(item)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_generate_missing_fields(self):
        mixin = _GenerateStreamMixin()
        mixin.api_key = "test_key"
        mixin.model = "test_model"
        mixin.api_url = "http://test/api"
        mixin.max_retries = 1
        mixin.retry_delay = 0

        case_json = json.dumps({"title": "测试用例"})

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(
            return_value=[
                b'data: {"choices": [{"delta": {"content": "' + case_json.encode() + b'"}}]\n'
            ]
        )

        results = []
        with patch("requests.post", return_value=mock_response):
            async for item in mixin.generate_test_case_stream({"module": "M1", "point": "P1"}):
                results.append(item)
        assert any(r.get("error") for r in results)

    @pytest.mark.asyncio
    async def test_generate_request_error(self):
        mixin = _GenerateStreamMixin()
        mixin.api_key = "test_key"
        mixin.model = "test_model"
        mixin.api_url = "http://test/api"
        mixin.max_retries = 1
        mixin.retry_delay = 0

        import requests
        with patch("requests.post", side_effect=requests.RequestException("connection error")):
            results = []
            async for item in mixin.generate_test_case_stream({"module": "M1", "point": "P1"}):
                results.append(item)
            assert any(r.get("error") for r in results)

    @pytest.mark.asyncio
    async def test_generate_invalid_json_response(self):
        mixin = _GenerateStreamMixin()
        mixin.api_key = "test_key"
        mixin.model = "test_model"
        mixin.api_url = "http://test/api"
        mixin.max_retries = 1
        mixin.retry_delay = 0

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(
            return_value=[
                b'data: {"choices": [{"delta": {"content": "not valid json"}}]\n'
            ]
        )

        results = []
        with patch("requests.post", return_value=mock_response):
            async for item in mixin.generate_test_case_stream({"module": "M1", "point": "P1"}):
                results.append(item)
        assert any(r.get("error") for r in results)


class TestAIStreamMixin:
    def test_inherits_both_mixins(self):
        assert issubclass(AIStreamMixin, _AnalyzeStreamMixin)
        assert issubclass(AIStreamMixin, _GenerateStreamMixin)
