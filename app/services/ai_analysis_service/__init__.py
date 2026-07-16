from app.services.ai_analysis_service._service import (
    AIAnalysisService,
    ai_analysis_service,
    get_ai_analysis_service,
)
from app.services.ai_analysis_service._extract import _ExtractMixin

aio_analysis_service = ai_analysis_service

# 性能优化：使用 AsyncOpenAIClient 替代 None，避免调用时缺客户端
# 走 complete_async + asyncio.wait_for 超时保护
from app.ai.openai_client import AsyncOpenAIClient

_extract_instance = AIAnalysisService(ai_client=AsyncOpenAIClient())

async def extract_test_points_from_content(*args, **kwargs):
    return await _ExtractMixin.extract_test_points_from_content(_extract_instance, *args, **kwargs)

async def extract_test_points_from_ui_specs(*args, **kwargs):
    return await _ExtractMixin.extract_test_points_from_ui_specs(_extract_instance, *args, **kwargs)

__all__ = [
    "AIAnalysisService",
    "ai_analysis_service",
    "aio_analysis_service",
    "get_ai_analysis_service",
    "extract_test_points_from_content",
    "extract_test_points_from_ui_specs",
]
