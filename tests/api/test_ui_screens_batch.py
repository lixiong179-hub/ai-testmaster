"""UI截图批量接口单测。

覆盖 Task 6.1：GET /api/v1/ui-screens/batch?ids=1,2,3

测试规范：
    - 使用真实测试库（async_db fixture，事务隔离，用例结束自动 rollback）
    - 图片文件使用 pytest 内置 tmp_path，用例结束自动清理
    - 覆盖正常、空值、异常、边界用例，核心分支覆盖率 >= 95%
    - 断言批量接口与单条接口 (/api/v1/file/preview-screen/{id}) 的等价性：
      同一组 ids 的批量结果 data URL 解码字节 == 多次单条结果的合并字节
"""
import base64
import os

from app.models.project import Project
from app.models.ui_prototype import UIPrototypeScreen
from app.models.user import User
from app.utils.jwt_utils import get_password_hash

# 最小的有效 1x1 透明 PNG 字节，用于构造真实图片文件
PNG_BYTES: bytes = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_png(tmp_path, name: str = "screen.png") -> str:
    """在临时目录写入一张真实 PNG 图片，返回绝对路径。"""
    path = tmp_path / name
    path.write_bytes(PNG_BYTES)
    return str(path)


async def _make_screen(
    async_db,
    project,
    file_path: str,
    file_type: str = "png",
    screen_name: str = "测试屏幕",
) -> UIPrototypeScreen:
    """创建一条 UIPrototypeScreen 记录并 flush 生成 id。"""
    screen = UIPrototypeScreen(
        project_id=project.id,
        prototype_name="测试原型",
        source="manual",
        screen_name=screen_name,
        file_type=file_type,
        original_file_path=file_path,
        parse_status="completed",
    )
    async_db.add(screen)
    await async_db.flush()
    return screen


class TestBatchGetUiScreens:
    """UI截图批量接口 GET /api/v1/ui-screens/batch 测试。"""

    async def test_batch_returns_data_url_mapping(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """正常批量请求返回 {id: data_url} 映射。"""
        file_path = _write_png(tmp_path, "a.png")
        screen1 = await _make_screen(async_db, async_test_project, file_path, screen_name="A")
        screen2 = await _make_screen(async_db, async_test_project, file_path, screen_name="B")

        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen1.id},{screen2.id}",
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert str(screen1.id) in data
        assert str(screen2.id) in data
        assert data[str(screen1.id)].startswith("data:image/png;base64,")

    async def test_batch_equivalent_to_single(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """等价性：批量接口 data_url 解码字节 == 单条 preview-screen 响应字节。"""
        file_path = _write_png(tmp_path, "eq.png")
        screen = await _make_screen(async_db, async_test_project, file_path, screen_name="EQ")

        single_resp = await async_auth_client.get(
            f"/api/v1/file/preview-screen/{screen.id}",
        )
        assert single_resp.status_code == 200
        single_bytes = single_resp.content

        batch_resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen.id}",
        )
        assert batch_resp.status_code == 200
        data_url = batch_resp.json()["data"][str(screen.id)]
        batch_bytes = base64.b64decode(data_url.split(",", 1)[1])

        # 批量结果 == 单条结果 == 原始文件字节
        assert batch_bytes == single_bytes == PNG_BYTES

    async def test_batch_equivalent_multiple_ids_merge(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """等价性：批量结果 == 多次单条结果的合并。"""
        path1 = _write_png(tmp_path, "m1.png")
        path2 = _write_png(tmp_path, "m2.png")
        screen1 = await _make_screen(async_db, async_test_project, path1, screen_name="M1")
        screen2 = await _make_screen(async_db, async_test_project, path2, screen_name="M2")

        batch_resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen1.id},{screen2.id}",
        )
        assert batch_resp.status_code == 200
        batch_data = batch_resp.json()["data"]

        # 逐条调用单条接口，合并结果
        merged: dict[str, bytes] = {}
        for sid in (screen1.id, screen2.id):
            single_resp = await async_auth_client.get(
                f"/api/v1/file/preview-screen/{sid}",
            )
            assert single_resp.status_code == 200
            merged[str(sid)] = single_resp.content

        # 批量接口每条 data_url 解码后 == 单条接口对应字节
        for sid_str, single_bytes in merged.items():
            data_url = batch_data[sid_str]
            assert base64.b64decode(data_url.split(",", 1)[1]) == single_bytes

    async def test_batch_without_auth(
        self, async_client, async_test_project, async_db, tmp_path
    ) -> None:
        """无认证请求返回 401/403。"""
        file_path = _write_png(tmp_path, "noauth.png")
        screen = await _make_screen(async_db, async_test_project, file_path, screen_name="NOAUTH")
        resp = await async_client.get(f"/api/v1/ui-screens/batch?ids={screen.id}")
        assert resp.status_code in (401, 403)

    async def test_batch_empty_ids(self, async_auth_client) -> None:
        """空 ids 参数返回 422。"""
        resp = await async_auth_client.get("/api/v1/ui-screens/batch?ids=")
        assert resp.status_code == 422

    async def test_batch_whitespace_only_ids(self, async_auth_client) -> None:
        """仅含空白与逗号的 ids 返回 422。"""
        resp = await async_auth_client.get("/api/v1/ui-screens/batch?ids= , , ")
        assert resp.status_code == 422

    async def test_batch_missing_ids_param(self, async_auth_client) -> None:
        """缺少 ids 必填参数返回 400/422（项目全局处理器将参数校验失败映射为 400）。"""
        resp = await async_auth_client.get("/api/v1/ui-screens/batch")
        assert resp.status_code in (400, 422)

    async def test_batch_invalid_id(self, async_auth_client) -> None:
        """ids 含非数字返回 422。"""
        resp = await async_auth_client.get(
            "/api/v1/ui-screens/batch?ids=1,abc,3"
        )
        assert resp.status_code == 422

    async def test_batch_non_positive_id(self, async_auth_client) -> None:
        """id 为 0 或负数返回 422。"""
        resp = await async_auth_client.get(
            "/api/v1/ui-screens/batch?ids=1,0,-3"
        )
        assert resp.status_code == 422

    async def test_batch_exceeds_limit(self, async_auth_client) -> None:
        """超过 100 个 id 返回 422。"""
        ids = ",".join(str(i) for i in range(1, 102))
        resp = await async_auth_client.get(f"/api/v1/ui-screens/batch?ids={ids}")
        assert resp.status_code == 422

    async def test_batch_at_limit_boundary(self, async_auth_client) -> None:
        """恰好 100 个 id 不超上限（不返回 422，因 id 不存在故 data 为空）。"""
        ids = ",".join(str(i) for i in range(1, 101))
        resp = await async_auth_client.get(f"/api/v1/ui-screens/batch?ids={ids}")
        assert resp.status_code == 200
        assert resp.json()["data"] == {}

    async def test_batch_skips_nonexistent_id(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """不存在的 id 不出现在结果中。"""
        file_path = _write_png(tmp_path, "exist.png")
        screen = await _make_screen(async_db, async_test_project, file_path, screen_name="EXIST")
        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen.id},999999",
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert str(screen.id) in data
        assert "999999" not in data

    async def test_batch_skips_unauthorized(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """其他用户项目的 screen 不返回（权限过滤）。"""
        suffix = os.getenv("PYTEST_XDIST_WORKER", "0")
        other_user = User(
            username=f"other_batch_user_{suffix}",
            email=f"other_batch_{suffix}@test.com",
            password_hash=get_password_hash("Other@123456"),
            is_active=True,
        )
        async_db.add(other_user)
        await async_db.flush()
        other_project = Project(
            name=f"other_project_batch_{suffix}",
            user_id=other_user.id,
            description="other",
            status=1,
            project_type="web",
        )
        async_db.add(other_project)
        await async_db.flush()
        file_path = _write_png(tmp_path, "other.png")
        other_screen = await _make_screen(async_db, other_project, file_path, screen_name="OTHER")

        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={other_screen.id}",
        )
        assert resp.status_code == 200
        assert str(other_screen.id) not in resp.json()["data"]

    async def test_batch_skips_missing_file(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """文件不存在的 screen 跳过。"""
        screen = await _make_screen(
            async_db, async_test_project, str(tmp_path / "noexist.png"), screen_name="MISSING"
        )
        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen.id}",
        )
        assert resp.status_code == 200
        assert str(screen.id) not in resp.json()["data"]

    async def test_batch_skips_unreadable_file(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """文件读取失败（路径指向目录）时跳过，覆盖 OSError 分支。"""
        screen = await _make_screen(async_db, async_test_project, str(tmp_path), screen_name="DIR")
        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen.id}",
        )
        assert resp.status_code == 200
        assert str(screen.id) not in resp.json()["data"]

    async def test_batch_jpg_to_jpeg_mime(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """file_type=jpg 时 data URL 使用 image/jpeg MIME。"""
        file_path = _write_png(tmp_path, "jpg.png")
        screen = await _make_screen(
            async_db, async_test_project, file_path, file_type="jpg", screen_name="JPG"
        )
        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen.id}",
        )
        assert resp.status_code == 200
        data_url = resp.json()["data"][str(screen.id)]
        assert data_url.startswith("data:image/jpeg;base64,")

    async def test_batch_empty_file_type_defaults_png(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """file_type 为空时兜底为 image/png。"""
        file_path = _write_png(tmp_path, "empty.png")
        screen = await _make_screen(
            async_db, async_test_project, file_path, file_type="", screen_name="EMPTY"
        )
        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen.id}",
        )
        assert resp.status_code == 200
        data_url = resp.json()["data"][str(screen.id)]
        assert data_url.startswith("data:image/png;base64,")

    async def test_batch_dedup_ids(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ) -> None:
        """重复 id 去重，结果仅含唯一 id。"""
        file_path = _write_png(tmp_path, "dedup.png")
        screen1 = await _make_screen(async_db, async_test_project, file_path, screen_name="D1")
        screen2 = await _make_screen(async_db, async_test_project, file_path, screen_name="D2")
        resp = await async_auth_client.get(
            f"/api/v1/ui-screens/batch?ids={screen1.id},{screen1.id},{screen2.id}",
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2

    async def test_batch_internal_error_returns_500(
        self, async_auth_client, monkeypatch
    ) -> None:
        """内部异常返回 500，覆盖兜底 except Exception 分支。"""
        from app.api.v1.endpoints import ui_screens_batch

        def _boom(raw_ids: str) -> list[int]:
            raise RuntimeError("boom")

        monkeypatch.setattr(ui_screens_batch, "_parse_screen_ids", _boom)
        resp = await async_auth_client.get(
            "/api/v1/ui-screens/batch?ids=1"
        )
        assert resp.status_code == 500
