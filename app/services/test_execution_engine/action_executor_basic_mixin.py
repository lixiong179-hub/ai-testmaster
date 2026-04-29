"""基础动作执行Mixin - 处理导航、等待、截图、切换窗口等基础操作。
"""
import asyncio
import re
from typing import Optional, Dict, Any
from loguru import logger

from app.services.test_execution_engine.models import (
    ActionType, StepExecutionError,
)


class ActionExecutorBasicMixin:

    def _parse_step_action(self, action_text: str) -> Dict[str, Any]:
        action_lower = action_text.lower()
        if "导航" in action_text or "访问" in action_text or "打开" in action_text or "navigate" in action_lower:
            return {"type": ActionType.NAVIGATE, "text": action_text}
        elif "验证码" in action_text or "captcha" in action_lower:
            return {"type": ActionType.CAPTCHA, "text": action_text}
        elif "刷新" in action_text or "refresh" in action_lower:
            return {"type": ActionType.REFRESH, "text": action_text}
        elif "按下" in action_text or "按键" in action_text or "key" in action_lower:
            return {"type": ActionType.KEYPRESS, "text": action_text}
        elif "输入" in action_text or "填写" in action_text or "input" in action_lower:
            return {"type": ActionType.INPUT, "text": action_text}
        elif "点击" in action_text or "按下" in action_text or "click" in action_lower:
            return {"type": ActionType.CLICK, "text": action_text}
        elif "验证" in action_text or "检查" in action_text or "assert" in action_lower or "verify" in action_lower:
            return {"type": ActionType.VERIFY, "text": action_text}
        elif "等待" in action_text or "wait" in action_lower:
            return {"type": ActionType.WAIT, "text": action_text}
        elif "滚动" in action_text or "scroll" in action_lower:
            return {"type": ActionType.SCROLL, "text": action_text}
        elif "悬停" in action_text or "hover" in action_lower:
            return {"type": ActionType.HOVER, "text": action_text}
        elif "选择" in action_text or "select" in action_lower:
            return {"type": ActionType.SELECT, "text": action_text}
        else:
            return {"type": ActionType.CLICK, "text": action_text}

    async def _execute_navigate(self, action_info: Dict[str, Any]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        url = self._extract_url(text)
        if url:
            await self.browser.navigate(url)
            logger.info(f"导航到: {url}")
        else:
            raise StepExecutionError(f"无法从动作中提取URL: {text}")

    async def _execute_refresh(self, action_info: Dict[str, Any]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        await self.browser.refresh()
        logger.info("页面刷新完成")

    async def _execute_keypress(self, action_info: Dict[str, Any]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        key = self._extract_key(text)
        await self.browser.press_key(key)
        logger.info(f"按下按键: {key}")

    def _extract_key(self, text: str) -> str:
        if "enter" in text.lower() or "回车" in text:
            return "Enter"
        elif "tab" in text.lower() or "制表" in text:
            return "Tab"
        elif "escape" in text.lower() or "esc" in text.lower():
            return "Escape"
        elif "space" in text.lower() or "空格" in text:
            return "Space"
        else:
            return "Enter"

    async def _execute_wait(self, action_info: Dict[str, Any]) -> None:
        text = action_info.get("text", "")
        wait_seconds = self._extract_wait_time(text)
        logger.info(f"等待 {wait_seconds} 秒")
        await asyncio.sleep(wait_seconds)

    async def _execute_scroll(self, action_info: Dict[str, Any]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        if "下" in text or "down" in text.lower():
            await self.browser.execute_javascript("window.scrollBy(0, 500)")
            logger.info("向下滚动")
        elif "上" in text or "up" in text.lower():
            await self.browser.execute_javascript("window.scrollBy(0, -500)")
            logger.info("向上滚动")
        else:
            await self.browser.execute_javascript("window.scrollBy(0, 500)")
            logger.info("默认向下滚动")

    def _extract_url(self, text: str) -> Optional[str]:
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]\']+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    def _extract_wait_time(self, text: str) -> int:
        match = re.search(r'(\d+)\s*(秒|seconds?)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 2
