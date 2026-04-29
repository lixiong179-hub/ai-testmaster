"""查询Mixin - 查询执行回放数据。
"""
import os
import base64
from typing import Optional, Dict, Any, List
from loguru import logger

from app.services.execution_replay.models import ReplayEvent


class QueryMixin:

    async def get_screenshot_at_time(self, session_id: str, timestamp: float) -> Optional[str]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        closest_event = None
        min_diff = float('inf')

        for event in session.timeline.events:
            diff = abs(event.timestamp - timestamp)
            if diff < min_diff:
                min_diff = diff
                closest_event = event

        if closest_event and closest_event.screenshot_path:
            if os.path.exists(closest_event.screenshot_path):
                with open(closest_event.screenshot_path, 'rb') as f:
                    screenshot_data = f.read()
                return base64.b64encode(screenshot_data).decode('utf-8')

        return None

    async def get_events_in_range(
        self,
        session_id: str,
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        events = []
        for event in session.timeline.events:
            if start_time <= event.timestamp <= end_time:
                events.append(event.to_dict())

        return events
