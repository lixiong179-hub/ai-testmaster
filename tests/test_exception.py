"""异常模块单元测试 - exception classes, response helpers, and handlers"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import InitErrorDetails
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

from app.core.exception import (
    BaseAPIException, DatabaseException, FileException,
    PermissionException, ParameterException, APIException,
    NotFoundException, UnauthorizedException, AuthenticationError,
    DuplicateException, create_response, create_error_response,
    RESPONSE_CODE,
    base_exception_handler, http_exception_handler,
    database_exception_handler, validation_exception_handler,
    request_validation_exception_handler, general_exception_handler,
    register_exception_handlers,
)


class TestBaseAPIException:
    def test_default_code(self):
        exc = BaseAPIException("test error")
        assert exc.code == 500
        assert exc.msg == "test error"
        assert exc.details is None

    def test_custom_code(self):
        exc = BaseAPIException("custom", code=400)
        assert exc.code == 400

    def test_with_details(self):
        exc = BaseAPIException("err", code=400, details={"field": "email"})
        assert exc.details == {"field": "email"}

    def test_str_representation(self):
        exc = BaseAPIException("test error")
        assert str(exc) == "test error"


class TestSubclassExceptions:
    def test_database_exception(self):
        exc = DatabaseException()
        assert exc.code == 500
        assert "数据库" in exc.msg

    def test_database_exception_custom_msg(self):
        exc = DatabaseException("连接超时")
        assert exc.msg == "连接超时"

    def test_file_exception(self):
        exc = FileException()
        assert exc.code == 400

    def test_permission_exception(self):
        exc = PermissionException()
        assert exc.code == 403

    def test_parameter_exception(self):
        exc = ParameterException()
        assert exc.code == 400

    def test_api_exception(self):
        exc = APIException()
        assert exc.code == 500

    def test_not_found_exception(self):
        exc = NotFoundException()
        assert exc.code == 404

    def test_unauthorized_exception(self):
        exc = UnauthorizedException()
        assert exc.code == 401

    def test_authentication_error(self):
        exc = AuthenticationError()
        assert exc.code == 401
        assert "认证" in exc.msg

    def test_authentication_error_custom_msg(self):
        exc = AuthenticationError("Token无效")
        assert exc.msg == "Token无效"

    def test_duplicate_exception(self):
        exc = DuplicateException()
        assert exc.code == 409


class TestCreateResponse:
    def test_success_response(self):
        resp = create_response(data={"id": 1})
        assert resp["code"] == 200
        assert resp["msg"] == "success"
        assert resp["message"] == "success"
        assert resp["data"] == {"id": 1}
        assert "timestamp" in resp

    def test_none_data_becomes_empty_dict(self):
        resp = create_response()
        assert resp["data"] == {}

    def test_custom_msg_and_code(self):
        resp = create_response(data={"x": 1}, msg="created", code=201)
        assert resp["msg"] == "created"
        assert resp["code"] == 201

    def test_msg_and_message_alias(self):
        resp = create_response(msg="hello")
        assert resp["msg"] == resp["message"]


class TestCreateErrorResponse:
    def test_error_response(self):
        resp = create_error_response("something failed")
        assert resp["code"] == 500
        assert resp["msg"] == "something failed"
        assert resp["data"] == {}

    def test_custom_code(self):
        resp = create_error_response("not found", code=404)
        assert resp["code"] == 404

    def test_with_details(self):
        resp = create_error_response("err", data={"field": "x"})
        assert resp["data"] == {"field": "x"}


class TestResponseCode:
    def test_known_codes(self):
        assert RESPONSE_CODE["SUCCESS"] == 200
        assert RESPONSE_CODE["NOT_FOUND"] == 404
        assert RESPONSE_CODE["UNAUTHORIZED"] == 401
        assert RESPONSE_CODE["DATABASE_ERROR"] == 500
        assert RESPONSE_CODE["DUPLICATE_ERROR"] == 409


def _make_request(path="/test/path", query_string=""):
    """创建模拟 Request 对象"""
    request = MagicMock(spec=Request)
    request.url = MagicMock()
    request.url.path = path
    request.query_params = query_string
    return request


class TestBaseExceptionHandler:
    """测试 base_exception_handler — 自定义业务异常处理"""

    @pytest.mark.asyncio
    async def test_base_exception_returns_json(self):
        request = _make_request()
        exc = BaseAPIException("业务错误", code=400)
        response = await base_exception_handler(request, exc)
        assert response.status_code == 400
        body = response.body.decode()
        assert "业务错误" in body

    @pytest.mark.asyncio
    async def test_base_exception_with_details(self):
        request = _make_request()
        exc = BaseAPIException("验证失败", code=400, details={"field": "email"})
        response = await base_exception_handler(request, exc)
        assert response.status_code == 400
        body = response.body.decode()
        assert "email" in body

    @pytest.mark.asyncio
    async def test_base_exception_404(self):
        request = _make_request("/api/users/9999")
        exc = NotFoundException("用户不存在")
        response = await base_exception_handler(request, exc)
        assert response.status_code == 404


class TestHttpExceptionHandler:
    """测试 http_exception_handler — FastAPI HTTPException 处理"""

    @pytest.mark.asyncio
    async def test_http_404(self):
        request = _make_request()
        exc = HTTPException(status_code=404, detail="Not Found")
        response = await http_exception_handler(request, exc)
        assert response.status_code == 404
        body = response.body.decode()
        assert "Not Found" in body

    @pytest.mark.asyncio
    async def test_http_405(self):
        request = _make_request()
        exc = HTTPException(status_code=405, detail="Method Not Allowed")
        response = await http_exception_handler(request, exc)
        assert response.status_code == 405


class TestDatabaseExceptionHandler:
    """测试 database_exception_handler — 数据库异常脱敏处理"""

    @pytest.mark.asyncio
    async def test_integrity_error(self):
        """IntegrityError 应返回脱敏消息，不暴露 SQL 细节"""
        request = _make_request()
        exc = IntegrityError("INSERT INTO users...", "params", None)
        response = await database_exception_handler(request, exc)
        assert response.status_code == 500
        body = response.body.decode()
        assert "完整性约束" in body
        # 关键：不暴露原始 SQL
        assert "INSERT INTO" not in body

    @pytest.mark.asyncio
    async def test_operational_error(self):
        """OperationalError 应返回连接失败提示"""
        request = _make_request()
        exc = OperationalError("Connection refused", "params", None)
        response = await database_exception_handler(request, exc)
        assert response.status_code == 500
        body = response.body.decode()
        assert "连接失败" in body

    @pytest.mark.asyncio
    async def test_generic_sqlalchemy_error(self):
        """通用 SQLAlchemyError 应返回通用消息"""
        request = _make_request()
        exc = SQLAlchemyError("unknown db error")
        response = await database_exception_handler(request, exc)
        assert response.status_code == 500
        body = response.body.decode()
        assert "数据库操作失败" in body


class TestValidationExceptionHandler:
    """测试 validation_exception_handler — Pydantic 验证异常"""

    @pytest.mark.asyncio
    async def test_validation_error_returns_field_details(self):
        request = _make_request()
        # 构造一个模拟的 ValidationError
        error = MagicMock()
        error.errors.return_value = [
            {"loc": ("body", "email"), "msg": "invalid email", "type": "value_error.email"},
        ]
        response = await validation_exception_handler(request, error)
        assert response.status_code == 400
        body = response.body.decode()
        assert "body.email" in body
        assert "invalid email" in body


class TestRequestValidationExceptionHandler:
    """测试 request_validation_exception_handler — Query/Path 参数验证"""

    @pytest.mark.asyncio
    async def test_request_validation_error(self):
        request = _make_request(query_string="page=abc")
        error = MagicMock()
        error.errors.return_value = [
            {"loc": ("query", "page"), "msg": "not a valid integer", "type": "type_error.integer"},
        ]
        response = await request_validation_exception_handler(request, error)
        assert response.status_code == 400
        body = response.body.decode()
        assert "query.page" in body


class TestGeneralExceptionHandler:
    """测试 general_exception_handler — 兜底异常处理"""

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_500(self):
        """未捕获异常应返回 500，不暴露异常详情"""
        request = _make_request()
        exc = RuntimeError("unexpected null pointer")
        response = await general_exception_handler(request, exc)
        assert response.status_code == 500
        body = response.body.decode()
        assert "服务器内部错误" in body
        # 关键安全检查：不向客户端暴露原始异常信息
        assert "null pointer" not in body


class TestRegisterExceptionHandlers:
    """测试 register_exception_handlers 注册逻辑"""

    def test_registers_all_handlers(self):
        app = MagicMock()
        register_exception_handlers(app)
        # 应注册 6 个异常处理器
        assert app.add_exception_handler.call_count == 6

    def test_exception_handler_order(self):
        """验证注册顺序：最具体优先，Exception 最后"""
        app = MagicMock()
        register_exception_handlers(app)
        calls = app.add_exception_handler.call_args_list
        # 最后一个注册的应该是 Exception（兜底）
        last_exc_class = calls[-1][0][0]
        assert last_exc_class is Exception
