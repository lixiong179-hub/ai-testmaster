"""B5i 拆分件护栏：截断 JSON 修复 / 批量事件构造 / 历史可信度归并 / steps_json 构造。

这四处原先都是单一长函数（`_repair_truncated_json`、`generate_test_cases_batch`、
`_assess_history_trust`、`_save_test_case`）的内联分支，拆分后对纯逻辑单独加锁。
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.test_case_generation.ai_response_parser import _repair_truncated_json
from app.services.test_case_generation.batch_orchestrator import (
    _build_batch_summary_event,
    _build_point_error_event,
    _build_point_failure_event,
    _build_point_success_event,
    _build_warning_event,
)
from app.services.test_case_generation.history_context import (
    _case_older_than_90_days,
    _requirement_is_newer,
    _trust_level,
    _ui_screen_mismatch,
)
from app.services.test_case_generation.validator import CaseValidator


class TestRepairTruncatedJson:
    def test_complete_array_kept(self):
        assert _repair_truncated_json('[{"a": 1}] trailing') == '[{"a": 1}]'

    def test_truncated_object_closed(self):
        assert _repair_truncated_json('{"a": {"b": 1') == '{"a": {"b": 1}}'

    def test_truncated_array_filled_with_brackets(self):
        assert _repair_truncated_json('[{"a": 1') == '[{"a": 1]}'

    def test_closed_inner_object_wins_over_unclosed_array(self):
        # 既有行为：最后一个完整对象优先（此处数组未闭合也不补 ]），加锁避免重构时改变
        assert _repair_truncated_json('[{"a": 1}') == '[{"a": 1}'

    def test_brackets_inside_string_ignored(self):
        text = '{"a": "文字{里有}括号"'
        assert _repair_truncated_json(text) == text + "}"

    def test_escaped_quote_does_not_end_string(self):
        text = '{"a": "他说\\"你好{", "b": 1}'
        assert _repair_truncated_json(text) == text

    def test_prefers_last_complete_object(self):
        text = '{"a": 1} {"b": 2'
        assert _repair_truncated_json(text) == '{"a": 1}'

    def test_empty_text(self):
        assert _repair_truncated_json("") == ""


class TestWarningEvent:
    def test_dict_warning_kept(self):
        event = _build_warning_event({"message": "缺 UI", "code": "UI_NO_MATCH"})
        assert event["message"] == "缺 UI"
        assert event["warning_detail"]["code"] == "UI_NO_MATCH"
        assert event["progress"] == 5

    def test_str_warning_gets_unknown_code(self):
        event = _build_warning_event("随便说说")
        assert event["message"] == "随便说说"
        assert event["warning_detail"] == {"message": "随便说说", "code": "UNKNOWN"}


class TestPointEvents:
    def test_failure_event_progress_by_completed(self):
        event = _build_point_failure_event(index=0, completed=2, total=4, failed_count=1)
        assert event["progress"] == int(10 + 2 / 4 * 85)
        assert event["current"] == 2 and event["total"] == 4
        assert event["error"] is True

    def test_error_event_has_no_current_field(self):
        event = _build_point_error_event(index=1, total=4, failed_count=2)
        assert event["progress"] == int(10 + 2 / 4 * 85)
        assert "current" not in event

    def test_success_event_without_saved_cases(self):
        event = _build_point_success_event(index=0, completed=1, total=2, saved_cases=[], skipped_count=3)
        assert event["case"] is None
        assert event["saved_count"] == 0
        assert event["skipped_count"] == 3

    def test_success_event_payload_from_first_case(self):
        saved = SimpleNamespace(id=9, title="登录成功", module="登录")
        event = _build_point_success_event(index=0, completed=1, total=2, saved_cases=[saved], skipped_count=0)
        assert event["case"] == {"id": 9, "title": "登录成功", "module": "登录"}
        assert event["saved_count"] == 1


class TestBatchSummaryEvent:
    def test_all_success(self):
        event = _build_batch_summary_event([SimpleNamespace(id=1, title="A")], 0, 1, {"total": 1})
        assert event["status"] == "success"
        assert event["cases"] == [{"id": 1, "title": "A"}]
        assert event["progress"] == 100

    def test_partial_when_failed(self):
        event = _build_batch_summary_event([], 2, 2, {})
        assert event["status"] == "partial"
        assert event["failed"] == 2


class TestHistoryTrustHelpers:
    def test_trust_level_high(self):
        assert _trust_level([]) == ("high", "")

    def test_trust_level_requirement_mismatch_is_low(self):
        assert _trust_level(["requirement_mismatch", "summary_missing"]) == ("low", "HISTORY_REQUIREMENT_MISMATCH")

    def test_trust_level_stale_is_medium(self):
        assert _trust_level(["case_older_than_90_days"]) == ("medium", "HISTORY_POTENTIALLY_STALE")

    def test_trust_level_other_reasons_joined(self):
        assert _trust_level(["summary_missing", "ui_screen_mismatch"]) == (
            "medium",
            "summary_missing,ui_screen_mismatch",
        )

    def test_requirement_is_newer(self):
        newer = SimpleNamespace(update_time=datetime(2026, 1, 2, tzinfo=UTC))
        case = SimpleNamespace(update_time=datetime(2026, 1, 1, tzinfo=UTC))
        assert _requirement_is_newer(newer, case) is True
        assert _requirement_is_newer(None, case) is False

    def test_requirement_is_newer_requires_datetime(self):
        assert (
            _requirement_is_newer(SimpleNamespace(update_time="2026-1-2"), SimpleNamespace(update_time=None)) is False
        )

    def test_case_older_than_90_days(self):
        old = SimpleNamespace(update_time=datetime.now(UTC) - timedelta(days=91))
        fresh = SimpleNamespace(update_time=datetime.now(UTC) - timedelta(days=10))
        assert _case_older_than_90_days(old) is True
        assert _case_older_than_90_days(fresh) is False
        assert _case_older_than_90_days(SimpleNamespace(update_time=None)) is False

    def test_ui_screen_mismatch(self):
        case = SimpleNamespace(linked_ui_screens=[SimpleNamespace(id=1)])
        assert _ui_screen_mismatch(case, {2}) is True
        assert _ui_screen_mismatch(case, {1, 2}) is False
        assert _ui_screen_mismatch(case, set()) is False
        assert _ui_screen_mismatch(SimpleNamespace(linked_ui_screens=[]), {2}) is False


class TestBuildStepsJson:
    def _fake_self(self):
        return SimpleNamespace(_correct_action_type=lambda action, action_type: action_type or "click")

    def test_first_step_inherits_case_test_data(self):
        rows = CaseValidator._build_steps_json(
            self._fake_self(),
            [{"action": "点击", "expected_result": "ok"}, {"action": "输入", "expected_result": "ok"}],
            [{"k": "v"}],
        )
        assert rows[0]["test_data"] == [{"k": "v"}]
        assert rows[1]["test_data"] == []
        assert rows[0]["step"] == "1"
        assert rows[0]["action_type"] == "click"

    def test_step_level_test_data_kept_when_no_case_data(self):
        rows = CaseValidator._build_steps_json(
            self._fake_self(),
            [{"action": "点击", "expected_result": "ok", "test_data": [1], "action_type": "input"}],
            None,
        )
        assert rows[0]["test_data"] == [1]
        assert rows[0]["action_type"] == "input"

    def test_defaults_for_missing_fields(self):
        rows = CaseValidator._build_steps_json(self._fake_self(), [{}], None)
        assert rows[0]["action"] == "执行"
        assert rows[0]["description"] == ""
