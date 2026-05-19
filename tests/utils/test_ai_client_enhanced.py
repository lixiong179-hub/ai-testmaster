import pytest
import json
from unittest.mock import patch, MagicMock

from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced
from app.utils.ai_client_enhanced._repair import _repair_truncated_json
from app.utils.ai_client_core import AIServiceError, AIResponseParseError


class TestRepairTruncatedJson:

    def test_already_valid_json(self):
        result = _repair_truncated_json('{"key": "value"}')
        assert result is None

    def test_valid_array(self):
        result = _repair_truncated_json('[{"a": 1}]')
        assert result is None

    def test_empty_string(self):
        result = _repair_truncated_json("")
        assert result is None

    def test_too_short(self):
        result = _repair_truncated_json("abc")
        assert result is None

    def test_truncated_object_no_closing_brace(self):
        truncated = '{"a": 1,'
        result = _repair_truncated_json(truncated)
        assert result is None

    def test_truncated_array(self):
        truncated = '[{"title": "T1"}, {"title": "T2"'
        result = _repair_truncated_json(truncated)
        assert result is not None
        parsed = json.loads(result)
        assert len(parsed) >= 1

    def test_truncated_string_value(self):
        truncated = '{"title": "未完成的字符'
        result = _repair_truncated_json(truncated)
        assert result is not None
        parsed = json.loads(result)
        assert "title" in parsed

    def test_trailing_comma_with_closing_brace(self):
        truncated = '{"a": 1, "b": 2,'
        result = _repair_truncated_json(truncated)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["a"] == 1
        assert parsed["b"] == 2

    def test_deeply_nested_truncation(self):
        truncated = '{"a": {"b": {"c": 1'
        result = _repair_truncated_json(truncated)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["a"]["b"]["c"] == 1

    def test_unrepairable_returns_none(self):
        truncated = "}}}random text{{{"
        result = _repair_truncated_json(truncated)
        assert result is None


class TestGenerateTestCaseEnhanced:

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_graph_prompt_mode(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"title": "图模式用例", "precondition": "P", "steps": [],
             "case_type": "ui_automation", "priority": "P0",
             "expected_result": "R", "test_data": {},
             "change_type": "added", "parent_case_id": None, "case_category": "positive"}
        ])
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", return_value=(True, [])), \
             patch("app.utils.ai_client_enhanced._enhanced.compute_quality_score", return_value=85.0):
            context = {"graph_prompt": "图模式提示词"}
            result = generate_test_case_enhanced(context)
            assert len(result) >= 1

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_normal_mode_with_requirement(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"title": "正常用例", "precondition": "P", "steps": [],
             "case_type": "ui_automation", "priority": "P0",
             "expected_result": "R", "test_data": {},
             "change_type": "added", "parent_case_id": None, "case_category": "positive"}
        ])
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", return_value=(True, [])), \
             patch("app.utils.ai_client_enhanced._enhanced.compute_quality_score", return_value=90.0):
            context = {"requirement": "需求文档", "test_points": [], "ui_specs": [], "project_config": {}}
            result = generate_test_case_enhanced(context)
            assert len(result) >= 1

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_case_type_constraint(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"title": "API用例", "precondition": "P", "steps": [],
             "case_type": "api_automation", "priority": "P0",
             "expected_result": "R", "test_data": {},
             "change_type": "added", "parent_case_id": None, "case_category": "positive"}
        ])
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", return_value=(True, [])), \
             patch("app.utils.ai_client_enhanced._enhanced.compute_quality_score", return_value=88.0):
            context = {"requirement": "R", "test_points": [], "ui_specs": [],
                       "project_config": {}, "case_type": "api_automation"}
            result = generate_test_case_enhanced(context)
            assert len(result) >= 1

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_empty_response_raises(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with pytest.raises(AIResponseParseError):
            context = {"graph_prompt": "test"}
            generate_test_case_enhanced(context)

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_code_block_extraction(self, mock_get_client):
        case_json = json.dumps([
            {"title": "代码块用例", "precondition": "P", "steps": [],
             "case_type": "ui_automation", "priority": "P0",
             "expected_result": "R", "test_data": {},
             "change_type": "added", "parent_case_id": None, "case_category": "positive"}
        ])
        content = f"```json\n{case_json}\n```"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = content
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", return_value=(True, [])), \
             patch("app.utils.ai_client_enhanced._enhanced.compute_quality_score", return_value=90.0):
            context = {"graph_prompt": "test"}
            result = generate_test_case_enhanced(context)
            assert len(result) >= 1

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_quality_below_threshold_retries(self, mock_get_client):
        mock_client = MagicMock()
        mock_response_good = MagicMock()
        mock_response_good.choices = [MagicMock()]
        mock_response_good.choices[0].message.content = json.dumps([
            {"title": "好用例", "precondition": "P", "steps": [],
             "case_type": "ui_automation", "priority": "P0",
             "expected_result": "R", "test_data": {},
             "change_type": "added", "parent_case_id": None, "case_category": "positive"}
        ])
        mock_client.chat.completions.create.return_value = mock_response_good
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        call_count = [0]
        def mock_validate(cases, min_count=1):
            call_count[0] += 1
            if call_count[0] == 1:
                return (False, ["缺少边界用例"])
            return (True, [])

        with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", side_effect=mock_validate), \
             patch("app.utils.ai_client_enhanced._enhanced.compute_quality_score", return_value=60.0), \
             patch("app.utils.ai_client_enhanced._enhanced.time.sleep"):
            context = {"graph_prompt": "test"}
            result = generate_test_case_enhanced(context)
            assert len(result) >= 1

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_history_cases_included(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"title": "评审用例", "precondition": "P", "steps": [],
             "case_type": "ui_automation", "priority": "P0",
             "expected_result": "R", "test_data": {},
             "change_type": "modified", "parent_case_id": 1, "case_category": "positive"}
        ])
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", return_value=(True, [])), \
             patch("app.utils.ai_client_enhanced._enhanced.compute_quality_score", return_value=90.0):
            context = {
                "requirement": "R", "test_points": [], "ui_specs": [],
                "project_config": {},
                "history_cases": [{"id": 1, "title": "旧用例", "module": "M"}]
            }
            result = generate_test_case_enhanced(context)
            assert len(result) >= 1

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_exception_raises_service_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with pytest.raises(AIServiceError):
            context = {"graph_prompt": "test"}
            generate_test_case_enhanced(context)

    @patch("app.utils.ai_client_enhanced._enhanced.get_ai_client")
    def test_new_format_normalization(self, mock_get_client):
        case_with_expected_results = {
            "title": "新格式用例",
            "precondition": "P",
            "steps": [{"step": "1", "action": "A", "action_type": "click",
                        "input_value": "", "target_element": "E",
                        "expected_result": "R"}],
            "expected_results": ["R"],
            "case_type": "ui_automation",
            "priority": "P0",
            "test_data": {},
            "change_type": "added",
            "parent_case_id": None,
            "case_category": "positive"
        }
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([case_with_expected_results])
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.model_name = "test-model"
        mock_get_client.return_value = mock_client

        with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", return_value=(True, [])), \
             patch("app.utils.ai_client_enhanced._enhanced.compute_quality_score", return_value=90.0):
            context = {"graph_prompt": "test"}
            result = generate_test_case_enhanced(context)
            assert len(result) >= 1
