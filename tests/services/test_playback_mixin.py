import pytest
import asyncio
from app.services.execution_replay.playback_mixin import PlaybackMixin
from app.services.execution_replay.models import (
    ReplayEvent,
    ReplayEventType,
    ExecutionTimeline,
    ReplaySession,
)
from datetime import datetime


def _make_session(session_id="test_sess", event_count=3):
    mixin = PlaybackMixin()
    mixin._default_speed = 1.0
    mixin._event_callback = None
    events = [
        ReplayEvent(
            timestamp=float(i),
            event_type=ReplayEventType.CLICK,
            action=f"action_{i}",
            step_number=i + 1,
            duration_ms=100,
        )
        for i in range(event_count)
    ]
    timeline = ExecutionTimeline(
        execution_id=1,
        test_case_id=100,
        start_time=datetime(2026, 1, 1),
        events=events,
    )
    session = ReplaySession(
        session_id=session_id,
        execution_id=1,
        timeline=timeline,
    )
    mixin._sessions = {session_id: session}
    mixin._update_activity = lambda sid: None
    return mixin, session


class TestStartReplay:
    @pytest.mark.asyncio
    async def test_start_success(self):
        mixin, session = _make_session()
        result = await mixin.start_replay("test_sess")
        assert result["status"] == "started"
        assert session.is_playing is True

    @pytest.mark.asyncio
    async def test_start_already_playing(self):
        mixin, session = _make_session()
        session.is_playing = True
        result = await mixin.start_replay("test_sess")
        assert result["status"] == "already_playing"

    @pytest.mark.asyncio
    async def test_start_nonexistent_session(self):
        mixin, _ = _make_session()
        with pytest.raises(ValueError, match="不存在"):
            await mixin.start_replay("nonexistent")

    @pytest.mark.asyncio
    async def test_start_with_speed(self):
        mixin, session = _make_session()
        result = await mixin.start_replay("test_sess", speed=2.0)
        assert session.speed == 2.0

    @pytest.mark.asyncio
    async def test_start_from_index(self):
        mixin, session = _make_session()
        result = await mixin.start_replay("test_sess", start_from=1)
        assert session.current_event_index == 1


class TestPauseReplay:
    @pytest.mark.asyncio
    async def test_pause_success(self):
        mixin, session = _make_session()
        session.is_playing = True
        result = await mixin.pause_replay("test_sess")
        assert result["status"] == "paused"
        assert session.is_paused is True

    @pytest.mark.asyncio
    async def test_pause_not_playing(self):
        mixin, session = _make_session()
        result = await mixin.pause_replay("test_sess")
        assert result["status"] == "not_playing"

    @pytest.mark.asyncio
    async def test_pause_nonexistent(self):
        mixin, _ = _make_session()
        with pytest.raises(ValueError, match="不存在"):
            await mixin.pause_replay("nonexistent")


class TestResumeReplay:
    @pytest.mark.asyncio
    async def test_resume_success(self):
        mixin, session = _make_session()
        session.is_playing = True
        session.is_paused = True
        result = await mixin.resume_replay("test_sess")
        assert result["status"] == "resumed"
        assert session.is_paused is False

    @pytest.mark.asyncio
    async def test_resume_not_paused(self):
        mixin, session = _make_session()
        result = await mixin.resume_replay("test_sess")
        assert result["status"] == "not_paused"


class TestStopReplay:
    @pytest.mark.asyncio
    async def test_stop_success(self):
        mixin, session = _make_session()
        session.is_playing = True
        session.is_paused = True
        result = await mixin.stop_replay("test_sess")
        assert result["status"] == "stopped"
        assert session.is_playing is False
        assert session.is_paused is False

    @pytest.mark.asyncio
    async def test_stop_nonexistent(self):
        mixin, _ = _make_session()
        with pytest.raises(ValueError, match="不存在"):
            await mixin.stop_replay("nonexistent")


class TestSeekTo:
    @pytest.mark.asyncio
    async def test_seek_success(self):
        mixin, session = _make_session()
        result = await mixin.seek_to("test_sess", 1)
        assert result["status"] == "seeked"
        assert result["current_index"] == 1

    @pytest.mark.asyncio
    async def test_seek_invalid_index_negative(self):
        mixin, _ = _make_session()
        with pytest.raises(ValueError, match="无效"):
            await mixin.seek_to("test_sess", -1)

    @pytest.mark.asyncio
    async def test_seek_invalid_index_too_large(self):
        mixin, _ = _make_session(event_count=3)
        with pytest.raises(ValueError, match="无效"):
            await mixin.seek_to("test_sess", 10)

    @pytest.mark.asyncio
    async def test_seek_nonexistent(self):
        mixin, _ = _make_session()
        with pytest.raises(ValueError, match="不存在"):
            await mixin.seek_to("nonexistent", 0)


class TestGetReplayStatus:
    @pytest.mark.asyncio
    async def test_status_initial(self):
        mixin, _ = _make_session()
        result = await mixin.get_replay_status("test_sess")
        assert result["is_playing"] is False
        assert result["is_paused"] is False
        assert result["current_event_index"] == 0
        assert result["total_events"] == 3

    @pytest.mark.asyncio
    async def test_status_playing(self):
        mixin, session = _make_session()
        session.is_playing = True
        result = await mixin.get_replay_status("test_sess")
        assert result["is_playing"] is True

    @pytest.mark.asyncio
    async def test_status_nonexistent(self):
        mixin, _ = _make_session()
        with pytest.raises(ValueError, match="不存在"):
            await mixin.get_replay_status("nonexistent")

    @pytest.mark.asyncio
    async def test_progress_calculation(self):
        mixin, session = _make_session(event_count=4)
        session.current_event_index = 2
        result = await mixin.get_replay_status("test_sess")
        assert result["progress"] == 50.0
