"""Legacy 工具Mixin - 兼容原始 video_service.py 的路径和URL方法。"""
from pathlib import Path
from datetime import datetime


class LegacyUtilsMixin:
    """Legacy 路径和URL工具方法。"""

    def get_video_path(self, task_id: int, case_id: int) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_case_{case_id}_{timestamp}.webm"
        return self._video_base_dir / filename

    def get_video_url(self, video_path: str) -> str:
        relative_path = Path(video_path).relative_to(self._video_base_dir)
        return f"/videos/{relative_path}"
