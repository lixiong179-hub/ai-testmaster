"""Legacy 用例生成执行行为护栏（G-8 B5e：`_execute_legacy` 拆分前置测试）。

锁定：aligned / signals 两种测试点来源、空响应与解析失败的两轮重试语义、
覆盖率缺口补生成、degraded 标记透传、异常降级为 failed 条目。
"""

from types import SimpleNamespace

import pytest

from app.pipelines.context import PipelineContext
from app.pipelines.steps import _execution, _parsing


def _ctx(ai_client) -> PipelineContext:
    ctx = PipelineContext(db=None, ai_client=ai_client, run=SimpleNamespace(id=1), iteration_id=9)
    ctx.get_ai_client = lambda: ai_client
    return ctx


def _client(*responses) -> SimpleNamespace:
    calls: list[dict] = []

    def _complete(**kwargs):
        calls.append(kwargs)
        result = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(result, Exception):
            raise result
        return result

    return SimpleNamespace(complete=_complete, calls=calls)


def _tp(tp_id: int = 11) -> dict:
    return {"id": tp_id, "module": "订单", "function": "创建", "point": "下单"}


@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch):
    monkeypatch.setattr(_execution, "_build_full_prompt", lambda **kwargs: "PROMPT")
    monkeypatch.setattr(_execution, "_enrich_case_data", lambda parsed, tp, has_ui: list(parsed))
    monkeypatch.setattr(_execution, "_dedup_cases_by_title", lambda cases: cases)
    monkeypatch.setattr(_execution, "_check_type_coverage", lambda cases: [])
    monkeypatch.setattr(_execution, "_generate_supplemental", lambda **kwargs: [])


def _run(ctx, aligned, signals=None):
    return _execution._execute_legacy(
        ctx,
        aligned,
        signals,
        "PRD 内容",
        "UI 描述",
        [],
        False,
    )


class TestTestPointSource:
    def test_aligned_testpoints_used(self, monkeypatch):
        monkeypatch.setattr(_parsing, "_parse_case_response", lambda content: [{"title": "用例A"}])
        client = _client(SimpleNamespace(content="ok", degraded=False))
        aligned = {"aligned_testpoints": [{"test_point": _tp(1)}, {"test_point": _tp(2)}]}

        cases, failed = _run(_ctx(client), aligned)

        assert failed == 0
        assert len(cases) == 2
        assert len(client.calls) == 2
        assert cases[0]["status"] == "success"
        assert cases[0]["case_data"] == [{"title": "用例A"}]

    def test_signals_fallback_skips_none(self, monkeypatch):
        monkeypatch.setattr(_parsing, "_parse_case_response", lambda content: [{"title": "用例B"}])
        client = _client(SimpleNamespace(content="ok", degraded=False))

        cases, _ = _run(_ctx(client), None, {"test_points": [_tp(3), None]})

        assert len(cases) == 1
        assert cases[0]["test_point"] == _tp(3)

    def test_request_metadata(self, monkeypatch):
        monkeypatch.setattr(_parsing, "_parse_case_response", lambda content: [{"title": "用例C"}])
        client = _client(SimpleNamespace(content="ok", degraded=False))

        _run(_ctx(client), {"aligned_testpoints": [{"test_point": _tp(5)}]})

        metadata = client.calls[0]["metadata"]
        assert metadata["step_name"] == "case_generation"
        assert metadata["test_point_id"] == 5
        assert metadata["iteration_id"] == 9
        assert metadata["attempt"] == 1


class TestRetrySemantics:
    def test_empty_content_exhausts_retries(self, monkeypatch):
        monkeypatch.setattr(_parsing, "_parse_case_response", lambda content: [{"title": "X"}])
        client = _client(SimpleNamespace(content="", degraded=False))

        cases, failed = _run(_ctx(client), {"aligned_testpoints": [{"test_point": _tp()}]})

        assert failed == 1
        assert len(client.calls) == 2
        assert cases[0]["status"] == "failed"
        assert cases[0]["error"] == "AI 返回空内容（重试后仍失败）"

    def test_parse_failure_exhausts_retries(self, monkeypatch):
        monkeypatch.setattr(_parsing, "_parse_case_response", lambda content: None)
        client = _client(SimpleNamespace(content="不是 JSON", degraded=False))

        cases, failed = _run(_ctx(client), {"aligned_testpoints": [{"test_point": _tp()}]})

        assert failed == 1
        assert cases[0]["error"] == "AI 响应解析失败（重试后仍失败）"

    def test_second_attempt_succeeds(self, monkeypatch):
        responses = iter([[], [{"title": "用例D"}]])

        def _parse(content):
            return next(responses)

        monkeypatch.setattr(_parsing, "_parse_case_response", _parse)
        client = _client(
            SimpleNamespace(content="bad", degraded=False),
            SimpleNamespace(content="good", degraded=True),
        )

        cases, failed = _run(_ctx(client), {"aligned_testpoints": [{"test_point": _tp()}]})

        assert failed == 0
        assert len(client.calls) == 2
        assert cases[0]["degraded"] is True
        assert cases[0]["case_data"] == [{"title": "用例D"}]


class TestCoverageAndFailure:
    def test_coverage_gap_triggers_supplemental(self, monkeypatch):
        monkeypatch.setattr(_parsing, "_parse_case_response", lambda content: [{"title": "用例E"}])
        coverage_results = iter([["negative"], []])
        monkeypatch.setattr(_execution, "_check_type_coverage", lambda cases: next(coverage_results))
        monkeypatch.setattr(_execution, "_generate_supplemental", lambda **kwargs: [{"title": "补丁用例"}])
        client = _client(SimpleNamespace(content="ok", degraded=False))

        cases, failed = _run(_ctx(client), {"aligned_testpoints": [{"test_point": _tp()}]})

        assert failed == 0
        assert [c["title"] for c in cases[0]["case_data"]] == ["用例E", "补丁用例"]
        assert cases[0]["coverage_gap"] == []

    def test_exception_marks_entry_failed(self, monkeypatch):
        def _boom(**kwargs):
            raise RuntimeError("prompt 构建失败")

        monkeypatch.setattr(_execution, "_build_full_prompt", _boom)
        client = _client(SimpleNamespace(content="ok", degraded=False))

        cases, failed = _run(_ctx(client), {"aligned_testpoints": [{"test_point": _tp()}]})

        assert failed == 1
        assert cases[0]["status"] == "failed"
        assert cases[0]["error"] == "prompt 构建失败"
        assert client.calls == []
