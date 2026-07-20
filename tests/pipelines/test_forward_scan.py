"""M2-T06 ForwardScan Step + Service 单元测试

覆盖：
    - ForwardScan Step: should_run / cache_key / execute / validate_output / fallback
    - ForwardScanService: scan / _coarse_screening / _refined_screening / _build_prompt
    - TF-IDF 粗筛 + LLM 精筛两阶段流程
    - 边界：空候选/无指纹/低相似度短路/LLM异常降级
    - _parse_forward_response / _try_parse_json / _is_valid_match 校验逻辑
    - _verdict_to_dict / _compute_stats / _compute_forward_confidence

使用真实 MySQL 数据库 + MockAIClient。
"""
import json

import pytest

from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration
from app.models.pipeline import Artifact
from app.pipelines.context import PipelineContext
from app.pipelines.steps.forward_scan import (
    CoarseMatch,
    ForwardScan,
    ForwardScanService,
    ForwardVerdict,
    _compute_forward_confidence,
    _compute_stats,
    _is_valid_match,
    _parse_forward_response,
    _try_parse_json,
    _verdict_to_dict,
)
from app.services import pipeline_service


def _make_candidates(project_id: int, descs: list = None) -> dict:
    if descs is None:
        descs = [
            {"description": "验证码输入校验", "module": "用户管理", "priority": 1, "reason": "新增验证码功能"},
            {"description": "验证码过期重发", "module": "用户管理", "priority": 2, "reason": "验证码有效期场景"},
        ]
    return {
        "project_id": project_id,
        "candidates": descs,
        "total_count": len(descs),
        "coverage_check": {"passed": True, "min_expected": 1, "actual_count": len(descs)},
        "confidence": 0.85,
    }


def _make_fingerprints(project_id: int, count: int = 5) -> dict:
    fps = []
    for i in range(count):
        fps.append({
            "case_id": 100 + i,
            "title": f"用例{i}",
            "module": "用户管理",
            "summary": f"摘要{i}",
            "priority": 1,
            "lifecycle_status": "active",
        })
    return {
        "project_id": project_id,
        "fingerprints": fps,
        "total_count": count,
        "stale_backfilled_count": 0,
    }


@pytest.fixture
def mock_ai():
    return MockAIClient()


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="forward_scan_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def make_ctx(db, mock_ai, test_iteration):
    _hash_counter = [0]

    def _make_ctx(candidates_payload=None, fingerprints_payload=None):
        _hash_counter[0] += 1
        run = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash=f"forward_scan_test_hash_{_hash_counter[0]}",
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

        if candidates_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="scenario_candidates",
                schema_version="1.0",
                payload=candidates_payload,
                content_hash=f"test_candidates_fs_{_hash_counter[0]}",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("scenario_candidates", artifact)

        if fingerprints_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="history_fingerprints",
                schema_version="1.0",
                payload=fingerprints_payload,
                content_hash=f"test_fingerprints_fs_{_hash_counter[0]}",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("history_fingerprints", artifact)

        return ctx

    return _make_ctx


class TestForwardScanShouldRun:
    def test_with_candidates(self, db, make_ctx, test_iteration):
        ctx = make_ctx(candidates_payload=_make_candidates(test_iteration.project_id))
        assert ForwardScan().should_run(ctx) is True

    def test_without_candidates(self, make_ctx):
        ctx = make_ctx()
        assert ForwardScan().should_run(ctx) is False

    def test_zero_total_count(self, db, make_ctx, test_iteration):
        payload = _make_candidates(test_iteration.project_id, descs=[])
        payload["total_count"] = 0
        ctx = make_ctx(candidates_payload=payload)
        assert ForwardScan().should_run(ctx) is False


class TestForwardScanCacheKey:
    def test_cache_key_with_both_artifacts(self, db, make_ctx, test_iteration):
        ctx = make_ctx(
            candidates_payload=_make_candidates(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=5),
        )
        key = ForwardScan().cache_key(ctx)
        assert len(key) == 64

    def test_cache_key_without_fingerprints(self, db, make_ctx, test_iteration):
        ctx = make_ctx(candidates_payload=_make_candidates(test_iteration.project_id))
        key = ForwardScan().cache_key(ctx)
        assert len(key) == 64

    def test_cache_key_stable(self, db, make_ctx, test_iteration):
        ctx1 = make_ctx(
            candidates_payload=_make_candidates(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=3),
        )
        ctx2 = make_ctx(
            candidates_payload=_make_candidates(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=3),
        )
        assert ForwardScan().cache_key(ctx1) == ForwardScan().cache_key(ctx2)


class TestForwardScanValidateOutput:
    def test_valid_payload(self):
        payload = {
            "project_id": 1,
            "verdicts": [{"candidate_index": 0, "label": "NEW"}],
            "total_count": 1,
            "stats": {"existing": 0, "modify": 0, "new": 1},
        }
        assert ForwardScan().validate_output(payload) is True

    def test_missing_key(self):
        payload = {"project_id": 1, "verdicts": []}
        assert ForwardScan().validate_output(payload) is False

    def test_total_count_mismatch(self):
        payload = {
            "project_id": 1,
            "verdicts": [{"candidate_index": 0, "label": "NEW"}],
            "total_count": 5,
            "stats": {"existing": 0, "modify": 0, "new": 1},
        }
        assert ForwardScan().validate_output(payload) is False


class TestForwardScanFallback:
    def test_fallback_generates_degraded_verdicts(self, db, make_ctx, test_iteration):
        ctx = make_ctx(candidates_payload=_make_candidates(test_iteration.project_id))
        result = ForwardScan().fallback(ctx, RuntimeError("测试异常"))
        assert result.success is True
        assert result.degraded is True
        assert result.artifact_kind == "forward_verdicts"
        assert result.artifact_confidence == 0.0
        assert all(v["label"] == "NEW" for v in result.artifact_payload["verdicts"])
        assert "降级" in result.artifact_payload["verdicts"][0]["reason"]

    def test_fallback_without_candidates(self, make_ctx):
        ctx = make_ctx()
        result = ForwardScan().fallback(ctx, RuntimeError("异常"))
        assert result.success is True
        assert result.artifact_payload["verdicts"] == []


class TestForwardScanExecute:
    def test_execute_missing_candidates(self, make_ctx):
        ctx = make_ctx()
        result = ForwardScan().execute(ctx)
        assert result.success is False
        assert "缺失" in result.error or "缺少" in result.error

    def test_execute_empty_candidates(self, db, make_ctx, test_iteration):
        payload = _make_candidates(test_iteration.project_id, descs=[])
        ctx = make_ctx(candidates_payload=payload)
        result = ForwardScan().execute(ctx)
        assert result.success is False

    def test_execute_without_fingerprints(self, db, make_ctx, mock_ai, test_iteration):
        ctx = make_ctx(candidates_payload=_make_candidates(test_iteration.project_id))
        result = ForwardScan().execute(ctx)
        assert result.success is True
        assert result.artifact_kind == "forward_verdicts"
        verdicts = result.artifact_payload["verdicts"]
        assert all(v["label"] == "NEW" for v in verdicts)
        assert result.artifact_payload["stats"]["new"] == len(verdicts)

    def test_execute_with_matches(self, db, make_ctx, mock_ai, test_iteration):
        ai_response = json.dumps({
            "label": "EXISTING",
            "matched_case_id": 100,
            "matched_title": "用例0",
            "confidence": 0.9,
            "reason": "场景一致",
        })
        mock_ai.set_response("forward_scan", ai_response)

        ctx = make_ctx(
            candidates_payload=_make_candidates(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=5),
        )
        result = ForwardScan().execute(ctx)
        assert result.success is True
        assert result.artifact_kind == "forward_verdicts"
        assert result.artifact_confidence > 0.0
        assert "stats" in result.artifact_payload

    def test_execute_llm_exception_fallback(self, db, mock_ai, test_iteration):
        from app.ai.mock_client import MockAIClient

        class FailingAIClient(MockAIClient):
            def complete(self, prompt, **kwargs):
                raise RuntimeError("AI 服务不可用")

        failing_ai = FailingAIClient()
        run = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="fs_fail_hash_v2",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=failing_ai,
            run=run,
            iteration_id=test_iteration.id,
            user_id=1,
        )

        candidates_payload = {
            "project_id": test_iteration.project_id,
            "candidates": [{"description": "验证码", "module": "用户管理", "priority": 1, "reason": "验证码功能"}],
            "total_count": 1,
            "coverage_check": {"passed": True, "min_expected": 1, "actual_count": 1},
            "confidence": 0.85,
        }
        artifact = Artifact(
            run_id=run.id,
            kind="scenario_candidates",
            schema_version="1.0",
            payload=candidates_payload,
            content_hash="test_cand_fail_v2",
        )
        db.add(artifact)
        db.flush()
        ctx.set_artifact("scenario_candidates", artifact)

        fingerprints_payload = {
            "project_id": test_iteration.project_id,
            "fingerprints": [
                {"case_id": 100, "title": "验证码校验", "module": "用户管理", "summary": "验证码", "priority": 1, "lifecycle_status": "active"},
            ],
            "total_count": 1,
            "stale_backfilled_count": 0,
        }
        fp_artifact = Artifact(
            run_id=run.id,
            kind="history_fingerprints",
            schema_version="1.0",
            payload=fingerprints_payload,
            content_hash="test_fp_fail_v2",
        )
        db.add(fp_artifact)
        db.flush()
        ctx.set_artifact("history_fingerprints", fp_artifact)

        result = ForwardScan().execute(ctx)
        assert result.success is True
        assert result.artifact_payload["stats"]["new"] >= 1


class TestForwardScanService:
    def test_scan_empty_candidates(self, mock_ai):
        service = ForwardScanService(ai_client=mock_ai)
        result = service.scan([], [])
        assert result == []

    def test_scan_no_fingerprints(self, mock_ai):
        service = ForwardScanService(ai_client=mock_ai)
        candidates = [{"description": "场景1", "module": "用户", "priority": 1, "reason": "新增"}]
        result = service.scan(candidates, [])
        assert len(result) == 1
        assert result[0].label == "NEW"
        assert result[0].reason == "无历史用例可匹配"
        assert result[0].confidence == 0.8

    def test_scan_low_similarity_short_circuits(self, mock_ai):
        service = ForwardScanService(
            ai_client=mock_ai,
            similarity_threshold=0.99,
        )
        candidates = [{"description": "完全不同的场景X", "module": "支付", "priority": 1, "reason": "新增"}]
        fingerprints = [
            {"case_id": 100, "title": "登录验证", "module": "用户管理", "summary": "验证码登录", "priority": 1},
            {"case_id": 101, "title": "注册流程", "module": "用户管理", "summary": "邮箱注册", "priority": 1},
        ]
        result = service.scan(candidates, fingerprints)
        assert len(result) == 1
        assert result[0].label == "NEW"
        assert "低于阈值" in result[0].reason
        assert result[0].confidence == 0.85

    def test_scan_with_llm_existing(self, mock_ai):
        ai_response = json.dumps({
            "label": "EXISTING",
            "matched_case_id": 100,
            "matched_title": "用例0",
            "confidence": 0.92,
            "reason": "描述完全一致",
        })
        mock_ai.set_response("forward_scan", ai_response)

        service = ForwardScanService(ai_client=mock_ai)
        candidates = [{"description": "登录验证码校验", "module": "用户管理", "priority": 1, "reason": "验证码功能"}]
        fingerprints = [
            {"case_id": 100, "title": "登录验证码校验", "module": "用户管理", "summary": "登录时输入验证码校验", "priority": 1},
            {"case_id": 101, "title": "注册流程", "module": "用户管理", "summary": "邮箱注册", "priority": 1},
        ]
        result = service.scan(candidates, fingerprints)
        assert len(result) == 1
        assert result[0].label == "EXISTING"
        assert result[0].matched_case_id == 100
        assert result[0].confidence == 0.92

    def test_scan_with_llm_modify(self, mock_ai):
        ai_response = json.dumps({
            "label": "MODIFY",
            "matched_case_id": 100,
            "matched_title": "登录验证码校验",
            "confidence": 0.78,
            "reason": "需要新增校验步骤",
        })
        mock_ai.set_response("forward_scan", ai_response)

        service = ForwardScanService(ai_client=mock_ai)
        candidates = [{"description": "登录验证码增强校验", "module": "用户管理", "priority": 2, "reason": "多因素验证 登录时验证码校验"}]
        fingerprints = [
            {"case_id": 100, "title": "登录验证码校验", "module": "用户管理", "summary": "登录时输入验证码校验用户身份", "priority": 1},
            {"case_id": 101, "title": "注册流程", "module": "用户管理", "summary": "邮箱注册", "priority": 1},
        ]
        result = service.scan(candidates, fingerprints)
        assert len(result) == 1
        assert result[0].label == "MODIFY"
        assert result[0].matched_case_id == 100

    def test_scan_with_llm_new(self, mock_ai):
        ai_response = json.dumps({
            "label": "NEW",
            "matched_case_id": None,
            "matched_title": "",
            "confidence": 0.88,
            "reason": "无匹配用例",
        })
        mock_ai.set_response("forward_scan", ai_response)

        service = ForwardScanService(ai_client=mock_ai)
        candidates = [{"description": "第三方支付回调", "module": "支付", "priority": 1, "reason": "新增支付方式"}]
        fingerprints = [
            {"case_id": 100, "title": "登录验证码校验", "module": "用户管理", "summary": "验证码", "priority": 1},
            {"case_id": 101, "title": "密码重置", "module": "用户管理", "summary": "重置密码", "priority": 1},
        ]
        result = service.scan(candidates, fingerprints)
        assert len(result) == 1
        assert result[0].label == "NEW"
        assert result[0].matched_case_id is None

    def test_scan_multiple_candidates(self, mock_ai):
        ai_response = json.dumps({
            "label": "EXISTING",
            "matched_case_id": 100,
            "matched_title": "登录验证码校验",
            "confidence": 0.9,
            "reason": "已存在",
        })
        mock_ai.set_response("forward_scan", ai_response)

        service = ForwardScanService(ai_client=mock_ai)
        candidates = [
            {"description": "登录验证码校验", "module": "用户管理", "priority": 1, "reason": "验证码 登录校验"},
            {"description": "XXAA支付回调通知处理接口对接", "module": "支付", "priority": 1, "reason": "新增 第三方 回调"},
        ]
        fingerprints = [
            {"case_id": 100, "title": "登录验证码校验", "module": "用户管理", "summary": "登录时输入验证码校验用户身份", "priority": 1},
            {"case_id": 101, "title": "注册流程", "module": "用户管理", "summary": "邮箱注册流程", "priority": 1},
        ]
        result = service.scan(candidates, fingerprints)
        assert len(result) == 2
        labels = {v.label for v in result}
        assert "EXISTING" in labels
        assert "NEW" in labels


class TestParseForwardResponse:
    def test_existing_valid(self):
        top_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.85)]
        result = _parse_forward_response(
            json.dumps({"label": "EXISTING", "matched_case_id": 100, "matched_title": "用例0", "confidence": 0.9, "reason": "一致"}),
            {"description": "场景", "reason": "理由"},
            top_matches,
        )
        assert result.label == "EXISTING"
        assert result.matched_case_id == 100

    def test_modify_valid(self):
        top_matches = [CoarseMatch(case_id=101, title="用例1", summary="摘要1", similarity=0.72)]
        result = _parse_forward_response(
            json.dumps({"label": "MODIFY", "matched_case_id": 101, "matched_title": "用例1", "confidence": 0.7, "reason": "需修改"}),
            {"description": "场景", "reason": "理由"},
            top_matches,
        )
        assert result.label == "MODIFY"
        assert result.matched_case_id == 101

    def test_new_valid(self):
        result = _parse_forward_response(
            json.dumps({"label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": 0.8, "reason": "无匹配"}),
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert result.label == "NEW"
        assert result.matched_case_id is None

    def test_invalid_json_fallback(self):
        result = _parse_forward_response(
            "not json{{{",
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert result.label == "NEW"
        assert "JSON 解析失败" in result.reason
        assert result.confidence == 0.0

    def test_invalid_label_corrected(self):
        result = _parse_forward_response(
            json.dumps({"label": "UNKNOWN", "matched_case_id": None, "matched_title": "", "confidence": 0.8, "reason": "未知"}),
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert result.label == "NEW"

    def test_existing_without_title_fallback(self):
        top_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.8)]
        result = _parse_forward_response(
            json.dumps({"label": "EXISTING", "matched_case_id": 100, "matched_title": "", "confidence": 0.9, "reason": "一致"}),
            {"description": "场景", "reason": "理由"},
            top_matches,
        )
        assert result.label == "NEW"

    def test_existing_invalid_case_id_fallback(self):
        top_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.8)]
        result = _parse_forward_response(
            json.dumps({"label": "EXISTING", "matched_case_id": 999, "matched_title": "不存在", "confidence": 0.9, "reason": ""}),
            {"description": "场景", "reason": "理由"},
            top_matches,
        )
        assert result.label == "NEW"

    def test_modify_invalid_case_id_fallback(self):
        top_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.8)]
        result = _parse_forward_response(
            json.dumps({"label": "MODIFY", "matched_case_id": 999, "matched_title": "不存在", "confidence": 0.6, "reason": "要改"}),
            {"description": "场景", "reason": "理由"},
            top_matches,
        )
        assert result.label == "NEW"

    def test_modify_without_title_fallback(self):
        top_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.8)]
        result = _parse_forward_response(
            json.dumps({"label": "MODIFY", "matched_case_id": 100, "matched_title": "", "confidence": 0.6, "reason": "要改"}),
            {"description": "场景", "reason": "理由"},
            top_matches,
        )
        assert result.label == "NEW"

    def test_existing_matched_case_id_is_bool(self):
        top_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.8)]
        result = _parse_forward_response(
            json.dumps({"label": "EXISTING", "matched_case_id": True, "matched_title": "用例0", "confidence": 0.9, "reason": "bool"}),
            {"description": "场景", "reason": "理由"},
            top_matches,
        )
        assert result.label == "NEW"

    def test_confidence_bounds_corrected(self):
        result = _parse_forward_response(
            json.dumps({"label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": 1.5, "reason": "高自信"}),
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert result.confidence == 1.0

        result = _parse_forward_response(
            json.dumps({"label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": -0.5, "reason": "负自信"}),
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert result.confidence == 0.0

    def test_non_numeric_confidence_default(self):
        result = _parse_forward_response(
            json.dumps({"label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": "high", "reason": "字符串"}),
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert result.confidence == 0.7

    def test_empty_reason_fallback_to_description(self):
        result = _parse_forward_response(
            json.dumps({"label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": 0.8, "reason": ""}),
            {"description": "场景描述", "reason": "原始理由"},
            [],
        )
        assert result.reason == "场景描述"

    def test_reason_truncated(self):
        result = _parse_forward_response(
            json.dumps({"label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": 0.8, "reason": "R" * 200}),
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert len(result.reason) == 100

    def test_empty_matched_title_for_new(self):
        result = _parse_forward_response(
            json.dumps({"label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": 0.8, "reason": "新场景"}),
            {"description": "场景", "reason": "理由"},
            [],
        )
        assert result.label == "NEW"
        assert result.matched_case_id is None
        assert result.matched_title == ""


class TestTryParseJson:
    def test_valid_dict(self):
        result = _try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_text(self):
        result = _try_parse_json('输出：{"label": "NEW"}')
        assert result == {"label": "NEW"}

    def test_invalid(self):
        result = _try_parse_json("not json at all")
        assert result is None

    def test_array_extracts_nested_dict(self):
        result = _try_parse_json('[{"a": 1}]')
        assert result == {"a": 1}

    def test_invalid_braces_content(self):
        result = _try_parse_json('结果: {not valid json}')
        assert result is None


class TestIsValidMatch:
    def test_valid_match(self):
        top_matches = [
            CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.9),
            CoarseMatch(case_id=101, title="用例1", summary="摘要1", similarity=0.7),
        ]
        assert _is_valid_match(100, top_matches) is True

    def test_invalid_match(self):
        top_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.9)]
        assert _is_valid_match(999, top_matches) is False


class TestCoarseScreening:
    def test_empty_fingerprints(self, mock_ai):
        service = ForwardScanService(ai_client=mock_ai)
        candidate = {"description": "测试", "reason": "测试"}
        result = service._coarse_screening([candidate], [])
        assert result == [[]]

    def test_returns_top_k(self, mock_ai):
        service = ForwardScanService(ai_client=mock_ai, top_k=2)
        candidate = {"description": "登录验证码校验", "reason": "新增"}
        fingerprints = [
            {"case_id": 100, "title": "登录验证码校验", "module": "用户管理", "summary": "登录时输入验证码校验用户身份", "priority": 1},
            {"case_id": 101, "title": "注册流程", "module": "用户管理", "summary": "邮箱注册", "priority": 1},
            {"case_id": 102, "title": "密码重置", "module": "用户管理", "summary": "重置密码", "priority": 1},
        ]
        result = service._coarse_screening([candidate], fingerprints)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_no_similar_fingerprints(self, mock_ai):
        service = ForwardScanService(ai_client=mock_ai)
        candidate = {"description": "XYZ_UNIQUE", "reason": "独特"}
        fingerprints = [
            {"case_id": 100, "title": "登录验证码校验", "module": "用户管理", "summary": "登录", "priority": 1},
            {"case_id": 101, "title": "注册流程", "module": "用户管理", "summary": "注册", "priority": 1},
        ]
        result = service._coarse_screening([candidate], fingerprints)
        assert len(result) == 1
        assert len(result[0]) == 2
        assert all(m.similarity < 0.5 for m in result[0])


class TestBuildPrompt:
    def test_prompt_contains_candidate_description(self, mock_ai):
        service = ForwardScanService(ai_client=mock_ai)
        candidate = {"description": "测试场景", "reason": "测试理由"}
        coarse_matches = [CoarseMatch(case_id=100, title="用例0", summary="摘要0", similarity=0.8)]
        prompt = service._build_prompt(candidate, coarse_matches)
        assert "测试场景" in prompt
        assert "用例0" in prompt

    def test_prompt_without_matches(self, mock_ai):
        service = ForwardScanService(ai_client=mock_ai)
        candidate = {"description": "新场景", "reason": "无历史"}
        prompt = service._build_prompt(candidate, [])
        assert "新场景" in prompt


class TestVerdictToDict:
    def test_round_trip(self):
        v = ForwardVerdict(
            candidate_index=0,
            candidate_description="场景描述",
            label="EXISTING",
            matched_case_id=100,
            matched_title="用例标题",
            matched_similarity=0.85,
            confidence=0.9,
            reason="匹配理由",
        )
        d = _verdict_to_dict(v)
        assert d["candidate_index"] == 0
        assert d["label"] == "EXISTING"
        assert d["matched_case_id"] == 100

    def test_new_verdict(self):
        v = ForwardVerdict(
            candidate_index=1,
            candidate_description="新场景",
            label="NEW",
            matched_case_id=None,
            matched_title="",
            matched_similarity=0.0,
            confidence=0.85,
            reason="无匹配",
        )
        d = _verdict_to_dict(v)
        assert d["label"] == "NEW"
        assert d["matched_case_id"] is None


class TestComputeStats:
    def test_mixed_labels(self):
        verdicts = [
            ForwardVerdict(0, "d", "EXISTING", 100, "t", 0.9, 0.9, "r"),
            ForwardVerdict(1, "d", "MODIFY", 101, "t", 0.7, 0.7, "r"),
            ForwardVerdict(2, "d", "NEW", None, "", 0.0, 0.8, "r"),
            ForwardVerdict(3, "d", "NEW", None, "", 0.0, 0.9, "r"),
        ]
        stats = _compute_stats(verdicts)
        assert stats == {"existing": 1, "modify": 1, "new": 2}

    def test_all_new(self):
        verdicts = [
            ForwardVerdict(0, "d", "NEW", None, "", 0.0, 0.8, "r"),
        ]
        stats = _compute_stats(verdicts)
        assert stats == {"existing": 0, "modify": 0, "new": 1}


class TestComputeForwardConfidence:
    def test_non_empty(self):
        verdicts = [
            ForwardVerdict(0, "d", "EXISTING", 100, "t", 0.9, 0.8, "r"),
            ForwardVerdict(1, "d", "NEW", None, "", 0.0, 0.6, "r"),
        ]
        conf = _compute_forward_confidence(verdicts)
        assert conf == pytest.approx(0.7)

    def test_empty(self):
        assert _compute_forward_confidence([]) == 0.0
