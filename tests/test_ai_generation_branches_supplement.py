"""
AI测试用例生成 - 遗漏分支补充测试

覆盖范围：
1. AIClient(AITestCaseMixin): analyze_requirements缓存/重试/JSON解析, generate_test_case重试/解析, _parse_generate_response, _validate_and_normalize_case
2. case_generation.AIMixin: _generate_case_with_ai重试/超时/HTTP错误/请求错误/响应格式错误
3. TestCaseGenerationAiMixin: generate_test_case_for_point UI关键词/分类推断, _build_ui_description
4. AIParseMixin: _parse_ai_response多级解析策略
5. TestCaseGenerationValidateMixin: _save_test_case完整流程, AUTO_PARSE_PRECONDITION分支
6. TestCaseGenerationBatchMixin: generate_test_cases_batch全流程(空测试点/warning/部分失败/全部成功)
7. batch-generate/stream端点
8. ContextMixin: _sort_flow_nodes
"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.models.project import Project
from app.models.test_case import TestCase
from app.utils.jwt_utils import create_access_token
from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
)
from app.utils.ai_client import AIClient


@pytest.fixture(scope="function")
def auth_client(client, db, testUser):
    token = create_access_token({"sub": str(testUser.id), "username": testUser.username})
    client.headers.update({"Authorization": f"Bearer {token}"})
    client._test_user_id = testUser.id
    yield client


@pytest.fixture(scope="function")
def real_project(db, testUser):
    proj = Project(
        name=f"test_proj_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        user_id=testUser.id,
        description="\u6d4b\u8bd5\u9879\u76ee",
        test_object_url="http://localhost:8080",
    )
    db.add(proj)
    db.flush()
    yield proj
    db.rollback()


def _make_ai_client():
    with patch("app.utils.ai_client_core.settings") as mock_settings:
        mock_settings.DEEPSEEK_API_URL = "http://fake-api/v1/chat/completions"
        mock_settings.DEEPSEEK_API_KEY = "test-key"
        mock_settings.DEEPSEEK_MODEL = "test-model"
        client = AIClient()
    client.max_retries = 2
    client.retry_delay = 0
    return client


class TestAITestCaseMixinAnalyzeRequirements:

    def test_analyze_requirements_cache_hit(self):
        ai = _make_ai_client()
        ai._set_to_cache("analyze_requirements:test", [{"module": "M", "point": "P"}])
        with patch.object(ai, "_get_cache_key", return_value="analyze_requirements:test"):
            result = ai.analyze_requirements("test content")
        assert len(result) == 1
        assert result[0]["module"] == "M"

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_valid_json_response(self, mock_post):
        ai = _make_ai_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps([{"module": "M", "point": "P", "priority": 1}])}}]
        }
        mock_post.return_value = mock_resp
        result = ai.analyze_requirements("test content")
        assert len(result) == 1

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_json_with_surrounding_text(self, mock_post):
        ai = _make_ai_client()
        content = 'Result:\n[{"module": "M", "point": "P", "priority": 1}]\nDone.'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        mock_post.return_value = mock_resp
        result = ai.analyze_requirements("test content")
        assert len(result) == 1

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_invalid_json_returns_empty(self, mock_post):
        ai = _make_ai_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "not json at all"}}]}
        mock_post.return_value = mock_resp
        result = ai.analyze_requirements("test content")
        assert result == []

    @patch("app.utils.ai_client_test_case.requests.post")
    @patch("app.utils.ai_client_test_case.time.sleep")
    def test_analyze_requirements_retry_then_success(self, mock_sleep, mock_post):
        ai = _make_ai_client()
        import requests
        mock_resp_fail = MagicMock()
        mock_resp_fail.raise_for_status.side_effect = requests.RequestException("timeout")
        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.raise_for_status = MagicMock()
        mock_resp_ok.json.return_value = {
            "choices": [{"message": {"content": json.dumps([{"module": "M", "point": "P"}])}}]
        }
        mock_post.side_effect = [mock_resp_fail, mock_resp_ok]
        result = ai.analyze_requirements("test content")
        assert len(result) == 1
        assert mock_sleep.call_count == 1

    @patch("app.utils.ai_client_test_case.requests.post")
    @patch("app.utils.ai_client_test_case.time.sleep")
    def test_analyze_requirements_all_retries_fail(self, mock_sleep, mock_post):
        ai = _make_ai_client()
        import requests
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.RequestException("connection error")
        mock_post.return_value = mock_resp
        with pytest.raises(AIServiceError):
            ai.analyze_requirements("test content")

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_unexpected_exception(self, mock_post):
        ai = _make_ai_client()
        mock_post.side_effect = RuntimeError("unexpected")
        with pytest.raises(AIServiceError):
            ai.analyze_requirements("test content")


class TestAITestCaseMixinGenerateTestCase:

    def test_generate_test_case_cache_hit(self):
        ai = _make_ai_client()
        ai._set_to_cache("generate_test_case:tp", {"title": "cached"})
        with patch.object(ai, "_get_cache_key", return_value="generate_test_case:tp"):
            result = ai.generate_test_case({"module": "M", "point": "P"})
        assert result["title"] == "cached"

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_valid_response(self, mock_post):
        ai = _make_ai_client()
        case_data = {
            "title": "\u6d4b\u8bd5\u7528\u4f8b",
            "precondition": "\u8d26\u53f7\u5df2\u767b\u5f55",
            "steps": [{"step": 1, "action": "\u70b9\u51fb\u6309\u94ae", "expected_result": "\u6210\u529f"}],
            "expected_result": "\u6210\u529f",
            "case_type": "ui_automation",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": json.dumps(case_data)}}]}
        mock_post.return_value = mock_resp
        result = ai.generate_test_case({"module": "M", "point": "P"})
        assert result["title"] == "\u6d4b\u8bd5\u7528\u4f8b"

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_parse_failure_raises(self, mock_post):
        ai = _make_ai_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
        mock_post.return_value = mock_resp
        with pytest.raises(AIResponseParseError):
            ai.generate_test_case({"module": "M", "point": "P"})

    @patch("app.utils.ai_client_test_case.requests.post")
    @patch("app.utils.ai_client_test_case.time.sleep")
    def test_generate_test_case_retry_on_network_error(self, mock_sleep, mock_post):
        ai = _make_ai_client()
        import requests
        mock_resp_fail = MagicMock()
        mock_resp_fail.raise_for_status.side_effect = requests.RequestException("network error")
        case_data = {"title": "T", "precondition": "P", "steps": [{"step": 1, "action": "A", "expected_result": "E"}]}
        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.raise_for_status = MagicMock()
        mock_resp_ok.json.return_value = {"choices": [{"message": {"content": json.dumps(case_data)}}]}
        mock_post.side_effect = [mock_resp_fail, mock_resp_ok]
        result = ai.generate_test_case({"module": "M", "point": "P"})
        assert result["title"] == "T"

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_json_decode_error(self, mock_post):
        ai = _make_ai_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = json.JSONDecodeError("", "", 0)
        mock_post.return_value = mock_resp
        with pytest.raises(AIResponseParseError):
            ai.generate_test_case({"module": "M", "point": "P"})


class TestAITestCaseMixinParseGenerateResponse:

    def test_parse_valid_dict(self):
        ai = _make_ai_client()
        content = json.dumps({"title": "T", "precondition": "P", "steps": []})
        result = ai._parse_generate_response(content)
        assert result["title"] == "T"

    def test_parse_json_with_surrounding_text(self):
        ai = _make_ai_client()
        content = 'Some text {"title": "T", "precondition": "P", "steps": []} more text'
        result = ai._parse_generate_response(content)
        assert result["title"] == "T"

    def test_parse_invalid_json_raises(self):
        ai = _make_ai_client()
        with pytest.raises(AIResponseParseError):
            ai._parse_generate_response("no json here")

    def test_parse_extracted_json_still_invalid_raises(self):
        ai = _make_ai_client()
        with pytest.raises(AIResponseParseError):
            ai._parse_generate_response("{invalid json content}")


class TestAITestCaseMixinValidateAndNormalize:

    def test_missing_required_fields_raises(self):
        ai = _make_ai_client()
        with pytest.raises(AIResponseFormatError):
            ai._validate_and_normalize_case({"title": "T"})

    def test_new_format_with_expected_results(self):
        ai = _make_ai_client()
        case = {
            "title": "T", "precondition": "P",
            "steps": [{"step": 1, "action": "A", "expected_result": "E"}],
            "expected_results": ["E1", "E2"],
        }
        result = ai._validate_and_normalize_case(case)
        assert result is not None

    def test_old_format_without_expected_results(self):
        ai = _make_ai_client()
        case = {
            "title": "T", "precondition": "P",
            "steps": [{"step": 1, "action": "A", "expected_result": "E"}],
        }
        result = ai._validate_and_normalize_case(case)
        assert result is not None

    def test_all_required_fields_present(self):
        ai = _make_ai_client()
        case = {"title": "T", "precondition": "P", "steps": []}
        result = ai._validate_and_normalize_case(case)
        assert result["title"] == "T"


class TestAiMixinGenerateCaseWithAi:

    async def _make_mixin(self):
        from app.services.case_generation.ai_mixin import AIMixin
        mixin = AIMixin()
        mixin._parse_ai_response = MagicMock(return_value={"title": "T"})
        mixin._async_sleep = AsyncMock()
        return mixin

    async def test_timeout_retry_then_fail(self):
        import httpx
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="AI\u751f\u6210\u5931\u8d25"):
                await mixin._generate_case_with_ai({
                    "requirement_content": "req", "ui_description": "", "ui_specs": [],
                    "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
                })
        assert mixin._async_sleep.call_count == 2

    async def test_http_status_error_retry(self):
        import httpx
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=mock_response))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError):
                await mixin._generate_case_with_ai({
                    "requirement_content": "req", "ui_description": "", "ui_specs": [],
                    "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
                })

    async def test_request_error_retry(self):
        import httpx
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("conn err"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError):
                await mixin._generate_case_with_ai({
                    "requirement_content": "req", "ui_description": "", "ui_specs": [],
                    "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
                })

    async def test_response_missing_choices_raises(self):
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {}
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="choices"):
                await mixin._generate_case_with_ai({
                    "requirement_content": "req", "ui_description": "", "ui_specs": [],
                    "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
                })

    async def test_response_empty_choices_raises(self):
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"choices": []}
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="\u4e3a\u7a7a"):
                await mixin._generate_case_with_ai({
                    "requirement_content": "req", "ui_description": "", "ui_specs": [],
                    "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
                })

    async def test_response_missing_message_raises(self):
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"choices": [{}]}
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="message"):
                await mixin._generate_case_with_ai({
                    "requirement_content": "req", "ui_description": "", "ui_specs": [],
                    "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
                })

    async def test_response_empty_content_raises(self):
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"choices": [{"message": {"content": ""}}]}
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="\u4e3a\u7a7a"):
                await mixin._generate_case_with_ai({
                    "requirement_content": "req", "ui_description": "", "ui_specs": [],
                    "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
                })

    async def test_success_on_first_attempt(self):
        mixin = await self._make_mixin()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"choices": [{"message": {"content": "valid json"}}]}
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await mixin._generate_case_with_ai({
                "requirement_content": "req", "ui_description": "", "ui_specs": [],
                "test_point": {"module": "M", "function": "F", "point": "P", "priority": 2}
            })
        assert result["title"] == "T"


class TestAiMixinGenerateTestCaseForPoint:

    async def test_no_ui_description_manual_category(self):
        from app.services.test_case_generation.ai_mixin import TestCaseGenerationAiMixin
        mixin = TestCaseGenerationAiMixin()
        mixin._generate_case_with_ai = AsyncMock(return_value={"title": "T"})
        await mixin.generate_test_case_for_point(
            context={"ui_descriptions": [], "requirement_content": "req"},
            test_point={"module": "M", "point": "P"},
            project_id=1,
        )
        call_args = mixin._generate_case_with_ai.call_args[0][0]
        assert call_args["case_category"] == "manual"

    async def test_ui_with_interactive_elements(self):
        from app.services.test_case_generation.ai_mixin import TestCaseGenerationAiMixin
        mixin = TestCaseGenerationAiMixin()
        mixin._generate_case_with_ai = AsyncMock(return_value={"title": "T"})
        await mixin.generate_test_case_for_point(
            context={"ui_descriptions": [{"description": "\u70b9\u51fb\u6309\u94ae\u63d0\u4ea4\u8868\u5355"}], "requirement_content": "req", "ui_specs": []},
            test_point={"module": "M", "point": "P"},
            project_id=1,
        )
        call_args = mixin._generate_case_with_ai.call_args[0][0]
        assert call_args["case_category"] == "ui_automation"

    async def test_ui_without_interactive_elements(self):
        from app.services.test_case_generation.ai_mixin import TestCaseGenerationAiMixin
        mixin = TestCaseGenerationAiMixin()
        mixin._generate_case_with_ai = AsyncMock(return_value={"title": "T"})
        await mixin.generate_test_case_for_point(
            context={"ui_descriptions": [{"description": "\u9759\u6001\u5c55\u793a\u9875\u9762\u6587\u5b57\u63cf\u8ff0"}], "requirement_content": "req", "ui_specs": []},
            test_point={"module": "M", "point": "P"},
            project_id=1,
        )
        call_args = mixin._generate_case_with_ai.call_args[0][0]
        assert call_args["case_category"] == "manual"

    async def test_case_type_override(self):
        from app.services.test_case_generation.ai_mixin import TestCaseGenerationAiMixin
        mixin = TestCaseGenerationAiMixin()
        mixin._generate_case_with_ai = AsyncMock(return_value={"title": "T"})
        await mixin.generate_test_case_for_point(
            context={"ui_descriptions": [], "requirement_content": "req"},
            test_point={"module": "M", "point": "P"},
            project_id=1,
            case_type="api_automation",
        )
        call_args = mixin._generate_case_with_ai.call_args[0][0]
        assert call_args["case_type"] == "api_automation"

    def test_build_ui_description_with_summary_fallback(self):
        from app.services.test_case_generation.ai_mixin import TestCaseGenerationAiMixin
        mixin = TestCaseGenerationAiMixin()
        result = mixin._build_ui_description([
            {"description": "", "summary": "\u5907\u7528\u63cf\u8ff0"},
            {"description": "\u4e3b\u63cf\u8ff0"},
        ])
        assert "\u5907\u7528\u63cf\u8ff0" in result
        assert "\u4e3b\u63cf\u8ff0" in result


class TestAiParseMixin:

    def test_direct_json_parse(self):
        from app.services.case_generation.ai_parse_mixin import AIParseMixin
        mixin = AIParseMixin()
        result = mixin._parse_ai_response('{"title": "T", "steps": []}')
        assert result["title"] == "T"

    def test_fix_common_json_issues_then_parse(self):
        from app.services.case_generation.ai_parse_mixin import AIParseMixin
        mixin = AIParseMixin()
        content = '{"title": "T", "steps": [],}'
        result = mixin._parse_ai_response(content)
        assert result["title"] == "T"

    def test_clean_json_string_then_parse(self):
        from app.services.case_generation.ai_parse_mixin import AIParseMixin
        mixin = AIParseMixin()
        content = '```json\n{"title": "T", "steps": []}\n```'
        result = mixin._parse_ai_response(content)
        assert result["title"] == "T"

    def test_regex_extract_then_fix(self):
        from app.services.case_generation.ai_parse_mixin import AIParseMixin
        mixin = AIParseMixin()
        content = 'Result: {"title": "T", "steps": []} end'
        result = mixin._parse_ai_response(content)
        assert result["title"] == "T"

    def test_all_strategies_fail_raises(self):
        from app.services.case_generation.ai_parse_mixin import AIParseMixin
        mixin = AIParseMixin()
        with pytest.raises(ValueError, match="\u65e0\u6cd5\u89e3\u6790"):
            mixin._parse_ai_response("totally not json")


class TestValidateMixinSaveTestCase:

    async def test_save_with_steps_and_test_data(self, db, real_project):
        from app.services.test_case_generation.validate_mixin import TestCaseGenerationValidateMixin
        mixin = TestCaseGenerationValidateMixin()
        mixin.db = db
        generated_case = {
            "title": "\u6d4b\u8bd5\u7528\u4f8b", "module": "\u6d4b\u8bd5\u6a21\u5757",
            "precondition": "\u8d26\u53f7\u5df2\u767b\u5f55",
            "steps": [
                {"step": 1, "action": "\u70b9\u51fb\u6309\u94ae", "expected_result": "\u6210\u529f", "action_type": "click"},
                {"step": 2, "action": "\u8f93\u5165\u6570\u636e", "expected_result": "\u5b8c\u6210", "action_type": "input", "input_value": "test"},
            ],
            "expected_result": "\u64cd\u4f5c\u6210\u529f", "priority": "P1",
            "case_type": "ui_automation", "test_category": "ui_automation",
            "test_data": [{"key": "value"}],
        }
        test_point = {"id": None, "module": "\u6d4b\u8bd5\u6a21\u5757", "point": "P"}
        with patch("app.services.test_case_generation.validate_mixin.settings") as mock_settings:
            mock_settings.AUTO_PARSE_PRECONDITION = False
            case = await mixin._save_test_case(real_project.id, generated_case, test_point)
        assert case.id is not None
        assert case.title == "\u6d4b\u8bd5\u7528\u4f8b"

    async def test_save_with_auto_parse_precondition(self, db, real_project):
        from app.services.test_case_generation.validate_mixin import TestCaseGenerationValidateMixin
        mixin = TestCaseGenerationValidateMixin()
        mixin.db = db
        generated_case = {
            "title": "\u81ea\u52a8\u89e3\u6790\u524d\u7f6e", "module": "\u6d4b\u8bd5\u6a21\u5757",
            "precondition": "1. \u6253\u5f00\u6d4f\u89c8\u5668 2. \u8f93\u5165\u7528\u6237\u540d",
            "steps": [], "expected_result": "\u524d\u7f6e\u5b8c\u6210", "priority": "P2",
            "case_type": "manual", "test_category": "manual",
        }
        test_point = {"id": None, "module": "\u6d4b\u8bd5\u6a21\u5757"}
        with patch("app.services.test_case_generation.validate_mixin.settings") as mock_settings, \
             patch("app.utils.ai_client.parse_precondition_to_steps", new_callable=AsyncMock) as mock_parse:
            mock_settings.AUTO_PARSE_PRECONDITION = True
            mock_parse.return_value = [
                {"action": "\u6253\u5f00\u6d4f\u89c8\u5668", "action_type": "navigate", "expected_result": "\u6d4f\u89c8\u5668\u6253\u5f00"},
            ]
            case = await mixin._save_test_case(real_project.id, generated_case, test_point)
        assert case.id is not None

    async def test_save_auto_parse_exception_handled(self, db, real_project):
        from app.services.test_case_generation.validate_mixin import TestCaseGenerationValidateMixin
        mixin = TestCaseGenerationValidateMixin()
        mixin.db = db
        generated_case = {
            "title": "\u89e3\u6790\u5f02\u5e38", "module": "\u6d4b\u8bd5\u6a21\u5757",
            "precondition": "\u524d\u7f6e\u6761\u4ef6", "steps": [],
            "expected_result": "\u5b8c\u6210", "priority": "P2",
            "case_type": "manual", "test_category": "manual",
        }
        test_point = {"id": None, "module": "\u6d4b\u8bd5\u6a21\u5757"}
        with patch("app.services.test_case_generation.validate_mixin.settings") as mock_settings, \
             patch("app.utils.ai_client.parse_precondition_to_steps", new_callable=AsyncMock) as mock_parse:
            mock_settings.AUTO_PARSE_PRECONDITION = True
            mock_parse.side_effect = Exception("parse error")
            case = await mixin._save_test_case(real_project.id, generated_case, test_point)
        assert case.id is not None


class TestBatchMixin:

    async def test_no_test_points_returns_warning(self):
        from app.services.test_case_generation.batch_mixin import TestCaseGenerationBatchMixin
        mixin = TestCaseGenerationBatchMixin()
        mixin.get_context_for_generation = AsyncMock(return_value={
            "test_points": [], "warnings": [], "pagination": {}
        })
        results = []
        async for item in mixin.generate_test_cases_batch(project_id=1, user_id=1):
            results.append(item)
        assert any(r.get("status") == "warning" and r.get("progress") == 100 for r in results)

    async def test_with_warnings_yields_warning_events(self):
        from app.services.test_case_generation.batch_mixin import TestCaseGenerationBatchMixin
        mixin = TestCaseGenerationBatchMixin()
        mixin.get_context_for_generation = AsyncMock(return_value={
            "test_points": [{"id": 1, "module": "M", "point": "P"}],
            "warnings": ["\u8b66\u544a1", "\u8b66\u544a2", "\u8b66\u544a3", "\u8b66\u544a4"],
            "pagination": {},
        })
        mixin.generate_test_case_for_point = AsyncMock(return_value={"title": "T", "steps": []})
        mixin._save_test_case = AsyncMock(return_value=MagicMock(id=1, title="T", module="M"))
        results = []
        async for item in mixin.generate_test_cases_batch(project_id=1, user_id=1):
            results.append(item)
        warning_events = [r for r in results if r.get("status") == "warning"]
        assert len(warning_events) == 3

    async def test_partial_failure_yields_partial_status(self):
        from app.services.test_case_generation.batch_mixin import TestCaseGenerationBatchMixin
        mixin = TestCaseGenerationBatchMixin()
        mixin.get_context_for_generation = AsyncMock(return_value={
            "test_points": [{"id": 1, "module": "M", "point": "P1"}, {"id": 2, "module": "M", "point": "P2"}],
            "warnings": [], "pagination": {},
        })
        mixin.generate_test_case_for_point = AsyncMock(side_effect=[
            {"title": "T1", "steps": []},
            Exception("AI\u5931\u8d25"),
        ])
        mixin._save_test_case = AsyncMock(return_value=MagicMock(id=1, title="T1", module="M"))
        results = []
        async for item in mixin.generate_test_cases_batch(project_id=1, user_id=1):
            results.append(item)
        final = results[-1]
        assert final["status"] == "partial"
        assert final["failed"] == 1

    async def test_all_success_yields_success_status(self):
        from app.services.test_case_generation.batch_mixin import TestCaseGenerationBatchMixin
        mixin = TestCaseGenerationBatchMixin()
        mixin.get_context_for_generation = AsyncMock(return_value={
            "test_points": [{"id": 1, "module": "M", "point": "P"}],
            "warnings": [], "pagination": {},
        })
        mixin.generate_test_case_for_point = AsyncMock(return_value={"title": "T", "steps": []})
        mixin._save_test_case = AsyncMock(return_value=MagicMock(id=1, title="T", module="M"))
        results = []
        async for item in mixin.generate_test_cases_batch(project_id=1, user_id=1):
            results.append(item)
        final = results[-1]
        assert final["status"] == "success"
        assert final["created"] == 1


class TestContextMixinFlowSort:

    async def test_sort_flow_nodes_main_first(self):
        from app.services.case_generation.context_mixin import _sort_flow_nodes

        class FakeNode:
            def __init__(self, flow_type, main_order=None, screen_order=0):
                self.flow_type = flow_type
                self.main_order = main_order
                self.screen_order = screen_order

        nodes = [
            FakeNode("branch", screen_order=2),
            FakeNode("main", main_order=2, screen_order=3),
            FakeNode("main", main_order=1, screen_order=1),
            FakeNode("exception", screen_order=4),
        ]
        sorted_nodes = _sort_flow_nodes(nodes)
        assert sorted_nodes[0].flow_type == "main"
        assert sorted_nodes[0].main_order == 1
        assert sorted_nodes[1].flow_type == "main"
        assert sorted_nodes[1].main_order == 2
