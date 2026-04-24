"""Legacy 查询Mixin - execution_replay_service.py 原始查询逻辑。"""
from typing import Optional, Dict, Any, List
from loguru import logger

from app.services.execution_replay.legacy_models import ReplayEvent


class LegacyQueryMixin:
    """回放数据查询：截图、事件范围。"""

    async def get_screenshot_at_time(
        self, execution_id: str, timestamp: float
    ) -> Optional[str]:
        session = self._active_replays.get(execution_id)
        if not session:
            return None
        screenshots = session.get("screenshots", [])
        if not screenshots:
            return None
        timeline = session["timeline"]
        for event in timeline.events:
            if event.event_type == "screenshot" and event.timestamp <= timestamp:
                return event.data.get("url")
        return screenshots[0] if screenshots else None

    async def get_events_in_range(
        self, execution_id: str, start_time: float, end_time: float
    ) -> List[ReplayEvent]:
        session = self._active_replays.get(execution_id)
        if not session:
            return []
        timeline = session["timeline"]
        events = []
        for event in timeline.events:
            if start_time <= event.timestamp <= end_time:
                events.append(event)
        return events
