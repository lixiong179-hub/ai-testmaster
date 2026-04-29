"""
可见模式配置服务

支持多级可见模式配置：
- 全局级别配置（默认）
- 任务级别配置（覆盖全局）
- 用例级别配置（最高优先级）

配置优先级：用例 > 任务 > 全局 > 默认值
"""
import os
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from loguru import logger

from app.models.project import Project
from app.models.test_task import TestTask
from app.models.test_case import TestCase


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


class VisibilityConfigService:
    """可见模式配置服务"""
    
    # 默认全局配置
    DEFAULT_GLOBAL_CONFIG = VisibilityConfig(
        headless=True,  # 默认无头模式
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
    
    # 速度配置映射
    SPEED_DELAY_MAP = {
        "slow": 1000,    # 慢速：1秒延迟
        "normal": 500,   # 正常：0.5秒延迟
        "fast": 100      # 快速：0.1秒延迟
    }
    
    def __init__(self):
        """初始化服务"""
        self._global_config: Optional[VisibilityConfig] = None
        self._task_configs: Dict[int, VisibilityConfig] = {}  # 任务级别配置缓存
        self._case_configs: Dict[int, VisibilityConfig] = {}  # 用例级别配置缓存
        self._video_base_dir = Path("./videos")
        self._screenshot_base_dir = Path("./screenshots")
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保目录存在"""
        self._video_base_dir.mkdir(parents=True, exist_ok=True)
        self._screenshot_base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_global_config(self) -> VisibilityConfig:
        """
        获取全局可见模式配置
        
        Returns:
            全局配置
        """
        if self._global_config is None:
            # 从环境变量读取
            self._global_config = self._load_config_from_env()
        return self._global_config
    
    def set_global_config(self, config: VisibilityConfig) -> None:
        """
        设置全局可见模式配置
        
        Args:
            config: 配置对象
        """
        self._global_config = config
        logger.info(f"全局可见模式配置已更新: headless={config.headless}, record_video={config.record_video}")
    
    def _load_config_from_env(self) -> VisibilityConfig:
        """从环境变量加载配置"""
        config = VisibilityConfig()
        
        # 读取环境变量
        headless = os.getenv("TEST_HEADLESS", "true").lower()
        config.headless = headless in ("true", "1", "yes")
        
        record_video = os.getenv("TEST_RECORD_VIDEO", "false").lower()
        config.record_video = record_video in ("true", "1", "yes")
        
        # 视频分辨率
        video_width = int(os.getenv("TEST_VIDEO_WIDTH", "1920"))
        video_height = int(os.getenv("TEST_VIDEO_HEIGHT", "1080"))
        config.video_resolution = (video_width, video_height)
        
        # 视频帧率
        config.video_fps = int(os.getenv("TEST_VIDEO_FPS", "30"))
        
        # 截图配置
        take_screenshot = os.getenv("TEST_TAKE_SCREENSHOT", "true").lower()
        config.take_screenshot = take_screenshot in ("true", "1", "yes")
        
        screenshot_on_failure = os.getenv("TEST_SCREENSHOT_ON_FAILURE", "true").lower()
        config.screenshot_on_failure = screenshot_on_failure in ("true", "1", "yes")
        
        # 执行速度
        config.execution_speed = os.getenv("TEST_EXECUTION_SPEED", "normal")
        config.action_delay_ms = self.SPEED_DELAY_MAP.get(config.execution_speed, 500)
        
        return config
    
    def get_task_config(self, task: TestTask) -> VisibilityConfig:
        """
        获取任务级别的可见模式配置
        
        Args:
            task: 测试任务对象
            
        Returns:
            任务级别配置（如果任务有配置）或全局配置
        """
        global_config = self.get_global_config()
        
        # 检查任务是否有自定义配置
        if hasattr(task, 'visibility_config') and task.visibility_config:
            try:
                task_config = VisibilityConfig.from_dict(task.visibility_config)
                # 合并配置：任务配置覆盖全局配置
                return self._merge_configs(global_config, task_config)
            except Exception as e:
                logger.warning(f"解析任务可见模式配置失败: {e}，使用全局配置")
        
        return global_config
    
    def get_case_config(self, case: TestCase, task: Optional[TestTask] = None) -> VisibilityConfig:
        """
        获取用例级别的可见模式配置
        
        配置优先级：用例 > 任务 > 全局
        
        Args:
            case: 测试用例对象
            task: 测试任务对象（可选）
            
        Returns:
            合并后的配置
        """
        # 从全局开始
        config = self.get_global_config()
        
        # 应用任务级别配置（如果有）
        if task:
            task_config = self.get_task_config(task)
            config = self._merge_configs(config, task_config)
        
        # 应用用例级别配置（最高优先级）
        if hasattr(case, 'visibility_config') and case.visibility_config:
            try:
                case_config = VisibilityConfig.from_dict(case.visibility_config)
                config = self._merge_configs(config, case_config)
            except Exception as e:
                logger.warning(f"解析用例可见模式配置失败: {e}")
        
        return config
    
    def _merge_configs(self, base: VisibilityConfig, override: VisibilityConfig) -> VisibilityConfig:
        """
        合并两个配置，override覆盖base
        
        合并规则：
        - override中显式设置的值（非None）会覆盖base中的值
        - override中未设置的值（None）保持base中的值
        
        Args:
            base: 基础配置
            override: 覆盖配置
            
        Returns:
            合并后的配置
        """
        merged = VisibilityConfig()
        
        # 定义所有配置字段
        config_fields = [
            'headless', 'record_video', 'video_resolution', 'video_fps',
            'take_screenshot', 'screenshot_on_failure', 'screenshot_on_success',
            'execution_speed', 'action_delay_ms', 'highlight_elements', 'show_ai_analysis'
        ]
        
        # 遍历所有字段
        for field_name in config_fields:
            base_value = getattr(base, field_name)
            override_value = getattr(override, field_name)
            
            # 对于布尔值，需要特殊处理，因为False也是有效值
            if isinstance(base_value, bool):
                # 使用override的值（无论True或False）
                setattr(merged, field_name, override_value)
            # 对于其他类型，如果override的值不是None，则使用override的值
            elif override_value is not None:
                setattr(merged, field_name, override_value)
            else:
                setattr(merged, field_name, base_value)
        
        return merged
    
    def update_task_config(self, task: TestTask, config: VisibilityConfig) -> None:
        """
        更新任务的可见模式配置
        
        Args:
            task: 测试任务
            config: 配置对象
        """
        task.visibility_config = config.to_dict()
        logger.info(f"任务 {task.id} 的可见模式配置已更新")
    
    def update_case_config(self, case: TestCase, config: VisibilityConfig) -> None:
        """
        更新用例的可见模式配置
        
        Args:
            case: 测试用例
            config: 配置对象
        """
        case.visibility_config = config.to_dict()
        logger.info(f"用例 {case.id} 的可见模式配置已更新")
    
    def get_video_save_path(self, task_id: int, case_id: int) -> Path:
        """
        获取视频保存路径
        
        Args:
            task_id: 任务ID
            case_id: 用例ID
            
        Returns:
            视频文件路径
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_case_{case_id}_{timestamp}.webm"
        return self._video_base_dir / filename
    
    def get_screenshot_save_path(self, task_id: int, case_id: int, step_number: int) -> Path:
        """
        获取截图保存路径
        
        Args:
            task_id: 任务ID
            case_id: 用例ID
            step_number: 步骤编号
            
        Returns:
            截图文件路径
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_case_{case_id}_step_{step_number}_{timestamp}.png"
        return self._screenshot_base_dir / filename
    
    def validate_config(self, config: VisibilityConfig) -> Tuple[bool, str]:
        """
        验证配置是否有效
        
        Args:
            config: 配置对象
            
        Returns:
            (是否有效, 错误信息)
        """
        # 验证视频分辨率
        if config.video_resolution[0] < 640 or config.video_resolution[1] < 480:
            return False, "视频分辨率不能小于640x480"
        
        if config.video_resolution[0] > 3840 or config.video_resolution[1] > 2160:
            return False, "视频分辨率不能大于4K(3840x2160)"
        
        # 验证视频帧率
        if config.video_fps < 15 or config.video_fps > 60:
            return False, "视频帧率必须在15-60之间"
        
        # 验证执行速度
        if config.execution_speed not in self.SPEED_DELAY_MAP:
            return False, f"无效的执行速度: {config.execution_speed}"
        
        # 验证延迟
        if config.action_delay_ms < 0 or config.action_delay_ms > 5000:
            return False, "操作延迟必须在0-5000毫秒之间"
        
        return True, ""
    
    def get_config_summary(self, config: VisibilityConfig) -> str:
        """
        获取配置摘要
        
        Args:
            config: 配置对象
            
        Returns:
            配置摘要字符串
        """
        mode = "无头模式(后台)" if config.headless else "可见模式(显示窗口)"
        video = "录制视频" if config.record_video else "不录制视频"
        screenshot = "截图" if config.take_screenshot else "不截图"
        
        return f"{mode} | {video} | {screenshot} | 速度:{config.execution_speed}"


# 全局配置服务实例
_visibility_config_service: Optional[VisibilityConfigService] = None


def get_visibility_config_service() -> VisibilityConfigService:
    """获取可见模式配置服务实例（单例）"""
    global _visibility_config_service
    if _visibility_config_service is None:
        _visibility_config_service = VisibilityConfigService()
    return _visibility_config_service
