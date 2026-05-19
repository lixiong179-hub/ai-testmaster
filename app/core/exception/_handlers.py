from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError
import logging

from app.core.exception._base import (
    BaseAPIException,
    RESPONSE_CODE,
    create_error_response,
)

logger = logging.getLogger(__name__)


async def base_exception_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    """
    处理自定义API异常（BaseAPIException及其子类）

    捕获所有继承自BaseAPIException的自定义异常，使用异常对象中
    携带的msg、code、details构建统一错误响应。

    处理逻辑：
        1. 记录WARNING级别日志（自定义异常属于预期的业务异常，非系统故障）
        2. 使用exc.code作为HTTP响应状态码和业务状态码
        3. 将exc.details作为data字段传递给前端

    Args:
        request: FastAPI请求对象，用于获取请求路径等上下文信息
        exc: 捕获到的自定义异常实例

    Returns:
        JSONResponse: 统一格式的错误响应，HTTP状态码与异常code一致

    注意：
        - 日志级别为WARNING，因为自定义异常是业务层面的预期错误
        - exc.details会作为data字段传递，可能包含敏感信息，生产环境需评估
    """
    logger.warning(f"API异常: {exc.msg}, 路径: {request.url.path}")
    return JSONResponse(
        status_code=exc.code,
        content=create_error_response(exc.msg, exc.code, exc.details)
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    处理FastAPI框架的HTTPException

    捕获FastAPI内部抛出的HTTP异常（如路由不匹配、方法不允许等），
    将其转换为系统统一响应格式。

    处理逻辑：
        1. 记录WARNING级别日志
        2. 使用exc.status_code作为HTTP响应状态码
        3. 使用exc.detail作为错误消息

    Args:
        request: FastAPI请求对象
        exc: FastAPI的HTTPException实例

    Returns:
        JSONResponse: 统一格式的错误响应

    注意：
        - HTTPException是FastAPI框架层面的异常，与自定义APIException不同
        - 此处理器确保框架异常也遵循统一响应格式
    """
    logger.warning(f"HTTP异常: {exc.detail}, 路径: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.detail, exc.status_code)
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    处理SQLAlchemy数据库异常

    捕获所有SQLAlchemy抛出的数据库异常，根据异常子类型
    返回更精确的错误消息，避免暴露底层数据库细节。

    处理逻辑：
        1. 记录ERROR级别日志（数据库异常属于服务端故障）
        2. 根据异常类型细分错误消息：
           - IntegrityError: 违反完整性约束（唯一键冲突、外键约束等）
           - OperationalError: 数据库连接/操作失败（连接超时、表不存在等）
           - 其他SQLAlchemyError: 通用数据库错误
        3. 统一返回500状态码，不暴露原始SQL或数据库结构信息

    Args:
        request: FastAPI请求对象
        exc: SQLAlchemy异常实例

    Returns:
        JSONResponse: 统一格式的错误响应，HTTP状态码500

    注意：
        - 日志级别为ERROR，数据库异常需要运维关注
        - 错误消息经过脱敏处理，不包含原始SQL语句、表名等敏感信息
        - IntegrityError通常对应业务层的DuplicateException，
          但此处处理的是SQLAlchemy层面未被业务捕获的异常
    """
    logger.error(f"数据库异常: {str(exc)}, 路径: {request.url.path}")
    error_msg = "数据库操作失败，请稍后重试"

    if isinstance(exc, IntegrityError):
        error_msg = "数据已存在或违反完整性约束"
    elif isinstance(exc, OperationalError):
        error_msg = "数据库连接失败，请检查数据库服务"

    return JSONResponse(
        status_code=RESPONSE_CODE["DATABASE_ERROR"],
        content=create_error_response(error_msg, RESPONSE_CODE["DATABASE_ERROR"])
    )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    处理Pydantic模型验证异常

    捕获Pydantic ValidationError，通常在请求体JSON反序列化后
    模型字段校验失败时触发。将验证错误详情提取为结构化列表返回前端。

    处理逻辑：
        1. 记录WARNING级别日志（参数错误属于客户端问题）
        2. 遍历exc.errors()提取每个验证错误的字段路径、消息、类型
        3. 将错误列表作为data字段的errors数组返回

    Args:
        request: FastAPI请求对象
        exc: Pydantic的ValidationError实例

    Returns:
        JSONResponse: 统一格式的错误响应，HTTP状态码400，
                      data中包含errors数组，结构如下：
                      {"errors": [{"field": "body.email", "message": "...", "type": "value_error.email"}]}

    注意：
        - 此处理器处理的是Pydantic模型层面的验证异常
        - 与request_validation_exception_handler的区别：
          本处理器处理请求体(Body)中的Pydantic模型验证，
          后者处理Query/Path/Header等请求参数验证
        - field路径使用"."连接层级，如"body.email"、"body.address.city"
    """
    logger.warning(f"参数验证失败: {str(exc)}, 路径: {request.url.path}")

    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    return JSONResponse(
        status_code=RESPONSE_CODE["VALIDATION_ERROR"],
        content=create_error_response(
            "参数验证失败",
            RESPONSE_CODE["VALIDATION_ERROR"],
            {"errors": errors}
        )
    )


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    处理FastAPI请求验证异常（Query/Path/Header参数验证失败）

    捕获FastAPI的RequestValidationError，当请求的Query参数、Path参数、
    Header参数等不符合路由定义的类型/约束时触发。处理逻辑与
    validation_exception_handler类似，但额外记录了查询参数信息。

    处理逻辑：
        1. 记录WARNING级别日志，包含查询参数信息（便于排查参数问题）
        2. 遍历exc.errors()提取验证错误详情
        3. 将错误列表作为data字段的errors数组返回

    Args:
        request: FastAPI请求对象
        exc: FastAPI的RequestValidationError实例

    Returns:
        JSONResponse: 统一格式的错误响应，HTTP状态码400，
                      data中包含errors数组

    注意：
        - 此处理器处理的是FastAPI路由层面的参数验证异常
        - 与validation_exception_handler的区别：
          本处理器处理Query/Path/Header参数验证，
          后者处理请求体(Body)中的Pydantic模型验证
        - 日志中额外记录了query_params，便于排查URL参数问题
        - field路径示例："query.page"（Query参数）、"path.id"（Path参数）
    """
    logger.warning(f"请求参数验证失败: {str(exc)}, 路径: {request.url.path}, 查询参数: {request.query_params}")

    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    return JSONResponse(
        status_code=RESPONSE_CODE["VALIDATION_ERROR"],
        content=create_error_response(
            "参数验证失败",
            RESPONSE_CODE["VALIDATION_ERROR"],
            {"errors": errors}
        )
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    处理所有未捕获的异常（兜底处理器）

    捕获所有未被其他异常处理器处理的异常，作为最后的防线确保
    任何未预期的异常都不会导致返回非标准格式的响应。

    处理逻辑：
        1. 记录ERROR级别日志，包含完整异常堆栈（exc_info=True）
        2. 返回通用的"服务器内部错误"消息，不暴露异常详情
        3. 统一返回500状态码

    Args:
        request: FastAPI请求对象
        exc: 未被其他处理器捕获的异常实例

    Returns:
        JSONResponse: 统一格式的错误响应，HTTP状态码500

    注意：
        - 日志级别为ERROR，未捕获异常属于系统故障，需要紧急处理
        - exc_info=True确保日志中包含完整的异常堆栈信息
        - 不向客户端暴露原始异常信息，防止泄露内部实现细节
        - 此处理器必须最后注册，否则会拦截其他更具体的异常处理器
    """
    logger.error(f"服务器内部错误: {str(exc)}, 路径: {request.url.path}", exc_info=True)

    return JSONResponse(
        status_code=RESPONSE_CODE["SERVER_ERROR"],
        content=create_error_response("服务器内部错误", RESPONSE_CODE["SERVER_ERROR"])
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册所有异常处理器到FastAPI应用

    将上述定义的所有异常处理器按优先级顺序注册到FastAPI应用实例。
    FastAPI的异常处理遵循"最具体优先"原则：当异常匹配多个处理器时，
    使用最具体的那个。

    注册顺序说明（从最具体到最通用）：
        1. BaseAPIException - 自定义业务异常（最具体，优先级最高）
        2. HTTPException - FastAPI框架HTTP异常
        3. SQLAlchemyError - 数据库异常
        4. ValidationError - Pydantic模型验证异常
        5. RequestValidationError - FastAPI请求参数验证异常
        6. Exception - 通用异常兜底（最通用，优先级最低，必须最后注册）

    Args:
        app: FastAPI应用实例，通常在main.py中创建

    注意：
        - Exception处理器必须最后注册，因为它是所有异常的父类，
          先注册会导致所有异常都被其拦截
        - 注册后，所有异常都会被对应的处理器捕获并返回统一格式
        - 此函数应在应用启动时调用，且应在路由注册之前调用
    """
    app.add_exception_handler(BaseAPIException, base_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("全局异常处理器注册完成")
