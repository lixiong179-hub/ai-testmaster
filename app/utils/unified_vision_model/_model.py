from typing import Optional
from loguru import logger

from app.utils.unified_vision_model._types import VisionModelType, resolve_default_model_type
from app.utils.unified_vision_model._core_mixin import _VisionCoreMixin
from app.utils.unified_vision_model._api_mixin import _VisionApiMixin


class UnifiedVisionModel(_VisionCoreMixin, _VisionApiMixin):
    def __init__(
        self,
        model_type: Optional[VisionModelType] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 2,
        timeout: int = 300,
        temperature: float = 0.3,
        max_tokens: int = 4096,
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
            max_tokens=max_tokens,
        )


def create_vision_model(
    model_type: Optional[str] = None,
    **kwargs,
) -> UnifiedVisionModel:
    if model_type is None:
        model_enum = resolve_default_model_type()
    else:
        try:
            model_enum = VisionModelType(model_type.lower())
        except ValueError:
            fallback = resolve_default_model_type()
            logger.error(f"不支持的模型类型: {model_type}，使用默认模型{fallback.value}")
            model_enum = fallback

    return UnifiedVisionModel(model_type=model_enum, **kwargs)


def get_default_vision_model() -> UnifiedVisionModel:
    from app.core.config import settings

    max_tokens = getattr(settings, 'VISION_MAX_TOKENS', 4096)
    return create_vision_model(max_tokens=max_tokens)
