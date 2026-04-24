
"""前置条件工具函数 - 验证码求解和登录表单识别。"""
import re
import json
from typing import TYPE_CHECKING
from loguru import logger

from app.services.precondition.models import PreconditionError, LoginFormInfo

if TYPE_CHECKING:
    pass


def solve_captcha_math(response: str) -> str:
    """求解数学验证码。"""
    math_patterns = [
        r'(\d+)\s*([-+×*÷/＋－×÷])\s*(\d+)\s*=\??',
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
                    result = num1 // num2
                else:
                    logger.warning(f"除数为零: {num1} / {num2}")
            if result is not None:
                logger.info(f"数学表达式计算: {num1} {operator} {num2} = {result}")
                return str(result)

    numbers = re.findall(r'\d+', response)
    if numbers:
        if len(numbers) == 1:
            return numbers[0]
        for num in reversed(numbers):
            if len(num) <= 4:
                return num

    alphanumeric = re.findall(r'[a-zA-Z0-9]+', response)
    if alphanumeric:
        filtered = [s for s in alphanumeric if s.lower() not in ['captcha', 'code', '验证码']]
        if filtered:
            return filtered[0]

    cleaned = response.strip()
    cleaned = re.sub(r'(?i)(captcha|code|验证码|result|结果|答案|answer)[:\s]*', '', cleaned)
    cleaned = cleaned.strip('"\'\n\r ')
    if cleaned and len(cleaned) <= 10:
        return cleaned

    return ""


def recognize_login_form(vision_model, screenshot: bytes) -> LoginFormInfo:
    """使用AI视觉模型识别登录表单的元素位置。"""
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
"""
    try:
        response = vision_model.analyze_image(screenshot, prompt)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            form_info = LoginFormInfo()
            for key in ["username_input", "password_input", "submit_button", "captcha_input", "captcha_image"]:
                if key in result and result[key]:
                    setattr(form_info, key, result[key])
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
