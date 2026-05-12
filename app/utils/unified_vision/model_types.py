"""
统一视觉模型类型定义模块

定义视觉模型相关的枚举、数据类和提供商配置。
是unified_vision包的基础设施模块，被所有Mixin引用。

核心类型：
    - VisionModelType: 支持的视觉模型类型枚举
    - ElementInfo: 页面元素信息数据类
    - ModelProviderConfig: 模型提供商配置数据类
    - MODEL_PROVIDER_CONFIGS: 预定义的模型提供商配置映射

支持的模型提供商：
    - OpenAI (gpt-4o): 通用视觉理解，OpenAI兼容API格式
    - 百度 (ernie-4.0-8k): 文心大模型，百度自定义API格式
    - 智谱 (glm-4v): GLM视觉模型，OpenAI兼容API格式
"""
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum


class VisionModelType(str, Enum):
    """视觉模型类型枚举

    继承str和Enum，可直接作为字符串使用。
    每种类型对应不同的API格式和请求/响应处理逻辑。
    """
    OPENAI = "openai"      # OpenAI及兼容API（如DeepSeek）
    BAIDU = "baidu"        # 百度文心大模型
    ZHIPU = "zhipu"        # 智谱GLM视觉模型
    MIMO = "mimo"          # 小米MiMo多模态模型（OpenAI兼容API）
    CUSTOM = "custom"      # 自定义模型（需手动配置API格式）


@dataclass
class ElementInfo:
    """页面元素信息数据类

    存储视觉模型识别到的页面元素的位置、类型和置信度信息。

    Attributes:
        x: 元素左上角x坐标（像素）
        y: 元素左上角y坐标（像素）
        width: 元素宽度（像素）
        height: 元素高度（像素）
        element_type: 元素类型（input/button/text等）
        placeholder: 元素占位符文本或标签
        confidence: 识别置信度（0-1）
        reasoning: 选择该元素的理由
    """
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    element_type: str = ""
    placeholder: str = ""
    confidence: float = 0.0
    reasoning: str = ""

    @property
    def is_valid(self) -> bool:
        """判断元素信息是否有效

        有效条件：宽高均大于0且置信度超过0.5

        Returns:
            bool: 有效返回True，否则返回False
        """
        return self.width > 0 and self.height > 0 and self.confidence > 0.5

    def to_dict(self) -> Dict[str, Any]:
        """将元素信息转换为字典

        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "element_type": self.element_type,
            "placeholder": self.placeholder,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class ModelProviderConfig:
    """模型提供商配置数据类

    封装单个模型提供商的完整配置信息，包括API密钥环境变量名、
    API端点URL、默认模型名称和生成参数。

    Attributes:
        model_type: 模型类型枚举值
        api_key_env: API密钥对应的环境变量名
        api_url: API端点URL
        model_name: 默认模型名称
        max_tokens: 最大生成token数
        temperature: 生成温度
        timeout: 请求超时时间（秒）
    """
    model_type: VisionModelType
    api_key_env: str
    api_url: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout: int = 60


# 预定义的模型提供商配置映射
# key为VisionModelType的value值，value为对应的ModelProviderConfig实例
MODEL_PROVIDER_CONFIGS: Dict[str, ModelProviderConfig] = {
    "openai": ModelProviderConfig(
        model_type=VisionModelType.OPENAI,
        api_key_env="OPENAI_API_KEY",
        api_url="https://api.openai.com/v1/chat/completions",
        model_name="gpt-4o",
    ),
    "baidu": ModelProviderConfig(
        model_type=VisionModelType.BAIDU,
        api_key_env="BAIDU_API_KEY",
        api_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie-4.0-8k",
        model_name="ernie-4.0-8k",
    ),
    "zhipu": ModelProviderConfig(
        model_type=VisionModelType.ZHIPU,
        api_key_env="ZHIPU_API_KEY",
        api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        model_name="glm-4v",
    ),
    "mimo": ModelProviderConfig(
        model_type=VisionModelType.MIMO,
        api_key_env="MIMO_API_KEY",
        api_url="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        model_name="mimo-v2.5",
    ),
}
