"""存储后端工厂函数。

根据 settings.STORAGE_BACKEND 配置返回 LocalStorage 或 S3Storage 实例。
单例缓存避免重复创建连接池。
"""
from functools import lru_cache
from typing import Optional

from app.core.config import settings
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorage
from app.services.storage.s3 import S3Storage


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """获取存储后端单例。

    配置项：
        - STORAGE_BACKEND: "local" 或 "s3"（默认 local）
        - STORAGE_LOCAL_ROOT_DIR: local 模式根目录（默认 settings.UPLOAD_DIR）
        - S3_ENDPOINT_URL: s3 模式 endpoint（兼容 MinIO）
        - S3_ACCESS_KEY: s3 模式 access key
        - S3_SECRET_KEY: s3 模式 secret key
        - S3_BUCKET: s3 模式桶名
        - S3_REGION: s3 模式区域（默认 us-east-1）
        - S3_USE_SSL: s3 模式是否启用 SSL（默认 true）

    返回：StorageBackend 实例

    异常：
        - ValueError：配置项缺失或 backend 类型非法
    """
    backend = (settings.STORAGE_BACKEND or "local").lower()
    if backend == "local":
        root_dir = settings.STORAGE_LOCAL_ROOT_DIR or settings.UPLOAD_DIR
        return LocalStorage(root_dir=root_dir)
    if backend == "s3":
        if not all([
            settings.S3_ENDPOINT_URL,
            settings.S3_ACCESS_KEY,
            settings.S3_SECRET_KEY,
            settings.S3_BUCKET,
        ]):
            raise ValueError(
                "S3 模式需配置 S3_ENDPOINT_URL/S3_ACCESS_KEY/S3_SECRET_KEY/S3_BUCKET"
            )
        return S3Storage(
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            use_ssl=settings.S3_USE_SSL,
        )
    raise ValueError(f"非法 STORAGE_BACKEND: {backend}，可选值: local/s3")


def get_storage_backend() -> str:
    """返回当前存储后端类型字符串，供健康检查与诊断使用。"""
    return (settings.STORAGE_BACKEND or "local").lower()


def reset_storage_cache() -> None:
    """清除单例缓存。

    业务用途：测试场景下切换配置后需重置缓存以生效。
    边界场景：生产环境不应调用。
    """
    get_storage.cache_clear()
