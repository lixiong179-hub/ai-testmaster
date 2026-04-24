"""可见模式配置 - 环境变量加载器
"""
import os
from app.services.visibility_config.models import VisibilityConfig


class VisibilityEnvLoader:
    """从环境变量加载可见模式配置"""

    SPEED_DELAY_MAP = {
        "slow": 1000,
        "normal": 500,
        "fast": 100
    }

    @staticmethod
    def load_from_env() -> VisibilityConfig:
        """从环境变量加载配置"""
        config = VisibilityConfig()

        headless = os.getenv("TEST_HEADLESS", "true").lower()
        config.headless = headless in ("true", "1", "yes")

        record_video = os.getenv("TEST_RECORD_VIDEO", "false").lower()
        config.record_video = record_video in ("true", "1", "yes")

        video_width = int(os.getenv("TEST_VIDEO_WIDTH", "1920"))
        video_height = int(os.getenv("TEST_VIDEO_HEIGHT", "1080"))
        config.video_resolution = (video_width, video_height)

        config.video_fps = int(os.getenv("TEST_VIDEO_FPS", "30"))

        take_screenshot = os.getenv("TEST_TAKE_SCREENSHOT", "true").lower()
        config.take_screenshot = take_screenshot in ("true", "1", "yes")

        screenshot_on_failure = os.getenv("TEST_SCREENSHOT_ON_FAILURE", "true").lower()
        config.screenshot_on_failure = screenshot_on_failure in ("true", "1", "yes")

        config.execution_speed = os.getenv("TEST_EXECUTION_SPEED", "normal")
        config.action_delay_ms = VisibilityEnvLoader.SPEED_DELAY_MAP.get(config.execution_speed, 500)

        return config
