"""基础动作执行Mixin - 处理导航、等待、截图、切换窗口等基础操作。"""

import asyncio
import re
from typing import Any
from loguru import logger

from app.services.test_execution_engine.models import (
    ActionType,
    StepExecutionError,
)


# 动作关键词表：按声明顺序匹配，先命中者生效（与原 if/elif 链等价）
_ACTION_RULES: tuple[tuple[tuple[str, ...], ActionType], ...] = (
    (("导航", "访问", "打开", "navigate"), ActionType.NAVIGATE),
    (("验证码", "captcha"), ActionType.CAPTCHA),
    (("刷新", "refresh"), ActionType.REFRESH),
    (("切换iframe", "切换frame", "switch_frame"), ActionType.SWITCH_FRAME),
    (("切换窗口", "switch_window"), ActionType.SWITCH_WINDOW),
    (("上传", "upload"), ActionType.UPLOAD),
    (("执行脚本", "execute_script"), ActionType.EXECUTE_SCRIPT),
    (("截图", "screenshot"), ActionType.SCREENSHOT),
    (("按下", "按键", "key"), ActionType.KEYPRESS),
    (("输入", "填写", "input"), ActionType.INPUT),
    (("点击", "按下", "click"), ActionType.CLICK),
    (("验证", "检查", "assert", "verify"), ActionType.VERIFY),
    (("等待", "wait"), ActionType.WAIT),
    (("滚动", "scroll"), ActionType.SCROLL),
    (("悬停", "hover"), ActionType.HOVER),
    (("选择", "select"), ActionType.SELECT),
)


def _match_action_type(action_text: str, action_lower: str) -> ActionType:
    """按关键词表匹配动作类型，未命中回退 CLICK。"""
    for keywords, action_type in _ACTION_RULES:
        if any(keyword in action_text or keyword in action_lower for keyword in keywords):
            return action_type
    return ActionType.CLICK


def _resolve_switch_target(action_info: dict[str, Any], step: Any) -> str:
    """优先级：step.target_element → action_info.target → action_info.text。"""
    target = (
        (getattr(step, "target_element", "") if step else "")
        or action_info.get("target")
        or action_info.get("text", "")
    )
    return str(target).strip()


def _locate_frame(page: Any, target: str) -> Any:
    """按 CSS/iframe 选择器定位，否则按 name/url 定位；均失败返回 None。"""
    is_selector = target.startswith(("#", ".", "[")) or target.startswith("iframe[")
    if is_selector and hasattr(page, "frame_locator"):
        return page.frame_locator(target)
    if hasattr(page, "frame"):
        frame = page.frame(name=target)
        return frame if frame is not None else page.frame(url=target)
    return None


async def _find_target_page(pages: list, target: str) -> Any:
    """按序号或标题/URL 匹配目标窗口，未找到返回 None。"""
    if target.isdigit():
        index = int(target)
        if 0 <= index < len(pages):
            return pages[index]
    for page in pages:
        title = page.title() if hasattr(page, "title") else ""
        if hasattr(title, "__await__"):
            title = await title
        url = getattr(page, "url", "")
        if target and (target in str(title) or target in str(url)):
            return page
    return None


class ActionExecutorBasicMixin:
    def _parse_step_action(self, action_text: str) -> dict[str, Any]:
        action_type = _match_action_type(action_text, action_text.lower())
        return {"type": action_type, "text": action_text}

    def _get_active_page(self) -> Any:
        return getattr(self.browser, "active_page", None) or getattr(self.browser, "_page", None)

    async def _execute_navigate(self, action_info: dict[str, Any]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        url = self._extract_url(text)
        if url:
            await self._navigate_to_url(url)
            return

        relative_path = self._extract_relative_path(text)
        if relative_path:
            await self._navigate_to_relative_path(relative_path)
            return

        target_element = action_info.get("target_element") or action_info.get("target")
        if self._is_css_selector(target_element):
            await self._navigate_by_menu_click(target_element)
            return

        raise StepExecutionError(f"无法从动作中提取URL或路径: {text}")

    async def _navigate_to_url(self, url: str) -> None:
        await self.browser.navigate(url, wait_until="networkidle")
        logger.info(f"导航到: {url}")

    async def _navigate_to_relative_path(self, relative_path: str) -> None:
        base_url = self._get_base_url()
        if not base_url:
            raise StepExecutionError("相对路径导航需要base_url")
        target_url = f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"
        await self.browser.navigate(target_url, wait_until="networkidle")
        logger.info("导航到SPA路径: {}", target_url)

    async def _navigate_by_menu_click(self, target_element: str) -> None:
        """无 URL/路径时，以菜单项点击完成 SPA 路由跳转。"""
        page = self._get_active_page()
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
        except Exception as exc:
            raise StepExecutionError(f"点击导航菜单项失败: {exc}") from exc

    async def _execute_refresh(self, action_info: dict[str, Any]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        await self.browser.refresh()
        logger.info("页面刷新完成")

    async def _execute_keypress(self, action_info: dict[str, Any]) -> None:
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

    async def _execute_wait(self, action_info: dict[str, Any]) -> None:
        text = action_info.get("text", "")
        wait_seconds = self._extract_wait_time(text)
        logger.info(f"等待 {wait_seconds} 秒")
        await asyncio.sleep(wait_seconds)

    async def _execute_scroll(self, action_info: dict[str, Any]) -> None:
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

    async def _execute_switch_frame(self, action_info: dict[str, Any], step=None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        page = self._get_active_page()
        if not page:
            raise StepExecutionError("浏览器页面未初始化")

        target = _resolve_switch_target(action_info, step)
        if not target or target.lower() in {"main", "default", "top"}:
            await self._switch_to_main_frame()
            return
        try:
            frame = _locate_frame(page, target)
            if frame is None:
                raise StepExecutionError(f"未找到目标iframe: {target}")
            await self._activate_frame(frame)
            logger.info("切换iframe完成: {}", target)
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"切换iframe失败: {exc}") from exc

    async def _switch_to_main_frame(self) -> None:
        if hasattr(self.browser, "switch_to_main"):
            result = self.browser.switch_to_main()
            if hasattr(result, "__await__"):
                await result
        elif hasattr(self.browser, "_current_frame"):
            self.browser._current_frame = None

    async def _activate_frame(self, frame: Any) -> None:
        if hasattr(self.browser, "switch_to_frame"):
            result = self.browser.switch_to_frame(frame)
            if hasattr(result, "__await__"):
                await result
        else:
            self.browser.active_frame = frame

    async def _execute_switch_window(self, action_info: dict[str, Any], step=None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        context = getattr(self.browser, "_context", None) or getattr(self.browser, "context", None)
        if not context:
            raise StepExecutionError("浏览器上下文未初始化")

        target = _resolve_switch_target(action_info, step)
        pages = list(getattr(context, "pages", []) or [])
        try:
            target_page = await _find_target_page(pages, target)
            if target_page is None:
                raise StepExecutionError(f"未找到匹配的窗口: {target}")
            await self._activate_page(target_page)
            logger.info("切换窗口完成: {}", target)
        except StepExecutionError:
            raise
        except Exception as exc:
            raise StepExecutionError(f"切换窗口失败: {exc}") from exc

    async def _activate_page(self, page: Any) -> None:
        bring_to_front = getattr(page, "bring_to_front", None)
        if bring_to_front:
            result = bring_to_front()
            if hasattr(result, "__await__"):
                await result
        self.browser._page = page
        self.browser.active_page = page

    async def _execute_upload(self, action_info: dict[str, Any], step=None) -> None:
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

    async def _execute_execute_script(self, action_info: dict[str, Any], step=None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        page = getattr(self.browser, "active_page", None) or getattr(self.browser, "_page", None)
        if not page:
            raise StepExecutionError("浏览器页面未初始化")

        script = (
            (getattr(step, "input_value", "") if step else "")
            or action_info.get("script")
            or action_info.get("text", "")
        )
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

    async def _execute_screenshot(self, action_info: dict[str, Any]) -> None:
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

    def _extract_url(self, text: str) -> str | None:
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]\']+'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    def _extract_relative_path(self, text: str) -> str | None:
        if not text or self._extract_url(text):
            return None
        match = re.search(r"(?<!\S)(/[A-Za-z0-9][A-Za-z0-9/_\-.]*)", text)
        return match.group(1) if match else None

    def _get_base_url(self) -> str | None:
        precondition_service = getattr(self, "precondition_service", None)
        test_object_info = getattr(precondition_service, "test_object_info", None)
        url = getattr(test_object_info, "url", None)
        return str(url) if url else None

    def _is_css_selector(self, value: str | None) -> bool:
        if not value or not isinstance(value, str):
            return False
        if value.startswith(("http://", "https://", "/")):
            return False
        if value.startswith(("#", ".", "[")):
            return True
        return bool(re.match(r"^[A-Za-z][\w-]*(?:[#.\[][^\s]+)", value))

    def _extract_wait_time(self, text: str) -> int:
        match = re.search(r"(\d+)\s*(秒|seconds?)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 2
