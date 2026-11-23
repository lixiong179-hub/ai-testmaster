"""D 级用例重生成行为护栏（G-8 B5f：`_regenerate_d_cases` 拆分前置测试）。

锁定：空响应/解析失败静默跳过、成功时替换 D 级用例并补「regenerated」评分条目、
临时 `_d_score_idx` 清理、陈旧 `_score_idx` 条目剔除、D 级仍置 pending_review、
analyzer 优先与异常兜底。
"""

from types import SimpleNamespace

import pytest

from app.pipelines.steps import _regeneration, case_generation


def _entry(tp=None, d_cases=None, good_cases=None, entry_id=1):
    parent = {"test_point": tp or {"id": 11}, "case_data": []}
    parent["case_data"].extend(good_cases or [])
    parent["case_data"].extend(d_cases or [])
    return {
        "test_point": tp or {"id": 11},
        "d_cases": d_cases or [],
        "d_score_idxs": [c.get("_d_score_idx") for c in (d_cases or []) if c.get("_d_score_idx") is not None],
        "good_titles": [c.get("title", "") for c in (good_cases or [])],
        "parent_entry": parent,
    }


def _client(content="ok", error=None):
    calls: list[dict] = []

    def _complete(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return SimpleNamespace(content=content, degraded=False)

    return SimpleNamespace(complete=_complete, calls=calls)


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(case_generation, "_enrich_case_data", lambda parsed, tp, has_ui: list(parsed))
    monkeypatch.setattr(case_generation, "_check_type_coverage", lambda cases: [])
    monkeypatch.setattr(_regeneration, "_compute_prior_score", lambda *a, **k: (70.0, "C", {"base": 70.0}))
    monkeypatch.setattr(_regeneration, "_score_to_grade", lambda score: "D" if score < 60 else "C")


class TestSkipPaths:
    def test_empty_content_keeps_parent(self):
        monkeypatch_client = _client(content="")
        ctx = SimpleNamespace(ai_client=monkeypatch_client, iteration_id=1, db=None)
        d_case = {"title": "D用例", "prior_quality_grade": "D", "_d_score_idx": 0}
        d_entry = _entry(d_cases=[d_case])
        before = list(d_entry["parent_entry"]["case_data"])
        scores: list[dict] = []

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, scores)

        assert d_entry["parent_entry"]["case_data"] == before
        assert scores == []

    def test_parse_failure_keeps_parent(self, monkeypatch):
        monkeypatch.setattr(case_generation, "_parse_case_response", lambda content: None)
        ctx = SimpleNamespace(ai_client=_client(), iteration_id=1, db=None)
        d_entry = _entry(d_cases=[{"title": "D用例", "prior_quality_grade": "D"}])
        scores: list[dict] = []

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, scores)

        assert scores == []

    def test_exception_is_logged_not_raised(self):
        ctx = SimpleNamespace(ai_client=_client(error=RuntimeError("AI 挂了")), iteration_id=1, db=None)
        d_entry = _entry(d_cases=[{"title": "D用例", "prior_quality_grade": "D"}])

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, [])


class TestRegeneration:
    def test_replaces_d_cases_and_appends_scores(self, monkeypatch):
        monkeypatch.setattr(case_generation, "_parse_case_response", lambda content: [{"title": "新用例"}])
        ctx = SimpleNamespace(ai_client=_client(), iteration_id=1, db=None)
        good = {"title": "好用例", "prior_quality_grade": "B"}
        d_case = {"title": "D用例", "prior_quality_grade": "D", "_d_score_idx": 3}
        d_entry = _entry(d_cases=[d_case], good_cases=[good])
        scores: list[dict] = [{"_score_idx": 3, "case_title": "D用例"}]

        _regeneration._regenerate_d_cases(ctx, [d_entry], {"has_ui": False}, {}, {}, scores)

        titles = [c["title"] for c in d_entry["parent_entry"]["case_data"]]
        assert titles == ["好用例", "新用例"]
        assert "_d_score_idx" not in d_entry["parent_entry"]["case_data"][0]
        # 覆盖度无缺口 +5 分均摊到 2 条用例 → 每条 +2.5
        assert scores == [
            {
                "test_point_id": 11,
                "case_title": "新用例",
                "score": 72.5,
                "grade": "C",
                "breakdown": {"base": 70.0, "coverage_adjustment": 2.5},
                "lifecycle_status": "draft",
                "regenerated": True,
            }
        ]

    def test_still_d_grade_marked_pending_review(self, monkeypatch):
        monkeypatch.setattr(case_generation, "_parse_case_response", lambda content: [{"title": "仍差"}])
        monkeypatch.setattr(_regeneration, "_compute_prior_score", lambda *a, **k: (30.0, "D", {}))
        ctx = SimpleNamespace(ai_client=_client(), iteration_id=1, db=None)
        d_entry = _entry(d_cases=[{"title": "D用例", "prior_quality_grade": "D"}])
        scores: list[dict] = []

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, scores)

        regen_case = d_entry["parent_entry"]["case_data"][0]
        assert regen_case["lifecycle_status"] == "pending_review"
        assert scores[0]["lifecycle_status"] == "pending_review"

    def test_clean_coverage_adds_adjustment(self, monkeypatch):
        monkeypatch.setattr(case_generation, "_parse_case_response", lambda content: [{"title": "新用例"}])
        ctx = SimpleNamespace(ai_client=_client(), iteration_id=1, db=None)
        d_entry = _entry(d_cases=[{"title": "D用例", "prior_quality_grade": "D"}])
        scores: list[dict] = []

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, scores)

        assert scores[0]["breakdown"]["coverage_adjustment"] == 5.0
        assert scores[0]["score"] == 75.0

    def test_analyzer_preferred(self, monkeypatch):
        monkeypatch.setattr(case_generation, "_parse_case_response", lambda content: [{"title": "新用例"}])
        monkeypatch.setattr(_regeneration, "_compute_analyzer_score", lambda analyzer, case: (90.0, "A", {}))
        monkeypatch.setattr(_regeneration, "_compute_prior_score", lambda *a, **k: pytest.fail("不应走先验评分"))
        ctx = SimpleNamespace(ai_client=_client(), iteration_id=1, db=None)
        d_entry = _entry(d_cases=[{"title": "D用例", "prior_quality_grade": "D"}])
        scores: list[dict] = []

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, scores, analyzer=SimpleNamespace())

        assert scores[0]["score"] == 95.0

    def test_analyzer_exception_falls_back_to_prior(self, monkeypatch):
        monkeypatch.setattr(case_generation, "_parse_case_response", lambda content: [{"title": "新用例"}])
        monkeypatch.setattr(
            _regeneration, "_compute_analyzer_score", lambda analyzer, case: (_ for _ in ()).throw(RuntimeError("x"))
        )
        ctx = SimpleNamespace(ai_client=_client(), iteration_id=1, db=None)
        d_entry = _entry(d_cases=[{"title": "D用例", "prior_quality_grade": "D"}])
        scores: list[dict] = []

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, scores, analyzer=SimpleNamespace())

        assert scores[0]["score"] == 75.0

    def test_prompt_metadata_contains_regen_count(self, monkeypatch):
        monkeypatch.setattr(case_generation, "_parse_case_response", lambda content: [{"title": "新用例"}])
        client = _client()
        ctx = SimpleNamespace(ai_client=client, iteration_id=1, db=None)
        d_entry = _entry(d_cases=[{"title": "D1", "prior_quality_grade": "D"}])

        _regeneration._regenerate_d_cases(ctx, [d_entry], {}, {}, {}, [])

        metadata = client.calls[0]["metadata"]
        assert metadata["step_name"] == "quality_gate_regen"
        assert metadata["regen_count"] == 1
