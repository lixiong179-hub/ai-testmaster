"""Stagehand自愈Mixin - 使用Stagehand云服务进行远程浏览器自愈。

Stagehand在远程Browserbase浏览器上执行操作，
本地Playwright浏览器状态不会同步更新。
建议仅在本地AI自愈不可用时作为最后手段使用。
"""
from typing import Optional, Dict, Any
from loguru import logger

from app.services.test_execution_engine.models import ActionType, StepExecutionError


class SelfHealingStagehandMixin:

    async def _stagehand_self_heal(
        self,
        stagehand_client,
        nl_description: str,
        action_type: ActionType,
        action_info: Dict[str, Any]
    ) -> Optional[str]:
        """使用Stagehand云服务进行自愈。"""
        from app.core.config import settings
        logger.warning(
            "Stagehand自愈将在远程浏览器执行，本地浏览器状态不会同步更新 | "
            f"步骤: {nl_description}"
        )
        try:
            session = await stagehand_client.sessions.start(
                model_name=settings.STAGEHAND_MODEL,
                browser={"type": "browserbase"}
            )
            self._stagehand_session_id = session.id

            current_url = ""
            if self.browser:
                try:
                    current_url = await self.browser.execute_javascript("window.location.href")
                except Exception as e:
                    logger.debug(f"获取当前URL失败: {e}")
            if current_url:
                await stagehand_client.sessions.navigate(session.id, url=current_url)

            action_instruction = nl_description
            if action_type == ActionType.INPUT:
                input_text = action_info.get("input_value", "")
                if input_text:
                    action_instruction = f"{nl_description}，输入内容: {input_text}"

            await stagehand_client.sessions.act(
                session.id,
                input=action_instruction,
                stream_response=False,
            )

            logger.info(f"Stagehand自愈执行成功 | 指令: {action_instruction}")
            return None

        except Exception as e:
            logger.error(f"Stagehand自愈执行失败: {e}")
            raise
        finally:
            if self._stagehand_session_id and stagehand_client:
                try:
                    await stagehand_client.sessions.end(self._stagehand_session_id)
                except Exception as e:
                    logger.debug(f"关闭Stagehand会话失败: {e}")
                self._stagehand_session_id = None

    async def _get_stagehand(self):
        """懒加载Stagehand客户端实例。"""
        from app.core.config import settings
        if not settings.AI_SELF_HEALING_ENABLED:
            self._stagehand_client = None
            return None

        if not settings.BROWSERBASE_API_KEY or not settings.BROWSERBASE_PROJECT_ID:
            self._stagehand_client = None
            return None

        if self._stagehand_client is not None:
            return self._stagehand_client

        try:
            from stagehand import AsyncStagehand
            self._stagehand_client = AsyncStagehand(
                browserbase_api_key=settings.BROWSERBASE_API_KEY,
                browserbase_project_id=settings.BROWSERBASE_PROJECT_ID,
                model_api_key=settings.DEEPSEEK_API_KEY,
            )
            logger.info("Stagehand客户端初始化成功")
            return self._stagehand_client
        except ImportError:
            logger.warning("stagehand包未安装，Stagehand自愈不可用。请运行: pip install stagehand")
            return None
        except Exception as e:
            logger.error(f"Stagehand客户端初始化失败: {e}")
            return None
