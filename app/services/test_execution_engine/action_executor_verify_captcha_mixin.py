"""验证码验证动作执行Mixin - 处理验证码识别与自动填写。
"""
import json
import asyncio
import re
from typing import Optional, Dict, Any
from loguru import logger

from app.services.test_execution_engine.models import (
    StepExecutionError, VerificationError,
)
from app.utils.ai_client_parser import parse_ai_json_object

CAPTCHA_RECOGNIZE_TIMEOUT = 30
CAPTCHA_MAX_RETRIES = 2


class ActionExecutorVerifyCaptchaMixin:

    @staticmethod
    def _eval_math_expression(expr: str) -> Optional[str]:
        cleaned = re.sub(r'[=?\s]', '', expr)
        match = re.match(r'^([\d.]+)([+\-*/])([\d.]+)$', cleaned)
        if not match:
            return None
        try:
            a, op, b = float(match.group(1)), match.group(2), float(match.group(3))
            if op == '+':
                result = a + b
            elif op == '-':
                result = a - b
            elif op == '*':
                result = a * b
            elif op == '/':
                if b == 0:
                    return None
                result = a / b
            else:
                return None
            return str(int(result)) if result == int(result) else str(result)
        except (ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _extract_captcha_text(response: str) -> Optional[str]:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            return None
        try:
            result = json.loads(json_match.group())
        except json.JSONDecodeError:
            return None

        captcha_text = result.get("captcha_result") or result.get("captcha_text")
        if captcha_text:
            return str(captcha_text).strip()

        captcha_original = result.get("captcha_original", "")
        if captcha_original:
            math_result = ActionExecutorVerifyCaptchaMixin._eval_math_expression(captcha_original)
            if math_result:
                return math_result
            digits = re.findall(r'\d+', captcha_original)
            if digits and len(digits[0]) >= 2:
                return digits[0]

        return None

    async def _call_vision_model_with_timeout(
        self, screenshot: bytes, prompt: str
    ) -> str:
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(
                None,
                self.vision_model.analyze_image,
                screenshot,
                prompt,
            ),
            timeout=CAPTCHA_RECOGNIZE_TIMEOUT,
        )

    async def _execute_captcha(self, action_info: Dict[str, Any], step_id: Optional[int]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        if not self.vision_model:
            raise StepExecutionError("视觉模型未初始化，无法执行验证码识别")

        text = action_info.get("text", "")
        logger.info(f"开始验证码识别: {text}")

        all_inputs = await self.browser.get_all_input_elements()
        logger.info(f"页面上找到 {len(all_inputs)} 个输入元素")

        prompt = """请仔细分析这个登录页面截图，完成以下任务：

1. 找到验证码图片（通常是一个包含数字/字母/数学运算的图片，位于输入框旁边）
2. 仔细识别验证码内容，特别注意：
   - 数字：0-9
   - 运算符：+（加）、-（减）、*（乘）、/（除）
   - 请仔细辨认每个字符，确保识别准确
3. 如果是数学表达式（如 3+5, 8-2, 4*2），请计算结果
4. 如果是纯数字/字母，直接识别

请返回JSON格式：
{
    "captcha_type": "math|text",
    "captcha_original": "原始内容（如 '3+5=?'）",
    "captcha_result": "计算或识别结果（如 '8'）",
    "captcha_image_location": {"x": 100, "y": 200, "width": 80, "height": 30},
    "confidence": 0.95
}

如果找不到验证码，返回：
{
    "captcha_result": null,
    "error": "未找到验证码"
}"""

        captcha_text: Optional[str] = None
        last_error: Optional[Exception] = None

        for attempt in range(1, CAPTCHA_MAX_RETRIES + 1):
            try:
                screenshot = await self.browser.take_screenshot()
                response = await self._call_vision_model_with_timeout(screenshot, prompt)
                logger.info(f"AI验证码识别响应(第{attempt}次): {response[:200]}...")

                captcha_text = self._extract_captcha_text(response)
                if captcha_text:
                    logger.info(f"验证码识别成功(第{attempt}次): {captcha_text}")
                    break
                else:
                    logger.warning(f"验证码识别结果为空(第{attempt}次)")
                    if attempt < CAPTCHA_MAX_RETRIES:
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                last_error = StepExecutionError(
                    f"验证码识别超时({CAPTCHA_RECOGNIZE_TIMEOUT}秒)，第{attempt}次尝试"
                )
                logger.warning(f"验证码识别超时(第{attempt}次)")
                if attempt < CAPTCHA_MAX_RETRIES:
                    await asyncio.sleep(1)
            except Exception as e:
                last_error = StepExecutionError(f"验证码识别失败: {str(e)}")
                logger.error(f"验证码识别执行失败(第{attempt}次): {str(e)}")
                if attempt < CAPTCHA_MAX_RETRIES:
                    await asyncio.sleep(1)

        if not captcha_text:
            raise last_error or StepExecutionError("验证码识别失败: 无法获取识别结果")

        captcha_input = None
        for input_el in all_inputs:
            placeholder = input_el.get("placeholder", "")
            if "验证码" in placeholder or "captcha" in placeholder.lower():
                captcha_input = input_el
                break

        if not captcha_input:
            text_inputs = [inp for inp in all_inputs if inp.get("type") in ["text", "", None]]
            if text_inputs:
                captcha_input = text_inputs[-1]

        if not captcha_input:
            raise StepExecutionError("验证码识别成功但未找到验证码输入框")

        selector = self._build_css_selector_from_attrs(captcha_input)
        if selector:
            try:
                await self.browser.fill(selector, captcha_text)
                logger.info(f"验证码输入成功(CSS选择器): {captcha_text}")
                return
            except Exception as e:
                logger.warning(f"选择器输入失败，降级为坐标方式: {e}")

        x = captcha_input.get("x", 0) + captcha_input.get("width", 0) // 2
        y = captcha_input.get("y", 0) + captcha_input.get("height", 0) // 2
        await self.browser.click(x, y)
        await asyncio.sleep(0.3)
        await self.browser.execute_javascript("""
            (function() {
                var el = document.activeElement;
                if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                    var desc = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    );
                    desc.set.call(el, arguments[0]);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
                var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
                for (var i = inputs.length - 1; i >= 0; i--) {
                    var placeholder = inputs[i].getAttribute('placeholder') || '';
                    if (placeholder.includes('验证码') || placeholder.includes('captcha')) {
                        var setter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        );
                        setter.set.call(inputs[i], arguments[0]);
                        inputs[i].dispatchEvent(new Event('input', { bubbles: true }));
                        inputs[i].dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    }
                }
                return false;
            })()
        """, captcha_text)
        logger.info(f"验证码输入完成(坐标方式): {captcha_text}")

    async def _execute_verify(self, action_info: Dict[str, Any], step_id: Optional[int]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        screenshot = await self.browser.take_screenshot()
        if self.vision_model:
            prompt = f"""请验证以下测试条件是否满足：
{text}

请返回JSON格式：
{{
    "passed": true/false,
    "reason": "验证通过/失败的原因"
}}
"""
            try:
                loop = asyncio.get_running_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self.vision_model.analyze_image,
                        screenshot,
                        prompt,
                    ),
                    timeout=CAPTCHA_RECOGNIZE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                raise VerificationError("AI验证超时")
            except Exception as e:
                raise VerificationError(f"AI验证请求失败: {str(e)}")

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                raw_json = json_match.group()
                result = parse_ai_json_object(raw_json)
                if result is not None:
                    if not result.get("passed", False):
                        raise VerificationError(result.get("reason", "验证失败"))
                    logger.info(f"验证通过: {result.get('reason', '')}")
                else:
                    raise VerificationError("AI验证响应格式异常，无法解析JSON")
            else:
                raise VerificationError("无法解析AI验证结果")
        else:
            logger.warning("视觉模型未初始化，跳过AI验证")
