from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

RESPONSE_CODE = {
    "SUCCESS": 200,
    "VALIDATION_ERROR": 400,
    "PARAMETER_ERROR": 400,
    "NOT_FOUND": 404,
    "PERMISSION_DENIED": 403,
    "FILE_ERROR": 400,
    "DUPLICATE_ERROR": 409,
    "DATABASE_ERROR": 500,
    "API_ERROR": 500,
    "SERVER_ERROR": 500,
    "UNAUTHORIZED": 401,
    "TOKEN_EXPIRED": 401,
}


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
        super().__init__(msg)


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
            "message": "success",
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
        "message": msg,
        "data": data or {},
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
            "message": "服务器内部错误",
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
        "message": msg,
        "data": data or {},
        "timestamp": int(datetime.now().timestamp())
    }
