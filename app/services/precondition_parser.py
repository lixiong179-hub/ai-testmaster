"""前置条件解析器 - 数据模型、异常定义与工具函数。

本模块定义前置条件体系所需的数据模型、异常体系和工具函数，
被PreconditionService及其Mixin共同依赖。

核心类:
    - TestObjectType: 被测对象类型枚举（WEB/APP）
    - PreconditionError: 前置条件基础异常
    - PreconditionConfigError: 配置错误异常
    - LoginError: 登录错误异常
    - TestObjectInfo: 被测对象信息数据类
    - LoginFormInfo: Web登录表单信息数据类
    - MobileLoginFormInfo: 移动端登录表单信息数据类
    - MobileAppConfig: 移动端App配置数据类
    - PreconditionTimingConfig: 前置条件时序配置数据类

核心函数:
    - handle_precondition_errors: 前置条件错误处理装饰器
    - solve_captcha_math: 数学验证码求解
    - recognize_login_form: AI识别登录表单元素位置

依赖关系:
    - app.utils.unified_vision_model: 视觉模型（用于登录表单识别）

异常体系设计:
    PreconditionError (基础异常)
    ├── PreconditionConfigError (配置错误)
    └── LoginError (登录错误)

    handle_precondition_errors装饰器将所有非PreconditionError异常
    转换为PreconditionError，统一错误处理。
"""
import functools
import traceback
import json
import re
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class TestObjectType(str, Enum):
    """被测对象类型枚举。"""
    WEB = "web"
    APP = "app"


class PreconditionError(Exception):
    """前置条件基础异常，所有前置条件相关异常的基类。"""
    pass


class PreconditionConfigError(PreconditionError):
    """前置条件配置错误，如缺少必填配置项。"""
    pass


class LoginError(PreconditionError):
    """登录错误，如登录表单识别失败、验证码识别失败。"""
    pass


@dataclass
class TestObjectInfo:
    """被测对象信息 - 存储Web/App项目的连接和认证信息。

    属性:
        type: 被测对象类型（WEB/APP）。
        url: Web项目访问地址。
        username: 登录用户名。
        password: 登录密码（已解密）。
        device_id: App设备ID。
        app_package: App包名。
        app_activity: App启动Activity。
    """
    type: TestObjectType
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    device_id: Optional[str] = None
    app_package: Optional[str] = None
    app_activity: Optional[str] = None

    def validate_web(self) -> None:
        """校验Web项目必填字段：URL必须存在且格式正确。

        Raises:
            PreconditionConfigError: URL缺失或格式无效。
        """
        if not self.url:
            raise PreconditionConfigError("Web项目必须配置访问地址(URL)")
        if not self.url.startswith(("http://", "https://")):
            raise PreconditionConfigError(f"无效的URL格式: {self.url}")

    def validate_app(self) -> None:
        """校验App项目必填字段：设备ID和包名必须存在。

        Raises:
            PreconditionConfigError: 设备ID或包名缺失。
        """
        if not self.device_id:
            raise PreconditionConfigError("App项目必须配置设备ID")
        if not self.app_package:
            raise PreconditionConfigError("App项目必须配置App包名")


@dataclass
class LoginFormInfo:
    """Web登录表单信息 - AI识别的登录表单元素位置。

    每个元素包含x/y/width/height坐标信息，用于：
    - CSS选择器定位失败时的坐标回退
    - 验证码图片区域截图裁剪

    属性:
        username_input: 用户名输入框位置。
        password_input: 密码输入框位置。
        submit_button: 提交按钮位置。
        captcha_input: 验证码输入框位置（可选）。
        captcha_image: 验证码图片位置（可选）。
    """
    username_input: Optional[Dict[str, Any]] = None
    password_input: Optional[Dict[str, Any]] = None
    submit_button: Optional[Dict[str, Any]] = None
    captcha_input: Optional[Dict[str, Any]] = None
    captcha_image: Optional[Dict[str, Any]] = None

    def is_complete(self) -> bool:
        """检查登录表单是否包含必要元素（用户名+密码+提交按钮）。"""
        return all([
            self.username_input is not None,
            self.password_input is not None,
            self.submit_button is not None
        ])

    def has_captcha(self) -> bool:
        """检查是否存在验证码（输入框+图片同时存在）。"""
        return self.captcha_input is not None and self.captcha_image is not None


@dataclass
class MobileLoginFormInfo:
    """移动端登录表单信息 - 支持账号登录和手机验证码登录两种模式。

    属性:
        username_input/password_input/submit_button: 账号登录元素
        phone_input/sms_code_input/get_sms_code_button: 手机登录元素
        captcha_input/captcha_image: 验证码元素（可选）
        agree_checkbox: 同意协议复选框（可选）
    """
    username_input: Optional[Dict[str, Any]] = None
    password_input: Optional[Dict[str, Any]] = None
    submit_button: Optional[Dict[str, Any]] = None
    captcha_input: Optional[Dict[str, Any]] = None
    captcha_image: Optional[Dict[str, Any]] = None
    agree_checkbox: Optional[Dict[str, Any]] = None
    phone_input: Optional[Dict[str, Any]] = None
    sms_code_input: Optional[Dict[str, Any]] = None
    get_sms_code_button: Optional[Dict[str, Any]] = None

    def is_complete(self) -> bool:
        """检查登录表单是否完整（账号登录或手机登录至少一种可用）。"""
        has_account_login = all([
            self.username_input is not None,
            self.password_input is not None,
            self.submit_button is not None
        ])
        has_phone_login = all([
            self.phone_input is not None,
            self.sms_code_input is not None,
            self.submit_button is not None
        ])
        return has_account_login or has_phone_login


@dataclass
class MobileAppConfig:
    """移动端App配置 - Appium/ADB连接参数。

    属性:
        platform_name: 平台名称（Android/iOS）。
        device_name/udid: 设备标识。
        app_package/app_activity: Android应用组件。
        bundle_id: iOS应用标识。
        app_path: 应用安装包路径。
        automation_name: 自动化框架名称。
        no_reset/full_reset: 是否重置应用状态。
        new_command_timeout: 命令超时时间（秒）。
        implicit_wait: 隐式等待时间（秒）。
    """
    platform_name: str = "Android"
    device_name: Optional[str] = None
    udid: Optional[str] = None
    platform_version: Optional[str] = None
    app_package: Optional[str] = None
    app_activity: Optional[str] = None
    bundle_id: Optional[str] = None
    app_path: Optional[str] = None
    automation_name: Optional[str] = None
    no_reset: bool = False
    full_reset: bool = False
    new_command_timeout: int = 300
    implicit_wait: int = 10


@dataclass
class PreconditionTimingConfig:
    """前置条件时序配置 - 控制登录和输入操作的等待时间。

    属性:
        max_login_wait_time: 登录后最大等待时间（秒）。
        wait_interval: 登录状态轮询间隔（秒）。
        captcha_padding: 验证码截图裁剪边距（像素）。
        input_delay: 键盘输入延迟（毫秒）。
        click_delay: 点击后等待时间（秒）。
        fill_delay: 填充后等待时间（秒）。
        mobile_login_wait: 移动端登录等待时间（秒）。
    """
    max_login_wait_time: int = 10
    wait_interval: int = 1
    captcha_padding: int = 10
    input_delay: int = 10
    click_delay: float = 0.2
    fill_delay: float = 0.1
    mobile_login_wait: int = 2


def handle_precondition_errors(func: Callable) -> Callable:
    """前置条件错误处理装饰器 - 统一异常转换和日志记录。

    处理策略:
        - PreconditionError及其子类: 直接抛出，不转换
        - BrowserError: 转换为PreconditionError
        - 其他异常: 转换为PreconditionError，记录完整堆栈

    Args:
        func: 被装饰的异步函数。

    Returns:
        装饰后的异步函数。
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except PreconditionError:
            raise
        except Exception as e:
            from app.utils.browser_controller_v2 import BrowserError
            if isinstance(e, BrowserError):
                error_msg = f"浏览器操作失败: {str(e)}"
                logger.error(error_msg)
                raise PreconditionError(error_msg) from e
            error_msg = f"{func.__name__} 失败: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            raise PreconditionError(error_msg) from e
    return wrapper


def solve_captcha_math(response: str) -> str:
    """求解数学验证码，支持四则运算和多种运算符格式。

    求解策略（按优先级）:
        1. 正则匹配数学表达式（如"3+5=?"、"4x6"）
        2. 提取所有数字，返回最后一个短数字
        3. 提取字母数字组合，过滤常见无关词
        4. 清洗后返回短字符串

    支持的运算符:
        加法: + ＋
        减法: - − －
        乘法: * × ＊
        除法: / ÷ ／

    Args:
        response: AI识别的验证码文本。

    Returns:
        计算结果字符串，无法求解时返回空字符串。
    """
    # 按严格度递减的顺序尝试匹配数学表达式
    math_patterns = [
        r'(\d+)\s*([-+×*÷/＋－×÷])\s*(\d+)\s*=\?',
        r'(\d+)\s*([-+×*÷/＋－×÷])\s*(\d+)\s*=?',
        r'(\d+)\s*([-+×*÷/＋－×÷])\s*(\d+)',
    ]
    for pattern in math_patterns:
        math_match = re.search(pattern, response)
        if math_match:
            num1 = int(math_match.group(1))
            operator = math_match.group(2)
            num2 = int(math_match.group(3))
            result = None
            if operator in ['+', '＋']:
                result = num1 + num2
            elif operator in ['-', '−', '－']:
                result = num1 - num2
            elif operator in ['*', '×', '＊']:
                result = num1 * num2
            elif operator in ['/', '÷', '／']:
                if num2 != 0:
                    result = num1 // num2  # 整数除法
                else:
                    logger.warning(f"除数为零: {num1} / {num2}")
            if result is not None:
                logger.info(f"数学表达式计算: {num1} {operator} {num2} = {result}")
                return str(result)

    # 回退策略1：提取数字
    numbers = re.findall(r'\d+', response)
    if numbers:
        if len(numbers) == 1:
            return numbers[0]
        # 返回最后一个短数字（避免匹配到年份等长数字）
        for num in reversed(numbers):
            if len(num) <= 4:
                return num

    # 回退策略2：提取字母数字组合
    alphanumeric = re.findall(r'[a-zA-Z0-9]+', response)
    if alphanumeric:
        filtered = [s for s in alphanumeric if s.lower() not in ['captcha', 'code', '验证码']]
        if filtered:
            return filtered[0]

    # 回退策略3：清洗后返回
    cleaned = response.strip()
    cleaned = re.sub(r'(?i)(captcha|code|验证码|result|结果|答案|answer)[:\s]*', '', cleaned)
    cleaned = cleaned.strip('"\'\n\r ')
    if cleaned and len(cleaned) <= 10:
        return cleaned

    return ""


def recognize_login_form(vision_model, screenshot: bytes) -> 'LoginFormInfo':
    """使用AI视觉模型识别登录表单的元素位置。

    识别流程:
        1. 构建识别Prompt（要求返回JSON格式的元素坐标）
        2. 调用视觉模型分析截图
        3. 从AI响应中提取JSON数据
        4. 构建LoginFormInfo实例

    Args:
        vision_model: 视觉模型实例。
        screenshot: 页面截图字节数据。

    Returns:
        LoginFormInfo实例，识别失败时返回空表单信息。

    Raises:
        PreconditionError: 视觉模型未初始化。
    """
    if not vision_model:
        raise PreconditionError("视觉模型未初始化")

    prompt = """请分析这个登录页面，识别以下元素的位置（返回JSON格式）：
1. 用户名输入框（username_input）
2. 密码输入框（password_input）
3. 登录/提交按钮（submit_button）
4. 验证码输入框（captcha_input）- 如果有的话
5. 验证码图片（captcha_image）- 如果有的话

返回格式示例：
{
    "username_input": {"x": 100, "y": 200, "width": 200, "height": 30},
    "password_input": {"x": 100, "y": 250, "width": 200, "height": 30},
    "submit_button": {"x": 150, "y": 320, "width": 100, "height": 40},
    "captcha_input": {"x": 100, "y": 380, "width": 150, "height": 30},
    "captcha_image": {"x": 260, "y": 380, "width": 80, "height": 30}
}

注意：
- x, y 是元素左上角的坐标
- width, height 是元素的宽高
- 坐标是相对于截图的像素坐标
- 如果某个元素不存在（如没有验证码），对应的值为 null
- 验证码通常是一个包含数字/字母的图片，位于验证码输入框旁边
"""
    try:
        response = vision_model.analyze_image(screenshot, prompt)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            form_info = LoginFormInfo()
            if "username_input" in result and result["username_input"]:
                form_info.username_input = result["username_input"]
            if "password_input" in result and result["password_input"]:
                form_info.password_input = result["password_input"]
            if "submit_button" in result and result["submit_button"]:
                form_info.submit_button = result["submit_button"]
            if "captcha_input" in result and result["captcha_input"]:
                form_info.captcha_input = result["captcha_input"]
            if "captcha_image" in result and result["captcha_image"]:
                form_info.captcha_image = result["captcha_image"]
            return form_info
        else:
            logger.warning("AI响应中未找到JSON格式数据")
            return LoginFormInfo()
    except json.JSONDecodeError as e:
        logger.error(f"AI响应JSON解析失败: {e}")
        return LoginFormInfo()
    except Exception as e:
        logger.error(f"识别登录表单失败: {e}")
        return LoginFormInfo()
