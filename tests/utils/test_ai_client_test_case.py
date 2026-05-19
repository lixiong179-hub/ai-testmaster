import pytest
import json
from unittest.mock import patch, MagicMock

from app.utils.ai_client_test_case import AITestCaseMixin
from app.utils.ai_client_core import (
    AIClientBase,
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
)


class _TestClient(AITestCaseMixin, AIClientBase):
    pass


@pytest.fixture
def client():
    return _TestClient()


def _mock_response(content: str, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests import HTTPError
        mock_resp.raise_for_status.side_effect = HTTPError(f"{status_code} Error")
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return mock_resp


class TestAnalyzeRequirements:

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_success(self, mock_post, client):
        test_points = [
            {"module": "用户管理", "function": "登录", "point": "验证登录", "priority": 1}
        ]
        mock_post.return_value = _mock_response(json.dumps(test_points))
        result = client.analyze_requirements("需求内容")
        assert len(result) == 1
        assert result[0]["module"] == "用户管理"

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_with_surrounding_text(self, mock_post, client):
        test_points = [
            {"module": "M1", "function": "F1", "point": "P1", "priority": 2}
        ]
        content = f"以下是分析结果：\n{json.dumps(test_points)}\n以上是测试点。"
        mock_post.return_value = _mock_response(content)
        result = client.analyze_requirements("需求内容")
        assert len(result) == 1

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_invalid_json_returns_empty(self, mock_post, client):
        mock_post.return_value = _mock_response("这不是JSON格式的内容")
        result = client.analyze_requirements("需求内容")
        assert result == []

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_cache_hit(self, mock_post, client):
        test_points = [{"module": "M", "function": "F", "point": "P", "priority": 1}]
        mock_post.return_value = _mock_response(json.dumps(test_points))
        result1 = client.analyze_requirements("缓存测试内容")
        assert len(result1) == 1
        result2 = client.analyze_requirements("缓存测试内容")
        assert len(result2) == 1
        assert mock_post.call_count == 1

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_request_exception_retries(self, mock_post, client):
        from requests import RequestException
        mock_post.side_effect = RequestException("Connection error")
        client.max_retries = 1
        with pytest.raises(AIServiceError):
            client.analyze_requirements("异常测试")

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_auth_error(self, mock_post, client):
        from requests import HTTPError
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = HTTPError("401 Unauthorized")
        mock_post.return_value = mock_resp
        client.max_retries = 1
        with pytest.raises(AIServiceError):
            client.analyze_requirements("认证失败测试")

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_analyze_requirements_rate_limit(self, mock_post, client):
        from requests import HTTPError
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = HTTPError("429 rate limit")
        mock_post.return_value = mock_resp
        client.max_retries = 1
        with pytest.raises(AIServiceError):
            client.analyze_requirements("限流测试")


class TestGenerateTestCase:

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_success(self, mock_post, client):
        case_data = {
            "title": "登录验证",
            "precondition": "账号已登录",
            "steps": [
                {"step": 1, "action": "输入用户名", "action_type": "input",
                 "input_value": "admin", "target_element": "用户名输入框",
                 "expected_result": "用户名输入成功"}
            ],
            "expected_results": ["用户名输入成功"],
            "case_type": "ui_automation",
            "test_category": "ui_automation"
        }
        mock_post.return_value = _mock_response(json.dumps(case_data))
        test_point = {"module": "用户管理", "function": "登录", "point": "验证登录", "priority": 1}
        result = client.generate_test_case(test_point)
        assert result["title"] == "登录验证"

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_with_context_in_json(self, mock_post, client):
        case_data = {
            "title": "边界值测试",
            "precondition": "系统可用",
            "steps": [
                {"step": 1, "action": "输入最大值", "action_type": "input",
                 "input_value": "999", "target_element": "输入框",
                 "expected_result": "接受输入"}
            ],
            "expected_result": "接受输入"
        }
        mock_post.return_value = _mock_response(json.dumps(case_data))
        test_point = {"module": "M", "function": "F", "point": "P", "priority": 2}
        result = client.generate_test_case(test_point)
        assert "title" in result

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_cache_hit(self, mock_post, client):
        case_data = {
            "title": "缓存用例",
            "precondition": "前置",
            "steps": [{"step": 1, "action": "操作", "action_type": "click",
                       "input_value": "", "target_element": "按钮",
                       "expected_result": "成功"}],
            "expected_result": "成功"
        }
        mock_post.return_value = _mock_response(json.dumps(case_data))
        test_point = {"module": "M", "function": "F", "point": "缓存测试", "priority": 1}
        result1 = client.generate_test_case(test_point)
        result2 = client.generate_test_case(test_point)
        assert mock_post.call_count == 1

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_missing_fields_raises(self, mock_post, client):
        invalid_case = {"title": "缺少字段"}
        mock_post.return_value = _mock_response(json.dumps(invalid_case))
        client.max_retries = 1
        test_point = {"module": "M", "function": "F", "point": "P", "priority": 1}
        with pytest.raises(AIResponseFormatError):
            client.generate_test_case(test_point)

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_unparseable_raises(self, mock_post, client):
        mock_post.return_value = _mock_response("not json at all")
        client.max_retries = 1
        test_point = {"module": "M", "function": "F", "point": "P", "priority": 1}
        with pytest.raises(AIResponseParseError):
            client.generate_test_case(test_point)

    @patch("app.utils.ai_client_test_case.requests.post")
    def test_generate_test_case_request_exception(self, mock_post, client):
        from requests import RequestException
        mock_post.side_effect = RequestException("timeout")
        client.max_retries = 1
        test_point = {"module": "M", "function": "F", "point": "P", "priority": 1}
        with pytest.raises(AIServiceError):
            client.generate_test_case(test_point)


class TestParseGenerateResponse:

    def test_parse_valid_json_dict(self, client):
        content = json.dumps({
            "title": "T", "precondition": "P",
            "steps": [{"step": 1, "action": "A", "action_type": "click",
                       "input_value": "", "target_element": "E",
                       "expected_result": "R"}],
            "expected_result": "R"
        })
        result = client._parse_generate_response(content)
        assert result["title"] == "T"

    def test_parse_json_with_surrounding_text(self, client):
        case_data = {
            "title": "T", "precondition": "P",
            "steps": [{"step": 1, "action": "A", "action_type": "click",
                       "input_value": "", "target_element": "E",
                       "expected_result": "R"}],
            "expected_result": "R"
        }
        content = f"```json\n{json.dumps(case_data)}\n```"
        result = client._parse_generate_response(content)
        assert result["title"] == "T"

    def test_parse_invalid_json_raises(self, client):
        with pytest.raises(AIResponseParseError):
            client._parse_generate_response("not json")

    def test_parse_empty_string_raises(self, client):
        with pytest.raises(AIResponseParseError):
            client._parse_generate_response("")


class TestValidateAndNormalizeCase:

    def test_missing_required_fields_raises(self, client):
        with pytest.raises(AIResponseFormatError):
            client._validate_and_normalize_case({"title": "only title"})

    def test_new_format_normalized(self, client):
        case = {
            "title": "T", "precondition": "P",
            "steps": [{"step": 1, "action": "A", "action_type": "click",
                       "input_value": "", "target_element": "E",
                       "expected_result": "R"}],
            "expected_results": ["R"],
            "case_type": "ui_automation"
        }
        result = client._validate_and_normalize_case(case)
        assert "steps" in result

    def test_old_format_normalized(self, client):
        case = {
            "title": "T", "precondition": "P",
            "steps": [{"step": 1, "action": "A", "action_type": "click",
                       "input_value": "", "target_element": "E",
                       "expected_result": "R"}],
            "case_type": "ui_automation"
        }
        result = client._validate_and_normalize_case(case)
        assert "steps" in result

    def test_missing_precondition_raises(self, client):
        with pytest.raises(AIResponseFormatError):
            client._validate_and_normalize_case({"title": "T", "steps": []})

    def test_missing_steps_raises(self, client):
        with pytest.raises(AIResponseFormatError):
            client._validate_and_normalize_case({"title": "T", "precondition": "P"})
