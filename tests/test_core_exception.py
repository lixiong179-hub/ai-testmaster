import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException, FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

from app.core.exception import (
    RESPONSE_CODE,
    BaseAPIException,
    DatabaseException,
    FileException,
    PermissionException,
    ParameterException,
    APIException,
    NotFoundException,
    UnauthorizedException,
    AuthenticationError,
    DuplicateException,
    create_response,
    create_error_response,
    base_exception_handler,
    http_exception_handler,
    database_exception_handler,
    validation_exception_handler,
    request_validation_exception_handler,
    general_exception_handler,
    register_exception_handlers,
)


class TestResponseCode:
    def test_success_code(self):
        assert RESPONSE_CODE["SUCCESS"] == 200

    def test_client_error_codes(self):
        assert RESPONSE_CODE["VALIDATION_ERROR"] == 400
        assert RESPONSE_CODE["PARAMETER_ERROR"] == 400
        assert RESPONSE_CODE["NOT_FOUND"] == 404
        assert RESPONSE_CODE["PERMISSION_DENIED"] == 403
        assert RESPONSE_CODE["FILE_ERROR"] == 400
        assert RESPONSE_CODE["DUPLICATE_ERROR"] == 409

    def test_server_error_codes(self):
        assert RESPONSE_CODE["DATABASE_ERROR"] == 500
        assert RESPONSE_CODE["API_ERROR"] == 500
        assert RESPONSE_CODE["SERVER_ERROR"] == 500

    def test_unauthorized_codes(self):
        assert RESPONSE_CODE["UNAUTHORIZED"] == 401
        assert RESPONSE_CODE["TOKEN_EXPIRED"] == 401


class TestExceptionClasses:
    def test_base_api_exception(self):
        exc = BaseAPIException("test error", code=400, details={"key": "val"})
        assert exc.msg == "test error"
        assert exc.code == 400
        assert exc.details == {"key": "val"}
        assert str(exc) == "test error"

    def test_base_api_exception_defaults(self):
        exc = BaseAPIException("error")
        assert exc.code == 500
        assert exc.details is None

    def test_database_exception(self):
        exc = DatabaseException()
        assert exc.msg == "数据库操作失�?
        assert exc.code == 500

    def test_database_exception_custom_msg(self):
        exc = DatabaseException("自定义数据库错误", details="extra")
        assert exc.msg == "自定义数据库错误"
        assert exc.details == "extra"

    def test_file_exception(self):
        exc = FileException()
        assert exc.msg == "文件操作失败"
        assert exc.code == 400

    def test_permission_exception(self):
        exc = PermissionException()
        assert exc.msg == "权限不足"
        assert exc.code == 403

    def test_parameter_exception(self):
        exc = ParameterException()
        assert exc.msg == "参数错误"
        assert exc.code == 400

    def test_api_exception(self):
        exc = APIException()
        assert exc.msg == "API调用失败"
        assert exc.code == 500

    def test_not_found_exception(self):
        exc = NotFoundException()
        assert exc.msg == "资源不存�?
        assert exc.code == 404

    def test_unauthorized_exception(self):
        exc = UnauthorizedException()
        assert exc.msg == "未授�?
        assert exc.code == 401

    def test_authentication_error(self):
        exc = AuthenticationError()
        assert exc.msg == "认证失败"
        assert exc.code == 401
        assert isinstance(exc, UnauthorizedException)

    def test_duplicate_exception(self):
        exc = DuplicateException()
        assert exc.msg == "资源已存�?
        assert exc.code == 409


class TestCreateResponse:
    def test_normal_response(self):
        data = {"id": 1, "name": "test"}
        result = create_response(data=data, msg="success", code=200)
        assert result["code"] == 200
        assert result["msg"] == "success"
        assert result["message"] == "success"
        assert result["data"] == data
        assert isinstance(result["timestamp"], int)

    def test_default_params(self):
        result = create_response()
        assert result["code"] == 200
        assert result["msg"] == "success"
        assert result["data"] == {}

    def test_none_data_becomes_empty_dict(self):
        result = create_response(data=None)
        assert result["data"] == {}

    def test_empty_string_msg(self):
        result = create_response(msg="")
        assert result["msg"] == ""
        assert result["message"] == ""

    def test_custom_code(self):
        result = create_response(code=201)
        assert result["code"] == 201

    def test_timestamp_is_recent(self):
        before = int(datetime.now().timestamp())
        result = create_response()
        after = int(datetime.now().timestamp())
        assert before <= result["timestamp"] <= after


class TestCreateErrorResponse:
    def test_normal_error_response(self):
        result = create_error_response(msg="error", code=500)
        assert result["code"] == 500
        assert result["msg"] == "error"
        assert result["message"] == "error"
        assert result["data"] == {}

    def test_error_with_data(self):
        result = create_error_response(msg="bad", code=400, data={"field": "name"})
        assert result["data"] == {"field": "name"}

    def test_error_none_data_becomes_empty_dict(self):
        result = create_error_response(msg="err", data=None)
        assert result["data"] == {}

    def test_error_empty_msg(self):
        result = create_error_response(msg="")
        assert result["msg"] == ""

    def test_error_default_code(self):
        result = create_error_response(msg="err")
        assert result["code"] == 500


class TestBaseExceptionHandler:
    @pytest.mark.asyncio
    async def test_base_exception_handler(self):
        request = MagicMock()
        request.url.path = "/api/test"
        exc = BaseAPIException("api error", code=400, details={"info": "extra"})

        response = await base_exception_handler(request, exc)
        assert response.status_code == 400
        body = response.body.decode() if isinstance(response.body, bytes) else str(response.body)
        import json
        data = json.loads(body)
        assert data["code"] == 400
        assert data["msg"] == "api error"


class TestHttpExceptionHandler:
    @pytest.mark.asyncio
    async def test_http_exception_handler(self):
        request = MagicMock()
        request.url.path = "/api/test"
        exc = HTTPException(status_code=404, detail="Not found")

        response = await http_exception_handler(request, exc)
        assert response.status_code == 404


class TestDatabaseExceptionHandler:
    @pytest.mark.asyncio
    async def test_generic_sqlalchemy_error(self):
        request = MagicMock()
        request.url.path = "/api/test"
        exc = SQLAlchemyError("db error")

        response = await database_exception_handler(request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_integrity_error(self):
        request = MagicMock()
        request.url.path = "/api/test"
        exc = IntegrityError("stmt", "params", Exception("orig"))

        response = await database_exception_handler(request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_operational_error(self):
        request = MagicMock()
        request.url.path = "/api/test"
        exc = OperationalError("stmt", "params", Exception("orig"))

        response = await database_exception_handler(request, exc)
        assert response.status_code == 500


class TestValidationExceptionHandler:
    @pytest.mark.asyncio
    async def test_validation_error_handler(self):
        from pydantic import BaseModel, field_validator

        class TestModel(BaseModel):
            name: str

            @field_validator("name")
            @classmethod
            def name_must_not_be_empty(cls, v):
                if not v:
                    raise ValueError("name cannot be empty")
                return v

        try:
            TestModel(name="")
        except ValidationError as exc:
            request = MagicMock()
            request.url.path = "/api/test"
            response = await validation_exception_handler(request, exc)
            assert response.status_code == 400


class TestRequestValidationExceptionHandler:
    @pytest.mark.asyncio
    async def test_request_validation_error_handler(self):
        request = MagicMock()
        request.url.path = "/api/test"
        request.query_params = {}

        errors = [
            {
                "loc": ("query", "page"),
                "msg": "field required",
                "type": "value_error.missing",
            }
        ]
        exc = RequestValidationError(errors=errors)

        response = await request_validation_exception_handler(request, exc)
        assert response.status_code == 400


class TestGeneralExceptionHandler:
    @pytest.mark.asyncio
    async def test_general_exception_handler(self):
        request = MagicMock()
        request.url.path = "/api/test"
        exc = RuntimeError("unexpected error")

        response = await general_exception_handler(request, exc)
        assert response.status_code == 500


class TestRegisterExceptionHandlers:
    def test_register_exception_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)

        routes = [route.path for route in app.routes]
        assert len(routes) > 0
