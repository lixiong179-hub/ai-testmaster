"""
统一视觉模型覆盖率测试
提升 unified_vision_model.py 的测试覆盖率
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.utils.unified_vision_model import (
    UnifiedVisionModel,
    VisionModelType,
    ElementInfo,
    ModelProviderConfig,
    MODEL_PROVIDER_CONFIGS
)


class TestVisionModelType(unittest.TestCase):
    """测试视觉模型类型枚举"""
    
    def test_model_types(self):
        """测试所有模型类型"""
        self.assertEqual(VisionModelType.KIMI.value, "kimi")
        self.assertEqual(VisionModelType.ZHIPU.value, "zhipu")
        self.assertEqual(VisionModelType.BAIDU.value, "baidu")
        self.assertEqual(VisionModelType.QWEN.value, "qwen")
        self.assertEqual(VisionModelType.DOUBAO.value, "doubao")


class TestElementInfo(unittest.TestCase):
    """测试元素信息类"""
    
    def test_element_info_creation(self):
        """测试创建元素信息"""
        element = ElementInfo(
            type="button",
            text="Submit",
            x=100,
            y=200,
            width=80,
            height=40,
            confidence=0.95
        )
        self.assertEqual(element.type, "button")
        self.assertEqual(element.text, "Submit")
        self.assertEqual(element.x, 100)
        self.assertEqual(element.y, 200)
        self.assertEqual(element.width, 80)
        self.assertEqual(element.height, 40)
        self.assertEqual(element.confidence, 0.95)


class TestModelProviderConfig(unittest.TestCase):
    """测试模型提供商配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = ModelProviderConfig(
            model_type=VisionModelType.KIMI,
            api_key_env="KIMI_API_KEY",
            base_url_env="KIMI_BASE_URL",
            model_name_env="KIMI_MODEL",
            default_base_url="https://api.moonshot.cn/v1",
            default_model_name="moonshot-v1-128k-vision-preview"
        )
        self.assertEqual(config.model_type, VisionModelType.KIMI)
        self.assertEqual(config.api_key_env, "KIMI_API_KEY")
        self.assertEqual(config.default_base_url, "https://api.moonshot.cn/v1")


class TestModelProviderConfigs(unittest.TestCase):
    """测试预定义的模型提供商配置"""
    
    def test_kimi_config(self):
        """测试Kimi配置"""
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.KIMI]
        self.assertEqual(config.model_type, VisionModelType.KIMI)
        self.assertEqual(config.api_key_env, "KIMI_API_KEY")
        self.assertEqual(config.default_base_url, "https://api.moonshot.cn/v1")
    
    def test_qwen_config(self):
        """测试通义千问配置"""
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.QWEN]
        self.assertEqual(config.model_type, VisionModelType.QWEN)
        self.assertEqual(config.api_key_env, "QWEN_API_KEY")
        self.assertEqual(config.default_model_name, "qwen-vl-plus")
    
    def test_zhipu_config(self):
        """测试智谱配置"""
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.ZHIPU]
        self.assertEqual(config.model_type, VisionModelType.ZHIPU)
        self.assertEqual(config.default_model_name, "glm-4v-plus")
    
    def test_baidu_config(self):
        """测试百度配置"""
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.BAIDU]
        self.assertEqual(config.model_type, VisionModelType.BAIDU)
        self.assertEqual(config.default_model_name, "ernie-bot-4")
    
    def test_doubao_config(self):
        """测试豆包配置"""
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.DOUBAO]
        self.assertEqual(config.model_type, VisionModelType.DOUBAO)
        self.assertEqual(config.default_model_name, "doubao-vision-pro-32k")


class TestUnifiedVisionModel(unittest.TestCase):
    """测试统一视觉模型类"""
    
    @patch.dict(os.environ, {"KIMI_API_KEY": "test-api-key"})
    def test_initialization_with_env(self):
        """测试从环境变量初始化"""
        model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
        self.assertEqual(model.model_type, VisionModelType.KIMI)
        self.assertEqual(model.api_key, "test-api-key")
    
    def test_initialization_with_params(self):
        """测试使用参数初始化"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.QWEN,
            api_key="custom-key",
            base_url="https://custom.url",
            model_name="custom-model",
            max_retries=5,
            timeout=120
        )
        self.assertEqual(model.model_type, VisionModelType.QWEN)
        self.assertEqual(model.api_key, "custom-key")
        self.assertEqual(model.base_url, "https://custom.url")
        self.assertEqual(model.model_name, "custom-model")
        self.assertEqual(model.max_retries, 5)
        self.assertEqual(model.timeout, 120)
    
    def test_encode_image(self):
        """测试图片编码"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key"
        )
        image_bytes = b"fake image data"
        encoded = model._encode_image(image_bytes)
        self.assertIsInstance(encoded, str)
        # 验证是有效的base64
        import base64
        decoded = base64.b64decode(encoded)
        self.assertEqual(decoded, image_bytes)
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_recognize_elements_mock(self, mock_post):
        """测试元素识别（Mock）"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key"
        )
        
        # 设置Mock响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '[{"type": "button", "text": "Submit", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.95}]'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        result = model.recognize_elements(
            screenshot=b"fake_image_data",
            description="Find the submit button"
        )
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, "button")
        self.assertEqual(result[0].text, "Submit")
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_describe_screenshot_mock(self, mock_post):
        """测试截图描述（Mock）"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key"
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "This is a login page with username and password fields."
                }
            }]
        }
        mock_post.return_value = mock_response
        
        result = model.describe_screenshot(screenshot=b"fake_screenshot_data")
        
        self.assertIsInstance(result, str)
        self.assertIn("login page", result)
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_retry_on_failure(self, mock_post):
        """测试失败重试机制"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key",
            max_retries=3,
            retry_delay=0.1
        )
        
        # 前两次失败，第三次成功
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "choices": [{"message": {"content": "Success"}}]
        }
        
        mock_post.side_effect = [
            Exception("Connection error"),
            Exception("Timeout"),
            mock_response_success
        ]
        
        result = model.describe_screenshot(screenshot=b"fake_data")
        self.assertEqual(result, "Success")
        self.assertEqual(mock_post.call_count, 3)
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_api_error_response(self, mock_post):
        """测试API错误响应"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key",
            max_retries=1
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        result = model.describe_screenshot(screenshot=b"fake_data")
        # 错误时返回默认值
        self.assertEqual(result, "无法描述页面内容")


class TestUnifiedVisionModelDifferentProviders(unittest.TestCase):
    """测试不同提供商的视觉模型"""
    
    def test_qwen_provider(self):
        """测试通义千问提供商"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.QWEN,
            api_key="qwen-key"
        )
        self.assertEqual(model.model_type, VisionModelType.QWEN)
        self.assertIn("dashscope", model.base_url)
    
    def test_zhipu_provider(self):
        """测试智谱提供商"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.ZHIPU,
            api_key="zhipu-key"
        )
        self.assertEqual(model.model_type, VisionModelType.ZHIPU)
        self.assertIn("bigmodel", model.base_url)
    
    def test_baidu_provider(self):
        """测试百度提供商"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.BAIDU,
            api_key="baidu-key"
        )
        self.assertEqual(model.model_type, VisionModelType.BAIDU)
        self.assertIn("baidu", model.base_url)
    
    def test_doubao_provider(self):
        """测试豆包提供商"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.DOUBAO,
            api_key="doubao-key"
        )
        self.assertEqual(model.model_type, VisionModelType.DOUBAO)
        self.assertIn("volces", model.base_url)


class TestUnifiedVisionModelWithoutAPIKey(unittest.TestCase):
    """测试没有API Key的情况"""
    
    def test_recognize_elements_without_api_key(self):
        """测试没有API Key时返回空列表"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key=None
        )
        result = model.recognize_elements(
            screenshot=b"fake_data",
            description="test"
        )
        self.assertEqual(result, [])
    
    def test_describe_screenshot_without_api_key(self):
        """测试没有API Key时返回提示信息"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key=None
        )
        result = model.describe_screenshot(screenshot=b"fake_data")
        self.assertEqual(result, "视觉模型未配置")


class TestParseElementRecognition(unittest.TestCase):
    """测试解析元素识别结果"""
    
    def test_parse_valid_json(self):
        """测试解析有效的JSON"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key"
        )
        
        valid_json = '''[
            {"type": "button", "text": "Login", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.95},
            {"type": "input", "text": "", "x": 100, "y": 300, "width": 200, "height": 30, "confidence": 0.88}
        ]'''
        
        result = model._parse_element_recognition(valid_json, min_confidence=0.8)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].type, "button")
        self.assertEqual(result[1].type, "input")
    
    def test_parse_invalid_json(self):
        """测试解析无效的JSON"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key"
        )
        
        invalid_json = "not valid json"
        result = model._parse_element_recognition(invalid_json, min_confidence=0.8)
        self.assertEqual(result, [])
    
    def test_parse_empty_json(self):
        """测试解析空的JSON"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key"
        )
        
        empty_json = "[]"
        result = model._parse_element_recognition(empty_json, min_confidence=0.8)
        self.assertEqual(result, [])
    
    def test_filter_by_confidence(self):
        """测试按置信度过滤"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key"
        )
        
        json_data = '''[
            {"type": "button", "text": "High", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.95},
            {"type": "input", "text": "Low", "x": 100, "y": 300, "width": 200, "height": 30, "confidence": 0.70}
        ]'''
        
        result = model._parse_element_recognition(json_data, min_confidence=0.8)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "High")


if __name__ == '__main__':
    unittest.main(verbosity=2)
