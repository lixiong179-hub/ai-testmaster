"""存储后端抽象基类。

定义统一的文件存储契约，所有具体实现（LocalStorage / S3Storage）必须继承并实现抽象方法。
设计为异步接口以匹配 FastAPI 异步端点；底层同步 IO 通过 asyncio.to_thread 包装，
避免阻塞事件循环。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class StorageObject:
    """存储对象元数据。

    业务用途：保存/读取文件后返回，包含访问路径与可选的公共 URL。
    边界场景：local 模式下 url 可能为 None；s3 模式下 url 可能为 presigned URL。
    """
    key: str
    size: int
    content_type: Optional[str] = None
    url: Optional[str] = None


class StorageBackend(ABC):
    """存储后端抽象基类。

    所有方法为协程，子类可使用 asyncio.to_thread 包装同步 IO。
    实现类必须线程安全（多 worker 共享实例）。
    """

    @abstractmethod
    async def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> StorageObject:
        """保存字节流到存储后端。

        参数：
            key: 对象键（如 "uploads/project_1/file.png"）
            data: 字节流
            content_type: MIME 类型（可选）

        返回：StorageObject 元数据

        异常：
            - IOError：写入失败
            - ValueError：key 为空或 data 为空
        """
        raise NotImplementedError

    @abstractmethod
    async def load(self, key: str) -> bytes:
        """读取字节流。

        异常：
            - FileNotFoundError：对象不存在
            - IOError：读取失败
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除对象。返回是否实际删除（不存在返回 False）。"""
        raise NotImplementedError

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """判断对象是否存在。"""
        raise NotImplementedError

    @abstractmethod
    async def url(self, key: str, expires: int = 3600) -> Optional[str]:
        """获取对象访问 URL。

        参数：
            key: 对象键
            expires: URL 有效期（秒），仅对需要签名的后端有效

        返回：
            - LocalStorage：返回 file:// 路径或 None
            - S3Storage：返回 presigned URL
        """
        raise NotImplementedError
