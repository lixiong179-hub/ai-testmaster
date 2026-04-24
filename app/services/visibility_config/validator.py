"""可见模式配置 - 配置验证器
"""
from typing import Tuple
from app.services.visibility_config.models import VisibilityConfig
from app.services.visibility_config.env_loader import VisibilityEnvLoader


class VisibilityConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate(config: VisibilityConfig) -> Tuple[bool, str]:
        """验证配置是否有效"""
        if config.video_resolution[0] < 640 or config.video_resolution[1] < 480:
            return False, "视频分辨率不能小于640x480"
        if config.video_resolution[0] > 3840 or config.video_resolution[1] > 2160:
            return False, "视频分辨率不能大于4K(3840x2160)"
        if config.video_fps < 15 or config.video_fps > 60:
            return False, "视频帧率必须在15-60之间"
        if config.execution_speed not in VisibilityEnvLoader.SPEED_DELAY_MAP:
            return False, f"无效的执行速度: {config.execution_speed}"
        if config.action_delay_ms < 0 or config.action_delay_ms > 5000:
            return False, "操作延迟必须在0-5000毫秒之间"
        return True, ""

    @staticmethod
    def get_summary(config: VisibilityConfig) -> str:
        """获取配置摘要"""
        mode = "无头模式(后台)" if config.headless else "可见模式(显示窗口)"
        video = "录制视频" if config.record_video else "不录制视频"
        screenshot = "截图" if config.take_screenshot else "不截图"
        return f"{mode} | {video} | {screenshot} | 速度:{config.execution_speed}"
