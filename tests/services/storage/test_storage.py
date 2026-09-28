"""存储抽象层单元测试。

覆盖：
    - LocalStorage: save/load/delete/exists/url + 边界场景
    - S3Storage: 真实 MinIO 容器测试（通过 docker-compose 启动）
    - factory: 配置路由 + 单例缓存 + 异常路径

测试数据隔离：每个用例使用唯一 key，互不干扰。
依赖：minio 容器需通过 docker-compose up minio 启动。
"""
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from app.services.storage import (
    LocalStorage,
    S3Storage,
    StorageBackend,
    get_storage,
    get_storage_backend,
    reset_storage_cache,
)
from app.services.storage.base import StorageObject


# ── LocalStorage 测试 ──


class TestLocalStorage:
    """LocalStorage 真实文件系统测试。"""

    @pytest.fixture
    def storage(self, tmp_path: Path) -> LocalStorage:
        """每个用例独立的临时目录。"""
        return LocalStorage(root_dir=str(tmp_path))

    async def test_save_and_load_roundtrip(self, storage: LocalStorage):
        """保存后读取应一致。"""
        key = "project_1/file.txt"
        data = b"hello world"
        obj = await storage.save(key, data, content_type="text/plain")

        assert isinstance(obj, StorageObject)
        assert obj.key == key
        assert obj.size == len(data)
        assert obj.content_type == "text/plain"

        loaded = await storage.load(key)
        assert loaded == data

    async def test_save_creates_parent_dirs(self, storage: LocalStorage):
        """保存时自动创建多级父目录。"""
        key = "deep/nested/path/file.bin"
        await storage.save(key, b"data")
        assert await storage.exists(key) is True

    async def test_load_nonexistent_raises(self, storage: LocalStorage):
        """读取不存在的对象抛 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            await storage.load("not_exists.txt")

    async def test_delete_existing_returns_true(self, storage: LocalStorage):
        """删除已存在对象返回 True。"""
        await storage.save("to_delete.txt", b"data")
        result = await storage.delete("to_delete.txt")
        assert result is True
        assert await storage.exists("to_delete.txt") is False

    async def test_delete_nonexistent_returns_false(self, storage: LocalStorage):
        """删除不存在对象返回 False，不抛异常。"""
        result = await storage.delete("not_exists.txt")
        assert result is False

    async def test_exists_nonexistent_returns_false(self, storage: LocalStorage):
        assert await storage.exists("not_exists.txt") is False

    async def test_url_returns_file_uri(self, storage: LocalStorage):
        """local 模式 url 返回 file:// 路径。"""
        await storage.save("file.txt", b"data")
        url = await storage.url("file.txt")
        assert url is not None
        assert url.startswith("file://")

    async def test_url_nonexistent_returns_none(self, storage: LocalStorage):
        assert await storage.url("not_exists.txt") is None

    async def test_empty_key_raises_value_error(self, storage: LocalStorage):
        with pytest.raises(ValueError, match="key 不能为空"):
            await storage.save("", b"data")
        with pytest.raises(ValueError, match="key 不能为空"):
            await storage.load("")
        with pytest.raises(ValueError, match="key 不能为空"):
            await storage.delete("")
        with pytest.raises(ValueError, match="key 不能为空"):
            await storage.exists("")
        with pytest.raises(ValueError, match="key 不能为空"):
            await storage.url("")

    async def test_none_data_raises_value_error(self, storage: LocalStorage):
        with pytest.raises(ValueError, match="data 不能为 None"):
            await storage.save("key.txt", None)  # type: ignore[arg-type]

    def test_empty_root_dir_raises_value_error(self):
        with pytest.raises(ValueError, match="root_dir 不能为空"):
            LocalStorage(root_dir="")

    async def test_path_traversal_blocked(self, storage: LocalStorage):
        """禁止 key 通过 ../ 逃逸根目录。"""
        with pytest.raises(ValueError, match="逃逸根目录"):
            await storage.save("../../etc/passwd", b"hacked")

    async def test_overwrite_existing(self, storage: LocalStorage):
        """相同 key 二次保存覆盖原内容。"""
        await storage.save("file.txt", b"old")
        await storage.save("file.txt", b"new content")
        assert await storage.load("file.txt") == b"new content"

    async def test_save_large_file(self, storage: LocalStorage):
        """大文件保存读取一致。"""
        data = b"x" * (1024 * 1024)  # 1MB
        await storage.save("large.bin", data)
        loaded = await storage.load("large.bin")
        assert loaded == data
        assert len(loaded) == 1024 * 1024


# ── S3Storage 测试（真实 MinIO 容器）──


# MinIO 测试需要 docker-compose 启动的 minio 容器
# 通过环境变量 MINIO_TEST_ENDPOINT 控制，未配置时跳过
_MINIO_ENDPOINT = os.getenv("MINIO_TEST_ENDPOINT", "")
_MINIO_ACCESS_KEY = os.getenv("MINIO_TEST_ACCESS_KEY", "minioadmin")
_MINIO_SECRET_KEY = os.getenv("MINIO_TEST_SECRET_KEY", "minioadmin")

skip_if_no_minio = pytest.mark.skipif(
    not _MINIO_ENDPOINT,
    reason="未配置 MINIO_TEST_ENDPOINT，跳过 S3Storage 真实容器测试",
)


@skip_if_no_minio
class TestS3Storage:
    """S3Storage 真实 MinIO 容器测试。"""

    @pytest.fixture
    def storage(self) -> S3Storage:
        """每个用例使用独立 bucket，避免数据干扰。"""
        import uuid as _uuid
        bucket = f"test-{_uuid.uuid4().hex[:8]}"
        return S3Storage(
            endpoint_url=_MINIO_ENDPOINT,
            access_key=_MINIO_ACCESS_KEY,
            secret_key=_MINIO_SECRET_KEY,
            bucket=bucket,
            use_ssl=False,
        )

    async def test_save_and_load_roundtrip(self, storage: S3Storage):
        key = "project/file.txt"
        data = b"s3 hello"
        obj = await storage.save(key, data, content_type="text/plain")
        assert obj.size == len(data)

        loaded = await storage.load(key)
        assert loaded == data

    async def test_load_nonexistent_raises(self, storage: S3Storage):
        with pytest.raises(FileNotFoundError):
            await storage.load("not_exists.txt")

    async def test_delete_existing_returns_true(self, storage: S3Storage):
        await storage.save("to_delete.txt", b"data")
        assert await storage.delete("to_delete.txt") is True
        assert await storage.exists("to_delete.txt") is False

    async def test_delete_nonexistent_returns_false(self, storage: S3Storage):
        assert await storage.delete("not_exists.txt") is False

    async def test_url_returns_presigned_url(self, storage: S3Storage):
        await storage.save("file.txt", b"data")
        url = await storage.url("file.txt", expires=300)
        assert url is not None
        assert "http" in url

    async def test_url_nonexistent_returns_none(self, storage: S3Storage):
        assert await storage.url("not_exists.txt") is None

    async def test_empty_key_raises(self, storage: S3Storage):
        with pytest.raises(ValueError):
            await storage.save("", b"data")


class TestS3StorageValidation:
    """S3Storage 构造参数校验（无需真实容器）。"""

    def test_empty_endpoint_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            S3Storage(
                endpoint_url="",
                access_key="k",
                secret_key="s",
                bucket="b",
            )

    def test_empty_access_key_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            S3Storage(
                endpoint_url="http://minio:9000",
                access_key="",
                secret_key="s",
                bucket="b",
            )

    def test_empty_bucket_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            S3Storage(
                endpoint_url="http://minio:9000",
                access_key="k",
                secret_key="s",
                bucket="",
            )


# ── 工厂函数测试 ──


class TestStorageFactory:
    """工厂函数配置路由测试。"""

    def setup_method(self):
        """每个用例前重置单例缓存。"""
        reset_storage_cache()

    def teardown_method(self):
        """用例后清理缓存避免污染。"""
        reset_storage_cache()

    def test_get_storage_returns_local_by_default(self):
        """默认返回 LocalStorage。"""
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "local"
            mock_settings.STORAGE_LOCAL_ROOT_DIR = tempfile.mkdtemp()
            mock_settings.UPLOAD_DIR = tempfile.mkdtemp()
            storage = get_storage()
            assert isinstance(storage, LocalStorage)

    def test_get_storage_returns_s3_when_configured(self):
        """配置 s3 后返回 S3Storage（mock _ensure_bucket 避免真实连接）。"""
        pytest.importorskip("boto3", reason="S3 存储需要 boto3")
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "s3"
            mock_settings.S3_ENDPOINT_URL = "http://minio:9000"
            mock_settings.S3_ACCESS_KEY = "k"
            mock_settings.S3_SECRET_KEY = "s"
            mock_settings.S3_BUCKET = "b"
            mock_settings.S3_REGION = "us-east-1"
            mock_settings.S3_USE_SSL = False
            with mock.patch.object(S3Storage, "_ensure_bucket"):
                storage = get_storage()
                assert isinstance(storage, S3Storage)

    def test_get_storage_invalid_backend_raises(self):
        """非法 backend 抛 ValueError。"""
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "azure"
            with pytest.raises(ValueError, match="非法 STORAGE_BACKEND"):
                get_storage()

    def test_get_storage_s3_missing_config_raises(self):
        """s3 模式配置缺失抛 ValueError。"""
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "s3"
            mock_settings.S3_ENDPOINT_URL = ""
            mock_settings.S3_ACCESS_KEY = ""
            mock_settings.S3_SECRET_KEY = ""
            mock_settings.S3_BUCKET = ""
            with pytest.raises(ValueError, match="S3 模式需配置"):
                get_storage()

    def test_get_storage_singleton(self):
        """get_storage 返回单例。"""
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "local"
            mock_settings.STORAGE_LOCAL_ROOT_DIR = tempfile.mkdtemp()
            mock_settings.UPLOAD_DIR = tempfile.mkdtemp()
            s1 = get_storage()
            s2 = get_storage()
            assert s1 is s2

    def test_reset_storage_cache_clears_singleton(self):
        """reset 后获取新实例。"""
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "local"
            mock_settings.STORAGE_LOCAL_ROOT_DIR = tempfile.mkdtemp()
            mock_settings.UPLOAD_DIR = tempfile.mkdtemp()
            s1 = get_storage()
            reset_storage_cache()
            s2 = get_storage()
            assert s1 is not s2

    def test_get_storage_backend_returns_string(self):
        """get_storage_backend 返回当前后端类型字符串。"""
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "s3"
            assert get_storage_backend() == "s3"
            mock_settings.STORAGE_BACKEND = "local"
            assert get_storage_backend() == "local"

    def test_get_storage_backend_default_when_unset(self):
        """STORAGE_BACKEND 为空时默认 local。"""
        with mock.patch("app.services.storage.factory.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = None
            assert get_storage_backend() == "local"


# ── StorageBackend 抽象基类校验 ──


class TestStorageBackendAbstract:
    """抽象基类不可直接实例化，子类必须实现所有方法。"""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore[abstract]

    def test_incomplete_subclass_raises(self):
        """未实现所有方法的子类不能实例化。"""
        class Incomplete(StorageBackend):
            async def save(self, key, data, content_type=None):
                pass
        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]
