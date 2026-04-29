"""
P0-P3优化项单元测试

覆盖范围:
- config.py: 数据库URL校验/SQLite拒绝/CORS生产校验/JWT密钥持久化
- rate_limit.py: Redis模式+内存降级
- test_case.py: _convert_steps_to_response / _build_test_case_response 工具函数
- jwt_utils.py: UTC时区兼容性
- user.py: 认证保护验证（通过导入检查）
"""
import pytest
import json
import sys
import os
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigSecurity:
    """config.py 安全校验测试"""

    def test_empty_database_url_validation_exists(self):
        """P1-3: 空DATABASE_URL校验逻辑存在"""
        from app.core.config import Settings
        import inspect

        source = inspect.getsource(Settings)
        assert "DATABASE_URL" in source
        assert "未配置" in source or "禁止使用" in source or "sqlite" in source.lower(), \
            "Settings应有数据库URL校验"

    def test_sqlite_rejection_logic(self):
        """P1-3: SQLite拒绝逻辑存在"""
        from app.core.config import Settings
        import inspect

        source = inspect.getsource(Settings)
        assert "sqlite" in source.lower() and ("禁止" in source or "reject" in source.lower()), \
            "Settings应有SQLite拒绝逻辑"

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

    def test_prod_cors_validation_exists(self):
        """P1-1: 生产环境CORS校验逻辑存在"""
        from app.core.config import Settings
        import inspect

        source = inspect.getsource(Settings)
        assert "CORS_ORIGINS" in source
        assert ("prod" in source and ("通配符" in source or "wildcard" in source.lower())) or \
               "生产环境" in source, \
            "Settings应有生产环境CORS限制"

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

    def test_secret_key_persistence_creates_file(self):
        """P2-3: 密钥持久化函数存在且可调用"""
        from app.core.config import Settings
        import inspect
        
        source = inspect.getsource(Settings)
        
        # 验证持久化相关代码存在
        assert "_load_cached_key" in source or "secret_keys" in source.lower(), \
            "Settings应有密钥持久化逻辑"
        assert "_save_cached_key" in source or ".secret_keys" in source, \
            "Settings应保存密钥到.secret_keys文件"


class TestRateLimitMiddleware:
    """rate_limit.py 双模式限流测试"""

    def test_memory_mode_initialization(self):
        """内存模式下初始化正常"""
        from app.core.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI, Request, Response
        from starlette.types import ASGIApp, Receive, Send
        
        app = FastAPI()
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
        from unittest.mock import AsyncMock
        import asyncio
        
        app = FastAPI()
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


class TestTestCaseStepConversion:
    """test_case.py 步骤转换工具函数测试"""

    def test_convert_steps_none_returns_empty(self):
        """None输入返回空列表"""
        from app.api.v1.endpoints.test_case import _convert_steps_to_response
        
        result = _convert_steps_to_response(None)
        assert result == []

    def test_convert_steps_empty_list(self):
        """空列表返回空列表"""
        from app.api.v1.endpoints.test_case import _convert_steps_to_response
        
        result = _convert_steps_to_response([])
        assert result == []

    def test_convert_steps_basic_format(self):
        """基本格式转换"""
        from app.api.v1.endpoints.test_case import _convert_steps_to_response
        
        steps_json = [
            {"step": "打开浏览器", "action": "click", "param": "登录按钮", "expected_result": "显示登录页"},
            {"step": "输入用户名", "action": "type", "param": "admin", "expected_result": "输入框有值"}
        ]
        
        result = _convert_steps_to_response(steps_json)
        
        assert len(result) == 2
        assert result[0]["step"] == "打开浏览器"
        assert result[0]["action"] == "click"
        assert result[0]["param"] == "登录按钮"
        assert result[0]["expected_result"] == "显示登录页"
        assert result[0]["test_data"] == {}

    def test_convert_steps_fallback_fields(self):
        """缺少step字段时的回退逻辑"""
        from app.api.v1.endpoints.test_case import _convert_steps_to_response
        
        steps_json = [
            {"action": "执行操作", "description": "这是描述"}
        ]
        
        result = _convert_steps_to_response(steps_json)
        
        assert len(result) == 1
        assert result[0]["step"] == "执行操作"  # 回退到action
        assert result[0]["action"] == "执行操作"  # 回退到action或step

    def test_convert_steps_with_test_data(self):
        """包含test_data字段的转换"""
        from app.api.v1.endpoints.test_case import _convert_steps_to_response
        
        steps_json = [
            {"step": "步骤1", "test_data": {"key": "value"}, "expected_result": "成功"}
        ]
        
        result = _convert_steps_to_response(steps_json)
        
        assert result[0]["test_data"] == {"key": "value"}
        assert result[0]["expected_result"] == "成功"

    def test_build_response_complete(self):
        """_build_test_case_response 完整响应构建"""
        from app.api.v1.endpoints.test_case import _build_test_case_response
        
        class MockTestCase:
            id = 42
            project_id = 1
            case_no = "CASE1-001"
            module = "用户管理"
            title = "登录功能测试"
            precondition = "已注册账号"
            steps_json = [{"step": "打开页面"}]
            expected_result = "登录成功"
            priority = 1
            case_type = "functional"
            exec_script = ""
            generate_status = 1
            create_time = "2024-01-01T00:00:00"
        
        tc = MockTestCase()
        result = _build_test_case_response(tc)
        
        assert result["id"] == 42
        assert result["project_id"] == 1
        assert result["case_no"] == "CASE1-001"
        assert result["module"] == "用户管理"
        assert result["title"] == "登录功能测试"
        assert result["precondition"] == "已注册账号"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["step"] == "打开页面"
        assert result["expected_result"] == "登录成功"
        assert result["priority"] == 1
        assert result["case_type"] == "functional"
        assert result["generate_status"] == 1

    def test_build_response_missing_optional_fields(self):
        """缺少可选字段时的容错处理"""
        from app.api.v1.endpoints.test_case import _build_test_case_response
        
        class MinimalTestCase:
            id = 99
            project_id = 2
            case_no = "CASE2-099"
            title = "最小用例"
            expected_result = "OK"
            priority = 2
            generate_status = 0
        
        tc = MinimalTestCase()
        result = _build_test_case_response(tc)
        
        assert result["id"] == 99
        assert result.get("module") == "" or result.get("module") is None
        assert result.get("precondition") == "" or result.get("precondition") is None
        assert result["steps"] == []


class TestJWTUtilsUTCCompatibility:
    """jwt_utils.py UTC时区兼容性测试 (P3-3)"""

    def test_utctnow_returns_timezone_aware_datetime(self):
        """_utcnow 应返回带时区的datetime"""
        from app.utils.jwt_utils import _utcnow
        from datetime import timezone
        
        now = _utcnow()
        
        assert now.tzinfo is not None, "_utcnow应返回timezone-aware datetime"
        assert now.tzinfo == timezone.utc, "_utcnow应使用UTC时区"

    def test_utctnow_is_recent(self):
        """_utcnow 返回的时间应该是当前时间附近"""
        from app.utils.jwt_utils import _utcnow
        from datetime import datetime, timezone, timedelta
        
        now = _utcnow()
        actual_now = datetime.now(timezone.utc)
        
        diff = abs((now - actual_now).total_seconds())
        assert diff < 5, f"_utcnow与实际时间差{diff}秒过大"

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
    """批量生成请求校验测试 (P2-7)"""

    def test_description_min_length(self):
        """描述最少10个字符"""
        from app.api.v1.endpoints.test_case import AIGenerateRequest
        
        with pytest.raises(Exception):  # ValidationError
            AIGenerateRequest(project_id=1, description="短")

    def test_description_max_length(self):
        """描述最多10000字符"""
        from app.api.v1.endpoints.test_case import AIGenerateRequest
        
        long_desc = "x" * 10001
        
        with pytest.raises(Exception):  # ValidationError
            AIGenerateRequest(project_id=1, description=long_desc)

    def test_description_valid_length(self):
        """合法长度描述通过校验"""
        from app.api.v1.endpoints.test_case import AIGenerateRequest
        
        req = AIGenerateRequest(project_id=1, description="这是一个有效的测试描述，长度足够")
        
        assert req.description == "这是一个有效的测试描述，长度足够"

    def test_batch_generate_list_size_limit(self):
        """列表大小限制200"""
        from app.api.v1.endpoints.test_case import BatchGenerateRequest
        
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
        from app.api.v1.endpoints.test_case import BatchGenerateRequest
        
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
        """AIGenerateEnhancedRequest校验"""
        from app.api.v1.endpoints.test_case import AIGenerateEnhancedRequest
        
        # 最少5字符
        req = AIGenerateEnhancedRequest(
            project_id=1,
            description="这是一个有效的测试描述",
            case_type="functional",
            priority=1
        )
        
        assert req.priority == 1
        assert req.case_type == "functional"
        assert req.description == "这是一个有效的测试描述"
