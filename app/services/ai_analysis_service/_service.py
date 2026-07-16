import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger

from app.ai.openai_client import AsyncOpenAIClient
from app.core.config import settings
from app.utils.ai_client_core import AIServiceError
from app.services.ai_analysis_service._extract import _ExtractMixin


class AIAnalysisService(_ExtractMixin):

    def __init__(self, ai_client: Optional[AsyncOpenAIClient]) -> None:
        self.ai_client = ai_client

    async def analyze_requirement(
        self,
        content: str,
        project_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not content or not content.strip():
            return {"test_points": [], "summary": "", "risk_areas": []}

        test_points = await self.extract_test_points_from_content(
            content=content, project_id=project_id, context=context,
        )

        summary = await self._generate_summary(content)

        risk_areas = self._identify_risk_areas(test_points)

        return {
            "test_points": test_points,
            "summary": summary,
            "risk_areas": risk_areas,
        }

    async def _generate_summary(self, content: str) -> str:
        prompt = f"""请用简洁的中文总结以下需求的核心功能点（不超过200字）：

{content[:3000]}"""

        if self.ai_client is None:
            logger.warning("AI客户端未注入，跳过摘要生成")
            return ""
        try:
            # 性能优化：使用 AsyncOpenAIClient.complete_async + 单次调用硬超时
            # 避免长尾 AI 请求阻塞 ASGI worker（与 ai_generator 一致）
            response = await self.ai_client.complete_async(
                prompt=prompt,
                system="你是一名资深测试工程师，擅长总结需求核心功能。",
                temperature=0.3,
                max_tokens=500,
                timeout=float(settings.AI_CALL_TIMEOUT_SECONDS),
            )
            return response.content.strip()
        except asyncio.TimeoutError:
            logger.error(f"AI生成摘要超时（>{settings.AI_CALL_TIMEOUT_SECONDS}s）")
            return ""
        except AIServiceError as e:
            logger.error(f"AI生成摘要失败: {e}")
            return ""
        except Exception as e:
            logger.error(f"生成摘要异常: {e}")
            return ""

    def _identify_risk_areas(
        self, test_points: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        risk_areas: List[Dict[str, Any]] = []

        high_priority_count = sum(
            1 for tp in test_points if tp.get("priority") == 1
        )
        if high_priority_count > 10:
            risk_areas.append({
                "area": "高优先级测试点过多",
                "description": f"共 {high_priority_count} 个高优先级测试点，建议重新评估优先级",
                "severity": "medium",
            })

        modules = set()
        for tp in test_points:
            module = tp.get("module", "")
            if module:
                modules.add(module)

        if len(modules) > 15:
            risk_areas.append({
                "area": "模块数量过多",
                "description": f"共 {len(modules)} 个模块，建议合并相关模块",
                "severity": "low",
            })

        return risk_areas


ai_analysis_service: Optional[AIAnalysisService] = None


def get_ai_analysis_service() -> AIAnalysisService:
    global ai_analysis_service
    if ai_analysis_service is None:
        # 性能优化：使用 AsyncOpenAIClient 替代原 OpenAI SDK 客户端，
        # 统一走 complete_async + asyncio.wait_for 超时保护
        ai_analysis_service = AIAnalysisService(ai_client=AsyncOpenAIClient())
    return ai_analysis_service
