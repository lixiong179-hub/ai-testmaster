"""
统一视觉模型适配器单元测试
覆盖率目标95%
"""
import os
import pytest
import base64
import json
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from requests import RequestException, HTTPError, Timeout, ConnectionError

from app.utils.unified_vision_model import (
    UnifiedVisionModel,
    VisionModelType,
    ElementInfo,
    ModelProviderConfig,
    MODEL_PROVIDER_CONFIGS,
    create_vision_model,
    get_default_vision_model
)


def create_test_image():
    """创建测试图片"""
    img = Image.new('RGB', (400, 300), color='lightblue')
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 150, 150], fill='red')
    draw.text((100, 200), "Test", fill='black')
    
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()


@pytest.fixture
def test_image():
    """测试图片fixture"""
    return create_test_image()


@pytest.fixture
def kimi_model():
    """Kimi模型fixture"""
    with patch.dict('os.environ', {'KIMI_API_KEY': 'test-kimi-key'}):
        return UnifiedVisionModel(model_type=VisionModelType.KIMI)


@pytest.fixture
def qwen_model():
    """通义千问模型fixture"""
    with patch.dict('os.environ', {'QWEN_API_KEY': 'test-qwen-key'}):
        return UnifiedVisionModel(model_type=VisionModelType.QWEN)


class TestUnifiedVisionModelInit:
    """测试模型初始化"""
    
    def test_kimi_model_init(self):
        """测试Kimi模型初始化"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'kimi-key-123'}):
            model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
            assert model.model_type == VisionModelType.KIMI
            assert model.api_key == 'kimi-key-123'
            assert model.base_url == 'https://api.moonshot.cn/v1'
            assert model.model_name == 'moonshot-v1-128k-vision-preview'
    
    def test_qwen_model_init(self):
        """测试通义千问模型初始化"""
        with patch.dict('os.environ', {'QWEN_API_KEY': 'qwen-key-123'}):
            model = UnifiedVisionModel(model_type=VisionModelType.QWEN)
            assert model.model_type == VisionModelType.QWEN
            assert model.api_key == 'qwen-key-123'
            assert model.base_url == 'https://dashscope.aliyuncs.com/api/v1'
    
    def test_model_init_no_api_key(self):
        """测试无API Key初始化"""
        # 使用patch来模拟settings中没有API key的情况
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.KIMI_API_KEY = ''
            model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
            assert model.api_key == ''
    
    def test_model_init_custom_config(self):
        """测试自定义配置初始化"""
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key='custom-key',
            base_url='https://custom.url/v1',
            model_name='custom-model',
            max_retries=5,
            timeout=120
        )
        assert model.api_key == 'custom-key'
        assert model.base_url == 'https://custom.url/v1'
        assert model.model_name == 'custom-model'
        assert model.max_retries == 5
        assert model.timeout == 120


class TestPrivateMethods:
    """测试私有方法"""
    
    def test_encode_image(self, kimi_model):
        """测试图片编码"""
        image_bytes = b'test_image_data'
        encoded = kimi_model._encode_image(image_bytes)
        assert encoded == base64.b64encode(image_bytes).decode('utf-8')
    
    def test_encode_image_empty(self, kimi_model):
        """测试空图片编码"""
        encoded = kimi_model._encode_image(b'')
        assert encoded == ''
    
    def test_build_request_payload_kimi(self, kimi_model):
        """测试Kimi请求体构建"""
        system_prompt = "系统提示"
        user_content = [
            {"type": "image", "image": "base64data"},
            {"type": "text", "text": "用户问题"}
        ]
        
        payload = kimi_model._build_request_payload(system_prompt, user_content)
        
        assert payload['model'] == 'moonshot-v1-128k-vision-preview'
        assert payload['messages'][0]['role'] == 'system'
        assert payload['messages'][0]['content'] == system_prompt
        assert payload['messages'][1]['role'] == 'user'
        assert payload['temperature'] == 0.3
        assert payload['max_tokens'] == 2000
    
    def test_build_request_payload_qwen(self, qwen_model):
        """测试通义千问请求体构建"""
        system_prompt = "系统提示"
        user_content = [
            {"type": "image", "image": "base64data"},
            {"type": "text", "text": "用户问题"}
        ]
        
        payload = qwen_model._build_request_payload(system_prompt, user_content)
        
        assert payload['model'] == 'qwen3-vl-flash'
        assert 'input' in payload
        assert 'parameters' in payload
    
    def test_parse_response_kimi(self, kimi_model):
        """测试Kimi响应解析"""
        response = {
            "choices": [{
                "message": {
                    "content": "测试响应内容"
                }
            }]
        }
        result = kimi_model._parse_response(response)
        assert result == "测试响应内容"
    
    def test_parse_response_qwen(self, qwen_model):
        """测试通义千问响应解析"""
        response = {
            "output": {
                "choices": [{
                    "message": {
                        "content": "通义千问响应"
                    }
                }]
            }
        }
        result = qwen_model._parse_response(response)
        assert result == "通义千问响应"
    
    def test_parse_response_qwen_list_format(self, qwen_model):
        """测试通义千问列表格式响应解析"""
        response = {
            "output": {
                "choices": [{
                    "message": {
                        "content": [{"text": "第一部分"}, {"text": "第二部分"}]
                    }
                }]
            }
        }
        result = qwen_model._parse_response(response)
        assert result == "第一部分\n第二部分"
    
    def test_parse_response_invalid(self, kimi_model):
        """测试无效响应解析"""
        response = {"invalid": "response"}
        result = kimi_model._parse_response(response)
        assert result is None


class TestElementRecognition:
    """测试元素识别功能"""
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_recognize_elements_single(self, mock_post, kimi_model, test_image):
        """测试单元素识别"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps([{
                        "type": "button",
                        "text": "登录",
                        "x": 100,
                        "y": 200,
                        "width": 80,
                        "height": 40,
                        "confidence": 0.95
                    }])
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        elements = kimi_model.recognize_elements(test_image, "登录按钮")
        
        assert len(elements) == 1
        assert elements[0].type == "button"
        assert elements[0].text == "登录"
        assert elements[0].confidence == 0.95
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_recognize_elements_multiple(self, mock_post, kimi_model, test_image):
        """测试多元素识别"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps([
                        {"type": "button", "text": "登录", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.95},
                        {"type": "button", "text": "注册", "x": 200, "y": 200, "width": 80, "height": 40, "confidence": 0.92}
                    ])
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        elements = kimi_model.recognize_elements(test_image, "按钮")
        
        assert len(elements) == 2
        assert elements[0].confidence >= elements[1].confidence  # 按置信度排序
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_recognize_elements_with_markdown(self, mock_post, kimi_model, test_image):
        """测试带markdown的JSON响应"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "```json\n" + json.dumps([{
                        "type": "input",
                        "text": "用户名",
                        "x": 100,
                        "y": 100,
                        "width": 200,
                        "height": 30,
                        "confidence": 0.95
                    }]) + "\n```"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        elements = kimi_model.recognize_elements(test_image, "输入框")
        
        assert len(elements) == 1
        assert elements[0].type == "input"
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_recognize_elements_confidence_filter(self, mock_post, kimi_model, test_image):
        """测试置信度过滤"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps([
                        {"type": "button", "text": "高置信度", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.95},
                        {"type": "button", "text": "低置信度", "x": 200, "y": 200, "width": 80, "height": 40, "confidence": 0.5}
                    ])
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        elements = kimi_model.recognize_elements(test_image, "按钮", min_confidence=0.9)
        
        assert len(elements) == 1
        assert elements[0].text == "高置信度"
    
    def test_recognize_elements_no_api_key(self, test_image):
        """测试无API Key时的元素识别"""
        model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
        model.api_key = ''
        
        elements = model.recognize_elements(test_image, "按钮")
        
        assert elements == []


class TestDescribeScreenshot:
    """测试截图描述功能"""
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_describe_screenshot_success(self, mock_post, kimi_model, test_image):
        """测试截图描述成功"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "这是一个测试页面，包含一个红色方块和文字'Test'。"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        description = kimi_model.describe_screenshot(test_image)
        
        assert "测试页面" in description
        assert "红色方块" in description
    
    def test_describe_screenshot_no_api_key(self, test_image):
        """测试无API Key时的截图描述"""
        model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
        model.api_key = ''
        
        description = model.describe_screenshot(test_image)
        
        assert description == "视觉模型未配置"


class TestVerifyActionResult:
    """测试操作结果验证功能"""
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_verify_action_success(self, mock_post, kimi_model, test_image):
        """测试操作成功验证"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({"success": True, "reason": "成功跳转到首页"})
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        success, reason = kimi_model.verify_action_result(
            test_image, test_image, "点击登录按钮", "跳转到首页"
        )
        
        assert success is True
        assert "成功" in reason
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_verify_action_failure(self, mock_post, kimi_model, test_image):
        """测试操作失败验证"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({"success": False, "reason": "页面未发生变化"})
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        success, reason = kimi_model.verify_action_result(
            test_image, test_image, "点击按钮", "预期变化"
        )
        
        assert success is False
        assert "未发生变化" in reason
    
    def test_verify_action_no_api_key(self, test_image):
        """测试无API Key时的操作验证"""
        model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
        model.api_key = ''
        
        success, reason = model.verify_action_result(
            test_image, test_image, "点击", "预期"
        )
        
        assert success is False
        assert "未配置" in reason


class TestElementInfo:
    """测试ElementInfo数据类"""
    
    def test_element_info_creation(self):
        """测试ElementInfo创建"""
        element = ElementInfo(
            type="button",
            text="提交",
            x=100,
            y=200,
            width=80,
            height=40,
            confidence=0.95
        )
        
        assert element.type == "button"
        assert element.text == "提交"
        assert element.x == 100
        assert element.y == 200
        assert element.width == 80
        assert element.height == 40
        assert element.confidence == 0.95
    
    def test_find_element_center(self, kimi_model):
        """测试元素中心计算"""
        element = ElementInfo(
            type="button",
            text="测试",
            x=100,
            y=200,
            width=80,
            height=40,
            confidence=0.9
        )
        
        center_x, center_y = kimi_model.find_element_center(element)
        
        assert center_x == 140  # 100 + 80/2
        assert center_y == 220  # 200 + 40/2


class TestErrorHandling:
    """测试错误处理"""
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_network_error(self, mock_post, kimi_model, test_image):
        """测试网络错误处理"""
        mock_post.side_effect = ConnectionError("网络连接失败")
        
        description = kimi_model.describe_screenshot(test_image)
        
        assert "无法" in description or "未配置" in description
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_timeout_error(self, mock_post, kimi_model, test_image):
        """测试超时错误处理"""
        mock_post.side_effect = Timeout("请求超时")
        
        description = kimi_model.describe_screenshot(test_image)
        
        assert "无法" in description or "未配置" in description
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_http_401_error(self, mock_post, kimi_model, test_image):
        """测试401错误处理"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("401 Unauthorized")
        mock_post.return_value = mock_response
        
        description = kimi_model.describe_screenshot(test_image)
        
        assert "无法" in description
    
    @patch('app.utils.unified_vision_model.requests.post')
    def test_retry_mechanism(self, mock_post, kimi_model, test_image):
        """测试重试机制"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "成功"}}]
        }
        mock_response.raise_for_status = Mock()
        
        # 第一次失败，第二次成功
        mock_post.side_effect = [
            ConnectionError("第一次失败"),
            mock_response
        ]
        
        description = kimi_model.describe_screenshot(test_image)
        
        assert mock_post.call_count == 2
        assert description == "成功"


class TestFactoryFunctions:
    """测试工厂函数"""
    
    def test_create_vision_model_kimi(self):
        """测试创建Kimi模型"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'test-key'}):
            model = create_vision_model("kimi")
            assert model.model_type == VisionModelType.KIMI
    
    def test_create_vision_model_qwen(self):
        """测试创建通义千问模型"""
        with patch.dict('os.environ', {'QWEN_API_KEY': 'test-key'}):
            model = create_vision_model("qwen")
            assert model.model_type == VisionModelType.QWEN
    
    def test_create_vision_model_invalid(self):
        """测试创建无效模型"""
        model = create_vision_model("invalid_model")
        # 应该回退到默认模型
        assert model.model_type == VisionModelType.KIMI
    
    def test_get_default_vision_model(self):
        """测试获取默认模型"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'test-key'}):
            model = get_default_vision_model()
            assert isinstance(model, UnifiedVisionModel)


class TestModelConfigs:
    """测试模型配置"""
    
    def test_model_provider_configs_exist(self):
        """测试所有模型配置存在"""
        assert VisionModelType.KIMI in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.QWEN in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.ZHIPU in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.BAIDU in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.DOUBAO in MODEL_PROVIDER_CONFIGS
    
    def test_kimi_config_values(self):
        """测试Kimi配置值"""
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.KIMI]
        assert config.model_type == VisionModelType.KIMI
        assert config.api_key_env == "KIMI_API_KEY"
        assert config.default_base_url == "https://api.moonshot.cn/v1"
    
    def test_qwen_config_values(self):
        """测试通义千问配置值"""
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.QWEN]
        assert config.model_type == VisionModelType.QWEN
        assert config.api_key_env == "QWEN_API_KEY"
        assert config.default_base_url == "https://dashscope.aliyuncs.com/api/v1"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
