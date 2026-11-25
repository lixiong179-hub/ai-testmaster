"""QualityGate.execute 编排行为护栏（G-8 B5a：`execute` 拆分前置测试）。

既有 `test_quality_gate.py` 覆盖评分函数本身，这里只锁定编排语义：
产物缺失短路、按用例/按测试点覆盖度调整、逐条回写先验分与生命周期、
重生成钩子与临时字段清理、payload 汇总字段、analyzer 成功/初始化失败两条路径。
"""

from types import SimpleNamespace

import pytest

from app.pipelines.context import PipelineContext
from app.pipelines.steps import quality_gate as qg


def _ctx(artifacts: dict[str, dict], iteration_id: int = 1, db=None) -> PipelineContext:
    ctx = PipelineContext(db=db, ai_client=None, run=SimpleNamespace(id=1), iteration_id=iteration_id)
    for kind, payload in artifacts.items():
        ctx.set_artifact(kind, SimpleNamespace(payload=payload))
    return ctx


def _cases(*, case_data: list[dict], coverage_gap: list[str] | None = None, status: str = "success") -> dict:
    entry = {"status": status, "case_data": case_data, "test_point": {"id": 11}}
    if coverage_gap is not None:
        entry["coverage_gap"] = coverage_gap
    return {"project_id": 99, "generated_cases": [entry]}


@pytest.fixture(autouse=True)
def _patch_helpers(monkeypatch):
    """隔离评分公式与覆盖度计算，只验证编排。"""
    monkeypatch.setattr(qg, "_compute_module_coverage", lambda cases: {"m1": 1.0})
    monkeypatch.setattr(qg, "_compute_ui_element_coverage", lambda signals, cases: {"ui": 0.5})
    monkeypatch.setattr(qg, "_collect_d_grade_cases", lambda cases: [])
    monkeypatch.setattr(qg, "_regenerate_d_cases", lambda *args, **kwargs: None)
    monkeypatch.setattr(qg, "_check_user_confirmed", lambda db, iteration_id: False)


def _patch_prior(monkeypatch, score: float = 80.0, grade: str = "B") -> list[dict]:
    calls: list[dict] = []

    def _fake(case_data, tp, signals, inferred, aligned, iteration_id, db, user_confirmed=False):
        calls.append({"case_data": case_data, "tp": tp, "user_confirmed": user_confirmed})
        return score, grade, {"base": score}

    monkeypatch.setattr(qg, "_compute_prior_score", _fake)
    return calls


class TestGuards:
    def test_missing_artifact_short_circuits(self):
        result = qg.QualityGate().execute(_ctx({}))

        assert result.success is False
        assert result.error == "缺少 generated_cases 产物"

    def test_no_success_entries_yields_zero_average(self, monkeypatch):
        _patch_prior(monkeypatch)
        ctx = _ctx({"generated_cases": _cases(case_data=[{"title": "A"}], status="failed")})

        payload = qg.QualityGate().execute(ctx).artifact_payload

        assert payload["total_graded"] == 0
        assert payload["average_score"] == 0.0
        assert payload["scores"] == []


class TestScoringLoop:
    def test_scores_each_case_and_writes_back_prior(self, monkeypatch):
        _patch_prior(monkeypatch, score=80.0, grade="B")
        case_data = [{"title": "用例1"}, {"title": "用例2"}]
        ctx = _ctx({"generated_cases": _cases(case_data=case_data, coverage_gap=[])})

        payload = qg.QualityGate().execute(ctx).artifact_payload

        assert payload["total_graded"] == 2
        assert payload["project_id"] == 99
        assert [s["test_point_id"] for s in payload["scores"]] == [11, 11]
        assert all("_score_idx" not in s for s in payload["scores"])
        assert case_data[0]["prior_quality_grade"] == "B"
        assert case_data[1]["prior_quality_score"] > 0

    def test_clean_coverage_gap_adds_positive_adjustment(self, monkeypatch):
        _patch_prior(monkeypatch, score=80.0, grade="B")
        ctx = _ctx({"generated_cases": _cases(case_data=[{"title": "A"}, {"title": "B"}], coverage_gap=[])})

        payload = qg.QualityGate().execute(ctx).artifact_payload

        assert payload["scores"][0]["breakdown"]["coverage_adjustment"] == 2.5
        assert payload["average_score"] == 82.5

    def test_coverage_gap_penalises_per_case(self, monkeypatch):
        _patch_prior(monkeypatch, score=80.0, grade="B")
        ctx = _ctx({"generated_cases": _cases(case_data=[{"title": "A"}, {"title": "B"}], coverage_gap=["x", "y"])})

        payload = qg.QualityGate().execute(ctx).artifact_payload

        assert payload["scores"][0]["breakdown"]["coverage_adjustment"] == -8.0
        assert payload["average_score"] == 72.0

    def test_d_grade_case_marked_pending_review(self, monkeypatch):
        _patch_prior(monkeypatch, score=20.0, grade="D")
        case_data = [{"title": "弱用例"}]
        ctx = _ctx({"generated_cases": _cases(case_data=case_data, coverage_gap=[])})

        payload = qg.QualityGate().execute(ctx).artifact_payload

        assert payload["needs_review_count"] == 1
        assert payload["scores"][0]["quality_status"] == "rejected"
        assert "_d_score_idx" not in case_data[0]

    def test_user_confirmed_passed_to_prior_scoring(self, monkeypatch):
        calls = _patch_prior(monkeypatch)
        ctx = _ctx({"generated_cases": _cases(case_data=[{"title": "A"}], coverage_gap=[])})

        qg.QualityGate().execute(ctx)

        assert calls[0]["user_confirmed"] is False
        assert calls[0]["tp"] == {"id": 11}


class TestAnalyzerPaths:
    def test_analyzer_score_preferred_over_prior(self, monkeypatch):
        prior_calls = _patch_prior(monkeypatch, score=80.0, grade="B")
        monkeypatch.setattr("app.services.case_quality.CaseQualityAnalyzer", lambda db: SimpleNamespace())
        monkeypatch.setattr(qg, "_compute_analyzer_score", lambda analyzer, case_data: (95.0, "A", {"base": 95.0}))
        ctx = _ctx({"generated_cases": _cases(case_data=[{"title": "A"}], coverage_gap=[])}, db=SimpleNamespace())

        payload = qg.QualityGate().execute(ctx).artifact_payload

        # 95 分 + 覆盖度无缺口奖励 5 分 → 封顶 100
        assert payload["average_score"] == 100.0
        assert payload["average_grade"] == "A"
        assert prior_calls == []

    def test_analyzer_failure_degrades_to_prior(self, monkeypatch):
        _patch_prior(monkeypatch, score=70.0, grade="C")
        monkeypatch.setattr("app.services.case_quality.CaseQualityAnalyzer", lambda db: SimpleNamespace())

        def _boom(analyzer, case_data):
            raise RuntimeError("analyzer down")

        monkeypatch.setattr(qg, "_compute_analyzer_score", _boom)
        ctx = _ctx({"generated_cases": _cases(case_data=[{"title": "A"}], coverage_gap=[])}, db=SimpleNamespace())

        payload = qg.QualityGate().execute(ctx).artifact_payload

        # 70 分 + 覆盖度无缺口奖励 5 分 → 75，等级按调整后分数重算
        assert payload["average_score"] == 75.0
        assert payload["average_grade"] == qg._score_to_grade(75.0)

    def test_analyzer_init_failure_degrades_to_prior(self, monkeypatch):
        _patch_prior(monkeypatch, score=60.0, grade="C")

        def _raise(db):
            raise RuntimeError("no session")

        monkeypatch.setattr("app.services.case_quality.CaseQualityAnalyzer", _raise)
        ctx = _ctx({"generated_cases": _cases(case_data=[{"title": "A"}], coverage_gap=[])}, db=SimpleNamespace())

        payload = qg.QualityGate().execute(ctx).artifact_payload

        # 60 分 + 覆盖度无缺口奖励 5 分
        assert payload["average_score"] == 65.0
        assert payload["module_coverage"] == {"m1": 1.0}
        assert payload["ui_element_coverage"] == {"ui": 0.5}
