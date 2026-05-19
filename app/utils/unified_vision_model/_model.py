from typing import Optional
from loguru import logger

from app.utils.unified_vision_model._types import VisionModelType
from app.utils.unified_vision_model._core_mixin import _VisionCoreMixin
from app.utils.unified_vision_model._api_mixin import _VisionApiMixin


class UnifiedVisionModel(_VisionCoreMixin, _VisionApiMixin):
    def __init__(
        self,
        model_type: VisionModelType = VisionModelType.MIMO,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 2,
        timeout: int = 300,
        temperature: float = 0.3,
    ):
        self._init_core(
            model_type=model_type,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            temperature=temperature,
        )


def create_vision_model(
    model_type: Optional[str] = None,
    **kwargs,
) -> UnifiedVisionModel:
    if model_type is None:
        from app.core.config import settings
        model_type = getattr(settings, 'VISION_MODEL_DEFAULT', 'mimo')
    try:
        model_enum = VisionModelType(model_type.lower())
    except ValueError:
        logger.error(f"不支持的模型类型: {model_type}，使用默认模型mimo")
        model_enum = VisionModelType.MIMO

    return UnifiedVisionModel(model_type=model_enum, **kwargs)


def get_default_vision_model() -> UnifiedVisionModel:
    from app.core.config import settings

    default_model = getattr(settings, 'VISION_MODEL_DEFAULT', 'mimo')
    return create_vision_model(default_model)
