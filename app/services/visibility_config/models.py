"""
可见模式配置数据模型
"""
from typing import Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class VisibilityLevel(str, Enum):
    """配置级别"""
    GLOBAL = "global"      # 全局级别
    TASK = "task"          # 任务级别
    CASE = "case"          # 用例级别


@dataclass
class VisibilityConfig:
    """可见模式配置"""
    # 浏览器可见性
    headless: bool = True  # True=无头模式(后台运行), False=可见模式(显示窗口)

    # 视频录制
    record_video: bool = False  # 是否录制视频
    video_resolution: Tuple[int, int] = (1920, 1080)  # 视频分辨率
    video_fps: int = 30  # 视频帧率

    # 截图
    take_screenshot: bool = True  # 是否截图
    screenshot_on_failure: bool = True  # 失败时自动截图
    screenshot_on_success: bool = False  # 成功时截图

    # 执行速度
    execution_speed: str = "normal"  # slow/normal/fast
    action_delay_ms: int = 500  # 操作间隔延迟(毫秒)

    # 调试
    highlight_elements: bool = True  # 高亮操作元素
    show_ai_analysis: bool = True  # 显示AI分析过程

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "headless": self.headless,
            "record_video": self.record_video,
            "video_resolution": self.video_resolution,
            "video_fps": self.video_fps,
            "take_screenshot": self.take_screenshot,
            "screenshot_on_failure": self.screenshot_on_failure,
            "screenshot_on_success": self.screenshot_on_success,
            "execution_speed": self.execution_speed,
            "action_delay_ms": self.action_delay_ms,
            "highlight_elements": self.highlight_elements,
            "show_ai_analysis": self.show_ai_analysis
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VisibilityConfig':
        """从字典创建"""
        config = cls()
        if "headless" in data:
            config.headless = data["headless"]
        if "record_video" in data:
            config.record_video = data["record_video"]
        if "video_resolution" in data:
            config.video_resolution = tuple(data["video_resolution"])
        if "video_fps" in data:
            config.video_fps = data["video_fps"]
        if "take_screenshot" in data:
            config.take_screenshot = data["take_screenshot"]
        if "screenshot_on_failure" in data:
            config.screenshot_on_failure = data["screenshot_on_failure"]
        if "screenshot_on_success" in data:
            config.screenshot_on_success = data["screenshot_on_success"]
        if "execution_speed" in data:
            config.execution_speed = data["execution_speed"]
        if "action_delay_ms" in data:
            config.action_delay_ms = data["action_delay_ms"]
        if "highlight_elements" in data:
            config.highlight_elements = data["highlight_elements"]
        if "show_ai_analysis" in data:
            config.show_ai_analysis = data["show_ai_analysis"]
        return config


@dataclass
class ResourceVisibilityRequest:
    """兼容旧测试导出的资源可见性请求模型。"""

    resource_type: str
    resource_id: int
    user_id: int
    user_roles: list[str] = field(default_factory=list)
