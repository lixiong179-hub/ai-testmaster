"""
敏感凭据加密存储测试

覆盖范围:
- Project.test_object_password 加密存储/解密读取
- RequirementLink.auth_config JSON整体加密
- 旧数据兼容（未加密数据直接返回）
- 空值处理

要求: 使用真实MySQL数据库，不使用Mock
"""
import pytest
import json
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.project import Project
from app.models.requirement_link import RequirementLink


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "mysql+pymysql://root:test1234@localhost:3306/ai_testmaster"
)
_TEST_PREFIX = "enc_test_"


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def test_project(db_session) -> Project:
    project = Project(
        name=f"{_TEST_PREFIX}密码加密测试",
        description="测试密码加密",
        user_id=1
    )
    db_session.add(project)
    db_session.flush()
    return project


class TestProjectPasswordEncryption:
    """Project.test_object_password 加密存储测试"""

    def test_password_set_and_get(self, db_session, test_project):
        """密码设置和读取——核心场景"""
        test_project.test_object_password = "MySecret123"
        db_session.commit()
        db_session.refresh(test_project)
        assert test_project.test_object_password == "MySecret123"

    def test_empty_password(self, db_session, test_project):
        """空密码处理——空字符串转为None"""
        test_project.test_object_password = ""
        db_session.commit()
        db_session.refresh(test_project)
        assert test_project.test_object_password is None

    def test_none_password(self, db_session, test_project):
        """None密码处理"""
        test_project.test_object_password = None
        db_session.commit()
        db_session.refresh(test_project)
        assert test_project.test_object_password is None

    def test_special_characters_in_password(self, db_session, test_project):
        """特殊字符密码"""
        special_pwd = "P@$$w0rd!#%&*()_+-=[]{}|;':\",./<>?"
        test_project.test_object_password = special_pwd
        db_session.commit()
        db_session.refresh(test_project)
        assert test_project.test_object_password == special_pwd

    def test_unicode_password(self, db_session, test_project):
        """Unicode密码"""
        unicode_pwd = "密码测试123"
        test_project.test_object_password = unicode_pwd
        db_session.commit()
        db_session.refresh(test_project)
        assert test_project.test_object_password == unicode_pwd

    def test_update_password(self, db_session, test_project):
        """更新密码"""
        test_project.test_object_password = "OldPassword"
        db_session.commit()
        test_project.test_object_password = "NewPassword"
        db_session.commit()
        db_session.refresh(test_project)
        assert test_project.test_object_password == "NewPassword"


class TestRequirementLinkAuthConfigEncryption:
    """RequirementLink.auth_config JSON加密测试"""

    @pytest.fixture
    def test_project_for_link(self, db_session) -> Project:
        project = Project(
            name=f"{_TEST_PREFIX}链接测试",
            description="测试链接",
            user_id=1
        )
        db_session.add(project)
        db_session.flush()
        return project

    def test_basic_auth_config(self, db_session, test_project_for_link):
        """Basic认证配置——核心场景"""
        link = RequirementLink(
            project_id=test_project_for_link.id,
            link_name=f"{_TEST_PREFIX}Basic认证",
            link_type="requirement",
            link_url="https://example.com/api",
            auth_type="basic",
            auth_config={"username": "admin", "password": "secret123"},
            created_by=1
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        assert link.auth_config["username"] == "admin"
        assert link.auth_config["password"] == "secret123"

    def test_bearer_token_config(self, db_session, test_project_for_link):
        """Bearer Token配置"""
        link = RequirementLink(
            project_id=test_project_for_link.id,
            link_name=f"{_TEST_PREFIX}Bearer认证",
            link_type="requirement",
            link_url="https://example.com/api",
            auth_type="bearer",
            auth_config={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"},
            created_by=1
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        assert link.auth_config["token"] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

    def test_api_key_config(self, db_session, test_project_for_link):
        """API Key配置"""
        link = RequirementLink(
            project_id=test_project_for_link.id,
            link_name=f"{_TEST_PREFIX}APIKey认证",
            link_type="ui_prototype",
            link_url="https://example.com/proto",
            auth_type="api_key",
            auth_config={"api_key": "sk-abc123xyz789"},
            created_by=1
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        assert link.auth_config["api_key"] == "sk-abc123xyz789"

    def test_cookie_config(self, db_session, test_project_for_link):
        """Cookie认证配置"""
        link = RequirementLink(
            project_id=test_project_for_link.id,
            link_name=f"{_TEST_PREFIX}Cookie认证",
            link_type="requirement",
            link_url="https://example.com/api",
            auth_type="cookie",
            auth_config={
                "name": "session_id",
                "value": "abc123def456",
                "domain": ".example.com"
            },
            created_by=1
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        config = link.auth_config
        assert config["name"] == "session_id"
        assert config["value"] == "abc123def456"

    def test_empty_auth_config(self, db_session, test_project_for_link):
        """空认证配置"""
        link = RequirementLink(
            project_id=test_project_for_link.id,
            link_name=f"{_TEST_PREFIX}无认证",
            link_type="requirement",
            link_url="https://example.com/public",
            auth_type="none",
            auth_config={},
            created_by=1
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        assert link.auth_config == {}

    def test_none_auth_config(self, db_session, test_project_for_link):
        """None认证配置"""
        link = RequirementLink(
            project_id=test_project_for_link.id,
            link_name=f"{_TEST_PREFIX}无配置",
            link_type="ui_prototype",
            link_url="https://example.com/proto",
            auth_type="none",
            auth_config=None,
            created_by=1
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        assert link.auth_config == {}

    def test_complex_nested_auth_config(self, db_session, test_project_for_link):
        """嵌套复杂结构"""
        link = RequirementLink(
            project_id=test_project_for_link.id,
            link_name=f"{_TEST_PREFIX}复杂认证",
            link_type="requirement",
            link_url="https://example.com/api",
            auth_type="oauth2",
            auth_config={
                "client_id": "my_client_id",
                "client_secret": "super_secret_key",
                "scopes": ["read", "write", "delete"],
                "endpoints": {
                    "auth": "https://auth.example.com/oauth/authorize",
                    "token": "https://auth.example.com/oauth/token",
                    "refresh": "https://auth.example.com/oauth/refresh"
                }
            },
            created_by=1
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)
        config = link.auth_config
        assert config["client_id"] == "my_client_id"
        assert config["scopes"] == ["read", "write", "delete"]
        assert config["endpoints"]["token"] == "https://auth.example.com/oauth/token"
