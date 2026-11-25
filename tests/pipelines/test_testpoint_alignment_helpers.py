"""TestPointAlignment 对齐拆分件护栏（G-8 B5f）。

拆分前 `execute` 里是「三源探测 + 未命中定状态」的内联循环，只能靠 Step 级用例间接覆盖；
拆分后对这四个纯函数单独加锁，保证状态口径（aligned / no_ui_match / no_sources）不漂移。
"""

from app.pipelines.steps.testpoint_alignment._helpers import (
    _align_test_points,
    _classify_unmatched,
    _detect_sources,
    _probe_matches,
)


UI_SPECS = [{"screen_id": 1, "screen_name": "登录页面", "ui_spec": {"elements": [{"type": "button", "text": "登录"}]}}]
CAPS = [{"name": "登录", "key": "login", "description": "用户登录", "confidence": 0.9}]
CANDS = [{"id": 1, "title": "登录流程", "description": "用户登录场景"}]


class TestDetectSources:
    def test_no_sources(self):
        sources, active = _detect_sources(False, [], [], [])
        assert sources == {"ui": False, "inferred": False, "scenario": False}
        assert active == []

    def test_all_sources(self):
        sources, active = _detect_sources(True, UI_SPECS, CAPS, CANDS)
        assert active == ["ui", "inferred", "scenario"]

    def test_has_ui_flag_without_specs_is_not_a_source(self):
        sources, active = _detect_sources(True, [], [], [])
        assert sources["ui"] is False
        assert active == []


class TestProbeMatches:
    def test_disabled_sources_yield_none(self):
        matches = _probe_matches(
            {"module": "登录", "point": "登录", "function": ""},
            {"ui": False, "inferred": False, "scenario": False},
            UI_SPECS,
            CAPS,
            CANDS,
        )
        assert matches == {"ui_match": None, "capability_match": None, "scenario_match": None}

    def test_ui_match_takes_first_screen(self):
        matches = _probe_matches(
            {"module": "登录", "point": "登录", "function": ""},
            {"ui": True, "inferred": False, "scenario": False},
            UI_SPECS,
            CAPS,
            CANDS,
        )
        assert matches["ui_match"]["screen_id"] == 1
        assert matches["capability_match"] is None

    def test_all_three_sources_matched(self):
        matches = _probe_matches(
            {"module": "登录", "point": "登录", "function": ""},
            {"ui": True, "inferred": True, "scenario": True},
            UI_SPECS,
            CAPS,
            CANDS,
        )
        assert all(matches.values())


class TestClassifyUnmatched:
    def _entry(self, status="aligned", notes=""):
        return {
            "test_point": {"point": "无关测试点"},
            "ui_match": None,
            "capability_match": None,
            "scenario_match": None,
            "alignment_status": status,
            "notes": notes,
        }

    def test_no_ui_match_when_any_source_active(self):
        entry = self._entry()
        assert (
            _classify_unmatched(
                entry, {"point": "无关"}, False, {"ui": False, "inferred": True, "scenario": False}, ["inferred"]
            )
            is True
        )
        assert entry["alignment_status"] == "no_ui_match"
        assert "AI 能力" in entry["notes"]

    def test_no_sources_when_nothing_active(self):
        entry = self._entry()
        assert (
            _classify_unmatched(
                entry, {"point": "无关"}, False, {"ui": False, "inferred": False, "scenario": False}, []
            )
            is False
        )
        assert entry["alignment_status"] == "no_sources"


class TestAlignTestPoints:
    def test_empty_test_points(self):
        aligned, conflicts = _align_test_points(
            [], {"ui": False, "inferred": False, "scenario": False}, [], False, [], [], []
        )
        assert aligned == [] and conflicts == []

    def test_matched_point_is_aligned_and_not_conflict(self):
        sources, active = _detect_sources(True, UI_SPECS, CAPS, CANDS)
        aligned, conflicts = _align_test_points(
            [{"module": "登录", "point": "登录", "function": ""}],
            sources,
            active,
            True,
            UI_SPECS,
            CAPS,
            CANDS,
        )
        assert len(aligned) == 1
        assert aligned[0]["alignment_status"] == "aligned"
        assert conflicts == []

    def test_unmatched_point_goes_to_both_lists(self):
        sources, active = _detect_sources(True, UI_SPECS, [], [])
        aligned, conflicts = _align_test_points(
            [{"module": "报表", "point": "导出报表", "function": ""}],
            sources,
            active,
            True,
            UI_SPECS,
            [],
            [],
        )
        assert len(aligned) == 1 and len(conflicts) == 1
        assert aligned[0] is conflicts[0]
        assert conflicts[0]["alignment_status"] == "no_ui_match"
