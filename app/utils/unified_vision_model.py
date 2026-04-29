"""
统一视觉模型适配器
支持国内多种多模态大模型：Kimi、智谱GLM、通义千问、文心一言、豆包等

设计思路：
- 大部分国内模型API都采用OpenAI兼容格式
- 只需要配置不同的API地址、模型名称即可
- 特殊格式（如通义千问、文心一言）通过配置覆盖方法实现
"""
import base64
import json
import time
import requests
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class VisionModelType(str, Enum):
    """支持的视觉模型类型"""
    KIMI = "kimi"                    # Moonshot Kimi
    ZHIPU = "zhipu"                  # 智谱GLM-4V
    BAIDU = "baidu"                  # 文心一言
    QWEN = "qwen"                    # 通义千问
    DOUBAO = "doubao"                # 字节豆包
    MIMO = "mimo"                    # 小米MiMo


@dataclass
class ElementInfo:
    """元素信息"""
    type: str
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class ModelProviderConfig:
    """模型提供商配置"""
    model_type: VisionModelType
    api_key_env: str                    # API Key的环境变量名
    base_url_env: str                   # Base URL的环境变量名
    model_name_env: str                 # 模型名称的环境变量名
    default_base_url: str
    default_model_name: str
    # 可选的自定义处理函数
    build_payload_fn: Optional[Callable] = None
    parse_response_fn: Optional[Callable] = None
    api_endpoint: str = "/chat/completions"  # API端点


# 预定义的模型提供商配置
MODEL_PROVIDER_CONFIGS: Dict[VisionModelType, ModelProviderConfig] = {
    VisionModelType.KIMI: ModelProviderConfig(
        model_type=VisionModelType.KIMI,
        api_key_env="KIMI_API_KEY",
        base_url_env="KIMI_BASE_URL",
        model_name_env="KIMI_MODEL",
        default_base_url="https://api.moonshot.cn/v1",
        default_model_name="moonshot-v1-128k-vision-preview"
    ),
    VisionModelType.ZHIPU: ModelProviderConfig(
        model_type=VisionModelType.ZHIPU,
        api_key_env="ZHIPU_API_KEY",
        base_url_env="ZHIPU_BASE_URL",
        model_name_env="ZHIPU_MODEL",
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model_name="glm-4v-plus"
    ),
    VisionModelType.QWEN: ModelProviderConfig(
        model_type=VisionModelType.QWEN,
        api_key_env="QWEN_API_KEY",
        base_url_env="QWEN_BASE_URL",
        model_name_env="QWEN_MODEL",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model_name="qwen-vl-plus",
        api_endpoint="/chat/completions",
        build_payload_fn=None,
        parse_response_fn=None
    ),
    VisionModelType.BAIDU: ModelProviderConfig(
        model_type=VisionModelType.BAIDU,
        api_key_env="BAIDU_API_KEY",
        base_url_env="BAIDU_BASE_URL",
        model_name_env="BAIDU_MODEL",
        default_base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
        default_model_name="ernie-bot-4",
        api_endpoint="/chat/completions"
    ),
    VisionModelType.DOUBAO: ModelProviderConfig(
        model_type=VisionModelType.DOUBAO,
        api_key_env="DOUBAO_API_KEY",
        base_url_env="DOUBAO_BASE_URL",
        model_name_env="DOUBAO_MODEL",
        default_base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model_name="doubao-vision-pro-32k"
    ),
    VisionModelType.MIMO: ModelProviderConfig(
        model_type=VisionModelType.MIMO,
        api_key_env="MIMO_API_KEY",
        base_url_env="MIMO_BASE_URL",
        model_name_env="MIMO_MODEL",
        default_base_url="https://token-plan-cn.xiaomimimo.com/v1",
        default_model_name="mimo-v2.5"
    ),
}


class UnifiedVisionModel:
    """
    统一视觉模型适配器
    
    支持通过配置动态切换不同的视觉模型，无需为每个模型创建单独的类
    """
    
    def __init__(
        self,
        model_type: VisionModelType = VisionModelType.MIMO,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 2,
        timeout: int = 300,
        temperature: float = 0.3
    ):
        """
        初始化统一视觉模型
        
        Args:
            model_type: 模型类型
            api_key: API Key，如果为None则从环境变量读取
            base_url: API基础URL，如果为None则使用默认值
            model_name: 模型名称，如果为None则使用默认值
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            timeout: 请求超时时间（秒）
            temperature: 温度参数
        """
        self.model_type = model_type
        self.provider_config = MODEL_PROVIDER_CONFIGS[model_type]
        
        # 加载配置（优先级：传入参数 > 环境变量 > 默认值）
        self.api_key = api_key or self._get_from_env_or_settings(
            self.provider_config.api_key_env
        )
        self.base_url = base_url or self._get_from_env_or_settings(
            self.provider_config.base_url_env,
            self.provider_config.default_base_url
        )
        self.model_name = model_name or self._get_from_env_or_settings(
            self.provider_config.model_name_env,
            self.provider_config.default_model_name
        )
        
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.temperature = temperature
        
        if not self.api_key:
            logger.warning(f"{model_type.value} API Key 未配置，视觉识别功能将不可用")
    
    def _get_from_env_or_settings(self, env_name: str, default: str = "") -> str:
        """从环境变量或settings获取配置"""
        import os
        from app.core.config import settings
        
        # 优先从环境变量获取
        value = os.getenv(env_name)
        if value:
            return value
        
        # 从settings获取
        return getattr(settings, env_name, default)
    
    def _encode_image(self, image_bytes: bytes) -> str:
        """将图片编码为base64"""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def _build_request_payload(
        self,
        system_prompt: str,
        user_content: List[Dict[str, Any]],
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        构建请求体（OpenAI兼容格式）
        
        大多数国内模型（Kimi、智谱、豆包）都支持OpenAI格式
        """
        # 转换用户内容为OpenAI格式
        content = []
        for item in user_content:
            if item.get('type') == 'image':
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{item['image']}"
                    }
                })
            else:
                content.append({
                    "type": "text",
                    "text": item.get('text', '')
                })

        # 文心一言使用不同的格式
        if self.model_type == VisionModelType.BAIDU:
            return self._build_baidu_payload(system_prompt, user_content, temperature)

        # 标准OpenAI格式（Kimi、智谱、豆包、通义千问、MiMo）
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            "temperature": temperature or self.temperature,
            "max_tokens": 2000
        }
    
    def _build_baidu_payload(
        self,
        system_prompt: str,
        user_content: List[Dict[str, Any]],
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """构建文心一言请求体"""
        # 文心一言的图片处理需要特殊处理
        messages = [{"role": "system", "content": system_prompt}]
        
        content_parts = []
        for item in user_content:
            if item.get('type') == 'image':
                content_parts.append(f"[图片]")
            else:
                content_parts.append(item.get('text', ''))
        
        messages.append({"role": "user", "content": "\n".join(content_parts)})
        
        return {
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_output_tokens": 2000
        }
    
    def _parse_response(self, response: Dict[str, Any]) -> Optional[str]:
        """解析响应"""
        # 文心一言使用不同的响应格式
        if self.model_type == VisionModelType.BAIDU:
            return self._parse_baidu_response(response)

        # 标准OpenAI格式（Kimi、智谱、豆包、通义千问、MiMo）
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(f"解析响应失败: {e}")
            return None
    
    def _parse_baidu_response(self, response: Dict[str, Any]) -> Optional[str]:
        """解析文心一言响应"""
        try:
            return response.get("result", "")
        except Exception as e:
            logger.error(f"解析文心一言响应失败: {e}")
            return None
    
    def _make_request(self, payload: Dict[str, Any]) -> Optional[str]:
        """发送请求"""
        if not self.api_key:
            logger.error(f"{self.model_type.value} API Key 未配置")
            return None
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 构建完整URL
        endpoint = self.provider_config.api_endpoint
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"{self.model_type.value} API 请求 - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                content = self._parse_response(result)
                logger.info(f"{self.model_type.value} API 请求成功")
                return content
                
            except requests.RequestException as e:
                logger.error(f"{self.model_type.value} API 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    self._handle_request_error(e)
                    return None
            except Exception as e:
                logger.error(f"{self.model_type.value} API 请求异常: {str(e)}")
                return None

        return None

    def _handle_request_error(self, error: requests.RequestException):
        """处理请求错误"""
        error_str = str(error)
        model_name = self.model_type.value
        
        if "401" in error_str:
            logger.error(f"{model_name} API 认证失败，请检查 API Key")
        elif "429" in error_str:
            logger.error(f"{model_name} API 请求频率过高，请稍后重试")
        elif "403" in error_str:
            logger.error(f"{model_name} API 权限不足")
        elif "404" in error_str:
            logger.error(f"{model_name} API 地址错误")
        elif "timeout" in error_str.lower():
            logger.error(f"{model_name} API 请求超时")
    
    # ==================== 公共API方法 ====================
    
    def recognize_elements(
        self,
        screenshot: bytes,
        description: str,
        min_confidence: float = 0.9
    ) -> List[ElementInfo]:
        """识别页面元素"""
        if not self.api_key:
            logger.error(f"{self.model_type.value} API Key 未配置")
            return []
        
        encoded_image = self._encode_image(screenshot)
        
        system_prompt = self._get_element_recognition_prompt()
        user_prompt = f"请识别截图中与'{description}'相关的所有可交互元素"
        
        user_content = [
            {"type": "image", "image": encoded_image},
            {"type": "text", "text": user_prompt}
        ]
        
        payload = self._build_request_payload(system_prompt, user_content)
        content = self._make_request(payload)
        
        if not content:
            return []
        
        return self._parse_element_recognition(content, min_confidence)
    
    def describe_screenshot(self, screenshot: bytes) -> str:
        """描述截图内容"""
        if not self.api_key:
            return "视觉模型未配置"
        
        encoded_image = self._encode_image(screenshot)
        
        system_prompt = "你是一个专业的UI测试工程师，请详细描述当前页面内容。"
        user_content = [
            {"type": "image", "image": encoded_image},
            {"type": "text", "text": "请描述这个页面的主要内容、布局和可交互元素"}
        ]
        
        payload = self._build_request_payload(system_prompt, user_content)
        result = self._make_request(payload)
        
        return result or "无法描述页面内容"
    
    def analyze_image(self, screenshot: bytes, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        分析图片内容
        
        Args:
            screenshot: 图片字节数据
            prompt: 用户提示词
            system_prompt: 系统提示词，如果为None则使用默认
            
        Returns:
            AI分析结果
        """
        if not self.api_key:
            return "视觉模型未配置"
        
        encoded_image = self._encode_image(screenshot)
        
        if system_prompt is None:
            system_prompt = "你是一个专业的UI测试工程师，擅长分析页面截图。"
        
        user_content = [
            {"type": "image", "image": encoded_image},
            {"type": "text", "text": prompt}
        ]
        
        payload = self._build_request_payload(system_prompt, user_content)
        result = self._make_request(payload)

        if result:
            logger.info(f"analyze_image 返回结果长度: {len(result)}")
        return result or "无法分析图片内容"
    
    def verify_action_result(
        self,
        before_screenshot: bytes,
        after_screenshot: bytes,
        action_description: str,
        expected_result: str
    ) -> tuple:
        """验证操作结果"""
        if not self.api_key:
            return (False, "视觉模型未配置")
        
        before_encoded = self._encode_image(before_screenshot)
        after_encoded = self._encode_image(after_screenshot)
        
        system_prompt = self._get_action_verification_prompt()
        user_content = [
            {"type": "text", "text": f"操作: {action_description}\n预期结果: {expected_result}"},
            {"type": "image", "image": before_encoded},
            {"type": "image", "image": after_encoded},
            {"type": "text", "text": "请验证操作是否成功，以JSON格式返回结果"}
        ]
        
        payload = self._build_request_payload(system_prompt, user_content)
        content = self._make_request(payload)
        
        if not content:
            return (False, "无法验证操作结果")
        
        return self._parse_verification_result(content)

    def analyze_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None) -> str:
        """
        纯文本LLM调用（不传图片）
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            
        Returns:
            AI分析结果
        """
        if not self.api_key:
            return "视觉模型未配置"

        if system_prompt is None:
            system_prompt = "你是一个专业的UI测试工程师。"

        user_content = [{"type": "text", "text": prompt}]

        payload = self._build_request_payload(system_prompt, user_content, temperature)
        result = self._make_request(payload)

        return result or "无法分析文本内容"

    def _get_element_recognition_prompt(self) -> str:
        """获取元素识别提示词"""
        return """你是一个专业的UI测试工程师，擅长识别网页和移动应用界面元素。

请分析提供的截图，识别出所有可交互元素。

对于每个识别到的元素，请提供以下信息（JSON格式）：
[
  {
    "type": "元素类型(button/input/link等)",
    "text": "元素文本内容",
    "x": 元素左上角x坐标(int),
    "y": 元素左上角y坐标(int),
    "width": 元素宽度(int),
    "height": 元素高度(int),
    "confidence": 识别置信度0-1(float)
  }
]

只返回JSON数组，不要其他解释文字。"""
    
    def _get_action_verification_prompt(self) -> str:
        """获取操作验证提示词"""
        return """你是一个专业的UI测试验证专家。

请比较操作前后的截图，验证操作是否达到预期效果。

请以JSON格式返回验证结果：
{
  "success": true/false,
  "reason": "验证结果的详细说明"
}

只返回JSON对象，不要其他解释文字。"""
    
    def _parse_element_recognition(self, content: str, min_confidence: float) -> List[ElementInfo]:
        """解析元素识别结果"""
        import re
        
        try:
            elements_data = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', content)
            if json_match:
                try:
                    elements_data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    logger.error("元素识别失败：无法解析JSON响应")
                    return []
            else:
                logger.error("元素识别失败：响应中未找到JSON")
                return []
        
        elements = []
        if isinstance(elements_data, list):
            for elem_data in elements_data:
                try:
                    element = ElementInfo(
                        type=elem_data.get('type', 'unknown'),
                        text=elem_data.get('text', ''),
                        x=int(elem_data.get('x', 0)),
                        y=int(elem_data.get('y', 0)),
                        width=int(elem_data.get('width', 0)),
                        height=int(elem_data.get('height', 0)),
                        confidence=float(elem_data.get('confidence', 0))
                    )
                    if element.confidence >= min_confidence:
                        elements.append(element)
                except (ValueError, TypeError) as e:
                    logger.warning(f"解析元素数据失败: {elem_data}, 错误: {e}")
                    continue
        
        elements.sort(key=lambda x: x.confidence, reverse=True)
        logger.info(f"元素识别成功，找到 {len(elements)} 个元素")
        return elements
    
    def _parse_verification_result(self, content: str) -> tuple:
        """解析验证结果"""
        import re
        
        if not content:
            return (False, "无法验证操作结果")
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'\{\s*"success"[\s\S]*\}', content)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    return (False, "无法解析验证结果")
            else:
                return (False, "响应中未找到JSON")
        
        success = result.get('success', False)
        reason = result.get('reason', '无说明')
        
        return (success, reason)
    
    def find_element_center(self, element: ElementInfo) -> tuple:
        """计算元素中心坐标"""
        center_x = element.x + element.width // 2
        center_y = element.y + element.height // 2
        return (center_x, center_y)


# ==================== 工厂函数 ====================

def create_vision_model(
    model_type: str = "kimi",
    **kwargs
) -> UnifiedVisionModel:
    """
    创建视觉模型的便捷函数
    
    Args:
        model_type: 模型类型名称 (kimi/zhipu/qwen/baidu/doubao/mimo)
        **kwargs: 其他配置参数
        
    Returns:
        UnifiedVisionModel实例
    """
    try:
        model_enum = VisionModelType(model_type.lower())
    except ValueError:
        logger.error(f"不支持的模型类型: {model_type}，使用默认模型mimo")
        model_enum = VisionModelType.MIMO
    
    return UnifiedVisionModel(model_type=model_enum, **kwargs)


def get_default_vision_model() -> UnifiedVisionModel:
    """获取默认视觉模型"""
    from app.core.config import settings
    
    default_model = getattr(settings, 'VISION_MODEL_DEFAULT', 'mimo')
    return create_vision_model(default_model)


# 向后兼容：保留旧的导入方式
__all__ = [
    'UnifiedVisionModel',
    'VisionModelType',
    'ElementInfo',
    'create_vision_model',
    'get_default_vision_model'
]
