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
        # R1 修复后 case_type 才是 manual/ui_automation（执行方式），
        # case_category 是 positive/boundary/exception（测试场景，未传入时为 None）。
        assert call_args["case_type"] == "manual"

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
        # R1 修复后断言 case_type（执行方式），而非 case_category（测试场景）。
        assert call_args["case_type"] == "ui_automation"

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
        # R1 修复后断言 case_type（执行方式），而非 case_category（测试场景）。
        assert call_args["case_type"] == "manual"

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


class TestValidateMixinSaveTestCase:

    async def test_save_with_steps_and_test_data(self, db, real_project):
        from app.services.test_case_generation.validate_mixin import TestCaseGenerationValidateMixin
        mixin = TestCaseGenerationValidateMixin()
        mixin.db = db
        generated_case = {
            "title": "\u5df2\u767b\u5f55\u7528\u6237\u5728\u8868\u5355\u9875\u586b\u5199\u6570\u636e\u5e76\u4fdd\u5b58", "module": "\u6d4b\u8bd5\u6a21\u5757",
            "precondition": "\u8d26\u53f7\u5df2\u767b\u5f55\uff0c\u6d4f\u89c8\u5668\u7f51\u7edc\u6b63\u5e38\uff0c\u5df2\u6253\u5f00\u6570\u636e\u5f55\u5165\u9875\u9762",
            "steps": [
                {"step": 1, "action": "\u70b9\u51fb\u65b0\u589e\u6570\u636e\u6309\u94ae", "expected_result": "\u6570\u636e\u5f55\u5165\u8868\u5355\u5c55\u5f00\u4e14\u540d\u79f0\u8f93\u5165\u6846\u53ef\u89c1", "action_type": "click"},
                {"step": 2, "action": "\u8f93\u5165\u6570\u636e\u540d\u79f0", "expected_result": "\u540d\u79f0\u8f93\u5165\u6846\u663e\u793a\u7528\u6237\u5df2\u8f93\u5165\u7684\u6587\u672c", "action_type": "input", "input_value": "\u81ea\u52a8\u5316\u7528\u6237\u6570\u636e001"},
            ],
            "expected_result": "\u9875\u9762\u4fdd\u7559\u7528\u6237\u8f93\u5165\u7684\u6570\u636e\u540d\u79f0\uff0c\u4e14\u8868\u5355\u4ecd\u5904\u4e8e\u53ef\u7f16\u8f91\u72b6\u6001", "priority": "P1",
            "case_type": "ui_automation", "test_category": "ui_automation",
            "case_category": "positive",
            "test_data": [{"key": "value"}],
        }
        test_point = {"id": None, "module": "\u6d4b\u8bd5\u6a21\u5757", "point": "P"}
        with patch("app.services.test_case_generation.validate_mixin.settings") as mock_settings:
            mock_settings.AUTO_PARSE_PRECONDITION = False
            case = await mixin._save_test_case(real_project.id, generated_case, test_point)
        assert case.id is not None
        assert case.title == "\u5df2\u767b\u5f55\u7528\u6237\u5728\u8868\u5355\u9875\u586b\u5199\u6570\u636e\u5e76\u4fdd\u5b58"

    async def test_save_with_auto_parse_precondition(self, db, real_project):
        from app.services.test_case_generation.validate_mixin import TestCaseGenerationValidateMixin
        mixin = TestCaseGenerationValidateMixin()
        mixin.db = db
        generated_case = {
            "title": "\u5df2\u767b\u5f55\u7528\u6237\u6253\u5f00\u524d\u7f6e\u914d\u7f6e\u9875\u5e76\u6821\u9a8c\u8868\u5355", "module": "\u6d4b\u8bd5\u6a21\u5757",
            "precondition": "\u8d26\u53f7\u5df2\u767b\u5f55\uff0c\u6d4f\u89c8\u5668\u7f51\u7edc\u6b63\u5e38\uff0c\u7528\u6237\u5177\u5907\u524d\u7f6e\u914d\u7f6e\u9875\u8bbf\u95ee\u6743\u9650",
            "steps": [
                {"step": 1, "action": "\u5bfc\u822a\u5230\u524d\u7f6e\u914d\u7f6e\u9875", "expected_result": "\u524d\u7f6e\u914d\u7f6e\u9875\u6807\u9898\u548c\u4e3b\u8868\u5355\u533a\u57df\u53ef\u89c1", "action_type": "navigate"},
                {"step": 2, "action": "\u67e5\u770b\u524d\u7f6e\u914d\u7f6e\u8868\u5355\u5185\u5bb9", "expected_result": "\u8868\u5355\u663e\u793a\u5df2\u52a0\u8f7d\u7684\u7528\u6237\u914d\u7f6e\u5b57\u6bb5", "action_type": "verify"},
            ],
            "expected_result": "\u9875\u9762\u5c55\u793a\u5b8c\u6574\u7684\u524d\u7f6e\u914d\u7f6e\u8868\u5355\uff0c\u5e76\u4fdd\u6301\u53ef\u67e5\u770b\u72b6\u6001", "priority": "P2",
            "case_type": "manual", "test_category": "manual",
            "case_category": "positive",
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
            "title": "\u5df2\u767b\u5f55\u7528\u6237\u6253\u5f00\u5f02\u5e38\u5904\u7406\u9875\u5e76\u67e5\u770b\u72b6\u6001", "module": "\u6d4b\u8bd5\u6a21\u5757",
            "precondition": "\u8d26\u53f7\u5df2\u767b\u5f55\uff0c\u6d4f\u89c8\u5668\u7f51\u7edc\u6b63\u5e38\uff0c\u7528\u6237\u5177\u5907\u5f02\u5e38\u5904\u7406\u9875\u8bbf\u95ee\u6743\u9650",
            "steps": [
                {"step": 1, "action": "\u5bfc\u822a\u5230\u5f02\u5e38\u5904\u7406\u9875", "expected_result": "\u5f02\u5e38\u5904\u7406\u9875\u6807\u9898\u548c\u72b6\u6001\u5217\u8868\u53ef\u89c1", "action_type": "navigate"},
                {"step": 2, "action": "\u67e5\u770b\u5f02\u5e38\u72b6\u6001\u5217\u8868", "expected_result": "\u5217\u8868\u663e\u793a\u5f02\u5e38\u7c7b\u578b\u548c\u5904\u7406\u72b6\u6001\u5b57\u6bb5", "action_type": "verify"},
            ],
            "expected_result": "\u9875\u9762\u5c55\u793a\u5f02\u5e38\u5904\u7406\u72b6\u6001\u5217\u8868\uff0c\u5e76\u4fdd\u6301\u53ef\u67e5\u770b\u72b6\u6001", "priority": "P2",
            "case_type": "manual", "test_category": "manual",
            "case_category": "positive",
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
