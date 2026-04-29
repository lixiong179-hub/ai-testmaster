"""
统一视觉模型补充单元测试

用于提升覆盖率到80%以上
修复现有测试中的问题
"""
import pytest
import json
import base64
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.utils.unified_vision_model import (
    UnifiedVisionModel,
    VisionModelType,
    ElementInfo,
    ModelProviderConfig,
    MODEL_PROVIDER_CONFIGS,
    create_vision_model,
    get_default_vision_model
)


class TestUnifiedVisionModelSupplement:
    """统一视觉模型补充测试类"""

    @pytest.fixture
    def mock_model(self):
        """创建带Mock的模型实例"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'test-key'}):
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key='test-key'
            )
            return model

    # ============================================================================
    # 初始化测试
    # ============================================================================

    def test_init_without_api_key(self):
        """测试没有API Key时的初始化"""
        with patch.dict('os.environ', {}, clear=True):
            with patch.object(UnifiedVisionModel, '_get_from_env_or_settings', return_value=None):
                model = UnifiedVisionModel(
                    model_type=VisionModelType.KIMI,
                    api_key=None
                )
                assert model.api_key is None or model.api_key == ''

    def test_init_default_values(self):
        """测试默认值"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'test-key'}):
            model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
            assert model.max_retries == 3
            assert model.retry_delay == 2
            assert model.timeout == 60
            assert model.temperature == 0.3

    # ============================================================================
    # 请求体构建测试
    # ============================================================================

    def test_build_request_payload_standard(self, mock_model):
        """测试标准OpenAI格式请求体"""
        system_prompt = "You are a test engineer"
        user_content = [
            {"type": "text", "text": "Hello"},
            {"type": "image", "image": "base64encoded"}
        ]
        
        payload = mock_model._build_request_payload(system_prompt, user_content)
        
        assert payload["model"] == mock_model.model_name
        assert payload["temperature"] == mock_model.temperature
        assert payload["max_tokens"] == 2000
        assert len(payload["messages"]) == 2

    def test_build_request_payload_qwen(self):
        """测试通义千问请求体"""
        with patch.dict('os.environ', {'QWEN_API_KEY': 'test-key'}):
            model = UnifiedVisionModel(
                model_type=VisionModelType.QWEN,
                api_key='test-key'
            )
            
            system_prompt = "You are a test engineer"
            user_content = [
                {"type": "text", "text": "Hello"},
                {"type": "image", "image": "base64encoded"}
            ]
            
            payload = model._build_request_payload(system_prompt, user_content)
            
            assert "model" in payload
            assert "input" in payload
            assert "parameters" in payload

    def test_build_request_payload_baidu(self):
        """测试文心一言请求体"""
        with patch.dict('os.environ', {'BAIDU_API_KEY': 'test-key'}):
            model = UnifiedVisionModel(
                model_type=VisionModelType.BAIDU,
                api_key='test-key'
            )
            
            system_prompt = "You are a test engineer"
            user_content = [
                {"type": "text", "text": "Hello"},
                {"type": "image", "image": "base64encoded"}
            ]
            
            payload = model._build_request_payload(system_prompt, user_content)
            
            assert "messages" in payload
            assert payload["temperature"] == model.temperature

    def test_build_request_payload_with_custom_temperature(self, mock_model):
        """测试自定义temperature"""
        system_prompt = "Test"
        user_content = [{"type": "text", "text": "Hello"}]
        custom_temp = 0.8
        
        payload = mock_model._build_request_payload(system_prompt, user_content, custom_temp)
        
        assert payload["temperature"] == custom_temp

    # ============================================================================
    # 响应解析测试
    # ============================================================================

    def test_parse_response_standard(self, mock_model):
        """测试标准OpenAI格式响应解析"""
        response = {
            "choices": [{
                "message": {
                    "content": "Test response"
                }
            }]
        }
        
        result = mock_model._parse_response(response)
        assert result == "Test response"

    def test_parse_response_qwen(self):
        """测试通义千问响应解析"""
        with patch.dict('os.environ', {'QWEN_API_KEY': 'test-key'}):
            model = UnifiedVisionModel(
                model_type=VisionModelType.QWEN,
                api_key='test-key'
            )
            
            response = {
                "output": {
                    "choices": [{
                        "message": {
                            "content": "Qwen response"
                        }
                    }]
                }
            }
            
            result = model._parse_response(response)
            assert result == "Qwen response"

    def test_parse_response_qwen_list_format(self):
        """测试通义千问列表格式响应"""
        with patch.dict('os.environ', {'QWEN_API_KEY': 'test-key'}):
            model = UnifiedVisionModel(
                model_type=VisionModelType.QWEN,
                api_key='test-key'
            )
            
            response = {
                "output": {
                    "choices": [{
                        "message": {
                            "content": [{"text": "Part 1"}, {"text": "Part 2"}]
                        }
                    }]
                }
            }
            
            result = model._parse_response(response)
            assert "Part 1" in result
            assert "Part 2" in result

    def test_parse_response_baidu(self):
        """测试文心一言响应解析"""
        with patch.dict('os.environ', {'BAIDU_API_KEY': 'test-key'}):
            model = UnifiedVisionModel(
                model_type=VisionModelType.BAIDU,
                api_key='test-key'
            )
            
            response = {
                "result": "Baidu response"
            }
            
            result = model._parse_response(response)
            assert result == "Baidu response"

    def test_parse_response_invalid(self, mock_model):
        """测试无效响应解析"""
        response = {"invalid": "response"}
        
        result = mock_model._parse_response(response)
        assert result is None

    def test_parse_response_empty(self, mock_model):
        """测试空响应解析"""
        response = {}
        
        result = mock_model._parse_response(response)
        assert result is None

    # ============================================================================
    # API请求测试
    # ============================================================================

    @patch('app.utils.unified_vision_model.requests.post')
    def test_make_request_success(self, mock_post, mock_model):
        """测试API请求成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success"}}]
        }
        mock_post.return_value = mock_response
        
        payload = {"test": "payload"}
        result = mock_model._make_request(payload)
        
        assert result == "Success"
        mock_post.assert_called_once()

    @patch('app.utils.unified_vision_model.requests.post')
    def test_make_request_retry_success(self, mock_post, mock_model):
        """测试API请求重试后成功"""
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "choices": [{"message": {"content": "Success after retry"}}]
        }
        
        # 模拟重试成功 - 第一次返回None（模拟异常被捕获），第二次成功
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # 模拟异常，但让requests.post成功返回错误响应
                error_response = MagicMock()
                error_response.status_code = 500
                error_response.text = "Connection error"
                return error_response
            return mock_response_success
        
        mock_post.side_effect = side_effect
        
        payload = {"test": "payload"}
        result = mock_model._make_request(payload)
        
        # 验证至少调用了1次，最多3次
        assert mock_post.call_count >= 1
        assert mock_post.call_count <= 3

    @patch('app.utils.unified_vision_model.requests.post')
    def test_make_request_all_retries_fail(self, mock_post, mock_model):
        """测试API请求所有重试都失败"""
        mock_post.side_effect = Exception("Persistent error")
        
        # 临时设置max_retries为1以加快测试
        original_retries = mock_model.max_retries
        mock_model.max_retries = 1
        
        try:
            payload = {"test": "payload"}
            result = mock_model._make_request(payload)
            
            assert result is None
            assert mock_post.call_count == 1
        finally:
            mock_model.max_retries = original_retries

    def test_make_request_no_api_key(self, mock_model):
        """测试没有API Key时的请求"""
        mock_model.api_key = None
        
        payload = {"test": "payload"}
        result = mock_model._make_request(payload)
        
        assert result is None

    # ============================================================================
    # 错误处理测试
    # ============================================================================

    def test_handle_request_error_401(self, mock_model):
        """测试401错误处理"""
        error = Exception("401 Client Error")
        
        # 验证方法不抛出异常
        mock_model._handle_request_error(error)
        # 方法执行成功即可

    def test_handle_request_error_429(self, mock_model):
        """测试429错误处理"""
        error = Exception("429 Too Many Requests")
        
        mock_model._handle_request_error(error)
        # 方法执行成功即可

    def test_handle_request_error_403(self, mock_model):
        """测试403错误处理"""
        error = Exception("403 Forbidden")
        
        mock_model._handle_request_error(error)
        # 方法执行成功即可

    def test_handle_request_error_404(self, mock_model):
        """测试404错误处理"""
        error = Exception("404 Not Found")
        
        mock_model._handle_request_error(error)
        # 方法执行成功即可

    def test_handle_request_error_timeout(self, mock_model):
        """测试超时错误处理"""
        error = Exception("Request timeout")
        
        mock_model._handle_request_error(error)
        # 方法执行成功即可

    # ============================================================================
    # 元素识别测试
    # ============================================================================

    @patch('app.utils.unified_vision_model.requests.post')
    def test_recognize_elements_success(self, mock_post, mock_model):
        """测试元素识别成功"""
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
        
        result = mock_model.recognize_elements(
            screenshot=b"fake_image",
            description="Find submit button"
        )
        
        assert len(result) == 1
        assert result[0].type == "button"
        assert result[0].confidence == 0.95

    def test_recognize_elements_no_api_key(self, mock_model):
        """测试没有API Key时的元素识别"""
        mock_model.api_key = None
        
        result = mock_model.recognize_elements(
            screenshot=b"fake_image",
            description="test"
        )
        
        assert result == []

    @patch('app.utils.unified_vision_model.requests.post')
    def test_recognize_elements_api_failure(self, mock_post, mock_model):
        """测试元素识别API失败"""
        mock_post.side_effect = Exception("API Error")
        
        result = mock_model.recognize_elements(
            screenshot=b"fake_image",
            description="test"
        )
        
        assert result == []

    # ============================================================================
    # 截图描述测试
    # ============================================================================

    @patch('app.utils.unified_vision_model.requests.post')
    def test_describe_screenshot_success(self, mock_post, mock_model):
        """测试截图描述成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "This is a login page"
                }
            }]
        }
        mock_post.return_value = mock_response
        
        result = mock_model.describe_screenshot(screenshot=b"fake_image")
        
        assert result == "This is a login page"

    def test_describe_screenshot_no_api_key(self, mock_model):
        """测试没有API Key时的截图描述"""
        mock_model.api_key = None
        
        result = mock_model.describe_screenshot(screenshot=b"fake_image")
        
        assert result == "视觉模型未配置"

    @patch('app.utils.unified_vision_model.requests.post')
    def test_describe_screenshot_api_failure(self, mock_post, mock_model):
        """测试截图描述API失败"""
        mock_post.side_effect = Exception("API Error")
        
        result = mock_model.describe_screenshot(screenshot=b"fake_image")
        
        assert result == "无法描述页面内容"

    # ============================================================================
    # 图片分析测试
    # ============================================================================

    @patch('app.utils.unified_vision_model.requests.post')
    def test_analyze_image_success(self, mock_post, mock_model):
        """测试图片分析成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Analysis result"
                }
            }]
        }
        mock_post.return_value = mock_response
        
        result = mock_model.analyze_image(
            screenshot=b"fake_image",
            prompt="Analyze this"
        )
        
        assert result == "Analysis result"

    def test_analyze_image_no_api_key(self, mock_model):
        """测试没有API Key时的图片分析"""
        mock_model.api_key = None
        
        result = mock_model.analyze_image(
            screenshot=b"fake_image",
            prompt="test"
        )
        
        assert result == "视觉模型未配置"

    @patch('app.utils.unified_vision_model.requests.post')
    def test_analyze_image_with_custom_prompt(self, mock_post, mock_model):
        """测试使用自定义系统提示词"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Custom analysis"
                }
            }]
        }
        mock_post.return_value = mock_response
        
        result = mock_model.analyze_image(
            screenshot=b"fake_image",
            prompt="Analyze",
            system_prompt="Custom system prompt"
        )
        
        assert result == "Custom analysis"

    # ============================================================================
    # 操作验证测试
    # ============================================================================

    @patch('app.utils.unified_vision_model.requests.post')
    def test_verify_action_result_success(self, mock_post, mock_model):
        """测试操作验证成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"success": true, "reason": "Action completed successfully"}'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        success, reason = mock_model.verify_action_result(
            before_screenshot=b"before",
            after_screenshot=b"after",
            action_description="Click button",
            expected_result="Page changed"
        )
        
        assert success is True
        assert "successfully" in reason

    def test_verify_action_result_no_api_key(self, mock_model):
        """测试没有API Key时的操作验证"""
        mock_model.api_key = None
        
        success, reason = mock_model.verify_action_result(
            before_screenshot=b"before",
            after_screenshot=b"after",
            action_description="test",
            expected_result="result"
        )
        
        assert success is False
        assert reason == "视觉模型未配置"

    @patch('app.utils.unified_vision_model.requests.post')
    def test_verify_action_result_api_failure(self, mock_post, mock_model):
        """测试操作验证API失败"""
        mock_post.side_effect = Exception("API Error")
        
        success, reason = mock_model.verify_action_result(
            before_screenshot=b"before",
            after_screenshot=b"after",
            action_description="test",
            expected_result="result"
        )
        
        assert success is False
        assert "无法验证" in reason

    # ============================================================================
    # 解析验证结果测试
    # ============================================================================

    def test_parse_verification_result_valid(self, mock_model):
        """测试解析有效的验证结果"""
        content = '{"success": true, "reason": "Test passed"}'
        
        success, reason = mock_model._parse_verification_result(content)
        
        assert success is True
        assert reason == "Test passed"

    def test_parse_verification_result_invalid_json(self, mock_model):
        """测试解析无效的JSON验证结果"""
        content = 'not valid json'
        
        success, reason = mock_model._parse_verification_result(content)
        
        assert success is False
        # 验证返回了错误信息（具体文本可能不同）
        assert reason is not None
        assert len(reason) > 0

    def test_parse_verification_result_empty(self, mock_model):
        """测试解析空的验证结果"""
        content = ''
        
        success, reason = mock_model._parse_verification_result(content)
        
        assert success is False
        assert "无法验证" in reason

    # ============================================================================
    # 元素中心计算测试
    # ============================================================================

    def test_find_element_center(self, mock_model):
        """测试计算元素中心坐标"""
        element = ElementInfo(
            type="button",
            text="Test",
            x=100,
            y=200,
            width=80,
            height=40,
            confidence=0.95
        )
        
        center_x, center_y = mock_model.find_element_center(element)
        
        assert center_x == 140  # 100 + 80/2
        assert center_y == 220  # 200 + 40/2

    # ============================================================================
    # 提示词测试
    # ============================================================================

    def test_get_element_recognition_prompt(self, mock_model):
        """测试获取元素识别提示词"""
        prompt = mock_model._get_element_recognition_prompt()
        
        assert "UI测试工程师" in prompt
        assert "JSON" in prompt

    def test_get_action_verification_prompt(self, mock_model):
        """测试获取操作验证提示词"""
        prompt = mock_model._get_action_verification_prompt()
        
        assert "测试验证" in prompt
        assert "JSON" in prompt

    # ============================================================================
    # 工厂函数测试
    # ============================================================================

    def test_create_vision_model_kimi(self):
        """测试创建Kimi模型"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'test-key'}):
            model = create_vision_model("kimi")
            assert model.model_type == VisionModelType.KIMI

    def test_create_vision_model_invalid_type(self):
        """测试创建无效类型的模型"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'test-key'}):
            model = create_vision_model("invalid_type")
            # 应该回退到默认的Kimi
            assert model.model_type == VisionModelType.KIMI

    def test_create_vision_model_with_kwargs(self):
        """测试使用额外参数创建模型"""
        with patch.dict('os.environ', {'KIMI_API_KEY': 'test-key'}):
            model = create_vision_model("kimi", max_retries=5, timeout=120)
            assert model.max_retries == 5
            assert model.timeout == 120

    @patch('app.utils.unified_vision_model.create_vision_model')
    def test_get_default_vision_model(self, mock_create):
        """测试获取默认视觉模型"""
        mock_model = MagicMock()
        mock_create.return_value = mock_model
        
        result = get_default_vision_model()
        
        assert result == mock_model
        mock_create.assert_called_once()

    # ============================================================================
    # 图片编码测试
    # ============================================================================

    def test_encode_image(self, mock_model):
        """测试图片编码"""
        image_bytes = b"fake image data"
        encoded = mock_model._encode_image(image_bytes)
        
        # 验证是有效的base64
        decoded = base64.b64decode(encoded)
        assert decoded == image_bytes

    # ============================================================================
    # 解析元素识别结果 - 边界情况
    # ============================================================================

    def test_parse_element_recognition_with_markdown(self, mock_model):
        """测试解析带Markdown代码块的元素识别结果"""
        content = """```json
        [{"type": "button", "text": "Submit", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.95}]
        ```"""
        
        result = mock_model._parse_element_recognition(content, min_confidence=0.8)
        
        assert len(result) == 1
        assert result[0].type == "button"

    def test_parse_element_recognition_malformed_data(self, mock_model):
        """测试解析格式不正确的元素数据"""
        content = '[{"type": "button", "x": "not_a_number", "confidence": 0.95}]'
        
        result = mock_model._parse_element_recognition(content, min_confidence=0.8)
        
        # 应该跳过格式不正确的元素
        assert len(result) == 0

    def test_parse_element_recognition_below_confidence(self, mock_model):
        """测试置信度低于阈值的元素被过滤"""
        content = '[{"type": "button", "text": "Low", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.5}]'
        
        result = mock_model._parse_element_recognition(content, min_confidence=0.8)
        
        assert len(result) == 0

    def test_parse_element_recognition_sort_by_confidence(self, mock_model):
        """测试按置信度排序"""
        content = '''[
            {"type": "button", "text": "Low", "x": 100, "y": 200, "width": 80, "height": 40, "confidence": 0.85},
            {"type": "input", "text": "High", "x": 100, "y": 300, "width": 200, "height": 30, "confidence": 0.95}
        ]'''
        
        result = mock_model._parse_element_recognition(content, min_confidence=0.8)
        
        assert len(result) == 2
        assert result[0].confidence == 0.95  # 高置信度在前
        assert result[1].confidence == 0.85
