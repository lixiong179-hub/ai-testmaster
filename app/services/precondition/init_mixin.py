
"""初始化Mixin - 视觉模型初始化。"""
from typing import Optional

from loguru import logger

from app.services.precondition.decorator import handle_precondition_errors


class InitMixin:
    """初始化Mixin - 管理视觉模型的创建。"""

    vision_model = None

    @handle_precondition_errors
    async def initialize(
        self,
        model_type=None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> 'InitMixin':
        """初始化视觉模型。"""
        if model_type:
            from app.utils.unified_vision_model import UnifiedVisionModel
            self.vision_model = UnifiedVisionModel(
                model_type=model_type,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name
            )
        else:
            from app.utils.unified_vision_model import get_default_vision_model
            self.vision_model = get_default_vision_model()
        logger.info("前置操作服务初始化完成")
        return self
