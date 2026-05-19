from typing import Optional
from fastapi import WebSocket


class _MessageMixin:

    async def send_log(self, execution_id: str, step_number: int, action: str, status: str, message: str = ""):
        await self.broadcast(execution_id, {
            "type": "log",
            "step_number": step_number,
            "action": action,
            "status": status,
            "message": message
        })

    async def send_screenshot(self, execution_id: str, step_number: int, screenshot_base64: str, highlight_region: Optional[dict] = None):
        message = {
            "type": "screenshot",
            "step_number": step_number,
            "screenshot": screenshot_base64
        }
        if highlight_region:
            message["highlight_region"] = highlight_region
        await self.broadcast(execution_id, message)

    async def send_progress(self, execution_id: str, current_step: int, total_steps: int, estimated_remaining_seconds: Optional[int] = None):
        progress = {
            "type": "progress",
            "current_step": current_step,
            "total_steps": total_steps,
            "percentage": round((current_step / total_steps) * 100, 1)
        }
        if estimated_remaining_seconds is not None:
            progress["estimated_remaining_seconds"] = estimated_remaining_seconds
        await self.broadcast(execution_id, progress)

    async def send_status(self, execution_id: str, status: str, message: str = ""):
        await self.broadcast(execution_id, {
            "type": "status",
            "status": status,
            "message": message
        })

    def get_connection_count(self, execution_id: Optional[str] = None) -> int:
        with self._lock:
            if execution_id:
                return len(self.active_connections.get(execution_id, []))
            total = 0
            for connections in self.active_connections.values():
                total += len(connections)
            return total
