from enum import Enum
from typing import Dict, Any
from dataclasses import dataclass


class VisibilityLevel(str, Enum):
    NONE = "none"
    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"
    FULL = "full"


@dataclass
class VisibilityConfig:
    headless: bool = True
    record_video: bool = False
    video_resolution: tuple = (1920, 1080)
    video_fps: int = 30
    take_screenshot: bool = True
    screenshot_on_failure: bool = True
    screenshot_on_success: bool = False
    execution_speed: str = "normal"
    action_delay_ms: int = 500
    highlight_elements: bool = True
    show_ai_analysis: bool = True

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "headless": self.headless,
            "record_video": self.record_video,
            "video_resolution": {
                "width": self.video_resolution[0],
                "height": self.video_resolution[1]
            } if isinstance(self.video_resolution, tuple) else self.video_resolution,
            "video_fps": self.video_fps,
            "take_screenshot": self.take_screenshot,
            "screenshot_on_failure": self.screenshot_on_failure,
            "screenshot_on_success": self.screenshot_on_success,
            "execution_speed": self.execution_speed,
            "action_delay_ms": self.action_delay_ms,
            "highlight_elements": self.highlight_elements,
            "show_ai_analysis": self.show_ai_analysis,
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisibilityConfig":
        if 'video_resolution' in data and isinstance(data['video_resolution'], dict):
            res = data['video_resolution']
            data['video_resolution'] = (res.get('width', 1920), res.get('height', 1080))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def get_level(self) -> VisibilityLevel:
        if not self.headless and self.record_video and self.highlight_elements:
            return VisibilityLevel.FULL
        if not self.headless and (self.record_video or self.highlight_elements):
            return VisibilityLevel.DETAILED
        if self.headless and self.take_screenshot and self.highlight_elements:
            return VisibilityLevel.STANDARD
        if self.headless and self.take_screenshot:
            return VisibilityLevel.MINIMAL
        return VisibilityLevel.NONE


DEFAULT_CONFIG = VisibilityConfig()
