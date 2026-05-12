"""登录策略Mixin - 选择器定位、验证码识别与表单交互策略。

本模块提供登录流程中的策略层辅助方法，包括CSS选择器定位、
坐标回退点击、验证码识别与求解等。作为LoginStrategyMixin被LoginMixin组合使用。

模块级函数:
    - _fill_by_selectors: 按选择器列表依次尝试输入文本
    - _click_by_selectors: 按选择器列表依次尝试点击元素

核心类:
    - LoginStrategyMixin: 登录策略Mixin，提供验证码处理和表单识别策略

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
    - app.services.precondition.parser_mixin: 数据模型与工具函数
"""
import asyncio
import os
import uuid
from typing import Dict, Any
from loguru import logger

from app.utils.browser_controller_v2 import ScreenshotConfig
from app.services.precondition.models import (
    LoginFormInfo,
    PreconditionTimingConfig,
)
from app.services.precondition.decorator import handle_precondition_errors
from app.services.precondition.utils import solve_captcha_math, recognize_login_form

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


class LoginStrategyMixin:
    """登录策略Mixin - 验证码识别与表单交互策略。

    职责:
        - 委托识别登录表单元素
        - 截取验证码图片并调用视觉模型识别
        - 求解数学验证码表达式

    设计意图:
        将登录策略（验证码处理、表单识别）从核心登录流程中抽离，便于:
        1. 独立测试验证码识别逻辑
        2. 支持不同的验证码类型（数学、文字、滑块等）
        3. 集中管理选择器策略和坐标回退

    使用场景:
        被LoginMixin通过多继承组合，
        在_perform_login中调用_recognize_and_solve_captcha处理验证码。
    """

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
