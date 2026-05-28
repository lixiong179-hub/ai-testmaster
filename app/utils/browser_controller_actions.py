from typing import Optional, Dict, Any, List
from loguru import logger

from app.utils.browser_controller_base import (
    ElementInfo,
    require_initialized,
    handle_browser_errors,
)


class ActionMixin:
    @require_initialized
    @handle_browser_errors
    async def click(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise ValueError(f"坐标必须非负: ({x}, {y})")
        logger.info(f"点击坐标: ({x}, {y})")
        assert self._page is not None
        await self._page.mouse.click(x, y)

    @require_initialized
    @handle_browser_errors
    async def hover(self, x: int, y: int) -> None:
        if x < 0 or y < 0:
            raise ValueError(f"坐标必须非负: ({x}, {y})")
        logger.info(f"悬停坐标: ({x}, {y})")
        assert self._page is not None
        await self._page.mouse.move(x, y)

    @require_initialized
    @handle_browser_errors
    async def click_element(self, selector: str) -> None:
        if not selector:
            raise ValueError("CSS选择器不能为空")
        logger.info(f"点击元素: {selector}")
        assert self._page is not None
        try:
            await self._page.wait_for_selector(selector, state="visible", timeout=5000)
        except TimeoutError:
            from app.utils.browser_controller_base import ElementNotFoundError
            raise ElementNotFoundError(f"元素未找到: {selector}")
        await self._page.click(selector)

    @require_initialized
    @handle_browser_errors
    async def fill(self, selector: str, text: str) -> None:
        if not selector:
            raise ValueError("CSS选择器不能为空")
        logger.info(f"在 {selector} 中填写文本: {text}")
        assert self._page is not None
        await self._page.fill(selector, text)

    @require_initialized
    @handle_browser_errors
    async def type_text(self, selector: str, text: str, delay: int = 50) -> None:
        if not selector:
            raise ValueError("CSS选择器不能为空")
        logger.info(f"在 {selector} 中逐字输入文本: {text}")
        assert self._page is not None
        await self._page.type(selector, text, delay=delay)

    @require_initialized
    @handle_browser_errors
    async def press_key(self, key: str) -> None:
        if not key:
            raise ValueError("按键名称不能为空")
        logger.info(f"按下按键: {key}")
        assert self._page is not None
        await self._page.keyboard.press(key)

    @require_initialized
    @handle_browser_errors
    async def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> None:
        if not selector:
            raise ValueError("CSS选择器不能为空")
        wait_options: Dict[str, Any] = {"state": "visible"}
        if timeout:
            wait_options["timeout"] = timeout
        assert self._page is not None
        await self._page.wait_for_selector(selector, **wait_options)
        logger.info(f"找到元素: {selector}")

    @require_initialized
    @handle_browser_errors
    async def get_page_info(self) -> Dict[str, Any]:
        assert self._page is not None
        title = await self._page.title()
        url = self._page.url
        viewport = await self._page.evaluate(
            "() => ({ width: window.innerWidth, height: window.innerHeight })"
        )
        return {"title": title, "url": url, "viewport": viewport}

    @require_initialized
    @handle_browser_errors
    async def execute_javascript(self, script: str, *args: Any) -> Any:
        if not script:
            raise ValueError("JavaScript代码不能为空")
        assert self._page is not None
        if args:
            if "arguments[" in script:
                payload = {
                    "source": script.replace("arguments[", "__args["),
                    "args": list(args),
                }
                return await self._page.evaluate("""
                    ({ source, args }) => {
                        const __args = args;
                        return eval(source);
                    }
                """, payload)
            payload: Any = args[0] if len(args) == 1 else list(args)
            return await self._page.evaluate(script, payload)
        return await self._page.evaluate(script)

    @require_initialized
    @handle_browser_errors
    async def scroll_to(self, x: int, y: int) -> None:
        assert self._page is not None
        await self._page.evaluate("([scrollX, scrollY]) => window.scrollTo(scrollX, scrollY)", [x, y])

    @require_initialized
    @handle_browser_errors
    async def get_element_info(self, selector: str) -> Optional[ElementInfo]:
        if not selector:
            return None
        try:
            assert self._page is not None
            element = await self._page.query_selector(selector)
            if not element:
                return None
            bbox = await element.bounding_box()
            if not bbox:
                return None
            attrs = await element.evaluate("""
                el => ({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    class: el.className || '',
                    name: el.getAttribute('name') || '',
                    text: el.textContent ? el.textContent.trim().substring(0, 100) : '',
                    type: el.getAttribute('type') || '',
                    placeholder: el.getAttribute('placeholder') || ''
                })
            """)
            return ElementInfo(
                x=bbox['x'], y=bbox['y'], width=bbox['width'], height=bbox['height'],
                tag=attrs.get('tag', ''), id=attrs.get('id', ''),
                class_name=attrs.get('class', ''), name=attrs.get('name', ''),
                text=attrs.get('text', ''),
                attributes={'type': attrs.get('type', ''), 'placeholder': attrs.get('placeholder', '')}
            )
        except Exception as e:
            logger.warning(f"获取元素信息失败: {e}")
            return None

    @require_initialized
    @handle_browser_errors
    async def highlight_element(self, selector: str, duration: int = 2000) -> None:
        if not selector:
            return
        try:
            assert self._page is not None
            await self._page.evaluate("""
                ([selector, duration]) => {
                    const element = document.querySelector(selector);
                    if (element) {
                        const originalOutline = element.style.outline;
                        const originalBackground = element.style.backgroundColor;
                        element.style.outline = '3px solid red';
                        element.style.backgroundColor = 'rgba(255, 0, 0, 0.2)';
                        setTimeout(() => {
                            element.style.outline = originalOutline;
                            element.style.backgroundColor = originalBackground;
                        }, duration);
                    }
                }
            """, [selector, duration])
            logger.info(f"高亮元素: {selector}")
        except Exception as e:
            logger.warning(f"高亮元素失败: {e}")

    @require_initialized
    @handle_browser_errors
    async def find_elements_by_text(self, text: str, tag: str = "*") -> List[Dict[str, Any]]:
        assert self._page is not None
        return await self._page.evaluate("""
            ([tag, text]) => {
                const elements = document.querySelectorAll(tag);
                const results = [];
                elements.forEach((el, index) => {
                    if (el.textContent && el.textContent.includes(text)) {
                        const rect = el.getBoundingClientRect();
                        results.push({
                            index: index, tag: el.tagName.toLowerCase(),
                            text: el.textContent.trim().substring(0, 50),
                            x: rect.x, y: rect.y, width: rect.width, height: rect.height
                        });
                    }
                });
                return results;
            }
        """, [tag, text])

    @require_initialized
    @handle_browser_errors
    async def get_all_input_elements(self) -> List[Dict[str, Any]]:
        assert self._page is not None
        return await self._page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input, textarea, select');
                return Array.from(inputs).map((el, index) => {
                    const rect = el.getBoundingClientRect();
                    return {
                        index: index, tag: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || 'text',
                        id: el.id || '', name: el.getAttribute('name') || '',
                        class: el.className || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        x: rect.x, y: rect.y, width: rect.width, height: rect.height
                    };
                });
            }
        """)
