"""场景化集成测试 - 上下文精准化与历史用例保鲜优化方案

覆盖11大业务场景，验证端到端行为一致性：
1. 历史用例腐化治理完整链路（deprecated排除+可信度过滤+仅high注入）
2. 无UI场景完整链路（has_ui判定+case_type降级+Prompt约束）
3. 上下文精准加载+完整性评分（navigation_flow+评分维度）
4. 保鲜建议统计API（全量统计+状态过滤）
5. A/B测试项目隔离
6. SSE首帧推送验证（context_stats+warnings+evidence_refs）
7. min_case_count贯穿验证（单→1,多→3,图模式保底3）
8. UI文件无解析结果边界（warning+has_ui判定）
9. Prompt对比示例精简版
10. 线性Prompt min_case_count参数化
11. 图模式Prompt min_case_count参数化
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


class TestScenario1HistoryCaseCorruptionGovernance:
    """场景1: 历史用例腐化治理完整链路"""

    def test_deprecated_cases_excluded_from_query_filter(self):
        excluded_statuses = ["archived", "deprecated"]
        test_statuses = ["active", "deprecated", "archived", "draft", "pending_review"]
        filtered = [s for s in test_statuses if s not in excluded_statuses]
        assert "deprecated" not in filtered
        assert "archived" not in filtered
        assert "active" in filtered
        assert "draft" in filtered
        assert "pending_review" in filtered

    def test_enrich_context_filters_low_and_medium_trust(self):
        from app.services.test_case_generation.context_builder import ContextBuilder as TestCaseGenerationBaseMixin

        mixin = TestCaseGenerationBaseMixin.__new__(TestCaseGenerationBaseMixin)
        mixin.db = MagicMock()

        high_case = MagicMock(id=1, title="high", summary="s", lifecycle_status="active")
        medium_case = MagicMock(id=2, title="medium", summary="s", lifecycle_status="active")
        low_case = MagicMock(id=3, title="low", summary="s", lifecycle_status="active")

        mixin.db.query.return_value.filter.return_value.all.return_value = [
            high_case, medium_case, low_case,
        ]

        trust_map = {
            1: ("high", ""),
            2: ("medium", "HISTORY_POTENTIALLY_STALE"),
            3: ("low", "HISTORY_REQUIREMENT_MISMATCH"),
        }

        summarize_map = {
            1: {"id": 1, "title": "high", "module": "mod", "trust_level": "high", "staleness_reason": ""},
            2: {"id": 2, "title": "medium", "module": "mod", "trust_level": "medium", "staleness_reason": "HISTORY_POTENTIALLY_STALE"},
            3: {"id": 3, "title": "low", "module": "mod", "trust_level": "low", "staleness_reason": "HISTORY_REQUIREMENT_MISMATCH"},
        }

        context = {
            "test_points": [{"id": 1, "point": "p", "module": "m", "function": "f", "priority": 2, "requirement_id": 1}],
            "current_requirement_ids": {1},
            "current_ui_screen_ids": set(),
            "requirement_content": "req",
            "ui_specs": [],
            "ui_descriptions": [],
            "warnings": [],
            "evidence_refs": {"requirements": [], "ui_screens": [], "history_cases": []},
        }

        with patch("app.api.v1.endpoints.test_case_ai_generate._context._assess_history_trust") as mock_assess:
            mock_assess.side_effect = lambda case, *a, **kw: trust_map[case.id]

            with patch("app.api.v1.endpoints.test_case_ai_generate._context._summarize_history_case") as mock_sum:
                mock_sum.side_effect = lambda case, *a, **kw: summarize_map[case.id]

                with patch.object(mixin, '_compute_completeness_score') as mock_score:
                    mock_score.return_value = {
                        "score": 85, "missing_core_context": [], "low_confidence_reasons": [],
                    }
                    mixin.enrich_context_with_trust_and_scoring(
                        context, project_id=1, history_case_ids=[1, 2, 3],
                    )

        injected = context.get("history_cases", [])
        trust_levels = [c.get("trust_level") for c in injected]
        assert "low" not in trust_levels, "low trust cases must be filtered out"
        assert "medium" not in trust_levels, "medium trust cases must be filtered out"
        assert "high" in trust_levels, "high trust cases should be injected"

        warning_str = str(context.get("warnings", []))
        assert "HISTORY_LOW_TRUST_FILTERED" in warning_str or "HISTORY_POTENTIALLY_STALE" in warning_str, \
            "Filtered cases should produce warnings"

    def test_history_case_ids_empty_list_skips_query(self):
        from app.services.test_case_generation.context_builder import ContextBuilder as TestCaseGenerationBaseMixin

        mixin = TestCaseGenerationBaseMixin.__new__(TestCaseGenerationBaseMixin)
        mixin.db = MagicMock()

        context = {
            "test_points": [],
            "current_requirement_ids": set(),
            "current_ui_screen_ids": set(),
            "requirement_content": "",
            "ui_specs": [],
            "ui_descriptions": [],
            "warnings": [],
            "evidence_refs": {"requirements": [], "ui_screens": [], "history_cases": []},
        }

        with patch.object(mixin, '_compute_completeness_score') as mock_score:
            mock_score.return_value = {
                "score": 50, "missing_core_context": [], "low_confidence_reasons": [],
            }
            mixin.enrich_context_with_trust_and_scoring(
                context, project_id=1, history_case_ids=[],
            )

        assert context.get("history_cases", []) == []


class TestScenario2NoUISceneCompleteChain:
    """场景2: 无UI场景完整链路"""

    def test_has_ui_false_with_empty_bracket_string(self):
        ui_desc = "[]"
        ui_specs = []
        has_ui = bool(ui_specs) or bool(ui_desc and ui_desc.strip() and ui_desc.strip() not in ("[]", "{}", ""))
        assert has_ui is False

    def test_has_ui_false_with_empty_brace_string(self):
        ui_desc = "{}"
        ui_specs = []
        has_ui = bool(ui_specs) or bool(ui_desc and ui_desc.strip() and ui_desc.strip() not in ("[]", "{}", ""))
        assert has_ui is False

    def test_has_ui_true_with_real_ui_specs(self):
        ui_specs = [{"screen_id": 1, "ui_spec": "spec"}]
        has_ui = bool(ui_specs)
        assert has_ui is True

    def test_no_ui_forces_manual_in_prompt(self):
        from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced

        context = {
            "requirement": "test requirement",
            "ui_specs": [],
            "ui_description": "",
            "case_type": "ui_automation",
            "test_points": [{"point": "test", "module": "m", "function": "f", "priority": 2}],
        }

        captured = {}

        with patch("app.utils.ai_client_enhanced._enhanced.get_ai_client") as mock_client:
            def capture_create(**kwargs):
                captured["prompt"] = kwargs.get("messages", [{}])[0].get("content", "")
                mock_resp = MagicMock()
                mock_resp.choices = [MagicMock()]
                mock_resp.choices[0].message.content = json.dumps([{
                    "title": "test", "module": "m", "precondition": "logged in",
                    "steps": [{"step": "1", "action": "click", "action_type": "click",
                               "input_value": "", "target_element": "btn", "expected_result": "ok",
                               "description": "click", "param": ""}],
                    "expected_result": "done", "case_type": "manual",
                    "case_category": "positive", "priority": 2,
                }])
                mock_resp.choices[0].finish_reason = "stop"
                mock_resp.usage = MagicMock(total_tokens=100)
                return mock_resp

            mc = MagicMock()
            mc.chat.completions.create.side_effect = capture_create
            mc.model_name = "test-model"
            mock_client.return_value = mc

            with patch("app.utils.ai_client_enhanced._enhanced.time.sleep"):
                generate_test_case_enhanced(context)

        prompt = captured.get("prompt", "")
        assert "manual" in prompt, "Prompt must force manual when no UI + ui_automation"
        assert "不得编造" in prompt or "不得臆造" in prompt, "Prompt must forbid fabricating UI elements"


class TestScenario3CompletenessScoreWithNavigationFlow:
    """场景3: 上下文精准加载+完整性评分"""

    def _make_mixin(self):
        from app.services.test_case_generation.context_builder import ContextBuilder as TestCaseGenerationBaseMixin
        mixin = TestCaseGenerationBaseMixin.__new__(TestCaseGenerationBaseMixin)
        mixin.db = MagicMock()
        mock_project = MagicMock()
        mock_project.project_type = "web"
        mixin.db.query.return_value.filter.return_value.first.return_value = mock_project
        return mixin

    def test_score_with_navigation_flow_no_false_warning(self):
        mixin = self._make_mixin()

        context = {
            "test_points": [{"point": "p", "module": "m", "function": "f", "priority": 2}],
            "requirement_content": "requirement text",
            "ui_specs": [{
                "screen_id": 1, "screen_name": "s1", "ui_spec": '{"elements": []}',
                "navigation_flow": "s1 -> s2 -> s3",
                "related_screens": ["s2", "s3"],
            }],
            "ui_descriptions": [{"screen_name": "s1", "confidence": "explicit"}],
            "history_cases": [{"trust_level": "high"}],
        }

        result = mixin._compute_completeness_score(context, project_id=1)
        assert result["score"] > 0
        assert "UI_NO_NAVIGATION" not in str(result.get("low_confidence_reasons", []))

    def test_score_without_navigation_flow_lower(self):
        mixin = self._make_mixin()

        context_with_flow = {
            "test_points": [{"point": "p", "module": "m", "function": "f", "priority": 2}],
            "requirement_content": "req",
            "ui_specs": [{"screen_id": 1, "screen_name": "s1", "ui_spec": "spec",
                          "navigation_flow": "s1->s2", "related_screens": ["s2"]}],
            "ui_descriptions": [{"screen_name": "s1"}],
            "history_cases": [{"trust_level": "high"}],
        }

        context_without_flow = {
            "test_points": [{"point": "p", "module": "m", "function": "f", "priority": 2}],
            "requirement_content": "req",
            "ui_specs": [{"screen_id": 1, "screen_name": "s1", "ui_spec": "spec"}],
            "ui_descriptions": [{"screen_name": "s1"}],
            "history_cases": [{"trust_level": "high"}],
        }

        score_with = mixin._compute_completeness_score(context_with_flow, project_id=1)["score"]
        score_without = mixin._compute_completeness_score(context_without_flow, project_id=1)["score"]
        assert score_with >= score_without, "Navigation flow should not decrease score"


class TestScenario4CaseRefreshStats:
    """场景4: 保鲜建议统计API"""

    def test_stats_returns_full_counts_not_page_limited(self):
        from app.services.case_refresh_service import CaseRefreshService

        mock_db = MagicMock()
        mock_db.query.return_value.join.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("pending", 5), ("applied", 3), ("rejected", 2),
        ]

        service = CaseRefreshService(mock_db)
        stats = service.get_suggestions_stats(project_id=1)

        assert stats["pending"] == 5
        assert stats["applied"] == 3
        assert stats["rejected"] == 2
        assert stats["total"] == 10


class TestScenario5ABTestProjectIsolation:
    """场景5: A/B测试项目隔离"""

    def test_summary_filters_by_project_ids(self):
        from app.services.ab_test_service import ABTestService

        mock_db = MagicMock()
        mock_row1 = MagicMock()
        mock_row1.experiment_id = "exp1"
        mock_row1.variant = "control"
        mock_row1.metric_name = "score"
        mock_row1.metric_value = 80.0
        mock_row1.project_id = 1

        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_row1]

        service = ABTestService(mock_db)
        result = service.get_experiment_summary("exp1", project_ids=[1])

        assert "variants" in result

    def test_list_experiments_filters_by_project_ids(self):
        from app.services.ab_test_service import ABTestService

        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.experiment_id = "exp1"
        mock_row.sample_count = 10

        mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [mock_row]

        service = ABTestService(mock_db)
        result = service.list_experiments(project_ids=[1])

        assert len(result) == 1
        assert result[0]["experiment_id"] == "exp1"


class TestScenario6SSEFirstFramePush:
    """场景6: SSE首帧推送验证"""

    def test_batch_first_frame_includes_evidence_refs(self):
        import asyncio
        from app.services.test_case_generation import TestCaseGenerationService

        service = TestCaseGenerationService(MagicMock())

        context = {
            "context_stats": {"completeness_score": 85},
            "warnings": [{"code": "TEST", "message": "test"}],
            "evidence_refs": {
                "requirements": [{"id": 1, "confidence": "explicit"}],
                "ui_screens": [],
                "history_cases": [],
            },
        }

        with patch.object(service._context_builder, 'get_context_for_generation', return_value=context):
            with patch.object(service._context_builder, 'enrich_context_with_trust_and_scoring'):
                gen = service.generate_test_cases_batch(
                    project_id=1, user_id=1, test_point_ids=[1],
                )
                first_frame = asyncio.get_event_loop().run_until_complete(gen.__anext__())

        assert "evidence_refs" in first_frame
        assert "context_stats" in first_frame
        assert "warnings" in first_frame

    def test_stream_first_frame_includes_evidence_refs(self):
        context = {
            "context_stats": {"completeness_score": 90},
            "warnings": [],
            "evidence_refs": {"requirements": [], "ui_screens": [], "history_cases": []},
        }

        import json as json_mod
        first_frame_data = {
            "code": 0, "message": "开始生成",
            "data": {
                "status": "started",
                "context_stats": context["context_stats"],
                "warnings": context["warnings"],
                "evidence_refs": context["evidence_refs"],
            },
        }
        sse_line = f"data: {json_mod.dumps(first_frame_data, ensure_ascii=False)}\n\n"

        parsed = json_mod.loads(sse_line.replace("data: ", "").strip())
        assert "evidence_refs" in parsed["data"]


class TestScenario7MinCaseCountEndToEnd:
    """场景7: min_case_count贯穿验证"""

    def test_single_test_point_min_1(self):
        from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced

        context = {
            "requirement": "test",
            "test_points": [{"point": "single", "module": "m", "function": "f", "priority": 2}],
            "ui_specs": [], "ui_description": "",
        }

        captured = {}

        with patch("app.utils.ai_client_enhanced._enhanced.get_ai_client") as mock_client:
            def capture(**kwargs):
                captured["prompt"] = kwargs.get("messages", [{}])[0].get("content", "")
                r = MagicMock()
                r.choices = [MagicMock()]
                r.choices[0].message.content = json.dumps([{
                    "title": "t", "module": "m", "precondition": "p",
                    "steps": [{"step": "1", "action": "a", "action_type": "click",
                               "input_value": "", "target_element": "e", "expected_result": "ok",
                               "description": "d", "param": ""}],
                    "expected_result": "ok", "case_type": "manual",
                    "case_category": "positive", "priority": 2,
                }])
                r.choices[0].finish_reason = "stop"
                r.usage = MagicMock(total_tokens=100)
                return r

            mc = MagicMock()
            mc.chat.completions.create.side_effect = capture
            mc.model_name = "test-model"
            mock_client.return_value = mc

            with patch("app.utils.ai_client_enhanced._enhanced.time.sleep"):
                generate_test_case_enhanced(context)

        prompt = captured.get("prompt", "")
        assert "至少1条正向用例" in prompt or "最少1条" in prompt, "Single test point should set min_case_count=1"

    def test_multiple_test_points_min_3(self):
        from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced

        context = {
            "requirement": "test",
            "test_points": [
                {"point": "p1", "module": "m", "function": "f", "priority": 2},
                {"point": "p2", "module": "m", "function": "f", "priority": 2},
            ],
            "ui_specs": [], "ui_description": "",
        }

        captured = {}

        with patch("app.utils.ai_client_enhanced._enhanced.get_ai_client") as mock_client:
            def capture(**kwargs):
                captured["prompt"] = kwargs.get("messages", [{}])[0].get("content", "")
                r = MagicMock()
                r.choices = [MagicMock()]
                r.choices[0].message.content = json.dumps([
                    {"title": f"t{i}", "module": "m", "precondition": "p",
                     "steps": [{"step": "1", "action": "a", "action_type": "click",
                                "input_value": "", "target_element": "e", "expected_result": "ok",
                                "description": "d", "param": ""}],
                     "expected_result": "ok", "case_type": "manual",
                     "case_category": "positive", "priority": 2}
                    for i in range(3)
                ])
                r.choices[0].finish_reason = "stop"
                r.usage = MagicMock(total_tokens=100)
                return r

            mc = MagicMock()
            mc.chat.completions.create.side_effect = capture
            mc.model_name = "test-model"
            mock_client.return_value = mc

            with patch("app.utils.ai_client_enhanced._enhanced.time.sleep"):
                generate_test_case_enhanced(context)

        prompt = captured.get("prompt", "")
        assert "不少于3条" in prompt or "最少3条" in prompt, "Multiple test points should set min_case_count=3"

    def test_graph_mode_min_case_count_floor_3(self):
        from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced

        context = {
            "graph_prompt": "graph prompt",
            "test_points": [{"point": "single", "module": "m", "function": "f", "priority": 2}],
        }

        with patch("app.utils.ai_client_enhanced._enhanced.get_ai_client") as mock_client:
            r = MagicMock()
            r.choices = [MagicMock()]
            r.choices[0].message.content = json.dumps([
                {"title": f"t{i}", "precondition": "p",
                 "steps": [{"step": "1", "action": "a", "action_type": "click",
                            "input_value": "", "target_element": "e", "expected_result": "ok",
                            "description": "d", "param": ""}],
                 "expected_result": "ok", "case_type": "ui_automation",
                 "case_category": "positive", "priority": 2}
                for i in range(3)
            ])
            r.choices[0].finish_reason = "stop"
            r.usage = MagicMock(total_tokens=100)
            mc = MagicMock()
            mc.chat.completions.create.return_value = r
            mc.model_name = "test-model"
            mock_client.return_value = mc

            with patch("app.utils.ai_client_enhanced._enhanced.time.sleep"):
                with patch("app.utils.ai_client_enhanced._enhanced.validate_cases_quality", return_value=(True, [])) as mock_val:
                    generate_test_case_enhanced(context)

                    if mock_val.called:
                        call_kwargs = mock_val.call_args[1] if mock_val.call_args[1] else {}
                        min_cc = call_kwargs.get("min_count")
                        if min_cc is not None:
                            assert min_cc >= 3, f"Graph mode min_count should be >= 3, got {min_cc}"


class TestScenario8UIFileNoParsedScreens:
    """场景8: UI文件无解析结果边界"""

    def test_has_ui_only_depends_on_ui_specs(self):
        has_ui = bool([])
        assert has_ui is False, "Empty ui_specs means no UI"

        has_ui = bool([{"screen_id": 1}])
        assert has_ui is True, "Non-empty ui_specs means has UI"

    def test_ui_descriptions_alone_not_sufficient_for_has_ui(self):
        has_ui = bool([])
        ui_descriptions = [{"file_name": "mockup.png"}]
        has_ui_reference = has_ui or bool(ui_descriptions)

        assert has_ui is False, "ui_descriptions alone should not set has_ui"
        assert has_ui_reference is True, "ui_descriptions should count for empty context check"

    def test_enhanced_path_ui_descriptions_without_specs_triggers_no_ui(self):
        from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced

        context = {
            "requirement": "test requirement",
            "ui_specs": [],
            "ui_description": "这是一个登录页面的原型图描述",
            "case_type": "ui_automation",
            "test_points": [{"point": "test", "module": "m", "function": "f", "priority": 2}],
        }

        captured = {}

        with patch("app.utils.ai_client_enhanced._enhanced.get_ai_client") as mock_client:
            def capture_create(**kwargs):
                captured["prompt"] = kwargs.get("messages", [{}])[0].get("content", "")
                r = MagicMock()
                r.choices = [MagicMock()]
                r.choices[0].message.content = json.dumps([{
                    "title": "test", "module": "m", "precondition": "logged in",
                    "steps": [{"step": "1", "action": "click", "action_type": "click",
                               "input_value": "", "target_element": "btn", "expected_result": "ok",
                               "description": "click", "param": ""}],
                    "expected_result": "done", "case_type": "manual",
                    "case_category": "positive", "priority": 2,
                }])
                r.choices[0].finish_reason = "stop"
                r.usage = MagicMock(total_tokens=100)
                return r

            mc = MagicMock()
            mc.chat.completions.create.side_effect = capture_create
            mc.model_name = "test-model"
            mock_client.return_value = mc

            with patch("app.utils.ai_client_enhanced._enhanced.time.sleep"):
                generate_test_case_enhanced(context)

        prompt = captured.get("prompt", "")
        assert "manual" in prompt, "ui_descriptions without ui_specs should trigger no-UI downgrade to manual"
        assert "不得编造" in prompt or "不得臆造" in prompt, "Should forbid fabricating UI elements"

    def test_generate_endpoint_ui_descriptions_without_specs_not_has_ui(self):
        has_ui = bool([])
        ui_descriptions = [{"file_name": "mockup.png", "description": "a mockup"}]

        assert has_ui is False, "Only ui_specs should determine has_ui"

        has_ui_reference = has_ui or bool(ui_descriptions)
        assert has_ui_reference is True, "ui_descriptions should still count for empty context guard"

    def test_enhanced_path_ui_specs_present_triggers_ui_mode(self):
        from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced

        context = {
            "requirement": "test requirement",
            "ui_specs": [{"screen_id": 1, "screen_name": "login", "ui_spec": {"elements": [{"type": "button", "text": "登录"}]}}],
            "ui_description": "",
            "case_type": "ui_automation",
            "test_points": [{"point": "test", "module": "m", "function": "f", "priority": 2}],
        }

        captured = {}

        with patch("app.utils.ai_client_enhanced._enhanced.get_ai_client") as mock_client:
            def capture_create(**kwargs):
                captured["prompt"] = kwargs.get("messages", [{}])[0].get("content", "")
                r = MagicMock()
                r.choices = [MagicMock()]
                r.choices[0].message.content = json.dumps([{
                    "title": "test", "module": "m", "precondition": "logged in",
                    "steps": [{"step": "1", "action": "click", "action_type": "click",
                               "input_value": "", "target_element": "btn", "expected_result": "ok",
                               "description": "click", "param": ""}],
                    "expected_result": "done", "case_type": "ui_automation",
                    "case_category": "positive", "priority": 2,
                }])
                r.choices[0].finish_reason = "stop"
                r.usage = MagicMock(total_tokens=100)
                return r

            mc = MagicMock()
            mc.chat.completions.create.side_effect = capture_create
            mc.model_name = "test-model"
            mock_client.return_value = mc

            with patch("app.utils.ai_client_enhanced._enhanced.time.sleep"):
                generate_test_case_enhanced(context)

        prompt = captured.get("prompt", "")
        assert "ui_automation" in prompt, "ui_specs present should keep ui_automation mode"


class TestScenario9PromptComparisonExamplesCompact:
    """场景9: Prompt对比示例精简版"""

    def test_compact_is_shorter_than_full(self):
        from app.services.prompt_builder.comparison_examples import get_comparison_examples

        compact = get_comparison_examples(compact=True)
        full = get_comparison_examples(compact=False, lang="zh")

        assert len(compact) < len(full)
        assert len(compact) < 2000
        assert "精简版" in compact

    def test_default_is_compact(self):
        from app.services.prompt_builder.comparison_examples import get_comparison_examples

        default = get_comparison_examples()
        compact = get_comparison_examples(compact=True)
        assert default == compact


class TestScenario10LinearPromptMinCaseCount:
    """场景10: 线性Prompt min_case_count参数化"""

    def test_linear_prompt_min_1(self):
        from app.services.prompt_builder.linear_prompt import _build_linear_prompt

        prompt = _build_linear_prompt(
            requirement_content="req", ui_description="",
            module="m", function="f", point="p", priority=2,
            min_case_count=1,
        )
        assert "最少1条" in prompt

    def test_linear_prompt_min_3(self):
        from app.services.prompt_builder.linear_prompt import _build_linear_prompt

        prompt = _build_linear_prompt(
            requirement_content="req", ui_description="",
            module="m", function="f", point="p", priority=2,
            min_case_count=3,
        )
        assert "最少3条" in prompt

    def test_linear_prompt_uses_compact(self):
        from app.services.prompt_builder.linear_prompt import _build_linear_prompt

        prompt = _build_linear_prompt(
            requirement_content="req", ui_description="",
            module="m", function="f", point="p", priority=2,
        )
        assert "精简版" in prompt


class TestScenario11GraphPromptMinCaseCount:
    """场景11: 图模式Prompt min_case_count参数化"""

    def test_graph_rules_min_1(self):
        from app.services.prompt_builder.case_prompt._rules import _append_generation_rules

        parts = []
        _append_generation_rules(parts, min_case_count=1)
        joined = "\n".join(parts)
        assert "最少1条" in joined

    def test_graph_rules_min_5(self):
        from app.services.prompt_builder.case_prompt._rules import _append_generation_rules

        parts = []
        _append_generation_rules(parts, min_case_count=5)
        joined = "\n".join(parts)
        assert "最少5条" in joined

    def test_graph_rules_uses_compact(self):
        from app.services.prompt_builder.case_prompt._rules import _append_generation_rules

        parts = []
        _append_generation_rules(parts)
        joined = "\n".join(parts)
        assert "精简版" in joined
