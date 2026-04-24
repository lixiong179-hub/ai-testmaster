"""可见模式配置服务 - 核心配置CRUD
"""
import os
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from loguru import logger

from app.models.project import Project
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.services.visibility_config.models import VisibilityConfig, VisibilityLevel
from app.services.visibility_config.env_loader import VisibilityEnvLoader
from app.services.visibility_config.validator import VisibilityConfigValidator
from app.services.visibility_config.merger import VisibilityConfigMerger


class VisibilityConfigCoreMixin:
    """可见模式配置服务 - 核心CRUD"""

    DEFAULT_GLOBAL_CONFIG = VisibilityConfig(
        headless=True,
        record_video=False,
        video_resolution=(1920, 1080),
        video_fps=30,
        take_screenshot=True,
        screenshot_on_failure=True,
        screenshot_on_success=False,
        execution_speed="normal",
        action_delay_ms=500,
        highlight_elements=True,
        show_ai_analysis=True
    )

    def __init__(self):
        """初始化服务"""
        self._global_config: Optional[VisibilityConfig] = None
        self._task_configs: Dict[int, VisibilityConfig] = {}
        self._case_configs: Dict[int, VisibilityConfig] = {}
        self._video_base_dir = Path("./videos")
        self._screenshot_base_dir = Path("./screenshots")
        self._ensure_directories()

    def _ensure_directories(self):
        """确保目录存在"""
        self._video_base_dir.mkdir(parents=True, exist_ok=True)
        self._screenshot_base_dir.mkdir(parents=True, exist_ok=True)

    def get_global_config(self) -> VisibilityConfig:
        """获取全局可见模式配置"""
        if self._global_config is None:
            self._global_config = VisibilityEnvLoader.load_from_env()
        return self._global_config

    def set_global_config(self, config: VisibilityConfig) -> None:
        """设置全局可见模式配置"""
        self._global_config = config
        logger.info(f"全局可见模式配置已更新: headless={config.headless}, record_video={config.record_video}")

    def get_task_config(self, task: TestTask) -> VisibilityConfig:
        """获取任务级别的可见模式配置"""
        global_config = self.get_global_config()
        if hasattr(task, 'visibility_config') and task.visibility_config:
            try:
                task_config = VisibilityConfig.from_dict(task.visibility_config)
                return VisibilityConfigMerger.merge(global_config, task_config)
            except Exception as e:
                logger.warning(f"解析任务可见模式配置失败: {e}，使用全局配置")
        return global_config

    def get_case_config(self, case: TestCase, task: Optional[TestTask] = None) -> VisibilityConfig:
        """获取用例级别的可见模式配置"""
        config = self.get_global_config()
        if task:
            task_config = self.get_task_config(task)
            config = VisibilityConfigMerger.merge(config, task_config)
        if hasattr(case, 'visibility_config') and case.visibility_config:
            try:
                case_config = VisibilityConfig.from_dict(case.visibility_config)
                config = VisibilityConfigMerger.merge(config, case_config)
            except Exception as e:
                logger.warning(f"解析用例可见模式配置失败: {e}")
        return config

    def update_task_config(self, task: TestTask, config: VisibilityConfig) -> None:
        """更新任务的可见模式配置"""
        task.visibility_config = config.to_dict()
        logger.info(f"任务 {task.id} 的可见模式配置已更新")

    def update_case_config(self, case: TestCase, config: VisibilityConfig) -> None:
        """更新用例的可见模式配置"""
        case.visibility_config = config.to_dict()
        logger.info(f"用例 {case.id} 的可见模式配置已更新")

    def get_video_save_path(self, task_id: int, case_id: int) -> Path:
        """获取视频保存路径"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_case_{case_id}_{timestamp}.webm"
        return self._video_base_dir / filename

    def get_screenshot_save_path(self, task_id: int, case_id: int, step_number: int) -> Path:
        """获取截图保存路径"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_case_{case_id}_step_{step_number}_{timestamp}.png"
        return self._screenshot_base_dir / filename

    def validate_config(self, config: VisibilityConfig) -> Tuple[bool, str]:
        """验证配置是否有效"""
        return VisibilityConfigValidator.validate(config)

    def get_config_summary(self, config: VisibilityConfig) -> str:
        """获取配置摘要"""
        return VisibilityConfigValidator.get_summary(config)
