"""
统一视觉模型适配器单元测试
覆盖率目标95%

使用本地 HTTP 服务器替代 mock，遵循项目"真实环境测试、禁止 Mock"规则。
"""
import os
import json
import threading
import pytest
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from PIL import Image, ImageDraw

from app.utils.unified_vision_model import (
    UnifiedVisionModel,
    VisionModelType,
    ElementInfo,
    ModelProviderConfig,
    MODEL_PROVIDER_CONFIGS,
    create_vision_model,
    get_default_vision_model,
)


def create_test_image() -> bytes:
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
    return create_test_image()


class _KimiAPIHandler(BaseHTTPRequestHandler):
    """模拟 Kimi API 的本地 HTTP 处理器。"""

    response_body: dict = {}

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(content_length)

        body = json.dumps(self.response_body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class _LocalServer:
    """管理本地 HTTP 服务器生命周期。"""

    def __init__(self, handler_class, response_body: dict):
        handler = type(
            handler_class.__name__,
            (handler_class,),
            {"response_body": response_body},
        )
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.thread.join(timeout=5)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


@pytest.fixture
def kimi_model():
    """Kimi 模型 fixture，使用真实 API Key。"""
    return UnifiedVisionModel(
        model_type=VisionModelType.KIMI,
        api_key="test-kimi-key",
    )


@pytest.fixture
def qwen_model():
    """通义千问模型 fixture。"""
    return UnifiedVisionModel(
        model_type=VisionModelType.QWEN,
        api_key="test-qwen-key",
    )


class TestUnifiedVisionModelInit:
    def test_kimi_model_init(self):
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="kimi-key-123",
        )
        assert model.model_type == VisionModelType.KIMI
        assert model.api_key == "kimi-key-123"
        assert model.base_url == "https://api.moonshot.cn/v1"
        assert model.model_name == "moonshot-v1-128k-vision-preview"

    def test_qwen_model_init(self):
        model = UnifiedVisionModel(
            model_type=VisionModelType.QWEN,
            api_key="qwen-key-123",
        )
        assert model.model_type == VisionModelType.QWEN
        assert model.api_key == "qwen-key-123"
        assert model.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def test_model_init_no_api_key(self, monkeypatch):
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        from app.core.config import settings
        original = getattr(settings, "KIMI_API_KEY", "")
        settings.KIMI_API_KEY = ""
        try:
            model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
            assert model.api_key == ""
        finally:
            settings.KIMI_API_KEY = original

    def test_model_init_custom_config(self):
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="custom-key",
            base_url="https://custom.url/v1",
            model_name="custom-model",
            max_retries=5,
            timeout=120,
        )
        assert model.api_key == "custom-key"
        assert model.base_url == "https://custom.url/v1"
        assert model.model_name == "custom-model"
        assert model.max_retries == 5
        assert model.timeout == 120


class TestPrivateMethods:
    def test_encode_image(self, kimi_model):
        image_bytes = b"test_image_data"
        encoded = kimi_model._encode_image(image_bytes)
        assert encoded == base64.b64encode(image_bytes).decode("utf-8")

    def test_encode_image_empty(self, kimi_model):
        encoded = kimi_model._encode_image(b"")
        assert encoded == ""

    def test_build_request_payload_kimi(self, kimi_model):
        system_prompt = "系统提示"
        user_content = [
            {"type": "image", "image": "base64data"},
            {"type": "text", "text": "用户问题"},
        ]
        payload = kimi_model._build_request_payload(system_prompt, user_content)
        assert payload["model"] == "moonshot-v1-128k-vision-preview"
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == system_prompt
        assert payload["messages"][1]["role"] == "user"
        assert payload["temperature"] == 0.3
        assert payload["max_tokens"] == kimi_model.max_tokens

    def test_build_request_payload_qwen(self, qwen_model):
        system_prompt = "系统提示"
        user_content = [
            {"type": "image", "image": "base64data"},
            {"type": "text", "text": "用户问题"},
        ]
        payload = qwen_model._build_request_payload(system_prompt, user_content)
        assert "model" in payload
        assert payload["messages"][0]["role"] == "system"

    def test_parse_response_kimi(self, kimi_model):
        response = {
            "choices": [{"message": {"content": "测试响应内容"}}]
        }
        result = kimi_model._parse_response(response)
        assert result == "测试响应内容"

    def test_parse_response_invalid(self, kimi_model):
        response = {"invalid": "response"}
        result = kimi_model._parse_response(response)
        assert result is None


class TestElementRecognition:
    def test_recognize_elements_single(self, test_image):
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "type": "button",
                                    "text": "登录",
                                    "x": 100,
                                    "y": 200,
                                    "width": 80,
                                    "height": 40,
                                    "confidence": 0.95,
                                }
                            ]
                        )
                    }
                }
            ]
        }
        server = _LocalServer(_KimiAPIHandler, response_body)
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                timeout=5,
            )
            elements = model.recognize_elements(test_image, "登录按钮")
            assert len(elements) == 1
            assert elements[0].type == "button"
            assert elements[0].text == "登录"
            assert elements[0].confidence == 0.95
        finally:
            server.stop()

    def test_recognize_elements_multiple(self, test_image):
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "type": "button",
                                    "text": "登录",
                                    "x": 100,
                                    "y": 200,
                                    "width": 80,
                                    "height": 40,
                                    "confidence": 0.95,
                                },
                                {
                                    "type": "button",
                                    "text": "注册",
                                    "x": 200,
                                    "y": 200,
                                    "width": 80,
                                    "height": 40,
                                    "confidence": 0.92,
                                },
                            ]
                        )
                    }
                }
            ]
        }
        server = _LocalServer(_KimiAPIHandler, response_body)
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                timeout=5,
            )
            elements = model.recognize_elements(test_image, "按钮")
            assert len(elements) == 2
            assert elements[0].confidence >= elements[1].confidence
        finally:
            server.stop()

    def test_recognize_elements_with_markdown(self, test_image):
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(
                            [
                                {
                                    "type": "input",
                                    "text": "用户名",
                                    "x": 100,
                                    "y": 100,
                                    "width": 200,
                                    "height": 30,
                                    "confidence": 0.95,
                                }
                            ]
                        )
                        + "\n```"
                    }
                }
            ]
        }
        server = _LocalServer(_KimiAPIHandler, response_body)
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                timeout=5,
            )
            elements = model.recognize_elements(test_image, "输入框")
            assert len(elements) == 1
            assert elements[0].type == "input"
        finally:
            server.stop()

    def test_recognize_elements_confidence_filter(self, test_image):
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "type": "button",
                                    "text": "高置信度",
                                    "x": 100,
                                    "y": 200,
                                    "width": 80,
                                    "height": 40,
                                    "confidence": 0.95,
                                },
                                {
                                    "type": "button",
                                    "text": "低置信度",
                                    "x": 200,
                                    "y": 200,
                                    "width": 80,
                                    "height": 40,
                                    "confidence": 0.5,
                                },
                            ]
                        )
                    }
                }
            ]
        }
        server = _LocalServer(_KimiAPIHandler, response_body)
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                timeout=5,
            )
            elements = model.recognize_elements(test_image, "按钮", min_confidence=0.9)
            assert len(elements) == 1
            assert elements[0].text == "高置信度"
        finally:
            server.stop()

    def test_recognize_elements_no_api_key(self, test_image):
        model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
        model.api_key = ""
        elements = model.recognize_elements(test_image, "按钮")
        assert elements == []


class TestDescribeScreenshot:
    def test_describe_screenshot_success(self, test_image):
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": "这是一个测试页面，包含一个红色方块和文字'Test'。"
                    }
                }
            ]
        }
        server = _LocalServer(_KimiAPIHandler, response_body)
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                timeout=5,
            )
            description = model.describe_screenshot(test_image)
            assert "测试页面" in description
            assert "红色方块" in description
        finally:
            server.stop()

    def test_describe_screenshot_no_api_key(self, test_image):
        model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
        model.api_key = ""
        description = model.describe_screenshot(test_image)
        assert description == "视觉模型未配置"


class TestVerifyActionResult:
    def test_verify_action_success(self, test_image):
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"success": True, "reason": "成功跳转到首页"}
                        )
                    }
                }
            ]
        }
        server = _LocalServer(_KimiAPIHandler, response_body)
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                timeout=5,
            )
            success, reason = model.verify_action_result(
                test_image, test_image, "点击登录按钮", "跳转到首页"
            )
            assert success is True
            assert "成功" in reason
        finally:
            server.stop()

    def test_verify_action_failure(self, test_image):
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"success": False, "reason": "页面未发生变化"}
                        )
                    }
                }
            ]
        }
        server = _LocalServer(_KimiAPIHandler, response_body)
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                timeout=5,
            )
            success, reason = model.verify_action_result(
                test_image, test_image, "点击按钮", "预期变化"
            )
            assert success is False
            assert "未发生变化" in reason
        finally:
            server.stop()

    def test_verify_action_no_api_key(self, test_image):
        model = UnifiedVisionModel(model_type=VisionModelType.KIMI)
        model.api_key = ""
        success, reason = model.verify_action_result(
            test_image, test_image, "点击", "预期"
        )
        assert success is False
        assert "未配置" in reason


class TestElementInfo:
    def test_element_info_creation(self):
        element = ElementInfo(
            type="button",
            text="提交",
            x=100,
            y=200,
            width=80,
            height=40,
            confidence=0.95,
        )
        assert element.type == "button"
        assert element.text == "提交"
        assert element.x == 100
        assert element.y == 200
        assert element.width == 80
        assert element.height == 40
        assert element.confidence == 0.95

    def test_find_element_center(self, kimi_model):
        element = ElementInfo(
            type="button",
            text="测试",
            x=100,
            y=200,
            width=80,
            height=40,
            confidence=0.9,
        )
        center_x, center_y = kimi_model.find_element_center(element)
        assert center_x == 140
        assert center_y == 220


class TestErrorHandling:
    def test_network_error(self, test_image):
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key",
            base_url="http://127.0.0.1:1",
            max_retries=1,
            retry_delay=0,
            timeout=1,
        )
        description = model.describe_screenshot(test_image)
        assert "无法" in description or "未配置" in description

    def test_timeout_error(self, test_image):
        model = UnifiedVisionModel(
            model_type=VisionModelType.KIMI,
            api_key="test-key",
            base_url="http://127.0.0.1:1",
            max_retries=1,
            retry_delay=0,
            timeout=1,
        )
        description = model.describe_screenshot(test_image)
        assert "无法" in description or "未配置" in description

    def test_http_401_error(self, test_image):
        class _ErrorHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get('Content-Length', 0))
                self.rfile.read(content_length)
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "unauthorized"}')

            def log_message(self, format, *args):
                pass

        server = _LocalServer(_ErrorHandler, {})
        server.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=server.url,
                max_retries=1,
                retry_delay=0,
                timeout=5,
            )
            description = model.describe_screenshot(test_image)
            assert "无法" in description
        finally:
            server.stop()

    def test_retry_mechanism(self, test_image):
        call_count = 0

        class _RetryHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                nonlocal call_count
                content_length = int(self.headers.get('Content-Length', 0))
                self.rfile.read(content_length)
                call_count += 1

                if call_count == 1:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "server error"}')
                else:
                    body = json.dumps(
                        {"choices": [{"message": {"content": "成功"}}]}
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), _RetryHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            model = UnifiedVisionModel(
                model_type=VisionModelType.KIMI,
                api_key="test-key",
                base_url=f"http://127.0.0.1:{port}",
                max_retries=3,
                retry_delay=0,
                timeout=5,
            )
            description = model.describe_screenshot(test_image)
            assert call_count >= 2
            assert description == "成功"
        finally:
            server.shutdown()
            thread.join(timeout=5)


class TestFactoryFunctions:
    def test_create_vision_model_kimi(self):
        model = create_vision_model("kimi", api_key="test-key")
        assert model.model_type == VisionModelType.KIMI

    def test_create_vision_model_qwen(self):
        model = create_vision_model("qwen", api_key="test-key")
        assert model.model_type == VisionModelType.QWEN

    def test_create_vision_model_invalid(self):
        model = create_vision_model("invalid_model")
        assert model.model_type == VisionModelType.MIMO

    def test_get_default_vision_model(self):
        model = get_default_vision_model()
        assert isinstance(model, UnifiedVisionModel)


class TestModelConfigs:
    def test_model_provider_configs_exist(self):
        assert VisionModelType.KIMI in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.QWEN in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.ZHIPU in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.BAIDU in MODEL_PROVIDER_CONFIGS
        assert VisionModelType.DOUBAO in MODEL_PROVIDER_CONFIGS

    def test_kimi_config_values(self):
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.KIMI]
        assert config.model_type == VisionModelType.KIMI
        assert config.api_key_env == "KIMI_API_KEY"
        assert config.default_base_url == "https://api.moonshot.cn/v1"

    def test_qwen_config_values(self):
        config = MODEL_PROVIDER_CONFIGS[VisionModelType.QWEN]
        assert config.model_type == VisionModelType.QWEN
        assert config.api_key_env == "QWEN_API_KEY"
        assert config.default_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
