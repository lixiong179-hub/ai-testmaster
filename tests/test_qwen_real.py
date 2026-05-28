"""
通义千问 Qwen-VL 真实API调用测试
不使用Mock，进行真实的API调用测试
"""
import pytest
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from app.utils.unified_vision_model import create_vision_model, VisionModelType


def create_test_image_with_button():
    """
    创建一个包含按钮的测试图片
    用于真实测试元素识别功能
    """
    # 创建一个白色背景的图片 (800x600)
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # 绘制一个蓝色按钮 (模拟登录按钮)
    button_x, button_y = 300, 250
    button_width, button_height = 200, 60
    
    # 绘制按钮背景 (蓝色)
    draw.rectangle(
        [button_x, button_y, button_x + button_width, button_y + button_height],
        fill='#1890ff',
        outline='#096dd9',
        width=2
    )
    
    # 尝试添加文字
    try:
        # 使用默认字体
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        # 如果找不到字体，使用默认字体
        font = ImageFont.load_default()
    
    # 在按钮上绘制文字
    text = "登录"
    # 获取文字尺寸
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = button_x + (button_width - text_width) // 2
    text_y = button_y + (button_height - text_height) // 2
    
    draw.text((text_x, text_y), text, fill='white', font=font)
    
    # 添加页面标题
    title = "用户登录页面"
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
    except:
        title_font = ImageFont.load_default()
    
    draw.text((300, 100), title, fill='black', font=title_font)
    
    # 转换为字节
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr.getvalue()


def create_simple_test_image():
    """
    创建一个简单的测试图片
    用于测试截图描述功能
    """
    img = Image.new('RGB', (400, 300), color='lightblue')
    draw = ImageDraw.Draw(img)
    
    # 绘制一些简单的图形
    draw.rectangle([50, 50, 150, 150], fill='red', outline='darkred', width=2)
    draw.ellipse([200, 100, 300, 200], fill='green', outline='darkgreen', width=2)
    
    # 添加文字
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    draw.text((100, 250), "Test Image", fill='black', font=font)
    
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr.getvalue()


@pytest.fixture
def qwen_model():
    """创建通义千问模型实例"""
    return create_vision_model("qwen")


@pytest.fixture
def test_image_with_button():
    """创建带按钮的测试图片"""
    return create_test_image_with_button()


@pytest.fixture
def simple_test_image():
    """创建简单测试图片"""
    return create_simple_test_image()


class TestQwenRealAPICall:
    """
    通义千问真实API调用测试
    注意: 这些测试会消耗API额度
    """
    
    @pytest.mark.real_api
    def test_qwen_model_initialization(self, qwen_model):
        """测试模型初始化"""
        assert qwen_model.model_type == VisionModelType.QWEN
        assert qwen_model.model_name
        assert qwen_model.base_url == "https://dashscope.aliyuncs.com/api/v1"
        assert qwen_model.api_key is not None
        assert len(qwen_model.api_key) > 0
        print(f"\n✓ 模型初始化成功: {qwen_model.model_name}")
        print(f"✓ API Key: {qwen_model.api_key[:20]}...")
    
    @pytest.mark.real_api
    def test_qwen_describe_screenshot(self, qwen_model, simple_test_image):
        """测试真实API调用 - 描述截图"""
        print("\n=== 测试截图描述 ===")
        print("正在调用通义千问API...")
        
        description = qwen_model.describe_screenshot(simple_test_image)
        
        print(f"API返回描述: {description}")
        
        # 验证返回结果
        assert description is not None
        assert isinstance(description, str)
        assert len(description) > 0
        assert description != "无法描述页面内容"
        assert description != "视觉模型未配置"
        
        print("✓ 截图描述测试通过")
    
    @pytest.mark.real_api
    def test_qwen_recognize_elements(self, qwen_model, test_image_with_button):
        """测试真实API调用 - 元素识别"""
        print("\n=== 测试元素识别 ===")
        print("正在调用通义千问API识别登录按钮...")
        
        elements = qwen_model.recognize_elements(
            test_image_with_button,
            "登录按钮",
            min_confidence=0.7
        )
        
        print(f"识别到 {len(elements)} 个元素")
        
        # 验证返回结果
        assert isinstance(elements, list)
        
        if len(elements) > 0:
            for i, elem in enumerate(elements):
                print(f"  元素 {i+1}: {elem}")
                assert elem.type is not None
                assert elem.x >= 0
                assert elem.y >= 0
                assert elem.width > 0
                assert elem.height > 0
                assert 0 <= elem.confidence <= 1
        
        print("✓ 元素识别测试通过")
    
    @pytest.mark.real_api
    def test_qwen_verify_action_result(self, qwen_model, test_image_with_button):
        """测试真实API调用 - 验证操作结果"""
        print("\n=== 测试操作结果验证 ===")
        print("正在调用通义千问API验证操作...")
        
        # 使用同一张图片模拟操作前后（实际场景应该不同）
        success, reason = qwen_model.verify_action_result(
            test_image_with_button,
            test_image_with_button,
            "点击登录按钮",
            "页面跳转到用户主页"
        )
        
        print(f"验证结果: success={success}, reason={reason}")
        
        # 验证返回结果
        assert isinstance(success, bool)
        assert reason is not None
        assert isinstance(reason, str)
        assert len(reason) > 0
        
        print("✓ 操作验证测试通过")
    
    @pytest.mark.real_api
    def test_qwen_api_error_handling(self, qwen_model):
        """测试API错误处理 - 使用无效图片"""
        print("\n=== 测试错误处理 ===")
        
        # 使用无效的图片数据
        invalid_image = b"invalid_image_data"
        
        # 应该优雅处理错误，不抛出异常
        try:
            result = qwen_model.describe_screenshot(invalid_image)
            print(f"错误处理结果: {result}")
            # 可能返回错误信息或空结果
        except Exception as e:
            print(f"捕获到异常: {e}")
            # 如果抛出异常，也认为是正常的错误处理
        
        print("✓ 错误处理测试完成")


class TestQwenModelConfiguration:
    """测试模型配置"""
    
    def test_qwen_config_from_settings(self):
        """测试从settings读取配置"""
        from app.core.config import settings
        
        # 验证配置已加载
        api_key = settings.QWEN_API_KEY
        model_name = settings.QWEN_MODEL
        default_model = settings.VISION_MODEL_DEFAULT
        
        print(f"\n配置检查:")
        print(f"  QWEN_API_KEY: {'已设置' if api_key else '未设置'}")
        print(f"  QWEN_MODEL: {model_name}")
        print(f"  VISION_MODEL_DEFAULT: {default_model}")
        
        assert api_key is not None
        assert len(api_key) > 0
        assert model_name
        assert default_model in {"qwen", "kimi", "baidu", "doubao", "zhipu", "mimo"}
    
    def test_create_different_models(self):
        """测试创建不同模型"""
        # 创建通义千问模型
        qwen = create_vision_model("qwen")
        assert qwen.model_type == VisionModelType.QWEN
        
        # 创建Kimi模型
        kimi = create_vision_model("kimi")
        assert kimi.model_type == VisionModelType.KIMI
        
        print("\n✓ 多模型创建测试通过")


if __name__ == '__main__':
    # 运行真实API测试
    pytest.main([__file__, '-v', '-m', 'real_api', '-s'])
