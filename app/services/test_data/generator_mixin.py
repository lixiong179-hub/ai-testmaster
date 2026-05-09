"""测试数据生成器核心 - 基于AI的测试数据生成引擎

本模块实现测试数据生成的核心引擎，包括AI调用、数据验证、
上下文构建和常量定义。作为GeneratorMixin被TestDataGenerator组合使用。

核心类:
    - GeneratorMixin: 测试数据生成器，提供AI驱动的数据生成能力

常量定义:
    - DATA_TYPE_STRING: 字符串类型
    - DATA_TYPE_NUMBER: 数字类型
    - DATA_TYPE_EMAIL: 邮箱类型
    - DATA_TYPE_PHONE: 手机号类型
    - DATA_TYPE_DATE: 日期类型
    - DATA_TYPE_ENUM: 枚举类型
    - DATA_TYPE_BOOLEAN: 布尔类型
    - DATA_TYPE_CUSTOM: 自定义类型

依赖关系:
    - app.utils.ai_client: AI客户端工具
    - app.core.config: 配置管理（API密钥、模型名称等）
    - app.services.prompt_builder: Prompt构建
    - app.services.test_data.response_handler: 响应解析与验证

AI生成流程:
    1. 构建生成Prompt（字段定义+上下文）
    2. 调用AI API（含重试机制）
    3. 解析AI返回的JSON格式数据
    4. 验证数据完整性

安全设计:
    - API密钥通过settings配置读取，禁止硬编码
    - 数据验证防止AI返回不完整数据
"""
import json
from typing import List, Dict, Any, Optional
from loguru import logger

from app.utils.ai_client import AIServiceError
from app.core.config import settings
from app.services.test_data.constants import (
    DATA_TYPE_STRING, DATA_TYPE_NUMBER, DATA_TYPE_EMAIL,
    DATA_TYPE_PHONE, DATA_TYPE_DATE, DATA_TYPE_ENUM,
    DATA_TYPE_BOOLEAN, DATA_TYPE_CUSTOM,
)
from app.services.prompt_builder import PromptBuilder
from app.services.test_data.response_handler import parse_ai_response, validate_generated_data


class GeneratorMixin:
    """测试数据生成器Mixin - AI驱动的测试数据生成引擎。

    职责:
        - 构建结构化的数据生成Prompt
        - 调用AI API生成测试数据
        - 验证生成数据的完整性
        - 支持批量数据生成

    设计意图:
        将数据生成逻辑从CRUD和参数化逻辑中抽离，便于:
        1. 独立测试数据生成逻辑
        2. 替换不同的AI服务提供商
        3. 统一管理数据验证规则

    使用场景:
        被TestDataGenerator通过多继承组合，
        对外提供generate_test_data和generate_test_data_batch接口。

    重试策略:
        - 最大重试次数: 3次
        - 退避策略: 指数退避（2^attempt秒）
        - 超时时间: 60秒
    """

    def __init__(self):
        """初始化生成器，设置默认超时时间。"""
        self.timeout = 60

    async def generate_test_data(
        self,
        field_definitions: List[Dict[str, Any]],
        count: int = 1,
        context: Optional[str] = None,
        data_type: str = "normal"
    ) -> List[Dict[str, Any]]:
        """为指定字段定义生成测试数据。

        生成流程:
            1. 构建生成Prompt（字段定义+上下文+数据类型）
            2. 调用AI API生成数据
            3. 解析AI返回的JSON格式数据
            4. 验证数据完整性（必填字段检查）

        数据类型:
            - normal: 正常数据
            - boundary: 边界值数据
            - invalid: 无效数据
            - special: 特殊字符数据

        Args:
            field_definitions: 字段定义列表，每项包含name/type/required等。
            count: 生成记录数，默认1。
            context: 业务上下文描述，可选。
            data_type: 数据类型，默认normal。

        Returns:
            生成的数据记录列表。

        Raises:
            ValueError: AI生成失败或数据验证不通过。
        """
        import httpx

        prompt = PromptBuilder().for_test_data(field_definitions, count, context, data_type)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 3000
        }

        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                    response = await client.post(
                        settings.DEEPSEEK_API_URL, headers=headers, json=payload
                    )
                    response.raise_for_status()
                    result = response.json()

                    if "choices" not in result:
                        raise ValueError("AI API响应格式错误：缺少choices字段")
                    choices = result["choices"]
                    if not choices or len(choices) == 0:
                        raise ValueError("AI API返回结果为空")

                    content = (choices[0].get("message") or {}).get("content", "")
                    if not content:
                        raise ValueError("AI响应内容为空")

                    data = parse_ai_response(content)
                    if not isinstance(data, list):
                        data = [data]

                    validated_data = validate_generated_data(data, field_definitions)
                    return validated_data

            except httpx.TimeoutException:
                last_error = f"AI API请求超时 (尝试 {attempt + 1}/{max_retries})"
                logger.warning(last_error)
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
            except httpx.HTTPStatusError as e:
                last_error = f"AI API HTTP错误: {e.response.status_code}"
                logger.error(last_error)
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
            except (ValueError, json.JSONDecodeError) as e:
                last_error = f"AI响应解析失败: {e}"
                logger.error(last_error)
                raise

        logger.error(f"AI生成失败，已重试{max_retries}次: {last_error}")
        raise ValueError(f"AI生成失败: {last_error}")

    async def generate_test_data_batch(
        self,
        field_definitions: List[Dict[str, Any]],
        counts: Dict[str, int],
        context: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量生成多种类型的测试数据。

        生成策略:
            为每种数据类型（normal/boundary/invalid/special）分别调用AI生成，
            汇总为完整的数据集。

        Args:
            field_definitions: 字段定义列表。
            counts: 各类型生成数量，如{"normal": 5, "boundary": 3}。
            context: 业务上下文描述，可选。

        Returns:
            按类型分组的数据字典，如{"normal": [...], "boundary": [...]}。
        """
        result = {}
        for data_type, count in counts.items():
            try:
                data = await self.generate_test_data(
                    field_definitions=field_definitions,
                    count=count,
                    context=context,
                    data_type=data_type
                )
                result[data_type] = data
            except Exception as e:
                logger.error(f"生成{data_type}类型数据失败: {e}")
                result[data_type] = []
        return result
