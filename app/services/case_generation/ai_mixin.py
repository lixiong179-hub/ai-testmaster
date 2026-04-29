"""用例生成AI Mixin - DeepSeek API调用、Prompt构建与响应解析。

本模块封装与DeepSeek AI API的交互逻辑，包括Prompt构建、
API调用（含重试机制）和AI响应解析。作为AIMixin被
TestCaseGenerationService组合使用。

核心类:
    - AIMixin: AI调用Mixin，提供用例生成的AI能力

设计模式:
    作为Mixin模块，通过多继承组合到TestCaseGenerationService中，提供:
    - _generate_case_with_ai: AI生成核心方法（含重试）
    - _parse_ai_response: AI响应解析（继承自AIParseMixin）

依赖关系:
    - app.utils.ai_client: AI客户端工具
    - app.core.config: 配置管理（API密钥、模型名称等）
    - app.services.prompt_builder: 统一Prompt构建
    - app.services.case_generation.ai_parse_mixin: 响应解析

AI调用流程:
    1. 构建生成Prompt（需求+UI+测试点信息）
    2. 调用DeepSeek API（最多3次重试，指数退避）
    3. 解析AI返回的JSON格式用例数据

安全设计:
    - API密钥通过settings配置读取，禁止硬编码
    - Prompt注入防护由ContentSanitizer在调用前处理
    - AI响应解析采用宽松匹配策略，兼容格式偏差
"""
import json
from typing import Dict, Any
from loguru import logger

from app.utils.ai_client import AIServiceError
from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.services.case_generation.ai_parse_mixin import AIParseMixin


class AIMixin(AIParseMixin):
    """AI调用Mixin - 封装DeepSeek API交互与响应解析。

    职责:
        - 调用DeepSeek API并处理重试逻辑
        - 使用PromptBuilder构建Prompt
        - 继承AIParseMixin的响应解析能力

    设计意图:
        将AI调用逻辑从生成流程中抽离，便于:
        1. 独立测试AI调用和响应解析
        2. 替换不同的AI服务提供商
        3. 统一管理重试策略和错误处理

    使用场景:
        被TestCaseGenerationService通过多继承组合，
        在生成流程中调用_generate_case_with_ai获取AI生成的用例数据。

    重试策略:
        - 最大重试次数: 3次
        - 退避策略: 指数退避（2^attempt秒）
        - 超时时间: 60秒
        - 可重试异常: TimeoutException, HTTPStatusError, RequestError
        - 不可重试异常: ValueError, JSONDecodeError（响应格式错误）
    """

    async def _generate_case_with_ai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """调用DeepSeek AI生成测试用例，含重试机制。

        调用流程:
            1. 从上下文中提取需求内容、UI描述和测试点
            2. 构建结构化Prompt
            3. 调用DeepSeek API（httpx异步客户端）
            4. 解析AI响应为JSON格式用例数据
            5. 失败时按指数退避重试

        Args:
            context: 生成上下文字典，需包含:
                - requirement_content: 需求文档内容
                - ui_description: UI描述文本
                - ui_specs: UI规格列表
                - test_point: 测试点信息（module/function/point/priority）

        Returns:
            AI生成的用例数据字典，包含:
                - title: 用例标题
                - module: 模块名称
                - precondition: 前置条件
                - steps: 测试步骤列表
                - expected_result: 预期结果
                - case_type: 用例类型
                - case_category: 用例分类
                - priority: 优先级

        Raises:
            ValueError: AI生成失败（重试耗尽或响应格式错误）。
        """
        import httpx

        # 从上下文中提取生成所需信息
        requirement_content = context.get("requirement_content", "")
        ui_description = context.get("ui_description", "")
        ui_specs = context.get("ui_specs", [])
        test_point = context.get("test_point", {})
        module = test_point.get("module", "未知模块")
        function = test_point.get("function") or test_point.get("point", "")
        point = test_point.get("point", "")
        priority = test_point.get("priority", 2)

        # 构建结构化Prompt
        prompt = PromptBuilder.build_linear_prompt(
            requirement_content=requirement_content, ui_description=ui_description,
            module=module, function=function, point=point, priority=priority, ui_specs=ui_specs
        )

        # 构建API请求头和载荷
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,  # 适中的创造性，保证用例多样性
            "max_tokens": 3000   # 限制输出长度，控制成本
        }

        # 重试机制：最多3次，指数退避
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                    response = await client.post(
                        settings.DEEPSEEK_API_URL, headers=headers, json=payload
                    )
                    response.raise_for_status()
                    result = response.json()

                    # 校验AI响应格式
                    if "choices" not in result:
                        raise ValueError("AI API响应格式错误：缺少choices字段")
                    choices = result["choices"]
                    if not choices or len(choices) == 0:
                        raise ValueError("AI API返回结果为空")
                    first_choice = choices[0]
                    if "message" not in first_choice:
                        raise ValueError("AI响应格式错误：缺少message字段")

                    message = first_choice["message"]
                    content = message.get("content", "")
                    if not content:
                        raise ValueError("AI响应内容为空")

                    # 解析AI响应为结构化用例数据
                    generated_case = self._parse_ai_response(content)
                    return generated_case

            except httpx.TimeoutException as e:
                # 超时异常，可重试
                last_error = f"AI API请求超时 (尝试 {attempt + 1}/{max_retries})"
                logger.warning(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s
            except httpx.HTTPStatusError as e:
                # HTTP状态码错误，可重试（可能是临时服务不可用）
                last_error = f"AI API HTTP错误: {e.response.status_code}"
                logger.error(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)
            except httpx.RequestError as e:
                # 网络请求错误，可重试
                last_error = "AI API请求错误"
                logger.error(f"AI API请求错误: {e}")
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)
            except (ValueError, json.JSONDecodeError) as e:
                # 响应格式错误，不重试（重试结果大概率相同）
                last_error = "AI响应解析失败"
                logger.error(f"AI响应解析失败: {e}")
                raise

        # 重试耗尽，抛出异常
        logger.error(f"AI生成失败，已重试{max_retries}次: {last_error}")
        raise ValueError(f"AI生成失败: {last_error}")

    async def _async_sleep(self, seconds: float) -> None:
        """异步休眠，用于重试间隔的指数退避。

        Args:
            seconds: 休眠秒数。
        """
        import asyncio
        await asyncio.sleep(seconds)
