"""
UI Spec Parser Service - 摹客UI原型视觉解析服务
将摹客导出的UI图通过VLM解析为结构化JSON（ui_spec）
"""
from typing import List, Dict, Any, Optional, Tuple

from app.utils.unified_vision_model import UnifiedVisionModel, get_default_vision_model
from app.core.config import settings

from app.services.ui_spec_parser.core_mixin import UISpecCoreMixin
from app.services.ui_spec_parser.ocr_mixin import UISpecOcrMixin
from app.services.ui_spec_parser.flow_mixin import UISpecFlowMixin


class UISpecParser(UISpecFlowMixin, UISpecOcrMixin, UISpecCoreMixin):
    """
    UI原型图视觉解析服务

    将摹客导出的UI图通过VLM解析为结构化JSON（ui_spec）
    包括：页面元素、导航关系、布局约束、跳转流程等
    """

    def __init__(self, vision_model: Optional[UnifiedVisionModel] = None, parse_mode: Optional[str] = None):
        self.vision_model = vision_model or get_default_vision_model()
        self.parse_mode = parse_mode or getattr(settings, 'UI_PARSER_MODE', 'text')
        self.max_retries = 3
        self.retry_delay = 2
        self._ocr_extractor = None
        self._text_model = None


# 全局实例
ui_spec_parser = UISpecParser()
UISpecParserService = UISpecParser


async def parse_ui_screen_async(image_path: str, screen_name_hint: Optional[str] = None) -> Tuple[bool, Dict[str, Any], str]:
    """异步解析单张UI图"""
    return await ui_spec_parser.parse_single_screen(image_path, screen_name_hint)


async def parse_ui_flow_sync(screens_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """异步生成页面流转"""
    return await ui_spec_parser.parse_multiple_screen_flows(screens_data)


__all__ = [
    "UISpecParser",
    "UISpecParserService",
    "ui_spec_parser",
    "parse_ui_screen_async",
    "parse_ui_flow_sync",
]
