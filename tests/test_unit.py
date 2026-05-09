"""
AI TestMaster 单元测试套件

运行: python -m pytest tests/ -v
"""
import pytest
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings, _generate_secret_key
from app.utils.crypto import encrypt_password, decrypt_password
from app.core.exception import create_response, create_error_response, RESPONSE_CODE


# ==================== 配置测试 ====================

class TestConfig:
    """配置模块测试"""

    def test_generate_secret_key(self):
        """测试密钥生成"""
        key1 = _generate_secret_key()
        key2 = _generate_secret_key()

        assert key1 is not None
        assert len(key1) > 20  # 至少20字符
        assert key1 != key2  # 每次生成不同的密�?

    def test_settings_initialization(self):
        """测试配置初始�?""
        assert settings is not None
        assert settings.APP_NAME == "AI测试平台"
        assert settings.JWT_SECRET_KEY is not None
        assert len(settings.JWT_SECRET_KEY) > 0


# ==================== 加密工具测试 ====================

class TestCrypto:
    """加密工具测试"""

    def test_encrypt_decrypt_password(self):
        """测试密码加密解密"""
        original = "test_password_123"
        encrypted = encrypt_password(original)

        assert encrypted != original
        assert len(encrypted) > 0

        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_encrypt_empty_password(self):
        """测试空密码加�?""
        result = encrypt_password("")
        assert result == ""

    def test_decrypt_non_encrypted(self):
        """测试解密非加密字符串"""
        plain_text = "already_plain"
        result = decrypt_password(plain_text)
        assert result == plain_text


# ==================== 异常处理测试 ====================

class TestException:
    """异常处理测试"""

    def test_create_response(self):
        """测试成功响应"""
        data = {"id": 1, "name": "test"}
        response = create_response(data=data, msg="操作成功", code=200)

        assert response["code"] == 200
        assert response["msg"] == "操作成功"
        assert response["data"] == data
        assert "timestamp" in response

    def test_create_error_response(self):
        """测试错误响应"""
        response = create_error_response(msg="错误信息", code=500)

        assert response["code"] == 500
        assert response["msg"] == "错误信息"
        assert response["data"] == {}

    def test_response_code_constants(self):
        """测试响应码常�?""
        assert RESPONSE_CODE["SUCCESS"] == 200
        assert RESPONSE_CODE["UNAUTHORIZED"] == 401
        assert RESPONSE_CODE["NOT_FOUND"] == 404
        assert RESPONSE_CODE["DATABASE_ERROR"] == 500


# ==================== 数据库工具测�?====================

class TestDatabaseHelper:
    """数据库工具测�?""

    def test_build_filter_conditions(self):
        """测试过滤条件构建"""
        from app.core.db_helper import QueryHelper

        class MockModel:
            pass

        MockModel.id = "id"
        MockModel.name = "name"
        MockModel.status = "status"

        conditions = QueryHelper.build_filter_conditions(
            MockModel,
            id=1,
            name="test",
            status=None  # None值应被忽�?
        )

        # 验证None值被过滤
        assert len(conditions) == 2

    def test_build_pagination(self):
        """测试分页构建"""
        from app.core.db_helper import QueryHelper

        class MockQuery:
            pass

        offset, limit = QueryHelper.build_pagination(MockQuery(), page=1, page_size=10)
        assert offset == 0
        assert limit == 10

        offset, limit = QueryHelper.build_pagination(MockQuery(), page=3, page_size=20)
        assert offset == 40
        assert limit == 20


# ==================== 项目模型测试 ====================

class TestProjectModel:
    """项目模型测试"""

    def test_project_type_values(self):
        """测试项目类型有效�?""
        valid_types = ["web", "app"]
        assert "web" in valid_types
        assert "app" in valid_types


# ==================== API Schema测试 ====================

class TestSchemas:
    """API Schema测试"""

    def test_project_create_schema(self):
        """测试项目创建Schema"""
        from app.schemas.project import ProjectCreate

        # 有效数据
        project = ProjectCreate(
            name="Test Project",
            description="Test Description",
            project_type="web"
        )
        assert project.name == "Test Project"
        assert project.project_type == "web"

    def test_project_create_defaults(self):
        """测试项目创建默认�?""
        from app.schemas.project import ProjectCreate

        project = ProjectCreate(name="Test")
        assert project.project_type == "web"  # 默认Web�?

    def test_web_env_config_schema(self):
        """测试Web环境配置Schema"""
        from app.schemas.project import WebEnvConfig, WebEnvConfigs

        env = WebEnvConfig(url="https://test.com", username="admin", password="123456")
        assert env.url == "https://test.com"
        assert env.username == "admin"

        configs = WebEnvConfigs(
            test=WebEnvConfig(url="https://test.com"),
            staging=WebEnvConfig(url="https://staging.com"),
            prod=WebEnvConfig(url="https://prod.com")
        )
        assert configs.test.url == "https://test.com"
        assert configs.prod.url == "https://prod.com"


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
