"""M2-T05 ScenarioCandidateExtractor Step 单元测试

覆盖：
    - should_run / cache_key / validate_output / fallback
    - execute 正常路径（有 PRD + UI + fingerprints）
    - execute 缺少 raw_signals / project_id
    - AI 返回解析：正常 JSON / 嵌套 dict / 纯数组 / 非法 JSON
    - _validate_candidates：模块匹配 / 模糊匹配 / 过滤空描述 / priority 修正
    - _extract_prd / _extract_ui / _extract_existing_modules / _extract_existing_summaries
    - _estimate_ui_controls / _compute_confidence
    - coverage_check 启发式校验

使用真实 MySQL 数据库 + MockAIClient。
"""
import json
import pytest

from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration
from app.models.pipeline import Artifact
from app.pipelines.steps.scenario_candidates import (
    ScenarioCandidateExtractor,
    _extract_prd,
    _extract_ui,
    _extract_existing_modules,
    _extract_existing_summaries,
    _parse_candidates,
    _validate_candidates,
    _find_closest_module,
    _estimate_ui_controls,
    _compute_confidence,
    _try_extract_json_array,
)
from app.services import pipeline_service
from app.pipelines.context import PipelineContext


def _make_raw_signals(project_id: int, **overrides) -> dict:
    payload = {
        "iteration_id": 1,
        "project_id": project_id,
        "prd_content": "新增验证码功能，登录时需输入图形验证码",
        "ui_specs": [
            {
                "screen_id": 1,
                "screen_name": "登录页",
                "ui_spec": {"components": [{"type": "input", "name": "captcha"}, {"type": "button", "name": "submit"}]},
            }
        ],
        "test_points": [{"id": 1, "module": "用户管理", "point": "验证码校验", "priority": 1}],
        "has_ui": True,
        "has_prd": True,
        "has_testpoints": True,
    }
    payload.update(overrides)
    return payload


def _make_fingerprints(project_id: int, modules: list = None) -> dict:
    mods = modules if modules is not None else ["用户管理", "订单管理"]
    fps = []
    for i, mod in enumerate(mods):
        fps.append({
            "case_id": 200 + i,
            "title": f"用例{i}",
            "module": mod,
            "summary": f"摘要{i}",
            "priority": 1,
            "lifecycle_status": "active",
        })
    return {
        "project_id": project_id,
        "fingerprints": fps,
        "total_count": len(fps),
        "stale_backfilled_count": 0,
    }


@pytest.fixture
def mock_ai():
    client = MockAIClient()
    return client


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="scenario_cand_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def make_ctx(db, mock_ai, test_iteration):
    def _make_ctx(raw_signals_payload=None, fingerprints_payload=None):
        run = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="scenario_cand_test_hash",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=mock_ai,
            run=run,
            iteration_id=test_iteration.id,
            user_id=1,
        )

        if raw_signals_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="raw_signals",
                schema_version="1.0",
                payload=raw_signals_payload,
                content_hash="test_raw_signals_sc",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("raw_signals", artifact)

        if fingerprints_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="history_fingerprints",
                schema_version="1.0",
                payload=fingerprints_payload,
                content_hash="test_fingerprints_sc",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("history_fingerprints", artifact)

        return ctx

    return _make_ctx


class TestShouldRun:
    def test_with_raw_signals(self, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        assert ScenarioCandidateExtractor().should_run(ctx) is True

    def test_without_raw_signals(self, make_ctx):
        ctx = make_ctx()
        assert ScenarioCandidateExtractor().should_run(ctx) is False


class TestCacheKey:
    def test_deterministic(self, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = ScenarioCandidateExtractor()
        assert step.cache_key(ctx) == step.cache_key(ctx)
        assert len(step.cache_key(ctx)) == 64


class TestValidateOutput:
    def test_valid(self):
        payload = {"project_id": 1, "candidates": [], "total_count": 0, "existing_modules": [], "coverage_check": {}}
        assert ScenarioCandidateExtractor().validate_output(payload) is True

    def test_missing_coverage_check(self):
        assert ScenarioCandidateExtractor().validate_output({"project_id": 1, "candidates": [], "total_count": 0, "existing_modules": []}) is False


class TestFallback:
    def test_fallback_returns_degraded(self, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        result = ScenarioCandidateExtractor().fallback(ctx, RuntimeError("test"))
        assert result.degraded is True
        assert result.artifact_payload["total_count"] == 0

    def test_fallback_without_raw_signals(self, make_ctx):
        ctx = make_ctx()
        result = ScenarioCandidateExtractor().fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestExecute:
    def test_execute_with_valid_ai(self, db, make_ctx, mock_ai, test_iteration):
        ai_response = json.dumps([
            {"description": "验证码输入校验", "module": "用户管理", "priority": 1, "reason": "新增验证码功能"},
            {"description": "验证码过期重发", "module": "用户管理", "priority": 2, "reason": "验证码有效期场景"},
        ])
        mock_ai.set_response("scenario_candidate_extractor", ai_response)

        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id),
        )
        result = ScenarioCandidateExtractor().execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "scenario_candidates"
        assert result.artifact_payload["total_count"] >= 1
        assert "coverage_check" in result.artifact_payload

    def test_execute_missing_raw_signals(self, make_ctx):
        ctx = make_ctx()
        result = ScenarioCandidateExtractor().execute(ctx)
        assert result.success is False

    def test_execute_missing_project_id(self, make_ctx):
        ctx = make_ctx(raw_signals_payload={"iteration_id": 1})
        result = ScenarioCandidateExtractor().execute(ctx)
        assert result.success is False

    def test_execute_ai_parse_failure(self, db, make_ctx, mock_ai, test_iteration):
        mock_ai.set_response("scenario_candidate_extractor", "not json{{{")
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id),
        )
        result = ScenarioCandidateExtractor().execute(ctx)
        assert result.success is False

    def test_execute_ai_exception(self, db, make_ctx, test_iteration):
        from app.ai.mock_client import MockAIClient

        class FailingAIClient(MockAIClient):
            def complete(self, prompt, **kwargs):
                raise RuntimeError("AI 服务不可用")

        failing_ai = FailingAIClient()
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id),
        )
        ctx.ai_client = failing_ai
        result = ScenarioCandidateExtractor().execute(ctx)
        assert result.success is False
        assert "AI 调用失败" in result.error

    def test_execute_without_fingerprints(self, db, make_ctx, mock_ai, test_iteration):
        ai_response = json.dumps([
            {"description": "无指纹场景", "module": "新模块", "priority": 1, "reason": "无历史指纹"},
        ])
        mock_ai.set_response("scenario_candidate_extractor", ai_response)

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        result = ScenarioCandidateExtractor().execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "scenario_candidates"

    def test_execute_coverage_check_fails(self, db, make_ctx, mock_ai, test_iteration):
        ai_response = json.dumps([
            {"description": "只有1个场景", "module": "用户管理", "priority": 1, "reason": "场景偏少"},
        ])
        mock_ai.set_response("scenario_candidate_extractor", ai_response)

        raw_signals = _make_raw_signals(test_iteration.project_id)
        raw_signals["ui_specs"] = [
            {"screen_name": "复杂页面",
             "ui_spec": {"components": [{"t": str(i)} for i in range(20)]}},
        ]
        ctx = make_ctx(
            raw_signals_payload=raw_signals,
            fingerprints_payload=_make_fingerprints(test_iteration.project_id),
        )
        result = ScenarioCandidateExtractor().execute(ctx)

        assert result.success is True
        assert result.artifact_payload["coverage_check"]["passed"] is False


class TestParseCandidates:
    def test_valid_array(self):
        raw = '[{"description": "场景1", "module": "用户", "priority": 1, "reason": "新增"}]'
        result = _parse_candidates(raw)
        assert len(result) == 1

    def test_nested_dict(self):
        raw = '{"candidates": [{"description": "场景1", "module": "用户", "priority": 1, "reason": "新增"}]}'
        result = _parse_candidates(raw)
        assert len(result) == 1

    def test_nested_with_scenarios_key(self):
        raw = '{"scenarios": [{"description": "场景1", "module": "用户", "priority": 1, "reason": "新增"}]}'
        result = _parse_candidates(raw)
        assert len(result) == 1

    def test_nested_with_items_key(self):
        raw = '{"items": [{"description": "场景1", "module": "用户", "priority": 1, "reason": "新增"}]}'
        result = _parse_candidates(raw)
        assert len(result) == 1

    def test_nested_with_results_key(self):
        raw = '{"results": [{"description": "场景1", "module": "用户", "priority": 1, "reason": "新增"}]}'
        result = _parse_candidates(raw)
        assert len(result) == 1

    def test_invalid_json(self):
        result = _parse_candidates("not json{{{")
        assert result is None

    def test_dict_without_recognized_keys(self):
        raw = '{"unknown_key": [{"a": 1}]}'
        result = _parse_candidates(raw)
        assert result is None

    def test_plain_string_json(self):
        result = _parse_candidates('"just a string"')
        assert result is None

    def test_extract_from_text(self):
        raw = '以下是结果：\n[{"description": "场景1", "module": "用户", "priority": 1, "reason": "新增"}]\n结束'
        result = _parse_candidates(raw)
        assert len(result) == 1


class TestValidateCandidates:
    def test_valid_candidates(self):
        candidates = [
            {"description": "验证码校验", "module": "用户管理", "priority": 1, "reason": "新增"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1

    def test_empty_description_filtered(self):
        candidates = [
            {"description": "", "module": "用户管理", "priority": 1, "reason": "空描述"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 0

    def test_long_description_filtered(self):
        candidates = [
            {"description": "A" * 60, "module": "用户管理", "priority": 1, "reason": "过长描述"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 0

    def test_non_dict_candidate_skipped(self):
        candidates = [
            "not_a_dict",
            {"description": "验证码校验", "module": "用户管理", "priority": 1, "reason": "新增"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1

    def test_empty_module_filtered(self):
        candidates = [
            {"description": "测试场景", "module": "", "priority": 1, "reason": "空模块"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 0

    def test_module_fuzzy_match(self):
        candidates = [
            {"description": "测试场景", "module": "用户", "priority": 1, "reason": "模糊匹配"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1
        assert result[0]["module"] == "用户管理"

    def test_module_no_match_kept_with_original(self):
        candidates = [
            {"description": "测试场景", "module": "完全不相关", "priority": 1, "reason": "无匹配"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1
        assert result[0]["module"] == "完全不相关"
        assert result[0]["module_original"] == "完全不相关"

    def test_priority_correction(self):
        candidates = [
            {"description": "测试场景", "module": "用户管理", "priority": 5, "reason": "优先级越界"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1
        assert result[0]["priority"] == 3

    def test_priority_non_int_correction(self):
        candidates = [
            {"description": "测试场景", "module": "用户管理", "priority": "high", "reason": "非整数优先级"},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1
        assert result[0]["priority"] == 3

    def test_no_existing_modules_allows_any(self):
        candidates = [
            {"description": "新模块场景", "module": "新模块", "priority": 1, "reason": "新增模块"},
        ]
        result = _validate_candidates(candidates, [])
        assert len(result) == 1

    def test_reason_fallback_to_description(self):
        candidates = [
            {"description": "测试场景", "module": "用户管理", "priority": 1},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1
        assert result[0]["reason"] == "测试场景"

    def test_reason_truncated(self):
        candidates = [
            {"description": "测试场景", "module": "用户管理", "priority": 1, "reason": "R" * 150},
        ]
        result = _validate_candidates(candidates, ["用户管理"])
        assert len(result) == 1
        assert len(result[0]["reason"]) == 100


class TestFindClosestModule:
    def test_exact_match(self):
        assert _find_closest_module("用户管理", ["用户管理", "订单"]) == "用户管理"

    def test_case_insensitive(self):
        assert _find_closest_module("USER", ["user"]) == "user"

    def test_substring_match(self):
        assert _find_closest_module("用户", ["用户管理"]) == "用户管理"

    def test_reverse_substring_match(self):
        assert _find_closest_module("用户管理模块", ["用户管理"]) == "用户管理"

    def test_no_match(self):
        assert _find_closest_module("支付", ["用户管理"]) is None


class TestExtractPrd:
    def test_with_prd(self):
        assert "验证码" in _extract_prd({"prd_content": "验证码功能"})

    def test_without_prd(self):
        assert "无 PRD" in _extract_prd({})

    def test_long_prd_truncated(self):
        long_prd = "A" * 5000
        result = _extract_prd({"prd_content": long_prd})
        assert len(result) == 3000


class TestExtractUi:
    def test_with_ui_specs(self):
        ui = [{"screen_name": "登录页", "ui_spec": {"components": [{"type": "input"}]}}]
        result = _extract_ui({"ui_specs": ui})
        assert "登录页" in result

    def test_without_ui(self):
        assert "无 UI" in _extract_ui({})

    def test_empty_ui_specs_list(self):
        assert "无 UI" in _extract_ui({"ui_specs": []})

    def test_non_serializable_ui_spec(self):
        ui = [{"screen_name": "异常页", "ui_spec": {"data": bytes([1, 2, 3])}}]
        result = _extract_ui({"ui_specs": ui})
        assert "异常页" in result

    def test_many_ui_specs_truncated(self):
        ui = [{"screen_name": f"屏幕{i}", "ui_spec": {"components": []}} for i in range(10)]
        result = _extract_ui({"ui_specs": ui})
        screen_count = result.count("###")
        assert screen_count == 5

    def test_without_screen_name(self):
        ui = [{"ui_spec": {"components": [{"type": "button"}]}}]
        result = _extract_ui({"ui_specs": ui})
        assert "未知屏幕" in result

    def test_empty_ui_spec_omitted(self):
        ui = [
            {"screen_name": "空屏幕", "ui_spec": None},
            {"screen_name": "正常屏幕", "ui_spec": {"components": [{"type": "text"}]}},
        ]
        result = _extract_ui({"ui_specs": ui})
        assert "空屏幕" not in result
        assert "正常屏幕" in result


class TestExtractExistingModules:
    def test_with_fingerprints(self):
        fps = _make_fingerprints(1, modules=["用户", "订单"])
        result = _extract_existing_modules(fps)
        assert "用户" in result
        assert "订单" in result

    def test_without_fingerprints(self):
        assert _extract_existing_modules(None) == []

    def test_empty_fingerprints_list(self):
        fps = _make_fingerprints(1, modules=[])
        result = _extract_existing_modules(fps)
        assert result == []


class TestExtractExistingSummaries:
    def test_with_fingerprints(self):
        fps = _make_fingerprints(1, modules=["用户"])
        result = _extract_existing_summaries(fps)
        assert "摘要" in result

    def test_without_fingerprints(self):
        assert "无已有" in _extract_existing_summaries(None)

    def test_empty_fingerprints_list(self):
        fps = _make_fingerprints(1, modules=[])
        assert "无已有" in _extract_existing_summaries(fps)

    def test_many_fingerprints_truncated(self):
        mods = [f"模块{i}" for i in range(30)]
        fps = _make_fingerprints(1, modules=mods)
        result = _extract_existing_summaries(fps)
        lines = result.strip().split("\n")
        assert len(lines) == 20


class TestEstimateUiControls:
    def test_with_components(self):
        signals = {"ui_specs": [{"ui_spec": {"components": [{"type": "input"}, {"type": "button"}]}}]}
        assert _estimate_ui_controls(signals) == 2

    def test_without_ui(self):
        assert _estimate_ui_controls({}) == 0

    def test_with_dict_components(self):
        signals = {"ui_specs": [{"ui_spec": {"components": {"input": {}, "button": {}}}}]}
        assert _estimate_ui_controls(signals) == 2

    def test_with_elements_key(self):
        signals = {"ui_specs": [{"ui_spec": {"elements": [{"type": "input"}, {"type": "label"}]}}]}
        assert _estimate_ui_controls(signals) == 2

    def test_with_ui_spec_as_list(self):
        signals = {"ui_specs": [{"ui_spec": [{"type": "input"}, {"type": "button"}, {"type": "submit"}]}]}
        assert _estimate_ui_controls(signals) == 3

    def test_fallback_to_specs_length(self):
        signals = {"ui_specs": [{"ui_spec": {}}, {"ui_spec": {}}, {"ui_spec": {}}]}
        assert _estimate_ui_controls(signals) == 3

    def test_components_neither_list_nor_dict(self):
        signals = {"ui_specs": [{"ui_spec": {"components": "not_a_collection"}}]}
        assert _estimate_ui_controls(signals) == 1

    def test_ui_spec_neither_dict_nor_list(self):
        signals = {"ui_specs": [{"ui_spec": None}, {"ui_spec": 42}]}
        assert _estimate_ui_controls(signals) == 2


class TestComputeConfidence:
    def test_empty(self):
        assert _compute_confidence([], True) == 0.0

    def test_coverage_ok(self):
        cands = [{"description": "场景", "module": "用户", "priority": 1, "reason": "新增"}]
        assert _compute_confidence(cands, True) >= 0.7

    def test_coverage_fail(self):
        cands = [{"description": "场景", "module": "用户", "priority": 3, "reason": "新增"}]
        assert _compute_confidence(cands, False) < 0.7

    def test_coverage_fail_with_high_priority(self):
        cands = [{"description": "场景", "module": "用户", "priority": 1, "reason": "新增"}]
        confidence = _compute_confidence(cands, False)
        assert 0.4 <= confidence < 0.7

    def test_bonus_capped_at_max(self):
        cands = [{"description": f"场景{i}", "module": "用户", "priority": 1, "reason": "新增"} for i in range(10)]
        confidence = _compute_confidence(cands, True)
        assert confidence == pytest.approx(0.9)


class TestTryExtractJsonArray:
    def test_embedded_array(self):
        text = '结果如下：\n[{"a": 1}]\n请查收'
        result = _try_extract_json_array(text)
        assert result is not None
        assert len(result) == 1

    def test_no_array(self):
        assert _try_extract_json_array("no array here") is None

    def test_invalid_json_inside_brackets(self):
        text = '结果: [invalid json here] 结束'
        result = _try_extract_json_array(text)
        assert result is None
