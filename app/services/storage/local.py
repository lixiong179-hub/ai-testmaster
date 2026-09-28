"""本地磁盘存储实现。

适用场景：单机 Docker Compose 部署、开发环境、单元测试。
不适用场景：多实例水平扩展（须切换至 S3Storage）。

设计说明：
    - 所有同步 IO 通过 asyncio.to_thread 包装，避免阻塞事件循环
    - 路径拼接使用 os.path.join 保证跨平台兼容
    - 自动创建父目录，避免调用方处理目录创建
"""
import asyncio
import os
from pathlib import Path
from typing import Optional

from app.services.storage.base import StorageBackend, StorageObject


class LocalStorage(StorageBackend):
    """本地磁盘存储实现。

    构造函数注入根目录，便于测试时使用临时目录。
    """

    def __init__(self, root_dir: str) -> None:
        if not root_dir:
            raise ValueError("root_dir 不能为空")
        self._root = Path(root_dir).resolve()
        # 确保根目录存在
        self._root.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        """将对象键映射为文件系统绝对路径。

        安全约束：禁止 key 通过 ../ 逃逸根目录。
        """
        if not key:
            raise ValueError("key 不能为空")
        full = (self._root / key).resolve()
        try:
            full.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"key 逃逸根目录: {key}") from exc
        return full

    async def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> StorageObject:
        if data is None:
            raise ValueError("data 不能为 None")
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._write_file, path, data)
        return StorageObject(
            key=key,
            size=len(data),
            content_type=content_type,
            url=None,
        )

    @staticmethod
    def _write_file(path: Path, data: bytes) -> None:
        """同步写入文件（在 to_thread 中执行）。"""
        with open(path, "wb") as f:
            f.write(data)

    async def load(self, key: str) -> bytes:
        path = self._full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"对象不存在: {key}")
        return await asyncio.to_thread(self._read_file, path)

    @staticmethod
    def _read_file(path: Path) -> bytes:
        """同步读取文件（在 to_thread 中执行）。"""
        with open(path, "rb") as f:
            return f.read()

    async def delete(self, key: str) -> bool:
        path = self._full_path(key)
        if not path.exists() or not path.is_file():
            return False
        await asyncio.to_thread(path.unlink)
        return True

    async def exists(self, key: str) -> bool:
        path = self._full_path(key)
        return path.exists() and path.is_file()

    async def url(self, key: str, expires: int = 3600) -> Optional[str]:
        path = self._full_path(key)
        if not path.exists():
            return None
        # 本地存储无 presigned URL 概念，返回 file:// 协议路径（仅供开发调试）
        return path.as_uri()
