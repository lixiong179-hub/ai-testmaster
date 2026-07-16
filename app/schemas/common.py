from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应信封模型，对应 create_response() 返回结构。

    所有API接口的成功响应都应符合此结构，包含 code、msg、message、data、timestamp
    五个标准字段。端点通过 response_model=ApiResponse 声明后，OpenAPI 文档将
    正确展示响应结构。

    timestamp 为可选字段（默认0），兼容部分直接返回 dict 而非 create_response() 的端点。
    """

    code: int = Field(200, description="业务状态码，200表示成功")
    msg: str = Field("success", description="响应消息")
    message: str = Field("success", description="msg的兼容别名")
    data: T = Field(default_factory=dict, description="响应数据")
    timestamp: int = Field(default=0, description="秒级Unix时间戳，0表示未设置")
