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
        elif "切换iframe" in action_text or "切换frame" in action_text or "switch_frame" in action_lower:
            return {"type": ActionType.SWITCH_FRAME, "text": action_text}
        elif "切换窗口" in action_text or "switch_window" in action_lower:
            return {"type": ActionType.SWITCH_WINDOW, "text": action_text}
        elif "上传" in action_text or "upload" in action_lower:
            return {"type": ActionType.UPLOAD, "text": action_text}
        elif "执行脚本" in action_text or "execute_script" in action_lower:
            return {"type": ActionType.EXECUTE_SCRIPT, "text": action_text}
        elif "截图" in action_text or "screenshot" in action_lower:
            return {"type": ActionType.SCREENSHOT, "text": action_text}
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
            await self.browser.navigate(url, wait_until="networkidle")
            logger.info(f"导航到: {url}")
            return

        relative_path = self._extract_relative_path(text)
        if relative_path:
            base_url = self._get_base_url()
            if not base_url:
                raise StepExecutionError("相对路径导航需要base_url")
            target_url = f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"
            await self.browser.navigate(target_url, wait_until="networkidle")
            logger.info("导航到SPA路径: {}", target_url)
            return

        target_element = action_info.get("target_element") or action_info.get("target")
        if self._is_css_selector(target_element):
            page = getattr(self.browser, "active_page", None) or getattr(self.browser, "_page", None)
            if not page:
                raise StepExecutionError("浏览器页面未初始化")
            try:
                result = page.click(target_element)
                if hasattr(result, "__await__"):
                    await result
                wait_for_load_state = getattr(page, "wait_for_load_state", None)
                if wait_for_load_state:
                    result = wait_for_load_state("networkidle")
                    if hasattr(result, "__await__"):
                        await result
                logger.info("点击导航菜单项: {}", target_element)
                return
            except Exception as exc:
                raise StepExecutionError(f"点击导航菜单项失败: {exc}") from exc

        raise StepExecutionError(f"无法从动作中提取URL或路径: {text}")

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

    async def _execute_switch_frame(self, action_info: Dict[str, Any], step=None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        page = getattr(self.browser, "active_page", None) or getattr(self.browser, "_page", None)
        if not page:
            raise StepExecutionError("浏览器页面未初始化")

        target = (getattr(step, "target_element", "") if step else "") or action_info.get("target") or action_info.get("text", "")
        target = str(target).strip()
        if not target or target.lower() in {"main", "default", "top"}:
            if hasattr(self.browser, "switch_to_main"):
                result = self.browser.switch_to_main()
                if hasattr(result, "__await__"):
                    await result
            elif hasattr(self.browser, "_current_frame"):
                self.browser._current_frame = None
            return
        try:
            frame = None
            is_selector = target.startswith(("#", ".", "[")) or target.startswith("iframe[")
            if is_selector and hasattr(page, "frame_locator"):
                frame = page.frame_locator(target)
            elif hasattr(page, "frame"):
                frame = page.frame(name=target)
                if frame is None:
                    frame = page.frame(url=target)
            if frame is None:
                raise StepExecutionError(f"未找到目标iframe: {target}")
            if hasattr(self.browser, "switch_to_frame"):
                result = self.browser.switch_to_frame(frame)
                if hasattr(result, "__await__"):
                    await result
            else:
                self.browser.active_frame = frame
            logger.info("切换iframe完成: {}", target)
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"切换iframe失败: {exc}") from exc

    async def _execute_switch_window(self, action_info: Dict[str, Any], step=None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        context = getattr(self.browser, "_context", None) or getattr(self.browser, "context", None)
        if not context:
            raise StepExecutionError("浏览器上下文未初始化")

        target = (getattr(step, "target_element", "") if step else "") or action_info.get("target") or action_info.get("text", "")
        target = str(target).strip()
        pages = list(getattr(context, "pages", []) or [])
        try:
            target_page = None
            if target.isdigit():
                index = int(target)
                if 0 <= index < len(pages):
                    target_page = pages[index]
            if target_page is None:
                for page in pages:
                    title = page.title() if hasattr(page, "title") else ""
                    if hasattr(title, "__await__"):
                        title = await title
                    url = getattr(page, "url", "")
                    if target and (target in str(title) or target in str(url)):
                        target_page = page
                        break
            if target_page is None:
                raise StepExecutionError(f"未找到匹配的窗口: {target}")
            bring_to_front = getattr(target_page, "bring_to_front", None)
            if bring_to_front:
                result = bring_to_front()
                if hasattr(result, "__await__"):
                    await result
            self.browser._page = target_page
            self.browser.active_page = target_page
            logger.info("切换窗口完成: {}", target)
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"切换窗口失败: {exc}") from exc

    async def _execute_upload(self, action_info: Dict[str, Any], step=None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        page = getattr(self.browser, "active_page", None) or getattr(self.browser, "_page", None)
        if not page:
            raise StepExecutionError("浏览器页面未初始化")

        selector = (getattr(step, "target_element", "") if step else "") or action_info.get("target") or ""
        file_path = (
            (getattr(step, "input_value", "") if step else "")
            or action_info.get("input_value")
            or action_info.get("file_path")
            or ""
        )
        if not selector:
            raise StepExecutionError("上传文件缺少目标元素选择器")
        if not file_path:
            raise StepExecutionError("上传文件缺少文件路径")
        try:
            result = page.set_input_files(selector, file_path)
            if hasattr(result, "__await__"):
                await result
            logger.info("文件上传完成: {}", selector)
        except Exception as exc:
            raise StepExecutionError(f"文件上传失败: {exc}") from exc

    async def _execute_execute_script(self, action_info: Dict[str, Any], step=None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        page = getattr(self.browser, "active_page", None) or getattr(self.browser, "_page", None)
        if not page:
            raise StepExecutionError("浏览器页面未初始化")

        script = (getattr(step, "input_value", "") if step else "") or action_info.get("script") or action_info.get("text", "")
        if not script:
            raise StepExecutionError("执行脚本缺少JavaScript代码")
        if not self._validate_script_safety(script):
            raise StepExecutionError("脚本安全校验失败")
        try:
            result = page.evaluate(script)
            if hasattr(result, "__await__"):
                await result
            logger.info("脚本执行完成")
        except Exception as exc:
            raise StepExecutionError(f"脚本执行失败: {exc}") from exc

    async def _execute_screenshot(self, action_info: Dict[str, Any]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        try:
            result = self.browser.take_screenshot()
            if hasattr(result, "__await__"):
                await result
            logger.info("截图完成")
        except Exception as exc:
            raise StepExecutionError(f"截图失败: {exc}") from exc

    def _validate_script_safety(self, script: str) -> bool:
        """限制 execute_script 只能执行无副作用的页面内脚本。"""
        if not script:
            return True

        sanitized = re.sub(r"""(['"])(?:\\.|(?!\1).)*\1""", "", script)
        dangerous_patterns = (
            r"\bwhile\s*\(\s*true\s*\)",
            r"\bfor\s*\(\s*;\s*;\s*\)",
            r"\bdocument\s*\.\s*cookie\b",
            r"\bwindow\s*\.\s*location\s*=",
            r"\bnew\s+XMLHttpRequest\s*\(",
            r"\bfetch\s*\(",
            r"\beval\s*\(",
            r"\bnew\s+Function\s*\(",
        )
        return not any(re.search(pattern, sanitized, re.IGNORECASE) for pattern in dangerous_patterns)

    def _extract_url(self, text: str) -> Optional[str]:
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]\']+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    def _extract_relative_path(self, text: str) -> Optional[str]:
        if not text or self._extract_url(text):
            return None
        match = re.search(r"(?<!\S)(/[A-Za-z0-9][A-Za-z0-9/_\-.]*)", text)
        return match.group(1) if match else None

    def _get_base_url(self) -> Optional[str]:
        precondition_service = getattr(self, "precondition_service", None)
        test_object_info = getattr(precondition_service, "test_object_info", None)
        url = getattr(test_object_info, "url", None)
        return str(url) if url else None

    def _is_css_selector(self, value: Optional[str]) -> bool:
        if not value or not isinstance(value, str):
            return False
        if value.startswith(("http://", "https://", "/")):
            return False
        if value.startswith(("#", ".", "[")):
            return True
        return bool(re.match(r"^[A-Za-z][\w-]*(?:[#.\[][^\s]+)", value))

    def _extract_wait_time(self, text: str) -> int:
        match = re.search(r'(\d+)\s*(秒|seconds?)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 2
