import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.test_case_generation.base_mixin import (
    TestCaseGenerationBaseMixin,
    _warning,
)


class TestCompletenessScore:
    def setup_method(self):
        self.db = MagicMock()
        self.mixin = TestCaseGenerationBaseMixin(self.db)
        self.project_mock = MagicMock()
        self.project_mock.project_type = "web"
        self.db.query.return_value.filter.return_value.first.return_value = self.project_mock

    def test_full_context_scores_100(self):
        context = {
            "test_points": [{"point": "登录验证", "module": "登录模块", "priority": 1, "requirement_id": 1}],
            "requirement_content": "用户可点击新增按钮添加成员",
            "ui_specs": [{"screen_id": 1, "screen_name": "登录页", "ui_spec": {"elements": []}}],
            "ui_descriptions": [{"screen_id": 1, "parse_status": "completed"}],
            "context_stats": {"history_cases_used": 3},
        }
        result = self.mixin._compute_completeness_score(context, project_id=1)
        assert result["score"] == 100
        assert result["missing_core_context"] == []
        assert result["low_confidence_reasons"] == []

    def test_no_requirement_scores_lower(self):
        context = {
            "test_points": [{"point": "登录验证", "module": "登录模块", "priority": 1}],
            "requirement_content": "",
            "ui_specs": [{"screen_id": 1, "ui_spec": {"elements": []}}],
            "ui_descriptions": [{"parse_status": "completed"}],
            "context_stats": {"history_cases_used": 0},
        }
        result = self.mixin._compute_completeness_score(context, project_id=1)
        assert result["score"] < 100
        assert "requirement" in result["missing_core_context"]
        assert "REQUIREMENT_NOT_FOUND" in result["low_confidence_reasons"]

    def test_no_ui_web_project_deducts(self):
        context = {
            "test_points": [{"point": "登录验证", "module": "登录模块", "priority": 1}],
            "requirement_content": "需求描述",
            "ui_specs": [],
            "ui_descriptions": [],
            "context_stats": {"history_cases_used": 0},
        }
        result = self.mixin._compute_completeness_score(context, project_id=1)
        assert "ui" in result["missing_core_context"]
        assert "UI_NO_MATCH" in result["low_confidence_reasons"]

    def test_no_ui_api_project_redistributes(self):
        self.project_mock.project_type = "api"
        context = {
            "test_points": [{"point": "接口验证", "module": "API模块", "priority": 1}],
            "requirement_content": "API需求描述",
            "ui_specs": [],
            "ui_descriptions": [],
            "context_stats": {"history_cases_used": 0},
        }
        result = self.mixin._compute_completeness_score(context, project_id=1)
        assert "ui" not in result["missing_core_context"]
        assert result["score"] > 55

    def test_no_test_point(self):
        context = {
            "test_points": [],
            "requirement_content": "需求描述",
            "ui_specs": [{"ui_spec": {"elements": []}}],
            "ui_descriptions": [{"parse_status": "completed"}],
            "context_stats": {"history_cases_used": 0},
        }
        result = self.mixin._compute_completeness_score(context, project_id=1)
        assert "test_point" in result["missing_core_context"]

    def test_low_score_triggers_warning(self):
        context = {
            "requirement_content": "",
            "test_points": [],
            "ui_specs": [],
            "ui_descriptions": [],
            "context_stats": {},
        }
        result = self.mixin._compute_completeness_score(context, project_id=1)
        assert result["score"] < 50


class TestBuildPriorityRules:
    def test_full_context(self):
        from app.utils.ai_client_enhanced._enhanced import _build_priority_rules
        rules = _build_priority_rules(has_ui=True, has_requirement=True, has_test_point=True)
        assert "信息优先级" in rules
        assert "当前测试点 > 关联需求文档" in rules
        assert "缺少需求文档" not in rules
        assert "缺少UI原型图" not in rules

    def test_no_requirement(self):
        from app.utils.ai_client_enhanced._enhanced import _build_priority_rules
        rules = _build_priority_rules(has_ui=True, has_requirement=False, has_test_point=True)
        assert "缺少需求文档" in rules
        assert "不得升级为业务事实来源" in rules

    def test_no_ui(self):
        from app.utils.ai_client_enhanced._enhanced import _build_priority_rules
        rules = _build_priority_rules(has_ui=False, has_requirement=True, has_test_point=True)
        assert "缺少UI原型图" in rules
        assert "待确认UI" in rules

    def test_no_test_point(self):
        from app.utils.ai_client_enhanced._enhanced import _build_priority_rules
        rules = _build_priority_rules(has_ui=True, has_requirement=True, has_test_point=False)
        assert "缺少测试点" in rules

    def test_hard_constraints_present(self):
        from app.utils.ai_client_enhanced._enhanced import _build_priority_rules
        rules = _build_priority_rules(has_ui=True, has_requirement=True, has_test_point=True)
        assert "硬约束" in rules
        assert "二级提示策略" in rules


class TestAssessHistoryTrust:
    def test_high_trust_fresh_case(self):
        from app.api.v1.endpoints.test_case_ai_generate._context import _assess_history_trust
        case = MagicMock()
        case.test_point_id = None
        case.update_time = datetime.now(timezone.utc)
        case.summary = "摘要"
        case.summary_version = 1
        trust, reason = _assess_history_trust(case, set(), set(), MagicMock())
        assert trust == "high"
        assert reason == ""

    def test_low_trust_requirement_mismatch(self):
        from app.api.v1.endpoints.test_case_ai_generate._context import _assess_history_trust
        db_mock = MagicMock()
        tp_mock = MagicMock()
        tp_mock.requirement_id = 999
        db_mock.query.return_value.filter.return_value.first.return_value = tp_mock
        case = MagicMock()
        case.test_point_id = 1
        case.update_time = datetime.now(timezone.utc)
        case.summary = "摘要"
        case.summary_version = 1
        trust, reason = _assess_history_trust(case, {1, 2, 3}, set(), db_mock)
        assert trust == "low"
        assert reason == "HISTORY_REQUIREMENT_MISMATCH"

    def test_medium_trust_stale_case(self):
        from app.api.v1.endpoints.test_case_ai_generate._context import _assess_history_trust
        db_mock = MagicMock()
        tp_mock = MagicMock()
        tp_mock.requirement_id = 1
        req_mock = MagicMock()
        req_mock.update_time = datetime.now(timezone.utc)
        case = MagicMock()
        case.test_point_id = 1
        case.update_time = datetime.now(timezone.utc) - timedelta(days=100)
        case.summary = "摘要"
        case.summary_version = 1

        def query_side_effect(model):
            result = MagicMock()
            result.filter.return_value.first.return_value = tp_mock if model.__name__ == 'TestPoint' else req_mock
            return result

        db_mock.query.side_effect = query_side_effect
        trust, reason = _assess_history_trust(case, {1}, set(), db_mock)
        assert trust == "medium"
        assert "HISTORY_POTENTIALLY_STALE" in reason

    def test_medium_trust_no_summary(self):
        from app.api.v1.endpoints.test_case_ai_generate._context import _assess_history_trust
        case = MagicMock()
        case.test_point_id = None
        case.update_time = datetime.now(timezone.utc)
        case.summary = None
        case.summary_version = 0
        trust, reason = _assess_history_trust(case, set(), set(), MagicMock())
        assert trust == "medium"
        assert "summary_missing" in reason


class TestSummarizeHistoryCaseWithTrust:
    def test_includes_trust_fields(self):
        from app.api.v1.endpoints.test_case_ai_generate._context import _summarize_history_case
        case = MagicMock()
        case.id = 1
        case.case_no = "TC-001"
        case.module = "登录"
        case.title = "登录验证"
        case.summary = "摘要"
        case.expected_result = "预期"
        case.steps_json = []
        result = _summarize_history_case(case, similarity=0.85, trust_level="high", staleness_reason="")
        assert result["trust_level"] == "high"
        assert result["staleness_reason"] == ""
        assert result["similarity"] == 0.85

    def test_low_trust_fields(self):
        from app.api.v1.endpoints.test_case_ai_generate._context import _summarize_history_case
        case = MagicMock()
        case.id = 2
        case.case_no = "TC-002"
        case.module = "注册"
        case.title = "注册验证"
        case.summary = ""
        case.expected_result = ""
        case.steps_json = []
        result = _summarize_history_case(
            case, similarity=0.5, trust_level="low", staleness_reason="HISTORY_REQUIREMENT_MISMATCH"
        )
        assert result["trust_level"] == "low"
        assert result["staleness_reason"] == "HISTORY_REQUIREMENT_MISMATCH"


class TestCaseRefreshSuggestionModel:
    def test_model_fields(self):
        from app.models.case_refresh_suggestion import CaseRefreshSuggestion
        suggestion = CaseRefreshSuggestion(
            case_id=1,
            trigger_reason="stale",
            suggestion_status="pending",
            review_status="pending",
        )
        assert suggestion.case_id == 1
        assert suggestion.trigger_reason == "stale"
        assert suggestion.suggestion_status == "pending"
        assert suggestion.review_status == "pending"
        assert suggestion.retry_count == 0

    def test_model_with_ai_result(self):
        from app.models.case_refresh_suggestion import CaseRefreshSuggestion
        suggestion = CaseRefreshSuggestion(
            case_id=1,
            requirement_id=10,
            trigger_reason="requirement_changed",
            suggested_title="新标题",
            suggested_steps=[{"step": "1", "action": "点击"}],
            suggested_expected_result="新预期",
            diff_description="标题和步骤变更",
            model_version="deepseek-v3",
        )
        assert suggestion.suggested_title == "新标题"
        assert suggestion.diff_description == "标题和步骤变更"
        assert suggestion.model_version == "deepseek-v3"


class TestCaseRefreshService:
    def setup_method(self):
        self.db = MagicMock()

    def test_create_suggestion(self):
        from app.services.case_refresh_service import CaseRefreshService
        service = CaseRefreshService(self.db)
        ai_result = {
            "is_valid": True,
            "suggested_title": "新标题",
            "suggested_steps": [{"step": "1", "action": "点击"}],
            "suggested_expected_result": "新预期",
            "diff_description": "步骤变更",
            "deprecation_reason": "",
        }
        suggestion = service.create_suggestion(
            case_id=1,
            trigger_reason="stale",
            requirement_id=10,
            ai_result=ai_result,
            model_version="v3",
        )
        assert suggestion.case_id == 1
        assert suggestion.suggested_title == "新标题"
        self.db.add.assert_called_once()

    def test_build_refresh_prompt(self):
        from app.services.case_refresh_service import CaseRefreshService
        service = CaseRefreshService(self.db)
        case = MagicMock()
        case.title = "登录验证"
        case.steps_json = [{"step": "1", "action": "点击登录"}]
        case.expected_result = "登录成功"
        requirement = MagicMock()
        requirement.description = "用户可登录系统"
        prompt = service.build_refresh_prompt(case, requirement)
        assert "登录验证" in prompt
        assert "用户可登录系统" in prompt
        assert "是否仍然有效" in prompt

    def test_parse_refresh_response_valid_json(self):
        from app.services.case_refresh_service import CaseRefreshService
        service = CaseRefreshService(self.db)
        response = '{"is_valid": true, "suggested_title": "新标题", "diff_description": "变更"}'
        result = service.parse_refresh_response(response)
        assert result["is_valid"] is True
        assert result["suggested_title"] == "新标题"

    def test_parse_refresh_response_with_code_block(self):
        from app.services.case_refresh_service import CaseRefreshService
        service = CaseRefreshService(self.db)
        response = '```json\n{"is_valid": false, "deprecation_reason": "需求已删除"}\n```'
        result = service.parse_refresh_response(response)
        assert result["is_valid"] is False
        assert result["deprecation_reason"] == "需求已删除"

    def test_parse_refresh_response_invalid(self):
        from app.services.case_refresh_service import CaseRefreshService
        service = CaseRefreshService(self.db)
        result = service.parse_refresh_response("not json at all")
        assert "AI响应解析失败" in result["diff_description"]
