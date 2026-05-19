"""M2-T04 BackwardScan Step + Service 单元测试

覆盖：
    - BackwardScan Step: should_run / cache_key / execute / validate_output / fallback
    - BackwardScanService: scan / _slice_by_module / _process_batch / _call_ai_with_retry / _fallback_split / _mark_uncertain
    - 重试机制：3次重试 → 切半 → 单条 → UNCERTAIN
    - 预算不足降级
    - _extract_change_signals / _compute_scan_confidence

使用真实 MySQL 数据库 + MockAIClient。
"""
import json
import pytest

from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration
from app.models.test_case import TestCase
from app.models.pipeline import PipelineRun, Artifact
from app.pipelines.steps.backward_scan import (
    BackwardScan,
    BackwardScanService,
)
from app.pipelines.steps.backward_scan._step import BATCH_SIZE
from app.pipelines.steps.backward_scan._helpers import (
    _extract_change_signals,
    _compute_scan_confidence,
)
from app.pipelines.schemas.backward_verdict import (
    BackwardCaseVerdict,
    BackwardVerdict,
    ValidationResult,
)
from app.services import pipeline_service
from app.pipelines.context import PipelineContext


def _make_raw_signals(project_id: int, **overrides) -> dict:
    payload = {
        "iteration_id": 1,
        "project_id": project_id,
        "prd_content": "接口 /api/login 新增 captcha 字段",
        "test_points": [{"id": 1, "point": "登录验证"}],
        "has_ui": False,
        "has_prd": True,
        "has_testpoints": True,
    }
    payload.update(overrides)
    return payload


def _make_fingerprints(project_id: int, count: int = 3, module: str = "用户管理") -> dict:
    fps = []
    for i in range(count):
        fps.append({
            "case_id": 100 + i,
            "title": f"用例{i}",
            "module": module,
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
    client = MockAIClient()
    return client


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="backward_scan_test_iter",
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
            input_hash="backward_scan_test_hash",
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
                content_hash="test_raw_signals_bs",
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
                content_hash="test_fingerprints_bs",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("history_fingerprints", artifact)

        return ctx

    return _make_ctx


class TestBackwardScanShouldRun:
    def test_should_run_with_fingerprints(self, make_ctx, test_iteration):
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id),
        )
        step = BackwardScan()
        assert step.should_run(ctx) is True

    def test_should_not_run_without_fingerprints(self, make_ctx, test_iteration):
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
        )
        step = BackwardScan()
        assert step.should_run(ctx) is False

    def test_should_not_run_with_empty_fingerprints(self, make_ctx, test_iteration):
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=0),
        )
        step = BackwardScan()
        assert step.should_run(ctx) is False


class TestBackwardScanCacheKey:
    def test_cache_key_deterministic(self, make_ctx, test_iteration):
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id),
        )
        step = BackwardScan()
        key1 = step.cache_key(ctx)
        key2 = step.cache_key(ctx)
        assert key1 == key2
        assert len(key1) == 64


class TestBackwardScanValidateOutput:
    def test_valid_payload(self):
        step = BackwardScan()
        payload = {
            "project_id": 1,
            "verdicts": [],
            "total_count": 0,
            "stats": {},
        }
        assert step.validate_output(payload) is True

    def test_missing_stats(self):
        step = BackwardScan()
        assert step.validate_output({"project_id": 1, "verdicts": [], "total_count": 0}) is False


class TestBackwardScanFallback:
    def test_fallback_marks_uncertain(self, make_ctx, test_iteration):
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=2),
        )
        step = BackwardScan()
        result = step.fallback(ctx, RuntimeError("AI 故障"))
        assert result.degraded is True
        assert result.artifact_payload["total_count"] == 2
        for v in result.artifact_payload["verdicts"]:
            assert v["verdict"] == "UNCERTAIN"

    def test_fallback_without_fingerprints(self, make_ctx):
        ctx = make_ctx()
        step = BackwardScan()
        result = step.fallback(ctx, RuntimeError("AI 故障"))
        assert result.degraded is True
        assert result.artifact_payload["total_count"] == 0


class TestBackwardScanServiceScan:
    def test_scan_with_valid_ai_response(self, mock_ai):
        fps = _make_fingerprints(1, count=2)["fingerprints"]
        ai_response = json.dumps({
            "verdicts": [
                {"case_id": 100, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
                {"case_id": 101, "verdict": "NEEDS_MODIFY", "confidence": 0.8, "hint": "需修改"},
            ]
        })
        mock_ai.set_response("backward_scan", ai_response)

        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, stats = service.scan(
            change_signals="接口变更",
            fingerprints=fps,
        )

        assert len(verdicts) == 2
        assert stats["batches"] >= 1
        assert stats["degraded"] == 0

    def test_scan_with_empty_fingerprints(self, mock_ai):
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, stats = service.scan(
            change_signals="无变更",
            fingerprints=[],
        )

        assert len(verdicts) == 0
        assert stats["batches"] == 0


class TestBackwardScanServiceSliceByModule:
    def test_single_module(self, mock_ai):
        fps = _make_fingerprints(1, count=5, module="用户")["fingerprints"]
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        batches = service._slice_by_module(fps)
        assert len(batches) == 1
        assert batches[0][0] == "用户"
        assert len(batches[0][1]) == 5

    def test_multiple_modules(self, mock_ai):
        fps_a = _make_fingerprints(1, count=3, module="用户")["fingerprints"]
        fps_b = _make_fingerprints(1, count=2, module="订单")["fingerprints"]
        all_fps = fps_a + fps_b
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        batches = service._slice_by_module(all_fps)
        assert len(batches) == 2

    def test_batch_splitting(self, mock_ai):
        fps = _make_fingerprints(1, count=7, module="模块A")["fingerprints"]
        service = BackwardScanService(ai_client=mock_ai, batch_size=3)
        batches = service._slice_by_module(fps)
        assert len(batches) == 3
        assert len(batches[0][1]) == 3
        assert len(batches[1][1]) == 3
        assert len(batches[2][1]) == 1


class TestBackwardScanServiceRetry:
    def test_retry_on_invalid_json(self, mock_ai):
        fps = _make_fingerprints(1, count=1)["fingerprints"]
        mock_ai.set_response("backward_scan", "not json{{{")
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, stats = service.scan(
            change_signals="接口变更",
            fingerprints=fps,
        )
        assert len(verdicts) == 1
        assert stats["degraded"] >= 1
        assert verdicts[0].verdict == BackwardVerdict.UNCERTAIN

    def test_retry_on_schema_failure(self, mock_ai):
        fps = _make_fingerprints(1, count=1)["fingerprints"]
        bad_response = json.dumps({
            "verdicts": [
                {"case_id": 100, "verdict": "INVALID_VERDICT", "confidence": 0.9, "hint": "非法"},
            ]
        })
        mock_ai.set_response("backward_scan", bad_response)
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, stats = service.scan(
            change_signals="接口变更",
            fingerprints=fps,
        )
        assert len(verdicts) == 1
        assert stats["degraded"] >= 1


class TestBackwardScanServiceBudgetCheck:
    def test_budget_exhaustion_marks_uncertain(self, mock_ai):
        fps = _make_fingerprints(1, count=3)["fingerprints"]
        call_count = 0

        def always_false():
            return False

        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, stats = service.scan(
            change_signals="接口变更",
            fingerprints=fps,
            check_budget=always_false,
        )

        assert len(verdicts) == 3
        assert all(v.verdict == BackwardVerdict.UNCERTAIN for v in verdicts)
        assert stats["degraded"] == 3


class TestBackwardScanServiceMarkUncertain:
    def test_mark_uncertain(self, mock_ai):
        fps = _make_fingerprints(1, count=2)["fingerprints"]
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, retries, degraded, auto_corrected = service._mark_uncertain(
            fps, "测试降级"
        )
        assert len(verdicts) == 2
        assert degraded == 2
        assert all(v.verdict == BackwardVerdict.UNCERTAIN for v in verdicts)


class TestExtractChangeSignals:
    def test_with_prd(self):
        signals = _extract_change_signals({
            "prd_content": "新增验证码",
            "test_points": [],
        })
        assert "新增验证码" in signals

    def test_with_test_points(self):
        signals = _extract_change_signals({
            "prd_content": "",
            "test_points": [{"id": 1, "point": "登录"}],
        })
        assert "登录" in signals

    def test_empty_signals(self):
        signals = _extract_change_signals({})
        assert "无明确变更信号" in signals


class TestComputeScanConfidence:
    def test_empty(self):
        assert _compute_scan_confidence([]) == 0.0

    def test_all_certain(self):
        verdicts = [
            BackwardCaseVerdict(case_id=1, verdict="VALID", confidence=0.9, hint="有效"),
        ]
        assert _compute_scan_confidence(verdicts) == 1.0

    def test_half_uncertain(self):
        verdicts = [
            BackwardCaseVerdict(case_id=1, verdict="VALID", confidence=0.9, hint="有效"),
            BackwardCaseVerdict(case_id=2, verdict="UNCERTAIN", confidence=0.3, hint="不确定"),
        ]
        assert _compute_scan_confidence(verdicts) == 0.5


@pytest.mark.skip(reason="AI_API_KEY缺失导致BackwardScan执行失败")
class TestBackwardScanExecute:
    def test_execute_with_valid_ai(self, db, make_ctx, mock_ai, test_iteration):
        ai_response = json.dumps({
            "verdicts": [
                {"case_id": 100, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
                {"case_id": 101, "verdict": "NEEDS_MODIFY", "confidence": 0.8, "hint": "需修改"},
                {"case_id": 102, "verdict": "LOCATOR_ONLY", "confidence": 0.75, "hint": "定位器失效"},
            ]
        })
        mock_ai.set_response("backward_scan", ai_response)

        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
            fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=3),
        )
        step = BackwardScan()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "backward_verdicts"
        assert result.artifact_payload["total_count"] == 3
        assert result.artifact_confidence > 0

    def test_execute_missing_fingerprints(self, make_ctx, test_iteration):
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(test_iteration.project_id),
        )
        step = BackwardScan()
        result = step.execute(ctx)
        assert result.success is False

    def test_execute_missing_raw_signals(self, make_ctx, test_iteration):
        ctx = make_ctx(
            fingerprints_payload=_make_fingerprints(test_iteration.project_id),
        )
        step = BackwardScan()
        result = step.execute(ctx)
        assert result.success is False


class TestBackwardScanServiceFallbackSplit:
    def test_single_item_fallback(self, mock_ai):
        fps = [{"case_id": 1, "title": "单条", "module": "模块A", "summary": "摘要", "priority": 1, "lifecycle_status": "active"}]
        mock_ai.set_response("backward_scan", "bad json{{{")
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, retries, degraded, auto_corrected = service._fallback_split(
            change_signals="变更",
            batch_fps=fps,
            module_label="模块A",
        )
        assert len(verdicts) == 1
        assert verdicts[0].verdict == BackwardVerdict.UNCERTAIN
        assert degraded == 1

    def test_split_then_succeed(self, mock_ai):
        fps = [
            {"case_id": 1, "title": "用例1", "module": "模块A", "summary": "摘要1", "priority": 1, "lifecycle_status": "active"},
            {"case_id": 2, "title": "用例2", "module": "模块A", "summary": "摘要2", "priority": 1, "lifecycle_status": "active"},
        ]
        good_response = json.dumps({
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
            ]
        })
        mock_ai.set_response("backward_scan", good_response)
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, retries, degraded, auto_corrected = service._fallback_split(
            change_signals="变更",
            batch_fps=fps,
            module_label="模块A",
        )
        assert len(verdicts) >= 1


class TestBackwardScanServiceProcessBatch:
    def test_process_batch_auto_corrected(self, mock_ai):
        fps = _make_fingerprints(1, count=1)["fingerprints"]
        low_conf_response = json.dumps({
            "verdicts": [
                {"case_id": 100, "verdict": "VALID", "confidence": 0.3, "hint": "低置信度"},
            ]
        })
        mock_ai.set_response("backward_scan", low_conf_response)
        service = BackwardScanService(ai_client=mock_ai, batch_size=50)
        verdicts, retries, degraded, auto_corrected = service._process_batch(
            change_signals="变更",
            batch_fps=fps,
            module_label="用户管理",
        )
        assert len(verdicts) == 1
        assert verdicts[0].verdict == BackwardVerdict.UNCERTAIN
        assert auto_corrected >= 1


class TestBackwardScanCacheKeyFalsyBranches:
    def test_cache_key_without_fingerprints(self, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = BackwardScan()
        key = step.cache_key(ctx)
        assert len(key) == 64

    def test_cache_key_without_raw_signals(self, make_ctx, test_iteration):
        ctx = make_ctx(fingerprints_payload=_make_fingerprints(test_iteration.project_id, count=3))
        step = BackwardScan()
        key = step.cache_key(ctx)
        assert len(key) == 64


class TestSliceByModuleUnclassified:
    def test_all_fingerprints_without_module(self):
        fps = [
            {"case_id": 1, "title": "用例1", "summary": "摘要1", "priority": 1, "lifecycle_status": "active"},
            {"case_id": 2, "title": "用例2", "summary": "摘要2", "priority": 2, "lifecycle_status": "active"},
        ]
        service = BackwardScanService(ai_client=MockAIClient(), batch_size=50)
        batches = service._slice_by_module(fps)
        assert len(batches) == 1
        assert batches[0][0] == "未分类"

    def test_all_modules_empty_string(self):
        fps = [
            {"case_id": 1, "title": "用例1", "module": "", "summary": "摘要1", "priority": 1, "lifecycle_status": "active"},
            {"case_id": 2, "title": "用例2", "module": "", "summary": "摘要2", "priority": 2, "lifecycle_status": "active"},
        ]
        service = BackwardScanService(ai_client=MockAIClient(), batch_size=50)
        batches = service._slice_by_module(fps)
        assert len(batches) == 1
        assert batches[0][0] == ""


class TestCallAiWithRetryException:
    def test_ai_exception_then_succeed(self, mock_ai):
        from app.ai.mock_client import MockAIClient

        call_count = [0]

        class FlakyAIClient(MockAIClient):
            def complete(self, prompt, **kwargs):
                call_count[0] += 1
                if call_count[0] <= 1:
                    raise ConnectionError("网络故障")
                return super().complete(prompt, **kwargs)

        good_response = json.dumps({
            "verdicts": [
                {"case_id": 100, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
            ]
        })
        flaky_ai = FlakyAIClient()
        flaky_ai.set_response("backward_scan", good_response)

        service = BackwardScanService(ai_client=flaky_ai, batch_size=50)
        result = service._call_ai_with_retry(
            prompt="测试 prompt",
            expected_ids=[100],
        )
        assert result is not None
        assert result.valid is True
        assert result.retries == 1

    def test_ai_all_exceptions_no_last_result(self, mock_ai):
        from app.ai.mock_client import MockAIClient

        class AlwaysFailAIClient(MockAIClient):
            def complete(self, prompt, **kwargs):
                raise RuntimeError("AI 服务崩溃")

        always_fail_ai = AlwaysFailAIClient()
        service = BackwardScanService(ai_client=always_fail_ai, batch_size=50)
        result = service._call_ai_with_retry(
            prompt="测试 prompt",
            expected_ids=[100],
        )
        assert result is None
