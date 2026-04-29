"""
前置操作服务覆盖率测试
提升 precondition_service.py 的测试覆盖率
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.services.precondition_service import (
    TestObjectType,
    PreconditionError,
    PreconditionConfigError,
    LoginError,
    TestObjectInfo,
    LoginFormInfo
)


class TestTestObjectType(unittest.TestCase):
    """测试测试对象类型枚举"""
    
    def test_object_types(self):
        """测试所有对象类型"""
        self.assertEqual(TestObjectType.WEB.value, "web")
        self.assertEqual(TestObjectType.APP.value, "app")


class TestPreconditionError(unittest.TestCase):
    """测试前置操作错误类"""
    
    def test_error_creation(self):
        """测试创建错误"""
        error = PreconditionError("测试错误消息")
        self.assertEqual(str(error), "测试错误消息")


class TestPreconditionConfigError(unittest.TestCase):
    """测试前置配置错误类"""
    
    def test_config_error_creation(self):
        """测试创建配置错误"""
        error = PreconditionConfigError("配置错误")
        self.assertEqual(str(error), "配置错误")


class TestLoginError(unittest.TestCase):
    """测试登录错误类"""
    
    def test_login_error_creation(self):
        """测试创建登录错误"""
        error = LoginError("登录失败")
        self.assertEqual(str(error), "登录失败")


class TestTestObjectInfo(unittest.TestCase):
    """测试被测对象信息类"""
    
    def test_web_info_creation(self):
        """测试创建Web对象信息"""
        info = TestObjectInfo(
            type=TestObjectType.WEB,
            url="https://example.com",
            username="admin",
            password="123456"
        )
        self.assertEqual(info.type, TestObjectType.WEB)
        self.assertEqual(info.url, "https://example.com")
        self.assertEqual(info.username, "admin")
        self.assertEqual(info.password, "123456")
    
    def test_app_info_creation(self):
        """测试创建App对象信息"""
        info = TestObjectInfo(
            type=TestObjectType.APP,
            device_id="device123",
            app_package="com.example.app",
            app_activity=".MainActivity"
        )
        self.assertEqual(info.type, TestObjectType.APP)
        self.assertEqual(info.device_id, "device123")
        self.assertEqual(info.app_package, "com.example.app")
    
    def test_validate_web_success(self):
        """测试验证Web配置成功"""
        info = TestObjectInfo(
            type=TestObjectType.WEB,
            url="https://example.com"
        )
        # 应该不抛出异常
        info.validate_web()
    
    def test_validate_web_no_url(self):
        """测试验证Web配置无URL"""
        info = TestObjectInfo(type=TestObjectType.WEB)
        with self.assertRaises(PreconditionConfigError) as context:
            info.validate_web()
        self.assertIn("URL", str(context.exception))
    
    def test_validate_web_invalid_url(self):
        """测试验证Web配置无效URL"""
        info = TestObjectInfo(
            type=TestObjectType.WEB,
            url="invalid-url"
        )
        with self.assertRaises(PreconditionConfigError) as context:
            info.validate_web()
        self.assertIn("无效的URL", str(context.exception))
    
    def test_validate_app_success(self):
        """测试验证App配置成功"""
        info = TestObjectInfo(
            type=TestObjectType.APP,
            device_id="device123",
            app_package="com.example.app"
        )
        # 应该不抛出异常
        info.validate_app()
    
    def test_validate_app_no_device(self):
        """测试验证App配置无设备ID"""
        info = TestObjectInfo(
            type=TestObjectType.APP,
            app_package="com.example.app"
        )
        with self.assertRaises(PreconditionConfigError) as context:
            info.validate_app()
        self.assertIn("设备ID", str(context.exception))


class TestLoginFormInfo(unittest.TestCase):
    """测试登录表单信息类"""
    
    def test_login_form_creation(self):
        """测试创建登录表单信息"""
        form = LoginFormInfo(
            username_input={"x": 100, "y": 200},
            password_input={"x": 100, "y": 250},
            submit_button={"x": 150, "y": 300}
        )
        self.assertEqual(form.username_input, {"x": 100, "y": 200})
        self.assertTrue(form.is_complete())
    
    def test_login_form_incomplete(self):
        """测试不完整的登录表单"""
        form = LoginFormInfo(
            username_input={"x": 100, "y": 200}
        )
        self.assertFalse(form.is_complete())
    
    def test_login_form_empty(self):
        """测试空登录表单"""
        form = LoginFormInfo()
        self.assertFalse(form.is_complete())


if __name__ == '__main__':
    unittest.main(verbosity=2)
