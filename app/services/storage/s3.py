"""S3 兼容存储实现（AWS S3 / MinIO）。

适用场景：多实例水平扩展、生产环境、跨可用区高可用。
依赖：boto3（`pip install boto3`）

设计说明：
    - 通过 endpoint_url 兼容 MinIO 与 AWS S3
    - 所有 boto3 同步调用通过 asyncio.to_thread 包装
    - presigned URL 支持有效期，便于临时共享
    - 客户端在构造时创建，线程安全可共享
"""
import asyncio
import io
from typing import Optional

from app.services.storage.base import StorageBackend, StorageObject


class S3Storage(StorageBackend):
    """S3 兼容存储实现。

    构造函数注入连接参数，便于测试与生产环境隔离。
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        use_ssl: bool = True,
    ) -> None:
        if not all([endpoint_url, access_key, secret_key, bucket]):
            raise ValueError("endpoint_url/access_key/secret_key/bucket 均不能为空")
        self._bucket = bucket
        # 延迟导入 boto3，避免未安装时影响整个模块加载
        import boto3  # noqa: WPS433
        from botocore.client import Config  # noqa: WPS433

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                s3={"addressing_style": "path"},
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3},
            ),
            use_ssl=use_ssl,
        )
        # 确保桶存在（幂等）
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """确保目标桶存在，不存在则创建。"""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    async def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> StorageObject:
        if not key:
            raise ValueError("key 不能为空")
        if data is None:
            raise ValueError("data 不能为 None")
        kwargs = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        await asyncio.to_thread(self._client.put_object, **kwargs)
        return StorageObject(
            key=key,
            size=len(data),
            content_type=content_type,
            url=None,
        )

    async def load(self, key: str) -> bytes:
        if not key:
            raise ValueError("key 不能为空")
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=key
            )
        except Exception as exc:
            # boto3 抛 ClientErrorNoSuchKey 时转为 FileNotFoundError
            from botocore.exceptions import ClientError  # noqa: WPS433
            if isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in (
                "NoSuchKey",
                "404",
            ):
                raise FileNotFoundError(f"对象不存在: {key}") from exc
            raise IOError(f"读取 S3 对象失败: {key}") from exc
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> bool:
        if not key:
            raise ValueError("key 不能为空")
        if not await self.exists(key):
            return False
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key
        )
        return True

    async def exists(self, key: str) -> bool:
        if not key:
            raise ValueError("key 不能为空")
        try:
            await asyncio.to_thread(
                self._client.head_object, Bucket=self._bucket, Key=key
            )
            return True
        except Exception:
            return False

    async def url(self, key: str, expires: int = 3600) -> Optional[str]:
        if not key:
            raise ValueError("key 不能为空")
        if not await self.exists(key):
            return None
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            ClientMethod="get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )
