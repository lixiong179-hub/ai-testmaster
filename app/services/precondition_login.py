"""前置条件登录Mixin - 自动登录、验证码识别与登录状态检测。

本模块实现前置条件的登录逻辑，包括登录表单填写、验证码识别与求解、
登录状态检测等。作为LoginMixin被PreconditionService组合使用。

核心类:
    - LoginMixin: 登录操作Mixin

模块级函数:
    - _fill_by_selectors: 按选择器列表依次尝试输入文本
    - _click_by_selectors: 按选择器列表依次尝试点击元素

选择器策略:
    采用选择器列表+坐标回退的双重定位策略:
    1. 优先使用CSS选择器定位（精确、快速）
    2. 选择器全部失败时，使用AI识别的坐标回退（兼容性强）

    选择器列表按匹配精度从高到低排列:
    - 精确选择器: input[name="username"], input[id="username"]
    - 模糊选择器: input[placeholder*="用户名"]
    - 通用选择器: input[type="text"]:first-of-type

依赖关系:
    - app.utils.browser_controller_v2: 浏览器控制器
    - app.services.precondition_parser: 数据模型与工具函数

登录流程:
    1. 截图当前页面
    2. AI识别登录表单元素位置
    3. 按选择器列表填写用户名和密码
    4. 检测验证码并识别求解
    5. 点击登录按钮
    6. 轮询检测登录状态（URL/标题/表单元素变化）

安全设计:
    - 密码字段在日志中脱敏为"敏感信息"
    - 登录失败时保存调试截图到logs/debug/目录
"""
import asyncio
import re
from typing import Optional, Dict, Any
from loguru import logger

from app.utils.browser_controller_v2 import ScreenshotConfig
from app.services.precondition_parser import (
    PreconditionError,
    LoginError,
    LoginFormInfo,
    PreconditionTimingConfig,
    handle_precondition_errors,
    solve_captcha_math,
    recognize_login_form,
)


# 用户名输入框选择器列表，按匹配精度从高到低排列
_USERNAME_SELECTORS = [
    'input[placeholder*="账号"]', 'input[placeholder*="用户名"]', 'input[placeholder*="用户"]',
    'input[placeholder*="Account"]', 'input[placeholder*="Username"]',
    'input[name="username"]', 'input[name="user"]', 'input[name="account"]',
    'input[id="username"]', 'input[id="user"]', 'input[id="account"]',
    'input[type="text"]:first-of-type',
    'input[type="text"]'
]

# 密码输入框选择器列表
_PASSWORD_SELECTORS = [
    'input[type="password"]',
    'input[placeholder*="密码"]', 'input[placeholder*="Password"]',
    'input[name="password"]', 'input[id="password"]'
]

# 验证码输入框选择器列表
_CAPTCHA_SELECTORS = [
    'input[placeholder*="验证码"]', 'input[placeholder*="Captcha"]',
    'input[placeholder*="Code"]', 'input[placeholder*="代码"]',
    'input[name="captcha"]', 'input[name="code"]', 'input[name="verifyCode"]',
    'input[id="captcha"]', 'input[id="code"]', 'input[id="verifyCode"]'
]

# 登录按钮选择器列表，覆盖常见UI框架
_BUTTON_SELECTORS = [
    'button:has-text("登录")', 'button:has-text("登入")', 'button:has-text("提交")',
    'button:has-text("Login")', 'button:has-text("Sign in")', 'button:has-text("Submit")',
    'button[type="submit"]', 'input[type="submit"]',
    '.el-button--primary', '.btn-primary', '.login-btn', '.submit-btn',
    'button.btn-login', 'button.btn-submit',
    'button'
]


async def _fill_by_selectors(page, selectors, text, label, fallback_coords=None) -> bool:
    """按选择器列表依次尝试输入文本，全部失败时使用坐标回退。

    定位策略:
        1. 遍历选择器列表，找到第一个可见元素并填充文本
        2. 所有选择器失败时，使用AI识别的坐标点击定位后键盘输入

    Args:
        page: Playwright Page实例。
        selectors: CSS选择器列表，按优先级排列。
        text: 待输入的文本内容。
        label: 输入框标签（用于日志，如"用户名"）。
        fallback_coords: AI识别的坐标回退，可选。

    Returns:
        输入成功返回True，失败返回False。
    """
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                await element.fill(text)
                logger.info(f"使用选择器 {selector} 输入{label}")
                return True
        except Exception as e:
            logger.debug(f"选择器 {selector} 失败: {e}")
            continue

    # 选择器全部失败，使用坐标回退
    if fallback_coords:
        x = fallback_coords["x"] + fallback_coords["width"] // 2
        y = fallback_coords["y"] + fallback_coords["height"] // 2
        await page.mouse.click(x, y)
        cfg = PreconditionTimingConfig()
        await asyncio.sleep(cfg.click_delay)
        # 清空已有内容后输入新文本
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Delete")
        await asyncio.sleep(cfg.fill_delay)
        await page.keyboard.type(text, delay=cfg.input_delay)
        logger.info(f"使用坐标点击输入{label}")
        return True
    return False


async def _click_by_selectors(page, selectors, fallback_coords=None) -> bool:
    """按选择器列表依次尝试点击元素，全部失败时使用坐标回退。

    Args:
        page: Playwright Page实例。
        selectors: CSS选择器列表，按优先级排列。
        fallback_coords: AI识别的坐标回退，可选。

    Returns:
        点击成功返回True，失败返回False。
    """
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                await element.click()
                logger.info(f"使用选择器 {selector} 点击")
                return True
        except Exception as e:
            logger.debug(f"选择器 {selector} 点击失败: {e}")
            continue

    # 选择器全部失败，使用坐标回退
    if fallback_coords:
        x = fallback_coords["x"] + fallback_coords["width"] // 2
        y = fallback_coords["y"] + fallback_coords["height"] // 2
        await page.mouse.click(x, y)
        logger.info("使用坐标点击")
        return True
    return False


class LoginMixin:
    """前置条件登录Mixin - 自动登录、验证码处理与状态检测。

    职责:
        - 自动识别登录表单元素
        - 填写用户名和密码
        - 识别并求解验证码
        - 点击登录按钮
        - 检测登录是否成功

    设计意图:
        将登录逻辑从执行器中抽离，便于:
        1. 独立测试登录流程
        2. 支持不同的登录策略（选择器优先/坐标优先）
        3. 验证码处理逻辑集中管理

    使用场景:
        被PreconditionService通过多继承组合，
        在execute_web_precondition中调用_perform_login执行自动登录。
    """

    @handle_precondition_errors
    async def _perform_login(self, username: str, password: str) -> None:
        """执行自动登录流程：识别表单 -> 填写信息 -> 处理验证码 -> 点击登录 -> 检测状态。

        登录流程:
            1. 截图当前页面
            2. AI识别登录表单元素位置
            3. 按选择器列表填写用户名
            4. 按选择器列表填写密码（日志脱敏）
            5. 检测验证码，存在则识别求解
            6. 点击登录按钮
            7. 轮询检测登录状态

        Args:
            username: 登录用户名。
            password: 登录密码（已解密）。

        Raises:
            PreconditionError: 浏览器或视觉模型未初始化。
            LoginError: 登录表单识别失败或验证码识别失败。
        """
        if not self.browser_controller or not self.vision_model:
            raise PreconditionError("浏览器或视觉模型未初始化")

        logger.info("开始执行自动登录")

        # 截图并识别登录表单
        screenshot = await self.browser_controller.take_screenshot()
        logger.info("页面截图完成")
        login_form = await self._recognize_login_form(screenshot)
        if not login_form.is_complete():
            raise LoginError("未能识别完整的登录表单，请检查页面是否包含用户名、密码输入框和登录按钮")
        logger.info("登录表单识别成功")

        page = self.browser_controller._page

        # 填写用户名
        await _fill_by_selectors(page, _USERNAME_SELECTORS, username, "用户名", login_form.username_input)
        logger.info("用户名输入完成")

        # 填写密码（日志中脱敏为"敏感信息"）
        await _fill_by_selectors(page, _PASSWORD_SELECTORS, password, "敏感信息", login_form.password_input)
        logger.info("敏感信息输入完成")

        # 验证码处理
        if login_form.has_captcha():
            logger.info("检测到验证码，开始识别...")
            captcha_text = await self._recognize_and_solve_captcha(login_form.captcha_image)
            if captcha_text and captcha_text != "无法识别":
                logger.info(f"验证码识别成功: {captcha_text}")
                await _fill_by_selectors(page, _CAPTCHA_SELECTORS, captcha_text, "验证码", login_form.captcha_input)
                logger.info("验证码输入完成")
            else:
                logger.warning("验证码识别失败，无法继续登录")
                raise LoginError("验证码识别失败，请手动输入验证码")
        else:
            logger.info("未检测到验证码")

        # 点击登录按钮
        await _click_by_selectors(page, _BUTTON_SELECTORS, login_form.submit_button)
        logger.info("登录按钮点击完成")

        # 轮询检测登录状态
        logger.info("等待页面跳转...")
        import os
        cfg = self._timing_config
        login_success = False
        for i in range(cfg.max_login_wait_time):
            await asyncio.sleep(cfg.wait_interval)
            page_info = await self.browser_controller.get_page_info()
            current_url = page_info.get('url', '')

            # 检查URL是否不再包含登录关键词
            url_ok = 'login' not in current_url.lower() and 'auth' not in current_url.lower()

            # 检查页面标题是否不再包含登录关键词
            title_ok = False
            try:
                page_title = await self.browser_controller.execute_javascript("document.title")
                if page_title and '登录' not in str(page_title) and 'login' not in str(page_title).lower():
                    title_ok = True
            except Exception:
                pass

            # 检查页面是否还存在登录表单元素
            has_login_form = False
            try:
                login_element_count = await self.browser_controller.execute_javascript("""
                    (function() {
                        var pwInputs = document.querySelectorAll('input[type="password"]');
                        var loginBtns = document.querySelectorAll('button[class*=login], [class*=Login]');
                        return pwInputs.length + loginBtns.length;
                    })()
                """)
                has_login_form = int(login_element_count or 0) > 0
            except Exception:
                pass

            if url_ok and (title_ok or not has_login_form):
                login_success = True
                logger.info(f"登录成功，已进入首页 (URL: {current_url})")
                break
            elif i == cfg.max_login_wait_time - 1:
                # 登录超时，保存调试截图
                logger.warning(f"登录超时，可能仍在登录页面 (URL: {current_url})")
                debug_dir = os.path.join(os.getcwd(), 'logs', 'debug')
                os.makedirs(debug_dir, exist_ok=True)
                from datetime import datetime
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                debug_path = os.path.join(debug_dir, f'login_failed_{ts}.png')
                try:
                    screenshot = await self.browser_controller.take_screenshot()
                    with open(debug_path, 'wb') as f:
                        f.write(screenshot)
                    logger.info(f"已保存登录失败截图: {debug_path}")
                except Exception as e:
                    logger.warning(f"保存登录失败截图失败: {e}")
            else:
                logger.debug(f"等待页面跳转... ({i+1}/{cfg.max_login_wait_time}s)")

        logger.info("自动登录执行完成")

    async def _recognize_login_form(self, screenshot: bytes) -> LoginFormInfo:
        """委托给precondition_parser的recognize_login_form函数。

        Args:
            screenshot: 页面截图字节数据。

        Returns:
            LoginFormInfo实例。
        """
        return recognize_login_form(self.vision_model, screenshot)

    @handle_precondition_errors
    async def _recognize_and_solve_captcha(self, captcha_image_location: Dict[str, Any]) -> str:
        """识别并求解验证码。

        流程:
            1. 截取验证码图片区域（含边距）
            2. 保存调试截图
            3. 调用AI视觉模型识别验证码内容
            4. 使用solve_captcha_math求解

        Args:
            captcha_image_location: 验证码图片位置信息（x/y/width/height）。

        Returns:
            验证码求解结果字符串，识别失败返回空字符串。
        """
        if not self.browser_controller or not self.vision_model:
            logger.warning("浏览器或视觉模型未初始化，无法识别验证码")
            return ""
        try:
            screenshot = await self.browser_controller.take_screenshot()
            cfg = self._timing_config
            # 裁剪验证码区域，添加边距确保完整
            clip_config = ScreenshotConfig(
                clip={
                    "x": max(0, captcha_image_location["x"] - cfg.captcha_padding),
                    "y": max(0, captcha_image_location["y"] - cfg.captcha_padding),
                    "width": captcha_image_location["width"] + cfg.captcha_padding * 2,
                    "height": captcha_image_location["height"] + cfg.captcha_padding * 2
                }
            )
            captcha_screenshot = await self.browser_controller.take_screenshot(clip_config)
            logger.info(f"验证码区域截图完成，大小: {len(captcha_screenshot)} bytes")

            # 保存调试截图
            import os
            import uuid
            debug_dir = os.path.join(os.getcwd(), 'logs', 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            captcha_debug_path = os.path.join(debug_dir, f'captcha_debug_{uuid.uuid4().hex[:8]}.png')
            with open(captcha_debug_path, "wb") as f:
                f.write(captcha_screenshot)
            logger.info(f"验证码截图已保存: {captcha_debug_path}")

            # 截图太小时回退到全页面截图
            if len(captcha_screenshot) < 10000:
                logger.warning("验证码截图太小，尝试使用全页面截图")
                captcha_screenshot = await self.browser_controller.take_screenshot()
                logger.info(f"使用全页面截图，大小: {len(captcha_screenshot)} bytes")

            prompt = """识别验证码图片中的数学表达式，计算并返回结果。

支持的运算符：
- 加法：+ （如 3+5=8）
- 减法：- （如 9-4=5）
- 乘法：* 或 × （如 4×6=24）
- 除法：/ 或 ÷ （如 8÷2=4）

重要：
1. 识别数学表达式（如 "4×6=?"）
2. 计算结果（如 24）
3. 只返回计算结果数字，不要任何其他文字

示例：
- 图片显示 "3+5=?" → 返回：8
- 图片显示 "9-4=?" → 返回：5
- 图片显示 "4×6=?" → 返回：24
- 图片显示 "8÷2=?" → 返回：4
- 图片显示 "7*3=?" → 返回：21
- 无法识别 → 返回："""
            response = self.vision_model.analyze_image(captcha_screenshot, prompt)
            logger.info(f"验证码识别响应: {response}")
            return solve_captcha_math(response)
        except Exception as e:
            logger.error(f"验证码识别失败: {e}")
            return ""

    @handle_precondition_errors
    async def check_login_status(self) -> bool:
        """检测当前是否已登录成功。

        检测策略（任一满足即判定为仍在登录页）:
            1. URL包含login/auth/signin关键词
            2. 页面标题包含登录/login关键词
            3. 页面存在可见的密码输入框

        Returns:
            已登录返回True，仍在登录页返回False。
        """
        if not self.is_browser_ready:
            return False
        try:
            page_info = await self.browser_controller.get_page_info()
            current_url = page_info.get('url', '').lower()
            current_title = page_info.get('title', '').lower()

            # 检查URL中的登录关键词
            login_url_keywords = ['login', 'auth', 'signin']
            for keyword in login_url_keywords:
                if keyword in current_url:
                    logger.info(f"URL包含登录关键词'{keyword}': {current_url}")
                    return False

            # 检查标题中的登录关键词
            login_title_keywords = ['登录', 'login', 'sign in']
            for keyword in login_title_keywords:
                if keyword in current_title:
                    logger.info(f"页面标题包含登录关键词'{keyword}': {current_title}")
                    return False

            # 检查是否存在可见的密码输入框
            page = self.browser_controller._page
            if page:
                has_visible_password = await page.evaluate("""
                    () => {
                        const inputs = document.querySelectorAll('input[type="password"]');
                        for (const input of inputs) {
                            if (input.offsetParent !== null) {
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if has_visible_password:
                    logger.info("页面存在可见的密码输入框，可能仍在登录页面")
                    return False

            return True
        except Exception as e:
            logger.warning(f"登录状态检测异常: {e}")
            return False
