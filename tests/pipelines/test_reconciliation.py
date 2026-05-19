"""M2-T07 Reconciliation Step 单元测试

覆盖：
    - Reconciliation Step: should_run / cache_key / execute / validate_output / fallback
    - merge() 纯函数：plan §6 矩阵所有 15 个格子 + NEW/无反向匹配
    - _lookup_matrix: 有效输入/无效输入/冲突检测
    - MergedAction 枚举所有值
    - 边界：空输入、缺失 case_id、前向后向互斥
    - _verdict_to_dict / _compute_reconciliation_stats / _compute_avg_confidence

使用真实 MySQL 数据库，零 AI 调用。
"""
import json

import pytest

from app.models.iteration import Iteration
from app.models.pipeline import Artifact
from app.pipelines.context import PipelineContext
from app.pipelines.steps.reconciliation import (
    CONFLICT_PAIRS,
    MERGE_MATRIX,
    MergedAction,
    MergedVerdict,
    Reconciliation,
    merge,
)
from app.pipelines.steps.reconciliation._merge import (
    _lookup_matrix,
    _verdict_to_dict,
    _compute_reconciliation_stats,
    _compute_avg_confidence,
)
from app.services import pipeline_service


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="recon_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def make_ctx(db, test_iteration):
    _hash_counter = [0]

    def _make_ctx(backward_payload=None, forward_payload=None):
        _hash_counter[0] += 1
        run = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash=f"recon_test_hash_{_hash_counter[0]}",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=None,
            run=run,
            iteration_id=test_iteration.id,
            user_id=1,
        )

        if backward_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="backward_verdicts",
                schema_version="1.0",
                payload=backward_payload,
                content_hash=f"test_bw_{_hash_counter[0]}",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("backward_verdicts", artifact)

        if forward_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="forward_verdicts",
                schema_version="1.0",
                payload=forward_payload,
                content_hash=f"test_fw_{_hash_counter[0]}",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("forward_verdicts", artifact)

        return ctx

    return _make_ctx


def _bw_artifact(project_id: int, verdicts: list) -> dict:
    return {
        "project_id": project_id,
        "verdicts": verdicts,
        "total_count": len(verdicts),
    }


def _fw_artifact(project_id: int, verdicts: list) -> dict:
    return {
        "project_id": project_id,
        "verdicts": verdicts,
        "total_count": len(verdicts),
        "stats": {"existing": 0, "modify": 0, "new": 0},
    }


def _bw_v(case_id: int, verdict: str, confidence: float = 0.8, hint: str = "") -> dict:
    return {"case_id": case_id, "verdict": verdict, "confidence": confidence, "hint": hint}


def _fw_v(candidate_index: int, label: str, matched_case_id=None, confidence=0.8, reason="") -> dict:
    return {
        "candidate_index": candidate_index,
        "label": label,
        "matched_case_id": matched_case_id,
        "confidence": confidence,
        "reason": reason,
    }


class TestReconciliationShouldRun:
    def test_with_both_artifacts(self, db, make_ctx, test_iteration):
        ctx = make_ctx(
            backward_payload=_bw_artifact(test_iteration.project_id, [_bw_v(100, "VALID")]),
            forward_payload=_fw_artifact(test_iteration.project_id, [_fw_v(0, "NEW")]),
        )
        assert Reconciliation().should_run(ctx) is True

    def test_with_only_backward(self, db, make_ctx, test_iteration):
        ctx = make_ctx(backward_payload=_bw_artifact(test_iteration.project_id, [_bw_v(100, "VALID")]))
        assert Reconciliation().should_run(ctx) is True

    def test_with_only_forward(self, db, make_ctx, test_iteration):
        ctx = make_ctx(forward_payload=_fw_artifact(test_iteration.project_id, [_fw_v(0, "NEW")]))
        assert Reconciliation().should_run(ctx) is True

    def test_with_neither(self, make_ctx):
        assert Reconciliation().should_run(make_ctx()) is False


class TestReconciliationCacheKey:
    def test_cache_key_deterministic(self, db, make_ctx, test_iteration):
        bw = _bw_artifact(test_iteration.project_id, [_bw_v(100, "VALID")])
        fw = _fw_artifact(test_iteration.project_id, [_fw_v(0, "NEW")])
        key1 = Reconciliation().cache_key(make_ctx(backward_payload=bw, forward_payload=fw))
        key2 = Reconciliation().cache_key(make_ctx(backward_payload=bw, forward_payload=fw))
        assert key1 == key2

    def test_cache_key_different_counts(self, db, make_ctx, test_iteration):
        key1 = Reconciliation().cache_key(
            make_ctx(
                backward_payload=_bw_artifact(test_iteration.project_id, [_bw_v(100, "VALID")]),
                forward_payload=_fw_artifact(test_iteration.project_id, [_fw_v(0, "NEW")]),
            )
        )
        key2 = Reconciliation().cache_key(
            make_ctx(
                backward_payload=_bw_artifact(test_iteration.project_id, [_bw_v(100, "VALID"), _bw_v(101, "DEPRECATED")]),
                forward_payload=_fw_artifact(test_iteration.project_id, [_fw_v(0, "NEW")]),
            )
        )
        assert key1 != key2


class TestReconciliationValidateOutput:
    def test_valid(self):
        payload = {"project_id": 1, "verdicts": [], "total_count": 0, "stats": {}}
        assert Reconciliation().validate_output(payload) is True

    def test_missing_stats(self):
        payload = {"project_id": 1, "verdicts": [], "total_count": 0}
        assert Reconciliation().validate_output(payload) is False

    def test_count_mismatch(self):
        payload = {"project_id": 1, "verdicts": [{"a": 1}], "total_count": 5, "stats": {}}
        assert Reconciliation().validate_output(payload) is False


class TestReconciliationFallback:
    def test_fallback_degraded(self, db, make_ctx, test_iteration):
        ctx = make_ctx(backward_payload=_bw_artifact(test_iteration.project_id, [_bw_v(100, "VALID")]))
        result = Reconciliation().fallback(ctx, RuntimeError("异常"))
        assert result.success is True
        assert result.degraded is True
        assert result.artifact_kind == "merged_verdicts"
        assert result.artifact_confidence == 0.0
        assert result.artifact_payload["verdicts"] == []

    def test_fallback_no_artifacts(self, make_ctx):
        result = Reconciliation().fallback(make_ctx(), RuntimeError("异常"))
        assert result.success is True
        assert result.artifact_payload["project_id"] == 0


class TestReconciliationExecute:
    def test_execute_valid(self, db, make_ctx, test_iteration):
        ctx = make_ctx(
            backward_payload=_bw_artifact(test_iteration.project_id, [_bw_v(100, "VALID")]),
            forward_payload=_fw_artifact(test_iteration.project_id, [_fw_v(0, "EXISTING", matched_case_id=100)]),
        )
        result = Reconciliation().execute(ctx)
        assert result.success is True
        assert result.artifact_kind == "merged_verdicts"
        assert result.artifact_confidence > 0.0
        assert "stats" in result.artifact_payload

    def test_execute_without_artifacts(self, make_ctx):
        ctx = make_ctx()
        result = Reconciliation().execute(ctx)
        assert result.success is True
        assert result.artifact_payload["total_count"] == 0

    def test_execute_from_forward_sets_project_id(self, db, make_ctx, test_iteration):
        ctx = make_ctx(forward_payload=_fw_artifact(test_iteration.project_id, [_fw_v(0, "NEW")]))
        result = Reconciliation().execute(ctx)
        assert result.artifact_payload["project_id"] == test_iteration.project_id


class TestMergeMatrixCells:
    """覆盖 plan §6 矩阵所有 15 个格子。"""

    def test_valid_existing(self):
        result = merge([_bw_v(100, "VALID")], [_fw_v(0, "EXISTING", matched_case_id=100)])
        assert len(result) == 1
        assert result[0].action == MergedAction.KEEP
        assert result[0].conflict_marker is False

    def test_valid_modify(self):
        result = merge([_bw_v(100, "VALID")], [_fw_v(0, "MODIFY", matched_case_id=100)])
        assert len(result) == 1
        assert result[0].action == MergedAction.NEEDS_MODIFY

    def test_valid_no_forward(self):
        result = merge([_bw_v(100, "VALID")], [])
        assert len(result) == 1
        assert result[0].action == MergedAction.KEEP

    def test_locator_only_existing(self):
        result = merge([_bw_v(100, "LOCATOR_ONLY")], [_fw_v(0, "EXISTING", matched_case_id=100)])
        assert result[0].action == MergedAction.LOCATOR_BROKEN

    def test_locator_only_modify(self):
        result = merge([_bw_v(100, "LOCATOR_ONLY")], [_fw_v(0, "MODIFY", matched_case_id=100)])
        assert result[0].action == MergedAction.LOCATOR_AND_MODIFY

    def test_locator_only_no_forward(self):
        result = merge([_bw_v(100, "LOCATOR_ONLY")], [])
        assert result[0].action == MergedAction.LOCATOR_BROKEN

    def test_needs_modify_existing(self):
        result = merge([_bw_v(100, "NEEDS_MODIFY")], [_fw_v(0, "EXISTING", matched_case_id=100)])
        assert result[0].action == MergedAction.NEEDS_MODIFY

    def test_needs_modify_modify(self):
        result = merge([_bw_v(100, "NEEDS_MODIFY")], [_fw_v(0, "MODIFY", matched_case_id=100)])
        assert result[0].action == MergedAction.NEEDS_MODIFY

    def test_needs_modify_no_forward(self):
        result = merge([_bw_v(100, "NEEDS_MODIFY")], [])
        assert result[0].action == MergedAction.NEEDS_MODIFY

    def test_deprecated_existing_conflict(self):
        result = merge([_bw_v(100, "DEPRECATED")], [_fw_v(0, "EXISTING", matched_case_id=100)])
        assert result[0].action == MergedAction.CONFLICT
        assert result[0].conflict_marker is True

    def test_deprecated_modify_conflict(self):
        result = merge([_bw_v(100, "DEPRECATED")], [_fw_v(0, "MODIFY", matched_case_id=100)])
        assert result[0].action == MergedAction.CONFLICT
        assert result[0].conflict_marker is True

    def test_deprecated_no_forward(self):
        result = merge([_bw_v(100, "DEPRECATED")], [])
        assert result[0].action == MergedAction.DEPRECATE
        assert result[0].conflict_marker is False

    def test_uncertain_existing(self):
        result = merge([_bw_v(100, "UNCERTAIN")], [_fw_v(0, "EXISTING", matched_case_id=100)])
        assert result[0].action == MergedAction.PENDING_REVIEW

    def test_uncertain_modify(self):
        result = merge([_bw_v(100, "UNCERTAIN")], [_fw_v(0, "MODIFY", matched_case_id=100)])
        assert result[0].action == MergedAction.PENDING_REVIEW

    def test_uncertain_no_forward(self):
        result = merge([_bw_v(100, "UNCERTAIN")], [])
        assert result[0].action == MergedAction.PENDING_REVIEW


class TestMergeForwardOnly:
    def test_forward_new_no_match(self):
        result = merge([], [_fw_v(0, "NEW")])
        assert len(result) == 1
        assert result[0].action == MergedAction.ADD_NEW
        assert result[0].source == "forward_only"

    def test_forward_new_even_with_backward(self):
        result = merge([_bw_v(100, "VALID")], [_fw_v(0, "NEW")])
        assert result[0].action == MergedAction.ADD_NEW

    def test_forward_existing_no_backward_match(self):
        result = merge([], [_fw_v(0, "EXISTING", matched_case_id=999)])
        assert result[0].action == MergedAction.ADD_NEW
        assert "未找到反向裁决" in result[0].reason


class TestMergeBackwardOnly:
    def test_multiple_backward_all_unmatched(self):
        result = merge(
            [_bw_v(100, "VALID"), _bw_v(101, "NEEDS_MODIFY")],
            [_fw_v(0, "NEW")],
        )
        actions = {v.case_id: v.action for v in result}
        assert actions[100] == MergedAction.KEEP
        assert actions[101] == MergedAction.NEEDS_MODIFY

    def test_backward_mixed_with_forward_matches(self):
        result = merge(
            [_bw_v(100, "VALID"), _bw_v(101, "NEEDS_MODIFY")],
            [_fw_v(0, "EXISTING", matched_case_id=100)],
        )
        actions = {v.case_id: v.action for v in result if v.case_id is not None}
        assert actions[100] == MergedAction.KEEP
        assert actions[101] == MergedAction.NEEDS_MODIFY


class TestMergeEdgeCases:
    def test_empty_both(self):
        assert merge([], []) == []

    def test_forward_missing_label_defaults_new(self):
        result = merge([], [{"candidate_index": 0, "confidence": 0.8}])
        assert result[0].action == MergedAction.ADD_NEW

    def test_backward_missing_case_id_skipped(self):
        result = merge([{"verdict": "VALID", "confidence": 0.8, "hint": ""}], [])
        assert result == []

    def test_confidence_min_of_both(self):
        result = merge(
            [_bw_v(100, "VALID", confidence=0.9)],
            [_fw_v(0, "MODIFY", matched_case_id=100, confidence=0.5)],
        )
        assert result[0].confidence == 0.5

    def test_multiple_forward_same_case_id(self):
        result = merge(
            [_bw_v(100, "VALID")],
            [
                _fw_v(0, "EXISTING", matched_case_id=100),
                _fw_v(1, "MODIFY", matched_case_id=100),
            ],
        )
        merged = [v for v in result if v.source == "merged"]
        assert len(merged) == 2
        assert merged[0].action == MergedAction.KEEP
        assert merged[1].action == MergedAction.NEEDS_MODIFY


class TestLookupMatrix:
    def test_valid_existing(self):
        action, conflict = _lookup_matrix("VALID", "EXISTING")
        assert action == MergedAction.KEEP
        assert conflict is False

    def test_deprecated_modify_conflict(self):
        action, conflict = _lookup_matrix("DEPRECATED", "MODIFY")
        assert action == MergedAction.CONFLICT
        assert conflict is True

    def test_unknown_verdict_defaults(self):
        action, conflict = _lookup_matrix("NONEXISTENT", "EXISTING")
        assert action == MergedAction.PENDING_REVIEW
        assert conflict is False

    def test_none_label(self):
        action, conflict = _lookup_matrix("VALID", None)
        assert action == MergedAction.KEEP
        assert conflict is False


class TestMergedActionEnum:
    def test_all_values_in_matrix(self):
        values = {"keep", "needs_modify", "locator_broken", "locator_and_modify",
                  "deprecate", "add_new", "conflict", "pending_review"}
        assert set(a.value for a in MergedAction) == values

    def test_conflict_pairs(self):
        assert ("DEPRECATED", "EXISTING") in CONFLICT_PAIRS
        assert ("DEPRECATED", "MODIFY") in CONFLICT_PAIRS


class TestVerdictToDict:
    def test_all_fields_serialized(self):
        v = MergedVerdict(
            source="merged",
            case_id=100,
            candidate_index=0,
            action=MergedAction.KEEP,
            backward_verdict="VALID",
            forward_label="EXISTING",
            confidence=0.9,
            reason="无需变更",
            conflict_marker=False,
        )
        d = _verdict_to_dict(v)
        assert d["source"] == "merged"
        assert d["action"] == "keep"
        assert d["conflict_marker"] is False


class TestComputeReconciliationStats:
    def test_all_actions_counted(self):
        v1 = MergedVerdict("merged", 100, 0, MergedAction.KEEP, "VALID", "EXISTING", 0.9, "r", False)
        v2 = MergedVerdict("backward_only", 101, None, MergedAction.DEPRECATE, "DEPRECATED", None, 0.7, "r", False)
        stats = _compute_reconciliation_stats([v1, v2])
        assert stats["keep"] == 1
        assert stats["deprecate"] == 1
        assert sum(stats.values()) == 2


class TestComputeAvgConfidence:
    def test_normal(self):
        v1 = MergedVerdict("merged", 100, 0, MergedAction.KEEP, "VALID", "EXISTING", 0.9, "r", False)
        v2 = MergedVerdict("merged", 101, 1, MergedAction.NEEDS_MODIFY, "NEEDS_MODIFY", "MODIFY", 0.5, "r", False)
        assert _compute_avg_confidence([v1, v2]) == pytest.approx(0.7)

    def test_empty(self):
        assert _compute_avg_confidence([]) == 0.0
