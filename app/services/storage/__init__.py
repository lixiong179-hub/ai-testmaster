"""对象存储抽象层模块。

提供统一的文件存储接口，支持本地磁盘与 S3 兼容存储（MinIO/AWS S3）切换，
为后端服务无状态化提供基础：本地存储仅适用于单机部署，多实例水平扩展时
必须切换至 S3/MinIO 以保证文件在所有实例间共享。

架构决策：
    - 抽象基类 StorageBackend 定义 save/load/delete/exists/url 接口
    - LocalStorage 单机部署默认实现，写入本地磁盘
    - S3Storage 多实例部署实现，兼容 AWS S3 / MinIO（通过 endpoint_url 配置）
    - 工厂函数 get_storage() 根据 settings.STORAGE_BACKEND 返回实现

依赖：
    - boto3（S3 实现）需通过 `pip install boto3` 安装
    - LocalStorage 无外部依赖
"""
from app.services.storage.base import StorageBackend, StorageObject
from app.services.storage.local import LocalStorage
from app.services.storage.s3 import S3Storage
from app.services.storage.factory import get_storage, get_storage_backend, reset_storage_cache

__all__ = [
    "StorageBackend",
    "StorageObject",
    "LocalStorage",
    "S3Storage",
    "get_storage",
    "get_storage_backend",
    "reset_storage_cache",
]
