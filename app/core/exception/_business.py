from typing import Any

from app.core.exception._base import BaseAPIException, RESPONSE_CODE


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
