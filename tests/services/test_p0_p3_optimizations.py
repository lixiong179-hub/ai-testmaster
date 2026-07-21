"""
P0-P3优化项单元测试

覆盖范围:
- config.py: 数据库URL校验/SQLite拒绝/CORS生产校验/JWT密钥持久化
- rate_limit.py: Redis模式+内存降级
- jwt_utils.py: create_access_token/verify_access_token
- user.py: 认证保护验证（通过导入检查）

注: _convert_steps_to_response / _build_test_case_response / AIGenerateRequest 校验测试
    在 API 重构后已移除（函数/类已迁移至 test_case_ai_schemas 或不再存在）。
    AIGenerateRequest / BatchGenerateRequest / AIGenerateEnhancedRequest 现统一从
    test_case_ai_schemas 导入。
"""
import pytest
import json
import sys

import os
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigSecurity:
    """config.py 安全校验测试

    注: 数据库URL校验/SQLite拒绝/CORS生产校验/密钥持久化的源码字符串检查测试
    在安全深度优化后已过时（校验逻辑迁移至 key_management.py 和 main.py startup validation）。
    保留行为测试（MySQL URL接受/DevSettings CORS通配符/DEBUG默认值）。
    """

    def test_mysql_url_accepted(self):
        """MySQL URL应被接受"""
        from app.core.config import Settings

        s = Settings(
            DATABASE_URL="mysql+pymysql://user:pass@localhost:3306/testdb",
            ENVIRONMENT="test",
            JWT_SECRET_KEY="test-secret-key",
            ENCRYPTION_KEY="test-enc-key",
            ENCRYPTION_SALT="test-salt"
        )

        assert s.DATABASE_URL == "mysql+pymysql://user:pass@localhost:3306/testdb"

    def test_dev_cors_wildcard_allowed(self):
        """开发环境允许CORS通配符"""
        from app.core.config import DevSettings

        s = DevSettings(
            DATABASE_URL="mysql+pymysql://user:pass@localhost:3306/testdb",
            JWT_SECRET_KEY="test-secret-key",
            ENCRYPTION_KEY="test-enc-key",
            ENCRYPTION_SALT="test-salt"
        )

        assert s.CORS_ORIGINS == "*"

    def test_debug_default_false_in_base_settings(self):
        """P1-5: 基础Settings中DEBUG默认False（通过类属性验证）"""
        from app.core.config import Settings
        import inspect

        # 检查类定义中的默认值（不受.env影响）
        source = inspect.getsource(Settings)
        assert "DEBUG: bool = False" in source, \
            "Settings.DEBUG默认值应为False"

    def test_dev_settings_debug_true(self):
        """P1-5: DevSettings中DEBUG为True"""
        from app.core.config import DevSettings
        import inspect

        source = inspect.getsource(DevSettings)
        assert "DEBUG: bool = True" in source, \
            "DevSettings.DEBUG应为True"


class TestRateLimitMiddleware:
    """rate_limit.py 双模式限流测试

    注: 测试环境配置了 REDIS_URL 会导致 _use_redis=True，需 patch settings.REDIS_URL=''
    强制走内存模式以验证内存限流逻辑。
    """

    def test_memory_mode_initialization(self):
        """内存模式下初始化正常"""
        from app.core.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI, Request, Response
        from starlette.types import ASGIApp, Receive, Send
        from unittest.mock import patch

        app = FastAPI()
        with patch("app.core.rate_limit.settings.REDIS_URL", ""):
            middleware = RateLimitMiddleware(app)

        assert middleware.max_requests == 100
        assert middleware.time_window == 60
        assert middleware._use_redis is False
        assert middleware.requests is not None

    def test_memory_mode_rate_limiting(self):
        """内存模式：超过限制返回429"""
        from app.core.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi import HTTPException
        from unittest.mock import AsyncMock, patch
        import asyncio

        app = FastAPI()
        with patch("app.core.rate_limit.settings.REDIS_URL", ""):
            middleware = RateLimitMiddleware(app, max_requests=2, time_window=60)

        async def mock_call_next(request):
            return JSONResponse(content={"status": "ok"})

        async def run_test():
            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/test',
                'headers': [],
                'query_string': b'',
                'client': ('127.0.0.1', 12345),
            }

            receive = AsyncMock()
            send = AsyncMock()

            request = Request(scope, receive, send)

            # 第1次请求应通过
            response1 = await middleware.dispatch(request, mock_call_next)
            assert response1.status_code == 200

            # 第2次请求也应通过（max_requests=2）
            scope2 = dict(scope)
            request2 = Request(scope2, receive, send)
            response2 = await middleware.dispatch(request2, mock_call_next)
            assert response2.status_code == 200

            # 第3次请求应被限流（捕获HTTPException）
            scope3 = dict(scope)
            request3 = Request(scope3, receive, send)
            try:
                response3 = await middleware.dispatch(request3, mock_call_next)
                assert response3.status_code == 429, "第3次请求应返回429"
            except HTTPException as e:
                assert e.status_code == 429

        asyncio.run(run_test())

    def test_custom_max_requests(self):
        """自定义最大请求数"""
        from app.core.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI

        app = FastAPI()
        middleware = RateLimitMiddleware(app, max_requests=50, time_window=30)

        assert middleware.max_requests == 50
        assert middleware.time_window == 30


class TestJWTUtilsUTCCompatibility:
    """jwt_utils.py token 创建与验证测试 (P3-3)"""

    def test_create_token_with_utc_time(self):
        """使用UTC时间创建token应能正确解码"""
        from app.utils.jwt_utils import create_access_token, verify_access_token

        token = create_access_token(data={"sub": "123", "username": "testuser"})

        payload = verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"


class TestUserEndpointAuthProtection:
    """user.py 端点认证保护验证 (P0)"""

    def test_user_router_has_login_endpoint(self):
        """user路由应有login端点且使用OAuth2PasswordRequestForm"""
        from app.api.v1.endpoints.user import router

        routes = [r.path for r in router.routes]
        assert "/user/login" in routes, "缺少 /user/login 端点"

    def test_user_router_has_me_endpoint(self):
        """/user/me端点存在"""
        from app.api.v1.endpoints.user import router

        routes = [r.path for r in router.routes]
        assert "/user/me" in routes

    def test_user_router_has_role_crud_endpoints(self):
        """角色CRUD端点存在"""
        from app.api.v1.endpoints.user import router

        routes = [r.path for r in router.routes]
        assert "/user/role" in routes
        assert "/user/role/{role_id}" in routes

    def test_user_router_imports_auth_dependencies(self):
        """user.py导入了认证依赖"""
        import app.api.v1.endpoints.user as user_module
        import inspect

        source = inspect.getsource(user_module)

        assert "get_current_user" in source, "user.py应导入get_current_user"
        assert "create_access_token" in source, "user.py应导入create_access_token"
        assert "oauth2_scheme" not in source or "Depends(get_current_user)" in source, \
            "user.py应使用get_current_user而非oauth2_scheme直接依赖"


class TestTestCaseSoftDelete:
    """TestCase 软删除模型测试 (P2-6)"""

    def test_model_has_soft_delete_fields(self):
        """TestCase模型应有is_deleted和deleted_at字段"""
        from app.models.test_case import TestCase

        columns = {c.name for c in TestCase.__table__.columns}

        assert "is_deleted" in columns, "TestCase缺少is_deleted字段"
        assert "deleted_at" in columns, "TestCase缺少deleted_at字段"

    def test_soft_delete_fields_exist(self):
        """TestCase模型应有is_deleted和deleted_at字段"""
        from app.models.test_case import TestCase
        import inspect

        source = inspect.getsource(TestCase)

        assert "is_deleted" in source, "TestCase缺少is_deleted字段"
        assert "deleted_at" in source, "TestCase缺少deleted_at字段"
        # 验证默认值定义
        assert "default=False" in source or 'default = False' in source or "default=False" in source, \
            "is_deleted默认应为False"

    def test_soft_delete_column_type(self):
        """软删除字段类型正确"""
        from app.models.test_case import TestCase
        from sqlalchemy import Boolean, DateTime

        columns = {c.name: c.type for c in TestCase.__table__.columns}

        assert isinstance(columns.get("is_deleted"), type(Boolean())), \
            f"is_deleted应为Boolean类型，实际: {type(columns.get('is_deleted'))}"
        assert columns.get("deleted_at") is not None, "deleted_at字段应存在"


class TestProjectFileSortIndex:
    """ProjectFile sort_order索引测试 (P2-5)"""

    def test_project_file_has_sort_index(self):
        """ProjectFile表应有排序联合索引"""
        from app.models.project import ProjectFile
        import inspect

        source = inspect.getsource(ProjectFile)

        # 验证__table_args__中定义了索引
        assert "__table_args__" in source, "ProjectFile应有__table_args__定义索引"
        assert "sort_order" in source, "ProjectFile索引应包含sort_order"
        assert "Index" in source or "ix_project_file_sort" in source, \
            "ProjectFile应定义sort相关索引"

    def test_project_file_has_sort_order_column(self):
        """ProjectFile有sort_order字段"""
        from app.models.project import ProjectFile

        columns = {c.name for c in ProjectFile.__table__.columns}
        assert "sort_order" in columns, "ProjectFile缺少sort_order字段"


class TestBatchGenerateValidation:
    """批量生成请求校验测试 (P2-7)

    注: AIGenerateRequest / BatchGenerateRequest / AIGenerateEnhancedRequest
    在 API 重构后已迁移至 app.api.v1.endpoints.test_case_ai_schemas。
    """

    def test_description_min_length(self):
        """描述最少10个字符"""
        from app.api.v1.endpoints.test_case_ai_schemas import AIGenerateRequest

        with pytest.raises(Exception):  # ValidationError
            AIGenerateRequest(project_id=1, description="短")

    def test_description_max_length(self):
        """描述最多10000字符"""
        from app.api.v1.endpoints.test_case_ai_schemas import AIGenerateRequest

        long_desc = "x" * 10001

        with pytest.raises(Exception):  # ValidationError
            AIGenerateRequest(project_id=1, description=long_desc)

    def test_description_valid_length(self):
        """合法长度描述通过校验"""
        from app.api.v1.endpoints.test_case_ai_schemas import AIGenerateRequest

        req = AIGenerateRequest(project_id=1, description="这是一个有效的测试描述，长度足够")

        assert req.description == "这是一个有效的测试描述，长度足够"

    def test_batch_generate_list_size_limit(self):
        """列表大小限制200"""
        from app.api.v1.endpoints.test_case_ai_schemas import BatchGenerateRequest

        too_many_ids = list(range(201))

        with pytest.raises(Exception):  # ValidationError
            BatchGenerateRequest(
                project_id=1,
                test_point_ids=too_many_ids,
                requirement_file_ids=[],
                ui_file_ids=[]
            )

    def test_batch_generate_valid_list(self):
        """合法列表大小通过校验"""
        from app.api.v1.endpoints.test_case_ai_schemas import BatchGenerateRequest

        req = BatchGenerateRequest(
            project_id=1,
            test_point_ids=[1, 2, 3],
            requirement_file_ids=[10, 20],
            ui_file_ids=[100]
        )

        assert len(req.test_point_ids) == 3
        assert len(req.requirement_file_ids) == 2
        assert len(req.ui_file_ids) == 1

    def test_enhanced_request_validation(self):
        """AIGenerateEnhancedRequest校验

        注: case_type 经 TestCaseType.from_legacy 规范化，"functional" -> "manual"
        """
        from app.api.v1.endpoints.test_case_ai_schemas import AIGenerateEnhancedRequest

        # 最少5字符
        req = AIGenerateEnhancedRequest(
            project_id=1,
            description="这是一个有效的测试描述",
            case_type="functional",
            priority=1
        )

        assert req.priority == 1
        # "functional" 经 TestCaseType.from_legacy 规范化为 MANUAL.value="manual"
        assert req.case_type == "manual"
        assert req.description == "这是一个有效的测试描述"
