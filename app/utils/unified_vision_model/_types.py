from typing import Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class VisionModelType(str, Enum):
    KIMI = "kimi"
    ZHIPU = "zhipu"
    BAIDU = "baidu"
    QWEN = "qwen"
    DOUBAO = "doubao"
    MIMO = "mimo"


@dataclass
class ElementInfo:
    type: str
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class ModelProviderConfig:
    model_type: VisionModelType
    api_key_env: str
    base_url_env: str
    model_name_env: str
    default_base_url: str
    default_model_name: str
    build_payload_fn: Optional[Callable] = None
    parse_response_fn: Optional[Callable] = None
    api_endpoint: str = "/chat/completions"


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
