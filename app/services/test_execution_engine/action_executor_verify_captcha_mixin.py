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


class ActionExecutorVerifyCaptchaMixin:

    async def _execute_captcha(self, action_info: Dict[str, Any], step_id: Optional[int]) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        if not self.vision_model:
            logger.warning("视觉模型未初始化，跳过验证码识别")
            return
        text = action_info.get("text", "")
        logger.info(f"开始验证码识别: {text}")
        try:
            all_inputs = await self.browser.get_all_input_elements()
            logger.info(f"页面上找到 {len(all_inputs)} 个输入元素")
            screenshot = await self.browser.take_screenshot()
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
            response = self.vision_model.analyze_image(screenshot, prompt)
            logger.info(f"AI验证码识别响应: {response[:200]}...")

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                captcha_text = result.get("captcha_result") or result.get("captcha_text")
                captcha_type = result.get("captcha_type", "text")
                captcha_original = result.get("captcha_original", "")

                if captcha_text:
                    if captcha_type == "math":
                        logger.info(f"数学验证码识别成功: {captcha_original} = {captcha_text}")
                    else:
                        logger.info(f"验证码识别成功: {captcha_text}")

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

                    if captcha_input:
                        selector = self._build_css_selector_from_attrs(captcha_input)
                        if selector:
                            try:
                                await self.browser.fill(selector, captcha_text)
                                logger.info(f"验证码输入成功: {captcha_text}")
                                return
                            except Exception as e:
                                logger.warning(f"选择器输入失败: {e}")

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
                        return
                    else:
                        logger.error("未找到验证码输入框")
                else:
                    logger.warning(f"验证码识别失败: {result.get('error', '未知错误')}")
            else:
                logger.warning("无法解析AI验证码识别结果")

        except Exception as e:
            logger.error(f"验证码识别执行失败: {str(e)}")
            raise StepExecutionError(f"验证码识别失败: {str(e)}")

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
            response = self.vision_model.analyze_image(screenshot, prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if not result.get("passed", False):
                    raise VerificationError(result.get("reason", "验证失败"))
                logger.info(f"验证通过: {result.get('reason', '')}")
            else:
                logger.warning("无法解析AI验证结果")
        else:
            logger.warning("视觉模型未初始化，跳过AI验证")
