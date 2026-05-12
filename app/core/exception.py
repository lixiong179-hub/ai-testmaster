"""
全局异常处理模块 - 统一返回格式

提供全局异常捕获、分类处理与统一响应格式输出，确保所有API接口
无论成功或失败，都返回结构一致的JSON响应，便于前端统一处理。

统一返回格式结构设计：
    {
        "code": int,       # 业务状态码（非HTTP状态码），200表示成功，其他表示各类错误
        "msg": str,        # 错误/成功消息（主要字段，推荐使用）
        "message": str,    # msg的兼容性别名字段，部分客户端/测试用例使用此字段名
        "data": dict,      # 响应数据，成功时为业务数据，失败时为错误详情或空字典
        "timestamp": int   # Unix时间戳（秒级），用于请求追踪和问题排查
    }

    设计说明：
        - code与HTTP状态码对齐但不完全等同，HTTP状态码用于传输层，
          code用于业务层细粒度区分
        - msg和message同时存在是为了兼容性：部分前端/测试框架使用message字段，
          新代码应统一使用msg字段
        - timestamp用于日志关联，便于通过时间戳定位请求链路

核心组件概览：
    - RESPONSE_CODE: 统一响应码常量字典，定义所有业务状态码
    - 自定义异常类层次结构:
        BaseAPIException (基础异常，所有自定义异常的父类)
        ├── DatabaseException    (数据库操作异常，500)
        ├── FileException        (文件操作异常，400)
        ├── PermissionException  (权限不足异常，403)
        ├── ParameterException   (参数错误异常，400)
        ├── APIException         (API调用异常，500)
        ├── NotFoundException    (资源不存在异常，404)
        ├── UnauthorizedException(未授权异常，401)
        │   └── AuthenticationError(认证失败异常，继承401，兼容JWT工具)
        └── DuplicateException   (资源重复异常，409)
    - create_response()/create_error_response(): 统一返回格式构建函数
    - 异常处理器: 针对不同异常类型注册的FastAPI异常处理函数
    - register_exception_handlers(): 将所有异常处理器注册到FastAPI应用

依赖关系：
    - FastAPI: HTTPException、Request、RequestValidationError
    - SQLAlchemy: SQLAlchemyError、IntegrityError、OperationalError
    - Pydantic: ValidationError
    - Python标准库: logging、datetime

使用方式：
    from app.core.exception import register_exception_handlers
    app = FastAPI()
    register_exception_handlers(app)
"""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError
from typing import Dict, Any
from datetime import datetime
import logging

# 配置模块级日志记录器，用于异常处理过程中的日志输出
# 日志级别策略：客户端错误用warning，服务端错误用error
logger = logging.getLogger(__name__)

# 统一响应码字典
# 定义系统中所有业务状态码，与HTTP状态码对齐但不完全等同
# 分类：成功(200)、客户端错误(400/401/403/404/409)、服务端错误(500)
RESPONSE_CODE = {
    # 成功 - 请求处理成功
    "SUCCESS": 200,

    # 客户端错误 - 由请求方导致的错误
    "VALIDATION_ERROR": 400,    # 数据验证失败（Pydantic模型校验不通过）
    "PARAMETER_ERROR": 400,     # 参数错误（业务参数不符合要求）
    "NOT_FOUND": 404,           # 资源不存在（请求的目标资源未找到）
    "PERMISSION_DENIED": 403,   # 权限不足（已认证但无操作权限）
    "FILE_ERROR": 400,          # 文件操作失败（文件上传/下载/处理异常）
    "DUPLICATE_ERROR": 409,     # 资源重复（创建已存在的唯一资源）

    # 服务端错误 - 由服务端内部问题导致的错误
    "DATABASE_ERROR": 500,      # 数据库操作失败（SQL执行异常）
    "API_ERROR": 500,           # API调用失败（外部/内部API调用异常）
    "SERVER_ERROR": 500,        # 服务器内部错误（未预期的运行时异常）

    # 未授权 - 认证相关错误
    "UNAUTHORIZED": 401,        # 未授权（未提供有效的认证凭证）
    "TOKEN_EXPIRED": 401,       # Token过期（认证凭证已失效，需重新登录）
}


# ==================== 自定义异常类 ====================

class BaseAPIException(Exception):
    """
    基础API异常类 - 所有自定义业务异常的父类

    职责：定义异常的通用属性（msg、code、details），为异常处理器
    提供统一的异常信息访问接口。

    设计意图：
        - 通过继承体系实现异常的分类处理，不同类型的异常自动携带
          对应的HTTP状态码，异常处理器无需手动映射
        - details字段支持传递结构化的错误详情（如验证错误列表），
          便于前端精确展示错误信息

    关键属性：
        msg (str): 错误消息，面向开发者的可读描述
        code (int): 业务状态码，对应RESPONSE_CODE中的值
        details (Any): 错误详情，可为任意类型（字典、列表等），
                       用于传递结构化的错误信息

    使用场景：
        - 通常不直接使用，而是通过子类抛出特定类型的异常
        - 如需自定义异常类型，继承此类并设置默认code即可
    """

    def __init__(self, msg: str, code: int = 500, details: Any = None):
        """
        初始化基础API异常

        Args:
            msg: 错误消息，描述异常原因
            code: 业务状态码，默认500（服务器内部错误）
            details: 错误详情，可选的结构化错误信息
        """
        self.msg = msg
        self.code = code
        self.details = details
        # 调用父类Exception的__init__，确保异常的str()输出正常
        super().__init__(msg)


class DatabaseException(BaseAPIException):
    """
    数据库操作异常

    当数据库操作（增删改查）失败时抛出，包括SQL执行错误、
    连接异常、约束违反等场景。

    设计意图：
        - 默认code为500（DATABASE_ERROR），因为数据库异常通常是服务端问题
        - 与SQLAlchemy的异常体系配合使用，在database_exception_handler中
          对IntegrityError和OperationalError做细粒度处理

    使用场景：
        - 数据库连接失败
        - SQL语法错误
        - 事务执行异常
        - 其他未预期的数据库操作失败
    """

    def __init__(self, msg: str = "数据库操作失败", details: Any = None):
        """
        初始化数据库异常

        Args:
            msg: 错误消息，默认"数据库操作失败"
            details: 错误详情，如原始SQL异常信息
        """
        super().__init__(msg, RESPONSE_CODE["DATABASE_ERROR"], details)


class FileException(BaseAPIException):
    """
    文件操作异常

    当文件上传、下载、读取、写入等操作失败时抛出。

    设计意图：
        - code为400（FILE_ERROR），文件操作失败通常由客户端
          提供了无效的文件（格式错误、大小超限等）导致

    使用场景：
        - 文件上传格式不支持
        - 文件大小超过限制
        - 文件读取/写入权限不足
        - 文件存储服务不可用
    """

    def __init__(self, msg: str = "文件操作失败", details: Any = None):
        """
        初始化文件操作异常

        Args:
            msg: 错误消息，默认"文件操作失败"
            details: 错误详情，如文件名、允许的格式列表等
        """
        super().__init__(msg, RESPONSE_CODE["FILE_ERROR"], details)


class PermissionException(BaseAPIException):
    """
    权限不足异常

    当已认证用户尝试执行其无权限的操作时抛出。
    与UnauthorizedException的区别：PermissionException表示用户已登录但权限不够，
    UnauthorizedException表示用户未登录或凭证无效。

    设计意图：
        - code为403（PERMISSION_DENIED），符合HTTP语义：
          403表示服务器理解请求但拒绝执行

    使用场景：
        - 普通用户访问管理员接口
        - 用户操作非自己拥有的资源
        - 角色权限不足
    """

    def __init__(self, msg: str = "权限不足", details: Any = None):
        """
        初始化权限异常

        Args:
            msg: 错误消息，默认"权限不足"
            details: 错误详情，如需要的权限列表
        """
        super().__init__(msg, RESPONSE_CODE["PERMISSION_DENIED"], details)


class ParameterException(BaseAPIException):
    """
    参数错误异常

    当业务参数不符合要求时抛出。与ValidationError的区别：
    ParameterException是业务层主动抛出的参数校验异常，
    ValidationError是Pydantic模型自动触发的数据校验异常。

    设计意图：
        - code为400（PARAMETER_ERROR），参数错误属于客户端问题

    使用场景：
        - 业务参数逻辑校验失败（如结束时间早于开始时间）
        - 必填参数为空
        - 参数值不在允许范围内
        - 参数组合不合法
    """

    def __init__(self, msg: str = "参数错误", details: Any = None):
        """
        初始化参数异常

        Args:
            msg: 错误消息，默认"参数错误"
            details: 错误详情，如参数名、期望值、实际值等
        """
        super().__init__(msg, RESPONSE_CODE["PARAMETER_ERROR"], details)


class APIException(BaseAPIException):
    """
    API调用异常

    当调用外部API或内部服务间API失败时抛出。

    设计意图：
        - code为500（API_ERROR），API调用失败通常是服务端问题
        - 与HTTPException区分：HTTPException是FastAPI框架层面的异常，
          APIException是业务层面的API调用异常

    使用场景：
        - 外部第三方API调用超时或返回错误
        - 内部微服务间调用失败
        - API响应格式不符合预期
    """

    def __init__(self, msg: str = "API调用失败", details: Any = None):
        """
        初始化API调用异常

        Args:
            msg: 错误消息，默认"API调用失败"
            details: 错误详情，如API名称、响应状态码、响应内容等
        """
        super().__init__(msg, RESPONSE_CODE["API_ERROR"], details)


class NotFoundException(BaseAPIException):
    """
    资源不存在异常

    当请求的目标资源在数据库或文件系统中不存在时抛出。

    设计意图：
        - code为404（NOT_FOUND），符合HTTP语义：
          404表示请求的资源未找到

    使用场景：
        - 根据ID查询记录返回None
        - 请求的文件路径不存在
        - 请求的API路由不存在（由FastAPI自动处理）
    """

    def __init__(self, msg: str = "资源不存在", details: Any = None):
        """
        初始化资源不存在异常

        Args:
            msg: 错误消息，默认"资源不存在"
            details: 错误详情，如资源类型、查询条件等
        """
        super().__init__(msg, RESPONSE_CODE["NOT_FOUND"], details)


class UnauthorizedException(BaseAPIException):
    """
    未授权异常

    当用户未提供有效的认证凭证（如未登录、Token无效）时抛出。
    与PermissionException的区别：UnauthorizedException表示认证失败（"你是谁"），
    PermissionException表示授权失败（"你能做什么"）。

    设计意图：
        - code为401（UNAUTHORIZED），符合HTTP语义：
          401表示请求需要用户认证

    使用场景：
        - 未携带Token访问受保护接口
        - Token格式无效
        - Token已过期
    """

    def __init__(self, msg: str = "未授权", details: Any = None):
        """
        初始化未授权异常

        Args:
            msg: 错误消息，默认"未授权"
            details: 错误详情，如Token过期时间等
        """
        super().__init__(msg, RESPONSE_CODE["UNAUTHORIZED"], details)


class AuthenticationError(UnauthorizedException):
    """
    认证失败异常（兼容测试与JWT工具）

    继承自UnauthorizedException，保持code=401的语义一致性。
    存在的目的是兼容项目中已有的测试用例和JWT工具类，
    这些代码可能直接捕获AuthenticationError而非UnauthorizedException。

    设计意图：
        - 作为UnauthorizedException的子类，确保异常处理器
          通过BaseAPIException匹配时能正确处理
        - 不覆盖code，继承父类的401状态码
        - 默认消息从"未授权"改为"认证失败"，语义更精确

    使用场景：
        - JWT Token验证失败
        - 用户名/密码错误
        - 测试用例中的认证失败断言
    """

    def __init__(self, msg: str = "认证失败", details: Any = None):
        """
        初始化认证失败异常

        Args:
            msg: 错误消息，默认"认证失败"
            details: 错误详情
        """
        # 不传code参数，继承父类UnauthorizedException的401状态码
        super().__init__(msg, details)


class DuplicateException(BaseAPIException):
    """
    资源重复异常

    当尝试创建已存在的唯一资源时抛出，如重复的用户名、邮箱等。

    设计意图：
        - code为409（DUPLICATE_ERROR），符合HTTP语义：
          409 Conflict表示请求与服务器当前状态冲突

    使用场景：
        - 注册时用户名/邮箱已存在
        - 创建重名的唯一资源
        - 重复提交幂等性要求的数据
    """

    def __init__(self, msg: str = "资源已存在", details: Any = None):
        """
        初始化资源重复异常

        Args:
            msg: 错误消息，默认"资源已存在"
            details: 错误详情，如冲突的字段名、已存在的值等
        """
        super().__init__(msg, RESPONSE_CODE["DUPLICATE_ERROR"], details)


# ==================== 统一返回格式函数 ====================

def create_response(
    data: Any = None,
    msg: str = "success",
    code: int = 200
) -> Dict[str, Any]:
    """
    构建统一成功响应格式

    生成符合系统统一规范的成功响应字典，包含code、msg、message、data、timestamp
    五个标准字段。所有API接口的成功响应都应通过此函数构建。

    Args:
        data: 响应数据，可以是字典、列表、基本类型等。为None时自动转为空字典{}。
        msg: 成功消息，默认"success"。
        code: 业务状态码，默认200表示成功。

    Returns:
        统一格式的响应字典，结构如下：
        {
            "code": 200,
            "msg": "success",
            "message": "success",  # msg的兼容性别名
            "data": {...},
            "timestamp": 1713600000
        }

    注意：
        - message字段是msg的兼容性别名，两者值始终相同
        - data为None时自动转为空字典，避免前端收到null
        - timestamp为秒级Unix时间戳，由datetime.now().timestamp()生成
    """
    return {
        "code": code,
        "msg": msg,
        # 兼容性别名：部分客户端和测试用例使用message字段名而非msg
        # 两个值保持一致，新代码应统一使用msg字段
        "message": msg,
        # data为None时转为空字典，避免前端需要额外处理null值
        "data": data or {},
        # 秒级Unix时间戳，用于日志关联和请求追踪
        "timestamp": int(datetime.now().timestamp())
    }


def create_error_response(
    msg: str,
    code: int = 500,
    data: Any = None
) -> Dict[str, Any]:
    """
    构建统一错误响应格式

    生成符合系统统一规范的错误响应字典，结构与create_response一致，
    但参数顺序和默认值针对错误场景优化（msg为必填，code默认500）。

    Args:
        msg: 错误消息，必填，描述错误原因
        code: 错误状态码，默认500（服务器内部错误）
        data: 错误详情数据，可选。用于传递结构化的错误信息，
              如验证错误列表、冲突字段等。为None时自动转为空字典。

    Returns:
        统一格式的错误响应字典，结构如下：
        {
            "code": 500,
            "msg": "服务器内部错误",
            "message": "服务器内部错误",  # msg的兼容性别名
            "data": {},
            "timestamp": 1713600000
        }

    注意：
        - 与create_response的区别：msg为必填参数（错误消息不可省略），
          code默认500而非200，更符合错误场景的语义
        - message字段是msg的兼容性别名，两者值始终相同
    """
    return {
        "code": code,
        "msg": msg,
        # 兼容性别名：与create_response保持一致
        "message": msg,
        "data": data or {},
        "timestamp": int(datetime.now().timestamp())
    }


# ==================== 全局异常处理器 ====================

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
    # 默认错误消息，不暴露数据库细节
    error_msg = "数据库操作失败，请稍后重试"

    # 处理特定数据库错误，提供更精确但安全的错误提示
    if isinstance(exc, IntegrityError):
        # 完整性约束违反：唯一键冲突、外键约束、非空约束等
        error_msg = "数据已存在或违反完整性约束"
    elif isinstance(exc, OperationalError):
        # 操作错误：数据库连接失败、SQL语法错误、表不存在等
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

    # 提取验证错误详情，转为前端友好的结构化格式
    errors = []
    for error in exc.errors():
        errors.append({
            # 字段路径：将loc元组用"."连接，如("body", "email") → "body.email"
            "field": ".".join(str(loc) for loc in error["loc"]),
            # 错误消息：Pydantic生成的可读错误描述
            "message": error["msg"],
            # 错误类型：Pydantic的错误类型标识，如value_error.email、type_error.integer
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
    # 额外记录查询参数，便于排查URL参数拼写、类型等问题
    logger.warning(f"请求参数验证失败: {str(exc)}, 路径: {request.url.path}, 查询参数: {request.query_params}")

    # 提取验证错误详情，格式与validation_exception_handler保持一致
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
    # 记录完整异常堆栈，exc_info=True确保traceback信息被完整记录
    logger.error(f"服务器内部错误: {str(exc)}, 路径: {request.url.path}", exc_info=True)

    return JSONResponse(
        status_code=RESPONSE_CODE["SERVER_ERROR"],
        content=create_error_response("服务器内部错误", RESPONSE_CODE["SERVER_ERROR"])
    )


# ==================== 注册异常处理器 ====================

def register_exception_handlers(app):
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
    # 注册自定义API异常处理器 - 处理所有BaseAPIException及其子类
    # 包括：DatabaseException, FileException, PermissionException,
    # ParameterException, APIException, NotFoundException,
    # UnauthorizedException, AuthenticationError, DuplicateException
    app.add_exception_handler(BaseAPIException, base_exception_handler)

    # 注册HTTP异常处理器 - 处理FastAPI框架抛出的HTTPException
    # 包括：404路由不存在、405方法不允许、422参数类型错误等
    app.add_exception_handler(HTTPException, http_exception_handler)

    # 注册数据库异常处理器 - 处理SQLAlchemy抛出的所有数据库异常
    # 包括：IntegrityError(约束违反)、OperationalError(操作错误)等
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)

    # 注册Pydantic验证异常处理器 - 处理请求体模型的字段验证失败
    # 触发场景：请求体JSON反序列化后，Pydantic模型字段校验不通过
    app.add_exception_handler(ValidationError, validation_exception_handler)

    # 注册FastAPI请求验证异常处理器 - 处理Query/Path/Header参数验证失败
    # 触发场景：URL查询参数、路径参数、请求头参数类型/约束校验不通过
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

    # 注册通用异常处理器（最后注册，作为兜底）
    # 捕获所有未被上述处理器处理的异常，确保不会返回非标准格式响应
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("全局异常处理器注册完成")
