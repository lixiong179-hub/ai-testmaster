"""视觉调用统一 SDK 单元测试（Task 9）。

覆盖：
    - VisualAISDK 构造与依赖注入
    - VisualCheckResult 数据类
    - run_visual_check 无基线返回 skip
    - run_visual_check 有基线对比流程（Mock storage + baseline）
    - compare 基线不存在抛 ValueError
    - approve_diff Diff 不存在抛 ValueError
"""
from __future__ import annotations

import io
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.services.storage.base import StorageBackend, StorageObject
from app.services.visual_ai.sdk import VisualAISDK, VisualCheckResult


# ── Mock 基础设施 ──


class _MockStorage(StorageBackend):
    """内存存储后端，用于测试。"""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> StorageObject:
        self._store[key] = data
        return StorageObject(key=key, size=len(data), content_type=content_type)

    async def load(self, key: str) -> bytes:
        if key not in self._store:
            raise FileNotFoundError(key)
        return self._store[key]

    async def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def url(self, key: str, expires: int = 3600) -> Optional[str]:
        return f"mock://{key}"


def _make_solid_png(width: int, height: int, color: tuple) -> bytes:
    """生成纯色 PNG 字节流。"""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _MockBaseline:
    """模拟 VisualBaseline ORM 对象。"""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", 1)
        self.project_id = kwargs.get("project_id", 1)
        self.test_case_id = kwargs.get("test_case_id")
        self.name = kwargs.get("name", "test")
        self.page_url = kwargs.get("page_url", "http://test")
        self.viewport_width = kwargs.get("viewport_width", 100)
        self.viewport_height = kwargs.get("viewport_height", 100)
        self.image_key = kwargs.get("image_key", "baseline.png")
        self.image_width = kwargs.get("image_width", 100)
        self.image_height = kwargs.get("image_height", 100)
        self.match_level = kwargs.get("match_level", "strict")
        self.dom_snapshot_key = kwargs.get("dom_snapshot_key")
        self.status = kwargs.get("status", "active")
        self.version = kwargs.get("version", 1)
        self.created_by = kwargs.get("created_by")
        self.created_at = kwargs.get("created_at")
        self.updated_at = kwargs.get("updated_at")


# ── 测试用例 ──


class TestVisualAISDKConstruction:
    """SDK 构造与依赖注入测试。"""

    def test_sdk_init_with_dependencies(self) -> None:
        """SDK 接受 db、storage、ai_client、redis_client 注入。"""
        mock_db = MagicMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        assert sdk._db is mock_db
        assert sdk._storage is mock_storage
        assert sdk._ai_client is None
        assert sdk._baseline_service is not None
        assert sdk._estimator is not None

    def test_sdk_init_with_ai_client(self) -> None:
        """SDK 接受 AI 客户端注入。"""
        mock_db = MagicMock()
        mock_storage = _MockStorage()
        mock_ai = MagicMock()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage, ai_client=mock_ai)

        assert sdk._ai_client is mock_ai


class TestVisualCheckResult:
    """VisualCheckResult 数据类测试。"""

    def test_default_values(self) -> None:
        """默认值正确。"""
        result = VisualCheckResult(
            baseline_id=1,
            diff_id=2,
            diff_percentage=5.0,
            diff_pixel_count=100,
            match_level="strict",
            status="pending",
        )
        assert result.baseline_id == 1
        assert result.diff_percentage == 5.0
        assert result.llm_analysis is None
        assert result.token_cost == 0
        assert result.llm_skipped is False
        assert result.skip_reason == ""
        assert result.diff_report == ""

    def test_skipped_result(self) -> None:
        """skip 结果特征。"""
        result = VisualCheckResult(
            baseline_id=None,
            diff_id=None,
            diff_percentage=0.0,
            diff_pixel_count=0,
            match_level="strict",
            status="skipped",
            skip_reason="no_baseline",
        )
        assert result.baseline_id is None
        assert result.status == "skipped"
        assert result.skip_reason == "no_baseline"


class TestRunVisualCheckNoBaseline:
    """run_visual_check 无基线场景测试。"""

    async def test_no_baseline_returns_skipped(self) -> None:
        """无活跃基线时返回 skip 结果。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        # Mock baseline_service.get_active_baseline 返回 None
        sdk._baseline_service.get_active_baseline = AsyncMock(return_value=None)

        result = await sdk.run_visual_check(
            project_id=1,
            page_url="http://test",
            viewport_width=1280,
            viewport_height=800,
            current_image_bytes=_make_solid_png(50, 50, (255, 0, 0)),
        )

        assert result.baseline_id is None
        assert result.diff_id is None
        assert result.status == "skipped"
        assert result.skip_reason == "no_baseline"


class TestRunVisualCheckWithBaseline:
    """run_visual_check 有基线场景测试。"""

    async def test_compare_with_baseline_identical_images(self) -> None:
        """有基线且截图相同时返回 0% 差异 + auto_approved。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()

        # 准备基线图片
        baseline_image = _make_solid_png(50, 50, (255, 0, 0))
        await mock_storage.save("baseline.png", baseline_image)

        baseline = _MockBaseline(
            id=1,
            image_key="baseline.png",
            match_level="strict",
            dom_snapshot_key=None,
        )

        sdk = VisualAISDK(db=mock_db, storage=mock_storage)
        sdk._baseline_service.get_active_baseline = AsyncMock(return_value=baseline)
        sdk._baseline_service.load_baseline_image = AsyncMock(return_value=baseline_image)

        # Mock DB add/commit/refresh
        mock_diff = MagicMock()
        mock_diff.id = 100
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await sdk.run_visual_check(
            project_id=1,
            page_url="http://test",
            viewport_width=50,
            viewport_height=50,
            current_image_bytes=baseline_image,  # 相同图片
        )

        assert result.baseline_id == 1
        assert result.diff_percentage == 0.0
        assert result.diff_pixel_count == 0
        # 0% < AUTO_APPROVE_THRESHOLD → auto_approved
        assert result.status == "auto_approved"
        assert result.llm_skipped is True  # 无 ai_client → 跳过 LLM

    async def test_compare_with_baseline_different_images(self) -> None:
        """有基线且截图不同时返回非零差异 + pending。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()

        baseline_image = _make_solid_png(50, 50, (255, 0, 0))
        current_image = _make_solid_png(50, 50, (0, 0, 255))
        await mock_storage.save("baseline.png", baseline_image)

        baseline = _MockBaseline(
            id=1,
            image_key="baseline.png",
            match_level="strict",
        )

        sdk = VisualAISDK(db=mock_db, storage=mock_storage)
        sdk._baseline_service.get_active_baseline = AsyncMock(return_value=baseline)
        sdk._baseline_service.load_baseline_image = AsyncMock(return_value=baseline_image)

        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await sdk.run_visual_check(
            project_id=1,
            page_url="http://test",
            viewport_width=50,
            viewport_height=50,
            current_image_bytes=current_image,
        )

        assert result.baseline_id == 1
        assert result.diff_percentage == 100.0
        assert result.diff_pixel_count == 2500
        # 100% > AUTO_APPROVE_THRESHOLD → pending
        assert result.status == "pending"
        assert result.llm_skipped is True  # 无 ai_client

    async def test_compare_generates_diff_report(self) -> None:
        """对比生成 Markdown Diff 报告。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()

        baseline_image = _make_solid_png(50, 50, (255, 0, 0))
        current_image = _make_solid_png(50, 50, (0, 0, 255))
        await mock_storage.save("baseline.png", baseline_image)

        baseline = _MockBaseline(id=1, image_key="baseline.png")
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)
        sdk._baseline_service.get_active_baseline = AsyncMock(return_value=baseline)
        sdk._baseline_service.load_baseline_image = AsyncMock(return_value=baseline_image)

        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await sdk.run_visual_check(
            project_id=1,
            page_url="http://test",
            viewport_width=50,
            viewport_height=50,
            current_image_bytes=current_image,
        )

        assert "视觉差异报告" in result.diff_report
        assert "100.00%" in result.diff_report


class TestCompareMethod:
    """compare 方法测试。"""

    async def test_compare_nonexistent_baseline_raises(self) -> None:
        """基线不存在时抛 ValueError。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)
        sdk._baseline_service.get_baseline_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="基线不存在"):
            await sdk.compare(
                baseline_id=999,
                current_image_bytes=b"fake",
            )


class TestApproveDiff:
    """approve_diff 方法测试。"""

    async def test_approve_nonexistent_diff_raises(self) -> None:
        """Diff 不存在时抛 ValueError。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Diff 不存在"):
            await sdk.approve_diff(
                project_id=1,
                diff_id=999,
                action="approve",
            )

    async def test_approve_diff_success(self) -> None:
        """审批存在的 Diff 返回 BaselineApproval 记录。"""
        from app.models.visual_diff import VisualDiff

        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        diff = MagicMock(spec=VisualDiff)
        diff.id = 10
        diff.project_id = 1
        diff.baseline_id = 5
        diff.status = "pending"
        mock_db.get = AsyncMock(return_value=diff)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        async def _refresh(obj: Any) -> None:
            obj.id = 100

        mock_db.refresh = AsyncMock(side_effect=_refresh)

        approval = await sdk.approve_diff(
            project_id=1, diff_id=10, action="approve", comment="ok", reviewer_id=2,
        )
        assert approval.action == "approve"
        assert approval.comment == "ok"
        assert diff.status == "approved"

    async def test_approve_diff_project_mismatch_raises(self) -> None:
        """Diff 的 project_id 与传入不匹配时抛 ValueError。"""
        from app.models.visual_diff import VisualDiff

        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        diff = MagicMock(spec=VisualDiff)
        diff.project_id = 999  # 不匹配
        mock_db.get = AsyncMock(return_value=diff)

        with pytest.raises(ValueError, match="Diff 不存在"):
            await sdk.approve_diff(project_id=1, diff_id=10, action="approve")


class TestBaselineDelegationMethods:
    """SDK 委托 BaselineService 的方法测试。"""

    async def test_get_baseline_delegates_to_service(self) -> None:
        """get_baseline 委托给 baseline_service.get_active_baseline。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        expected = _MockBaseline(id=7)
        sdk._baseline_service.get_active_baseline = AsyncMock(return_value=expected)

        result = await sdk.get_baseline(
            project_id=1, page_url="http://x", viewport_width=100, viewport_height=100,
        )
        assert result is expected
        sdk._baseline_service.get_active_baseline.assert_awaited_once()

    async def test_list_baselines_delegates_to_service(self) -> None:
        """list_baselines 委托给 baseline_service.list_baselines。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        expected = [_MockBaseline(id=1), _MockBaseline(id=2)]
        sdk._baseline_service.list_baselines = AsyncMock(return_value=expected)

        result = await sdk.list_baselines(project_id=1, status="active", limit=10)
        assert result == expected
        sdk._baseline_service.list_baselines.assert_awaited_once()

    async def test_update_baseline_delegates_to_service(self) -> None:
        """update_baseline 委托给 baseline_service.update_baseline。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        expected = _MockBaseline(id=1, version=2)
        sdk._baseline_service.update_baseline = AsyncMock(return_value=expected)

        result = await sdk.update_baseline(
            baseline_id=1, new_image_bytes=b"png", dom_html="<html></html>",
        )
        assert result is expected
        # 验证 dom_html 被编码为 bytes 传入
        call_kwargs = sdk._baseline_service.update_baseline.call_args.kwargs
        assert call_kwargs["dom_snapshot_bytes"] == b"<html></html>"

    async def test_update_baseline_none_dom_html(self) -> None:
        """dom_html 为 None 时传 None。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        sdk._baseline_service.update_baseline = AsyncMock(return_value=_MockBaseline())

        await sdk.update_baseline(baseline_id=1, new_image_bytes=b"png")
        call_kwargs = sdk._baseline_service.update_baseline.call_args.kwargs
        assert call_kwargs["dom_snapshot_bytes"] is None

    async def test_delete_baseline_delegates_to_service(self) -> None:
        """delete_baseline 委托给 baseline_service.delete_baseline。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        sdk._baseline_service.delete_baseline = AsyncMock(return_value=True)

        result = await sdk.delete_baseline(baseline_id=1)
        assert result is True
        sdk._baseline_service.delete_baseline.assert_awaited_once()

    async def test_create_baseline_delegates_to_service(self) -> None:
        """create_baseline 委托给 baseline_service.create_baseline。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        expected = _MockBaseline(id=1)
        sdk._baseline_service.create_baseline = AsyncMock(return_value=expected)

        result = await sdk.create_baseline(
            project_id=1,
            name="基线",
            page_url="http://x",
            viewport_width=100,
            viewport_height=100,
            image_bytes=b"png",
            dom_html="<html></html>",
        )
        assert result is expected
        call_kwargs = sdk._baseline_service.create_baseline.call_args.kwargs
        assert call_kwargs["dom_snapshot_bytes"] == b"<html></html>"


class TestListDiffs:
    """list_diffs 方法测试。"""

    async def test_list_diffs_returns_list(self) -> None:
        """list_diffs 返回 Diff 列表。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        diff1 = MagicMock()
        diff2 = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [diff1, diff2]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=result_mock)

        result = await sdk.list_diffs(project_id=1)
        assert result == [diff1, diff2]
        mock_db.execute.assert_awaited_once()

    async def test_list_diffs_with_status_filter(self) -> None:
        """list_diffs 带 status 过滤参数。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        mock_db.execute = AsyncMock(return_value=result_mock)

        result = await sdk.list_diffs(project_id=1, status="pending", limit=10)
        assert result == []


class TestCheckTokenBudget:
    """_check_token_budget 内部方法测试。"""

    def test_check_token_budget_no_ai_client(self) -> None:
        """无 ai_client 时返回跳过。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage)

        skipped, reason, _ = sdk._check_token_budget(
            project_id=1,
            baseline_image=b"x",
            current_image_bytes=b"y",
            effective_match_level="strict",
        )
        assert skipped is True
        assert reason == "ai_client_unavailable"

    def test_check_token_budget_with_ai_client_within_limit(self) -> None:
        """有 ai_client 且预算充足时不跳过。"""
        mock_db = AsyncMock()
        mock_storage = _MockStorage()
        mock_ai = MagicMock()
        sdk = VisualAISDK(db=mock_db, storage=mock_storage, ai_client=mock_ai)

        skipped, reason, estimated = sdk._check_token_budget(
            project_id=1,
            baseline_image=b"x" * 100,
            current_image_bytes=b"y" * 100,
            effective_match_level="strict",
        )
        assert skipped is False
        assert reason == ""
        assert estimated > 0
