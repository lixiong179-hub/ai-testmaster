"""
TestPointAlignment Step 专项测试

覆盖 TestPointAlignment 类所有方�?+ 所有纯函数的分支路径�?目标：line�?5%, branch�?5%�?"""
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from app.pipelines.steps.testpoint_alignment import (
    TestPointAlignment,
    _align_from_inferred_only,
    _build_no_match_note,
    _compute_alignment_confidence,
    _compute_coverage,
    _extract_inferred_capabilities,
    _extract_scenario_candidates,
    _find_matching_capability,
    _find_matching_scenario,
    _is_cjk,
    _is_significant_match,
)
from app.pipelines.base import StepResult
from app.pipelines.context import PipelineContext


class _FakeArtifact:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload


class _FakeRun:
    id = 1


def _make_ctx(
    iteration_id: int = 1,
    raw_signals: Optional[Dict[str, Any]] = None,
    inferred: Optional[Dict[str, Any]] = None,
    scenario_candidates: Optional[Dict[str, Any]] = None,
) -> PipelineContext:
    ctx = PipelineContext(
        db=MagicMock(),
        ai_client=MagicMock(),
        run=_FakeRun(),
        iteration_id=iteration_id,
    )
    if raw_signals is not None:
        ctx.set_artifact("raw_signals", _FakeArtifact(raw_signals))
    if inferred is not None:
        ctx.set_artifact("inferred_business_summary", _FakeArtifact(inferred))
    if scenario_candidates is not None:
        ctx.set_artifact("scenario_candidates", _FakeArtifact(scenario_candidates))
    return ctx


# ==================== _is_cjk ====================


class TestIsCJK:
    def test_chinese_char(self) -> None:
        assert _is_cjk("�?) is True

    def test_ascii_char(self) -> None:
        assert _is_cjk("a") is False

    def test_digit(self) -> None:
        assert _is_cjk("1") is False

    def test_cjk_extension_a(self) -> None:
        assert _is_cjk("\u3400") is True

    def test_cjk_extension_b(self) -> None:
        assert _is_cjk("\U00020000") is True

    def test_japanese_kana(self) -> None:
        assert _is_cjk("�?) is False


# ==================== _is_significant_match ====================


class TestIsSignificantMatch:
    def test_exact_match(self) -> None:
        assert _is_significant_match("登录", "登录") is True

    def test_cjk_substring_match(self) -> None:
        assert _is_significant_match("登录", "用户登录页面") is True

    def test_short_query_rejected(self) -> None:
        assert _is_significant_match("a", "abc") is False

    def test_empty_query(self) -> None:
        assert _is_significant_match("", "target") is False

    def test_empty_target(self) -> None:
        assert _is_significant_match("query", "") is False

    def test_not_found(self) -> None:
        assert _is_significant_match("注册", "登录页面") is False

    def test_long_query_always_matches(self) -> None:
        assert _is_significant_match("用户管理", "系统用户管理模块") is True

    def test_ascii_word_boundary(self) -> None:
        assert _is_significant_match("login", "user_login_page") is True

    def test_query_start(self) -> None:
        assert _is_significant_match("log", "logfile") is True

    def test_short_cjk_in_middle_of_english(self) -> None:
        assert _is_significant_match("ab", "xabcy") is False

    def test_two_char_query_at_boundary(self) -> None:
        assert _is_significant_match("ab", "ab_cd") is True


# ==================== _extract_inferred_capabilities ====================


class TestExtractInferredCapabilities:
    def test_none_returns_empty(self) -> None:
        assert _extract_inferred_capabilities(None) == []

    def test_empty_dict(self) -> None:
        assert _extract_inferred_capabilities({}) == []

    def test_no_inferred_capabilities_key(self) -> None:
        inferred = {"parsed": {}}
        assert _extract_inferred_capabilities(inferred) == []

    def test_inferred_capabilities_not_list(self) -> None:
        inferred = {"parsed": {"inferred_capabilities": "not_a_list"}}
        assert _extract_inferred_capabilities(inferred) == []

    def test_valid_capabilities(self) -> None:
        inferred = {
            "parsed": {
                "inferred_capabilities": [
                    {"name": "登录", "key": "login", "description": "用户登录能力"},
                    {"name": "注册", "key": "register", "description": "用户注册能力"},
                ]
            }
        }
        result = _extract_inferred_capabilities(inferred)
        assert len(result) == 2
        assert result[0]["name"] == "登录"

    def test_filters_non_dict_entries(self) -> None:
        inferred = {
            "parsed": {
                "inferred_capabilities": [
                    {"name": "登录", "key": "login"},
                    "not_a_dict",
                    None,
                    123,
                ]
            }
        }
        result = _extract_inferred_capabilities(inferred)
        assert len(result) == 1

    def test_fallback_to_change_summary(self) -> None:
        inferred = {
            "parsed": {
                "change_summary": {
                    "new_capabilities": [{"name": "新功�?, "key": "new_feat"}],
                    "modified_capabilities": [{"name": "修改功能", "key": "mod_feat"}],
                }
            }
        }
        result = _extract_inferred_capabilities(inferred)
        assert len(result) == 2

    def test_change_summary_new_only(self) -> None:
        inferred = {
            "parsed": {
                "change_summary": {
                    "new_capabilities": [{"name": "新功�?, "key": "new_feat"}],
                }
            }
        }
        result = _extract_inferred_capabilities(inferred)
        assert len(result) == 1

    def test_change_summary_not_list_fallback(self) -> None:
        inferred = {
            "parsed": {
                "change_summary": {
                    "new_capabilities": "not_list",
                    "modified_capabilities": "not_list",
                }
            }
        }
        result = _extract_inferred_capabilities(inferred)
        assert result == []

    def test_inferred_capabilities_priority_over_change_summary(self) -> None:
        inferred = {
            "parsed": {
                "inferred_capabilities": [{"name": "cap1", "key": "c1"}],
                "change_summary": {
                    "new_capabilities": [{"name": "new1", "key": "n1"}],
                },
            }
        }
        result = _extract_inferred_capabilities(inferred)
        assert len(result) == 1
        assert result[0]["name"] == "cap1"


# ==================== _extract_scenario_candidates ====================


class TestExtractScenarioCandidates:
    def test_none_returns_empty(self) -> None:
        assert _extract_scenario_candidates(None) == []

    def test_empty_dict(self) -> None:
        assert _extract_scenario_candidates({}) == []

    def test_candidates_not_list(self) -> None:
        assert _extract_scenario_candidates({"candidates": "not_list"}) == []

    def test_valid_candidates(self) -> None:
        candidates = {
            "candidates": [
                {"id": 1, "title": "登录流程", "description": "用户登录场景"},
                {"id": 2, "title": "注册流程", "description": "用户注册场景"},
            ]
        }
        result = _extract_scenario_candidates(candidates)
        assert len(result) == 2

    def test_filters_non_dict_entries(self) -> None:
        candidates = {
            "candidates": [
                {"id": 1, "title": "登录"},
                "string_entry",
                None,
            ]
        }
        result = _extract_scenario_candidates(candidates)
        assert len(result) == 1


# ==================== _find_matching_capability ====================


class TestFindMatchingCapability:
    def test_exact_name_match(self) -> None:
        tp = {"module": "", "point": "登录", "function": ""}
        caps = [{"name": "登录", "key": "login", "description": ""}]
        result = _find_matching_capability(tp, caps)
        assert result is not None
        assert result["capability_key"] == "login"
        assert result["match_score"] >= 0.3

    def test_key_match(self) -> None:
        tp = {"module": "", "point": "登录验证", "function": ""}
        caps = [{"name": "验证", "key": "登录验证", "description": ""}]
        result = _find_matching_capability(tp, caps)
        assert result is not None
        assert result["capability_key"] == "登录验证"

    def test_description_contains_match(self) -> None:
        tp = {"module": "", "point": "注销", "function": ""}
        caps = [{"name": "xx", "key": "xx", "description": "包含注销功能"}]
        result = _find_matching_capability(tp, caps)
        assert result is not None
        assert result["match_score"] >= 0.3

    def test_no_match(self) -> None:
        tp = {"module": "", "point": "无关", "function": ""}
        caps = [{"name": "登录", "key": "login", "description": "登录功能"}]
        result = _find_matching_capability(tp, caps)
        assert result is None

    def test_best_match_selected(self) -> None:
        tp = {"module": "", "point": "登录", "function": ""}
        caps = [
            {"name": "用户管理", "key": "user_mgmt", "description": "包含登录等功�?},
            {"name": "登录", "key": "login", "description": "登录功能"},
        ]
        result = _find_matching_capability(tp, caps)
        assert result is not None
        assert result["capability_key"] == "login"

    def test_match_by_module(self) -> None:
        tp = {"module": "用户", "point": "", "function": ""}
        caps = [{"name": "用户管理", "key": "user", "description": ""}]
        result = _find_matching_capability(tp, caps)
        assert result is not None

    def test_match_by_function(self) -> None:
        tp = {"module": "", "point": "", "function": "登录"}
        caps = [{"name": "登录系统", "key": "login", "description": ""}]
        result = _find_matching_capability(tp, caps)
        assert result is not None

    def test_empty_capabilities(self) -> None:
        tp = {"module": "", "point": "登录", "function": ""}
        result = _find_matching_capability(tp, [])
        assert result is None

    def test_score_below_threshold(self) -> None:
        tp = {"module": "", "point": "一个很长的完全不匹配的查询", "function": ""}
        caps = [{"name": "简�?, "key": "short", "description": "完全不相�?}]
        result = _find_matching_capability(tp, caps)
        assert result is None


# ==================== _find_matching_scenario ====================


class TestFindMatchingScenario:
    def test_exact_title_match(self) -> None:
        tp = {"point": "登录", "function": ""}
        cands = [{"id": 1, "title": "登录流程", "description": ""}]
        result = _find_matching_scenario(tp, cands)
        assert result is not None
        assert result["scenario_id"] == 1

    def test_description_contains_match(self) -> None:
        tp = {"point": "注销", "function": ""}
        cands = [{"id": 1, "title": "用户", "description": "包含注销操作"}]
        result = _find_matching_scenario(tp, cands)
        assert result is not None

    def test_function_field_match(self) -> None:
        tp = {"point": "", "function": "注册"}
        cands = [{"id": 1, "title": "注册流程", "description": ""}]
        result = _find_matching_scenario(tp, cands)
        assert result is not None

    def test_no_match(self) -> None:
        tp = {"point": "无关", "function": ""}
        cands = [{"id": 1, "title": "登录", "description": "登录"}]
        result = _find_matching_scenario(tp, cands)
        assert result is None

    def test_best_match_selected(self) -> None:
        tp = {"point": "登录", "function": ""}
        cands = [
            {"id": 1, "title": "用户管理", "description": "含登�?},
            {"id": 2, "title": "登录页面", "description": ""},
        ]
        result = _find_matching_scenario(tp, cands)
        assert result is not None
        assert result["scenario_id"] == 2

    def test_empty_candidates(self) -> None:
        tp = {"point": "登录", "function": ""}
        result = _find_matching_scenario(tp, [])
        assert result is None

    def test_score_below_threshold(self) -> None:
        tp = {"point": "完全不同的查询文�?, "function": ""}
        cands = [{"id": 1, "title": "简�?, "description": "不相�?}]
        result = _find_matching_scenario(tp, cands)
        assert result is None


# ==================== _build_no_match_note ====================


class TestBuildNoMatchNote:
    def test_with_ui_source(self) -> None:
        tp = {"point": "登录测试"}
        note = _build_no_match_note(tp, ["ui"])
        assert "登录测试" in note
        assert "UI 控件" in note

    def test_with_inferred_source(self) -> None:
        tp = {"point": "注册"}
        note = _build_no_match_note(tp, ["inferred"])
        assert "注册" in note
        assert "AI 能力" in note

    def test_with_scenario_source(self) -> None:
        tp = {"point": "忘记密码"}
        note = _build_no_match_note(tp, ["scenario"])
        assert "忘记密码" in note
        assert "场景候�? in note

    def test_with_multiple_sources(self) -> None:
        tp = {"point": "多源"}
        note = _build_no_match_note(tp, ["ui", "inferred", "scenario"])
        assert "/" in note
        assert "UI 控件" in note
        assert "AI 能力" in note
        assert "场景候�? in note

    def test_unknown_source_skipped(self) -> None:
        tp = {"point": "测试"}
        note = _build_no_match_note(tp, ["unknown_key"])
        assert note == "测试�?'测试' 未在  中找到匹�?


# ==================== _align_from_inferred_only ====================


class TestAlignFromInferredOnly:
    def test_single_capability(self) -> None:
        caps = [{"name": "登录", "key": "login", "description": "用户登录"}]
        aligned, conflicts = _align_from_inferred_only(caps)
        assert len(aligned) == 1
        assert len(conflicts) == 0
        assert aligned[0]["test_point"]["source"] == "inferred"
        assert aligned[0]["test_point"]["module"] == "登录"
        assert aligned[0]["capability_match"]["capability_key"] == "login"
        assert aligned[0]["alignment_status"] == "aligned"

    def test_multiple_capabilities(self) -> None:
        caps = [
            {"name": "登录", "key": "login", "description": ""},
            {"name": "注册", "key": "register", "description": "用户注册能力"},
        ]
        aligned, conflicts = _align_from_inferred_only(caps)
        assert len(aligned) == 2
        assert len(conflicts) == 0
        assert aligned[1]["test_point"]["point"] == "用户注册能力"

    def test_empty_capabilities(self) -> None:
        aligned, conflicts = _align_from_inferred_only([])
        assert aligned == []
        assert conflicts == []

    def test_capability_missing_description(self) -> None:
        caps = [{"name": "功能", "key": "feat"}]
        aligned, conflicts = _align_from_inferred_only(caps)
        assert aligned[0]["test_point"]["point"] == ""


# ==================== _compute_coverage ====================


class TestComputeCoverage:
    def test_no_inferred_caps(self) -> None:
        result = _compute_coverage([], [], [])
        assert result is None

    def test_full_coverage(self) -> None:
        aligned = [
            {"capability_match": {"capability_key": "login"}},
            {"capability_match": {"capability_key": "register"}},
        ]
        inferred_caps = [
            {"key": "login", "name": "登录"},
            {"key": "register", "name": "注册"},
        ]
        result = _compute_coverage(aligned, [], inferred_caps)
        assert result is not None
        assert result["total_capabilities"] == 2
        assert result["covered_capabilities"] == 2
        assert result["coverage_rate"] == 1.0

    def test_partial_coverage(self) -> None:
        aligned = [{"capability_match": {"capability_key": "login"}}]
        inferred_caps = [
            {"key": "login", "name": "登录"},
            {"key": "register", "name": "注册"},
        ]
        result = _compute_coverage(aligned, [], inferred_caps)
        assert result is not None
        assert result["total_capabilities"] == 2
        assert result["covered_capabilities"] == 1
        assert result["coverage_rate"] == 0.5

    def test_zero_coverage(self) -> None:
        aligned: List[Dict[str, Any]] = []
        inferred_caps = [{"key": "login", "name": "登录"}]
        result = _compute_coverage(aligned, [], inferred_caps)
        assert result is not None
        assert result["coverage_rate"] == 0.0

    def test_skips_entries_without_capability_match(self) -> None:
        aligned = [{"capability_match": None}]
        inferred_caps = [{"key": "login", "name": "登录"}]
        result = _compute_coverage(aligned, [], inferred_caps)
        assert result is not None
        assert result["covered_capabilities"] == 0

    def test_skips_non_dict_capability_match(self) -> None:
        aligned = [{"capability_match": "not_a_dict"}]
        inferred_caps = [{"key": "login", "name": "登录"}]
        result = _compute_coverage(aligned, [], inferred_caps)
        assert result is not None
        assert result["covered_capabilities"] == 0


# ==================== _compute_alignment_confidence ====================


class TestComputeAlignmentConfidence:
    def test_all_aligned(self) -> None:
        aligned = [{"alignment_status": "aligned"}, {"alignment_status": "aligned"}]
        assert _compute_alignment_confidence(aligned, []) == 1.0

    def test_none_aligned(self) -> None:
        aligned = [{"alignment_status": "no_ui_match"}, {"alignment_status": "no_sources"}]
        assert _compute_alignment_confidence(aligned, []) == 0.0

    def test_empty_list(self) -> None:
        assert _compute_alignment_confidence([], []) == 0.0


# ==================== TestPointAlignment.should_run ====================


class TestShouldRun:
    def test_no_raw_signals_returns_false(self) -> None:
        ctx = _make_ctx()
        step = TestPointAlignment()
        assert step.should_run(ctx) is False

    def test_empty_test_points_no_inferred_returns_false(self) -> None:
        ctx = _make_ctx(raw_signals={"test_points": [], "ui_specs": [], "has_ui": False})
        step = TestPointAlignment()
        assert step.should_run(ctx) is False

    def test_with_test_points_returns_true(self) -> None:
        ctx = _make_ctx(raw_signals={"test_points": [{"id": 1}], "ui_specs": [], "has_ui": False})
        step = TestPointAlignment()
        assert step.should_run(ctx) is True

    def test_no_test_points_but_has_inferred_returns_true(self) -> None:
        ctx = _make_ctx(
            raw_signals={"test_points": [], "ui_specs": [], "has_ui": False},
            inferred={"parsed": {"inferred_capabilities": [{"name": "test"}]}},
        )
        step = TestPointAlignment()
        assert step.should_run(ctx) is True


# ==================== TestPointAlignment.cache_key ====================


class TestCacheKey:
    def test_no_signals_returns_empty(self) -> None:
        ctx = _make_ctx()
        step = TestPointAlignment()
        assert step.cache_key(ctx) == ""

    def test_deterministic(self) -> None:
        ctx = _make_ctx(raw_signals={
            "test_points": [{"id": 1, "point": "登录"}, {"id": 2, "point": "注册"}],
            "ui_specs": [{"screen_id": 1}],
            "has_ui": True,
        })
        step = TestPointAlignment()
        key1 = step.cache_key(ctx)
        key2 = step.cache_key(ctx)
        assert key1 == key2
        assert len(key1) == 64

    def test_different_testpoints_produce_different_key(self) -> None:
        step = TestPointAlignment()
        ctx1 = _make_ctx(raw_signals={"test_points": [{"id": 1}], "ui_specs": [], "has_ui": False})
        ctx2 = _make_ctx(raw_signals={"test_points": [{"id": 2}], "ui_specs": [], "has_ui": False})
        assert step.cache_key(ctx1) != step.cache_key(ctx2)

    def test_with_inferred(self) -> None:
        ctx = _make_ctx(
            raw_signals={"test_points": [{"id": 1}], "ui_specs": [], "has_ui": False},
            inferred={"parsed": {"inferred_capabilities": [{"name": "登录", "key": "login"}]}},
        )
        step = TestPointAlignment()
        key = step.cache_key(ctx)
        assert len(key) == 64

    def test_with_scenario_candidates(self) -> None:
        ctx = _make_ctx(
            raw_signals={"test_points": [{"id": 1}], "ui_specs": [], "has_ui": False},
            scenario_candidates={"candidates": [{"id": 1, "title": "登录"}]},
        )
        step = TestPointAlignment()
        key = step.cache_key(ctx)
        assert len(key) == 64

    def test_inferred_hash_error(self) -> None:
        ctx = _make_ctx(
            raw_signals={"test_points": [{"id": 1}], "ui_specs": [], "has_ui": False},
            inferred={"parsed": {"inferred_capabilities": object()}},
        )
        step = TestPointAlignment()
        key = step.cache_key(ctx)
        assert len(key) == 64


# ==================== TestPointAlignment.validate_output ====================


class TestValidateOutput:
    def test_valid_payload(self) -> None:
        step = TestPointAlignment()
        assert step.validate_output({"aligned_testpoints": [], "sources": {}}) is True

    def test_missing_aligned_testpoints(self) -> None:
        step = TestPointAlignment()
        assert step.validate_output({"sources": {}}) is False

    def test_missing_sources(self) -> None:
        step = TestPointAlignment()
        assert step.validate_output({"aligned_testpoints": []}) is False

    def test_empty_dict(self) -> None:
        step = TestPointAlignment()
        assert step.validate_output({}) is False


# ==================== TestPointAlignment.fallback ====================


class TestFallback:
    def test_returns_degraded(self) -> None:
        ctx = _make_ctx(raw_signals={
            "test_points": [{"id": 1, "module": "用户", "point": "登录", "function": ""}],
            "ui_specs": [],
            "has_ui": False,
        })
        step = TestPointAlignment()
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.degraded is True
        assert result.success is True
        assert result.artifact_kind == "aligned_testpoints"
        assert result.artifact_confidence == 0.3
        payload = result.artifact_payload
        assert payload["aligned_count"] == 0
        assert payload["conflict_count"] == 0
        aligned = payload["aligned_testpoints"]
        assert len(aligned) == 1
        assert aligned[0]["alignment_status"] == "fallback"
        assert "test error" in aligned[0]["notes"]

    def test_fallback_no_signals(self) -> None:
        ctx = _make_ctx()
        step = TestPointAlignment()
        result = step.fallback(ctx, RuntimeError("no data"))
        assert result.degraded is True
        assert result.success is True
        assert result.artifact_payload["total_testpoints"] == 0


# ==================== TestPointAlignment.execute ====================


class TestExecute:
    def test_no_raw_signals(self) -> None:
        ctx = _make_ctx()
        step = TestPointAlignment()
        result = step.execute(ctx)
        assert result.success is False
        assert result.error is not None

    def test_basic_alignment_with_testpoints(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [
                {"id": 1, "module": "用户管理", "point": "登录功能", "function": "", "priority": 1},
            ],
            "ui_specs": [],
            "has_ui": False,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        assert result.success is True
        assert result.artifact_kind == "aligned_testpoints"
        payload = result.artifact_payload
        assert payload["total_testpoints"] == 1
        aligned = payload["aligned_testpoints"]
        assert aligned[0]["alignment_status"] == "no_sources"
        assert payload["sources"]["ui"] is False
        assert payload["sources"]["inferred"] is False

    def test_ui_matching(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [
                {"id": 1, "module": "用户管理", "point": "", "function": "", "priority": 1},
            ],
            "ui_specs": [
                {"screen_id": 1, "screen_name": "用户管理页面", "ui_spec": {}},
            ],
            "has_ui": True,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        aligned = payload["aligned_testpoints"]
        assert aligned[0]["ui_match"] is not None
        assert aligned[0]["ui_match"]["screen_id"] == 1
        assert aligned[0]["alignment_status"] == "aligned"

    def test_capability_matching(self) -> None:
        ctx = _make_ctx(
            raw_signals={
                "project_id": 1,
                "test_points": [
                    {"id": 1, "module": "", "point": "登录", "function": "", "priority": 1},
                ],
                "ui_specs": [],
                "has_ui": False,
            },
            inferred={
                "parsed": {
                    "inferred_capabilities": [
                        {"name": "登录", "key": "login", "description": "用户登录"},
                    ]
                }
            },
        )
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        aligned = payload["aligned_testpoints"]
        assert aligned[0]["capability_match"] is not None
        assert aligned[0]["capability_match"]["capability_key"] == "login"
        assert aligned[0]["alignment_status"] == "aligned"

    def test_scenario_matching(self) -> None:
        ctx = _make_ctx(
            raw_signals={
                "project_id": 1,
                "test_points": [
                    {"id": 1, "module": "", "point": "登录", "function": "", "priority": 1},
                ],
                "ui_specs": [],
                "has_ui": False,
            },
            scenario_candidates={
                "candidates": [
                    {"id": 1, "title": "登录流程", "description": "用户登录"},
                ]
            },
        )
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        aligned = payload["aligned_testpoints"]
        assert aligned[0]["scenario_match"] is not None
        assert aligned[0]["scenario_match"]["scenario_id"] == 1

    def test_no_match_produces_conflict(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [
                {"id": 1, "module": "不存�?, "point": "不存�?, "function": "", "priority": 1},
            ],
            "ui_specs": [
                {"screen_id": 1, "screen_name": "用户管理", "ui_spec": {}},
            ],
            "has_ui": True,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        assert payload["conflict_count"] == 1
        assert len(payload["conflicts"]) == 1
        assert payload["conflicts"][0]["alignment_status"] == "no_ui_match"

    def test_pause_triggered_on_low_confidence(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [
                {"id": 1, "module": "登录功能", "point": "", "function": "", "priority": 1},
                {"id": 2, "module": "不存在模�?, "point": "", "function": "", "priority": 1},
            ],
            "ui_specs": [
                {"screen_id": 1, "screen_name": "登录功能页面", "ui_spec": {}},
            ],
            "has_ui": True,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        assert result.pause_for_confirmation is True
        assert result.artifact_confidence == 0.5
        assert "测试点未对齐" in (result.confirmation_reason or "")

    def test_align_from_inferred_only(self) -> None:
        ctx = _make_ctx(
            raw_signals={
                "project_id": 1,
                "test_points": [],
                "ui_specs": [],
                "has_ui": False,
            },
            inferred={
                "parsed": {
                    "inferred_capabilities": [
                        {"name": "登录", "key": "login", "description": "用户登录"},
                        {"name": "注册", "key": "register", "description": "用户注册能力"},
                    ]
                }
            },
        )
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        assert payload["total_testpoints"] == 2
        aligned = payload["aligned_testpoints"]
        assert len(aligned) == 2
        assert aligned[0]["test_point"]["source"] == "inferred"

    def test_multiple_testpoints_multiple_sources(self) -> None:
        ctx = _make_ctx(
            raw_signals={
                "project_id": 1,
                "test_points": [
                    {"id": 1, "module": "用户管理", "point": "登录", "function": "", "priority": 1},
                    {"id": 2, "module": "", "point": "注销", "function": "", "priority": 2},
                ],
                "ui_specs": [
                    {"screen_id": 1, "screen_name": "用户管理页面", "ui_spec": {}},
                ],
                "has_ui": True,
            },
            inferred={
                "parsed": {
                    "inferred_capabilities": [
                        {"name": "注销系统", "key": "logout", "description": "用户注销"},
                    ]
                }
            },
        )
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        assert payload["sources"]["ui"] is True
        assert payload["sources"]["inferred"] is True

        aligned = payload["aligned_testpoints"]
        tp1 = aligned[0]
        assert tp1["ui_match"] is not None
        assert tp1["ui_match"]["screen_id"] == 1

        tp2 = aligned[1]
        assert tp2["capability_match"] is not None
        assert tp2["capability_match"]["capability_key"] == "logout"

    def test_active_sources_tracking(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [{"id": 1, "module": "", "point": "", "function": "", "priority": 1}],
            "ui_specs": [],
            "has_ui": False,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        assert payload["active_sources"] == []

    def test_coverage_none_without_inferred_caps(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [{"id": 1, "module": "test", "point": "", "function": "", "priority": 1}],
            "ui_specs": [],
            "has_ui": False,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        assert result.artifact_payload["coverage"] is None

    def test_artifact_provenance(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [{"id": 1, "module": "t", "point": "", "function": "", "priority": 1}],
            "ui_specs": [],
            "has_ui": False,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        assert result.artifact_provenance is not None
        assert result.artifact_provenance["step"] == "testpoint_alignment"
        assert result.artifact_provenance["version"] == "2.0"

    def test_execute_with_all_three_sources_together(self) -> None:
        ctx = _make_ctx(
            raw_signals={
                "project_id": 1,
                "test_points": [
                    {"id": 1, "module": "用户管理", "point": "登录", "function": "登录", "priority": 1},
                ],
                "ui_specs": [
                    {"screen_id": 1, "screen_name": "用户管理页面", "ui_spec": {}},
                ],
                "has_ui": True,
            },
            inferred={
                "parsed": {
                    "inferred_capabilities": [
                        {"name": "登录", "key": "login", "description": "用户登录"},
                    ]
                }
            },
            scenario_candidates={
                "candidates": [
                    {"id": 1, "title": "登录流程", "description": "用户登录场景"},
                ]
            },
        )
        step = TestPointAlignment()
        result = step.execute(ctx)
        assert result.success is True
        payload = result.artifact_payload
        aligned = payload["aligned_testpoints"]
        assert aligned[0]["ui_match"] is not None
        assert aligned[0]["capability_match"] is not None
        assert aligned[0]["scenario_match"] is not None
        assert aligned[0]["alignment_status"] == "aligned"
        assert payload["active_sources"] == ["ui", "inferred", "scenario"]

    def test_edge_case_empty_everything(self) -> None:
        ctx = _make_ctx(raw_signals={
            "project_id": 1,
            "test_points": [],
            "ui_specs": [],
            "has_ui": False,
        })
        step = TestPointAlignment()
        result = step.execute(ctx)
        assert result.success is True
        payload = result.artifact_payload
        assert payload["total_testpoints"] == 0
        assert payload["aligned_count"] == 0

    def test_build_no_match_with_only_inferred_source(self) -> None:
        ctx = _make_ctx(
            raw_signals={
                "project_id": 1,
                "test_points": [
                    {"id": 1, "module": "", "point": "未知功能", "function": "", "priority": 1},
                ],
                "ui_specs": [],
                "has_ui": False,
            },
            inferred={
                "parsed": {
                    "inferred_capabilities": [
                        {"name": "登录", "key": "login", "description": "用户登录"},
                    ]
                }
            },
        )
        step = TestPointAlignment()
        result = step.execute(ctx)
        payload = result.artifact_payload
        assert payload["conflict_count"] == 1
        conflict = payload["conflicts"][0]
        assert "AI 能力" in conflict["notes"]
