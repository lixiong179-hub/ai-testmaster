"""前置条件登录Mixin - 自动登录、验证码识别与登录状态检测。

本模块实现前置条件的登录逻辑，包括登录表单填写、验证码识别与求解、
登录状态检测等。作为LoginMixin被PreconditionService组合使用。

核心类:
    - LoginMixin: 登录操作Mixin

设计模式:
    作为Mixin模块，通过多继承组合到PreconditionService中，提供:
    - _perform_login: 执行自动登录流程
    - check_login_status: 检测登录状态
    - _recognize_login_form: 识别登录表单（继承自LoginStrategyMixin）
    - _recognize_and_solve_captcha: 验证码识别（继承自LoginStrategyMixin）

依赖关系:
    - app.utils.browser_controller_v2: 浏览器控制器
    - app.services.precondition.login_strategy_mixin: 登录策略（选择器、验证码等）
    - app.services.precondition.parser_mixin: 数据模型与工具函数

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
import os
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

from app.services.precondition.login_strategy_mixin import (
    LoginStrategyMixin,
    _fill_by_selectors,
    _click_by_selectors,
    _USERNAME_SELECTORS,
    _PASSWORD_SELECTORS,
    _CAPTCHA_SELECTORS,
    _BUTTON_SELECTORS,
)
from app.services.precondition.models import (
    PreconditionError,
    LoginError,
    PreconditionTimingConfig,
)
from app.services.precondition.decorator import handle_precondition_errors


class LoginMixin(LoginStrategyMixin):
    """前置条件登录Mixin - 自动登录、验证码处理与状态检测。

    职责:
        - 自动识别登录表单元素
        - 填写用户名和密码
        - 识别并求解验证码（继承自LoginStrategyMixin）
        - 点击登录按钮
        - 检测登录是否成功

    设计意图:
        将登录逻辑从执行器中抽离，便于:
        1. 独立测试登录流程
        2. 支持不同的登录策略（选择器优先/坐标优先）
        3. 验证码处理逻辑集中管理（在LoginStrategyMixin中）

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
