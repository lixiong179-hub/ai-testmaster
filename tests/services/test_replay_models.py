import pytest
from app.services.execution_replay.models import (
    ReplayEventType,
    SessionStatus,
    ActionType,
    ReplayEvent,
    ExecutionTimeline,
    ReplaySession,
)
from datetime import datetime


class TestReplayEventType:
    def test_all_values(self):
        assert ReplayEventType.NAVIGATE.value == "navigate"
        assert ReplayEventType.CLICK.value == "click"
        assert ReplayEventType.INPUT.value == "input"
        assert ReplayEventType.VERIFY.value == "verify"
        assert ReplayEventType.WAIT.value == "wait"
        assert ReplayEventType.SCROLL.value == "scroll"
        assert ReplayEventType.HOVER.value == "hover"
        assert ReplayEventType.SELECT.value == "select"
        assert ReplayEventType.SCREENSHOT.value == "screenshot"
        assert ReplayEventType.ERROR.value == "error"


class TestSessionStatus:
    def test_all_values(self):
        assert SessionStatus.PENDING.value == "pending"
        assert SessionStatus.PLAYING.value == "playing"
        assert SessionStatus.PAUSED.value == "paused"
        assert SessionStatus.COMPLETED.value == "completed"


class TestActionType:
    def test_all_values(self):
        assert ActionType.CLICK.value == "click"
        assert ActionType.INPUT.value == "input"
        assert ActionType.SCROLL.value == "scroll"
        assert ActionType.NAVIGATE.value == "navigate"


class TestReplayEvent:
    def test_to_dict(self):
        event = ReplayEvent(
            timestamp=1.5,
            event_type=ReplayEventType.CLICK,
            action="点击按钮",
            step_number=1,
            screenshot_path="/tmp/screenshot.png",
            duration_ms=500,
        )
        d = event.to_dict()
        assert d["timestamp"] == 1.5
        assert d["event_type"] == "click"
        assert d["action"] == "点击按钮"
        assert d["step_number"] == 1
        assert d["duration_ms"] == 500

    def test_defaults(self):
        event = ReplayEvent(
            timestamp=0.0,
            event_type=ReplayEventType.CLICK,
            action="test",
            step_number=1,
        )
        assert event.screenshot_path is None
        assert event.element_info is None
        assert event.error_message is None
        assert event.duration_ms == 0

    def test_with_error(self):
        event = ReplayEvent(
            timestamp=0.0,
            event_type=ReplayEventType.ERROR,
            action="test",
            step_number=1,
            error_message="element not found",
        )
        d = event.to_dict()
        assert d["error_message"] == "element not found"


class TestExecutionTimeline:
    def test_to_dict(self):
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=100,
            start_time=datetime(2026, 1, 1, 12, 0, 0),
        )
        d = timeline.to_dict()
        assert d["execution_id"] == 1
        assert d["test_case_id"] == 100
        assert d["events"] == []
        assert d["total_duration_ms"] == 0

    def test_with_events(self):
        event = ReplayEvent(
            timestamp=0.0,
            event_type=ReplayEventType.CLICK,
            action="click",
            step_number=1,
        )
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=100,
            start_time=datetime(2026, 1, 1),
            events=[event],
        )
        d = timeline.to_dict()
        assert len(d["events"]) == 1

    def test_none_end_time(self):
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=100,
            start_time=datetime(2026, 1, 1),
            end_time=None,
        )
        d = timeline.to_dict()
        assert d["end_time"] is None


class TestReplaySession:
    def test_to_dict(self):
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=100,
            start_time=datetime(2026, 1, 1),
        )
        session = ReplaySession(
            session_id="sess_001",
            execution_id=1,
            timeline=timeline,
        )
        d = session.to_dict()
        assert d["session_id"] == "sess_001"
        assert d["execution_id"] == 1
        assert d["current_event_index"] == 0
        assert d["speed"] == 1.0
        assert d["is_playing"] is False
        assert d["is_paused"] is False

    def test_with_playing_state(self):
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=100,
            start_time=datetime(2026, 1, 1),
        )
        session = ReplaySession(
            session_id="sess_002",
            execution_id=1,
            timeline=timeline,
            is_playing=True,
            speed=2.0,
        )
        d = session.to_dict()
        assert d["is_playing"] is True
        assert d["speed"] == 2.0
