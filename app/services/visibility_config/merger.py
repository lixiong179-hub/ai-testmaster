"""可见模式配置 - 配置合并器
"""
from app.services.visibility_config.models import VisibilityConfig


class VisibilityConfigMerger:
    """配置合并器 - 合并不同层级的配置"""

    @staticmethod
    def merge(base: VisibilityConfig, override: VisibilityConfig) -> VisibilityConfig:
        """合并两个配置，override覆盖base"""
        merged = VisibilityConfig()
        config_fields = [
            'headless', 'record_video', 'video_resolution', 'video_fps',
            'take_screenshot', 'screenshot_on_failure', 'screenshot_on_success',
            'execution_speed', 'action_delay_ms', 'highlight_elements', 'show_ai_analysis'
        ]

        for field_name in config_fields:
            base_value = getattr(base, field_name)
            override_value = getattr(override, field_name)

            if isinstance(base_value, bool):
                setattr(merged, field_name, override_value)
            elif override_value is not None:
                setattr(merged, field_name, override_value)
            else:
                setattr(merged, field_name, base_value)

        return merged
