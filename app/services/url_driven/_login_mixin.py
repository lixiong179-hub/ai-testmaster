"""站点探索 - 轻量选择器登录 Mixin。

用纯 CSS 选择器定位登录表单的用户名/密码/提交按钮完成自动登录，
不依赖 AI vision_model，避免探索阶段引入重模型推理开销与不确定性。
登录失败统一降级为仅探索登录页（spec Scenario：登录失败降级探索登录页）。

定位策略遵循“取首个可见”原则，覆盖中英文常见字段命名与提交按钮文案；
page 对象由 SiteExplorer.explore 从 BrowserControllerV2.active_page 注入。
"""
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from app.utils.browser_controller_v2 import BrowserControllerV2

# 密码框唯一选择器：type=password 是登录表单的强特征
_PASSWORD_SELECTOR = 'input[type="password"]'

# 用户名框候选选择器：name 语义优先于通用 type，按命中优先级排序
_USERNAME_SELECTORS: Tuple[str, ...] = (
    'input[name*="user" i]',
    'input[name*="account" i]',
    'input[name*="email" i]',
    'input[name*="name" i]',
    'input[type="text"]',
    'input:not([type])',
)

# 提交按钮候选选择器：覆盖标准 submit 与中英文登录按钮文案
_SUBMIT_SELECTORS: Tuple[str, ...] = (
    'button[type="submit"]',
    'button:has-text("登录")',
    'button:has-text("login")',
    'button:has-text("sign in")',
    'input[type="submit"]',
)


class LoginMixin:
    """轻量选择器登录 Mixin。

    提供 _login_with_selectors 以纯 CSS 选择器完成登录表单定位与提交，
    成功后由调用方重新采集登录后页面快照；自身不持有浏览器资源。
    依赖宿主类的 _detect_login_page 判定登录态与 _page_timeout_ms 控制等待。
    """

    async def _login_with_selectors(
        self, controller: BrowserControllerV2, credentials: Dict[str, str]
    ) -> bool:
        """用 CSS 选择器定位登录表单并提交，不依赖 AI，失败降级返回 False。

        成功判定：提交后页面不再含可见 password 输入框（宿主 _detect_login_page
        返回 False）；任何定位/填写/提交异常均视为登录失败降级为仅探索登录页。

        Args:
            controller: 已初始化的浏览器控制器，active_page 须为登录页。
            credentials: 登录凭据 {"username", "password"}，缺一即返回 False。

        Returns:
            True 表示登录成功；False 表示失败或异常，调用方应仅探索登录页。
        """
        username = credentials.get("username")
        password = credentials.get("password")
        if not username or not password:
            logger.warning("登录凭据不完整，跳过选择器自动登录")
            return False

        page = controller.active_page
        if page is None:
            logger.warning("浏览器无活动页面，跳过选择器自动登录")
            return False

        page_timeout: int = getattr(self, "_page_timeout_ms", 30000)
        try:
            password_input = await self._locate_first_visible(page, (_PASSWORD_SELECTOR,))
            if password_input is None:
                logger.warning("未定位到可见密码框，跳过选择器自动登录")
                return False
            username_input = await self._locate_first_visible(page, _USERNAME_SELECTORS)
            if username_input is None:
                logger.warning("未定位到可见用户名框，跳过选择器自动登录")
                return False
            submit_button = await self._locate_first_visible(page, _SUBMIT_SELECTORS)
            if submit_button is None:
                logger.warning("未定位到可见提交按钮，跳过选择器自动登录")
                return False

            await username_input.fill(username)
            await password_input.fill(password)
            await submit_button.click()
            await self._wait_login_settle(page, page_timeout)

            if await self._detect_login_page(page):
                logger.warning("登录后仍检测到登录页，降级为仅探索登录页")
                return False
            logger.info("选择器自动登录成功")
            return True
        except Exception as e:
            logger.warning(f"选择器自动登录异常，降级为仅探索登录页: {e}")
            return False

    async def _locate_first_visible(
        self, page: Any, selectors: Tuple[str, ...]
    ) -> Optional[Any]:
        """按候选选择器顺序取首个可见元素，全部不可见返回 None。

        用 locator.first + is_visible 逐个判定，避免 count() 误判隐藏元素；
        单个选择器判定异常不阻断后续选择器，统一吞掉后继续。
        """
        for selector in selectors:
            try:
                candidate = page.locator(selector).first
                if await candidate.is_visible():
                    return candidate
            except Exception as e:
                logger.debug(f"选择器定位异常 {selector}: {e}")
        return None

    async def _wait_login_settle(self, page: Any, timeout_ms: int) -> None:
        """等待登录提交后页面稳定：优先 domcontentloaded，未跳转再等 URL 变化。

        domcontentloaded 覆盖整页导航；URL 变化等待覆盖 SPA 前端路由跳转；
        两者皆未触发时由调用方按 _detect_login_page 兜底判定登录态。
        """
        url_before = page.url
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception as e:
            logger.debug(f"等待 domcontentloaded 失败，转而等待 URL 变化: {e}")
        if page.url == url_before:
            try:
                await page.wait_for_url(lambda u: u != url_before, timeout=timeout_ms)
            except Exception as e:
                logger.debug(f"等待 URL 变化失败，交由登录页检测兜底: {e}")
