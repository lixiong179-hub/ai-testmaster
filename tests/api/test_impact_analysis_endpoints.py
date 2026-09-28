"""TIA 智能调度端点 async 集成测试。

覆盖 /api/v1/projects/{id}/impact-analysis/* 端点：
    - POST /schedule               生成 TIA 调度计划
    - GET  /coverage               分页查询覆盖率映射
    - GET  /stats                  项目级覆盖率统计
    - POST /coverage               写入覆盖率映射（json_content 路径）
    - DELETE /coverage             清空项目覆盖率映射

测试用例:
    - 调度计划: TIA_ENABLED=False 全量执行 / 不存在项目 403 / 成功生成
    - 覆盖率写入: 成功 / 缺少参数 400 / 非法 test_case_id 400
    - 覆盖率查询: 空列表 / 有数据 / 按用例过滤 / 按文件过滤 / 分页
    - 覆盖率统计: 空项目 / 有数据项目
    - 覆盖率清空: 全部清空 / 按用例清空
    - 权限校验: 非项目所有者 403

事务隔离: async_db 外层事务包裹整个测试，结束 rollback 不落库，自动清理。

greenlet 适配: TIA 端点使用 asyncio.to_thread + PrimarySessionLocal() 在线程池中
执行 sync service。autouse fixture 用 greenlet_spawn 替换 to_thread，在事件循环
线程的 greenlet 中执行 sync 调用。
"""
import asyncio
import uuid

import pytest
from sqlalchemy.util.concurrency import greenlet_spawn

from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_coverage_map import TestCoverageMap
from app.models.user import User
from app.utils.jwt_utils import get_password_hash


@pytest.fixture(autouse=True)
def _patch_to_thread_for_greenlet():
    """patch asyncio.to_thread 使用 greenlet_spawn 执行 sync service 调用。

    TIA 端点使用 asyncio.to_thread(_run_sync, _do) 在线程池中执行 sync service。
    _run_sync 中 PrimarySessionLocal() 被 patch 为绑定到 async_db 的 sync session，
    其 connection 是 async connection 的 sync 代理，在线程池中执行 IO 时缺少
    greenlet 上下文导致 MissingGreenlet 错误。

    用 greenlet_spawn 替换 to_thread，在事件循环线程的 greenlet 中执行 sync 调用，
    使 async/sync 桥接可用。
    """
    original_to_thread = asyncio.to_thread

    async def _greenlet_to_thread(fn, *args, **kwargs):
        return await greenlet_spawn(fn, *args, **kwargs)

    asyncio.to_thread = _greenlet_to_thread
    yield
    asyncio.to_thread = original_to_thread


# ============================================================================
# 测试数据构造辅助函数
# ============================================================================


async def _create_other_user_project(async_db):
    """创建属于其他用户的项目，用于 403 无权限场景。

    返回 (other_user, other_project)。
    """
    suffix = uuid.uuid4().hex[:8]
    other_user = User(
        username=f"other_user_tia_{suffix}",
        email=f"other_tia_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"),
        is_active=True,
        is_superuser=False,
    )
    async_db.add(other_user)
    await async_db.flush()

    other_project = Project(
        name=f"other_project_tia_{suffix}",
        user_id=other_user.id,
        description="other project for TIA permission test",
        status=1,
        project_type="web",
    )
    async_db.add(other_project)
    await async_db.flush()
    return other_user, other_project


async def _create_test_case(async_db, project, *, title=None):
    """创建测试用例并 flush，返回 TestCase 对象。"""
    suffix = uuid.uuid4().hex[:8]
    case = TestCase(
        project_id=project.id,
        case_no=f"TIA-API-{suffix}",
        module="TIA端点测试",
        title=title or f"TIA测试用例-{suffix}",
        precondition="无",
        steps_json=[],
        expected_result="预期成功",
        priority=2,
        case_type="ui_automation",
        test_category="ui_automation",
        generate_status=1,
    )
    async_db.add(case)
    await async_db.flush()
    return case


async def _create_coverage_map(
    async_db,
    project,
    test_case_id,
    file_path="app/services/foo.py",
    line_start=1,
    line_end=10,
    test_name="test_foo",
):
    """创建单条覆盖率映射并 flush。"""
    mapping = TestCoverageMap(
        project_id=project.id,
        test_case_id=test_case_id,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        test_name=test_name,
    )
    async_db.add(mapping)
    await async_db.flush()
    return mapping


# ============================================================================
# 调度计划端点测试
# ============================================================================


class TestBuildSchedulePlan:
    """POST /projects/{id}/impact-analysis/schedule 端点测试。"""

    async def test_schedule_tia_disabled_returns_full_run(
        self, async_auth_client, async_test_project, monkeypatch
    ):
        """TIA_ENABLED=False 时返回全量执行计划。"""
        from app.core.config import settings

        monkeypatch.setattr(settings, "TIA_ENABLED", False)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/schedule",
            json={"total_test_count": 10},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_full_run"] is True
        assert data["is_effective"] is False
        assert data["tia_enabled"] is False
        assert "TIA_ENABLED=False" in data["fallback_reason"]

    async def test_schedule_project_not_owner_403(
        self, async_auth_client, async_db
    ):
        """非项目所有者调用返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{other_project.id}/impact-analysis/schedule",
            json={"total_test_count": 10},
        )
        assert resp.status_code == 403

    async def test_schedule_tia_enabled_no_coverage_returns_full_run(
        self, async_auth_client, async_test_project, monkeypatch
    ):
        """TIA_ENABLED=True 但无覆盖率数据时降级全量执行。"""
        from app.core.config import settings

        monkeypatch.setattr(settings, "TIA_ENABLED", True)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/schedule",
            json={"total_test_count": 10},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tia_enabled"] is True
        # 无覆盖率数据 → 降级全量执行
        assert data["is_full_run"] is True
        assert "冷启动" in data["fallback_reason"] or "无变更" in data["fallback_reason"]


# ============================================================================
# 覆盖率写入端点测试
# ============================================================================


class TestIngestCoverage:
    """POST /projects/{id}/impact-analysis/coverage 端点测试。"""

    async def test_ingest_with_json_content_success(
        self, async_auth_client, async_test_project, async_db, tmp_path
    ):
        """通过 json_content 写入覆盖率映射成功。"""
        case = await _create_test_case(async_db, async_test_project)
        # 构造 coverage.py 格式数据，文件路径需为绝对路径才能被 _to_relative_path 处理
        # 这里使用项目根目录下的相对路径，CoverageCollector 会处理
        coverage_data = {
            "files": {
                str(async_test_project.id): {  # 占位，实际由 _to_relative_path 处理
                    "executed_lines": [1, 2, 3, 10, 11]
                }
            }
        }

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage",
            json={
                "test_case_id": case.id,
                "test_name": "test_ingest",
                "json_content": coverage_data,
            },
        )
        # 由于文件路径不在项目根目录下，可能写入 0 行，但响应应成功
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["test_case_id"] == case.id
        assert "rows_written" in data

    async def test_ingest_missing_both_path_and_content_400(
        self, async_auth_client, async_test_project, async_db
    ):
        """json_path 与 json_content 均未提供时返回 400。

        HTTPException 经 http_exception_handler 转为统一错误响应格式
        {"code","msg","message","data","timestamp"}，故断言 msg 字段。
        """
        case = await _create_test_case(async_db, async_test_project)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage",
            json={"test_case_id": case.id},
        )
        assert resp.status_code == 400
        assert "至少需提供一项" in resp.json()["msg"]

    async def test_ingest_invalid_test_case_id_400(
        self, async_auth_client, async_test_project
    ):
        """非法 test_case_id（≤0）触发参数校验 400。

        全局 exception handler 将 Pydantic ValidationError 转为 400 响应。
        """
        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage",
            json={"test_case_id": 0, "json_content": {"files": {}}},
        )
        assert resp.status_code == 400

    async def test_ingest_project_not_owner_403(
        self, async_auth_client, async_db
    ):
        """非项目所有者调用返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{other_project.id}/impact-analysis/coverage",
            json={"test_case_id": 1, "json_content": {"files": {}}},
        )
        assert resp.status_code == 403


# ============================================================================
# 覆盖率查询端点测试
# ============================================================================


class TestListCoverageMaps:
    """GET /projects/{id}/impact-analysis/coverage 端点测试。"""

    async def test_list_empty_project(
        self, async_auth_client, async_test_project
    ):
        """空项目查询覆盖率映射返回空列表。"""
        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    async def test_list_with_data(
        self, async_auth_client, async_test_project, async_db
    ):
        """有数据时返回映射列表。"""
        case = await _create_test_case(async_db, async_test_project)
        await _create_coverage_map(
            async_db, async_test_project, case.id,
            file_path="app/foo.py", line_start=1, line_end=10,
        )

        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["project_id"] == async_test_project.id
        assert item["test_case_id"] == case.id
        assert item["file_path"] == "app/foo.py"
        assert item["line_start"] == 1
        assert item["line_end"] == 10

    async def test_list_filter_by_test_case_id(
        self, async_auth_client, async_test_project, async_db
    ):
        """按 test_case_id 过滤。"""
        case1 = await _create_test_case(async_db, async_test_project, title="case1")
        case2 = await _create_test_case(async_db, async_test_project, title="case2")
        await _create_coverage_map(
            async_db, async_test_project, case1.id, file_path="app/a.py"
        )
        await _create_coverage_map(
            async_db, async_test_project, case2.id, file_path="app/b.py"
        )

        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage",
            params={"test_case_id": case1.id},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["test_case_id"] == case1.id

    async def test_list_filter_by_file_path(
        self, async_auth_client, async_test_project, async_db
    ):
        """按 file_path 过滤。"""
        case = await _create_test_case(async_db, async_test_project)
        await _create_coverage_map(
            async_db, async_test_project, case.id, file_path="app/a.py"
        )
        await _create_coverage_map(
            async_db, async_test_project, case.id, file_path="app/b.py"
        )

        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage",
            params={"file_path": "app/a.py"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["file_path"] == "app/a.py"

    async def test_list_pagination(
        self, async_auth_client, async_test_project, async_db
    ):
        """分页查询。"""
        case = await _create_test_case(async_db, async_test_project)
        # 创建 5 条映射
        for i in range(5):
            await _create_coverage_map(
                async_db, async_test_project, case.id,
                file_path=f"app/file_{i}.py",
            )

        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage",
            params={"page": 1, "page_size": 2},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    async def test_list_project_not_owner_403(
        self, async_auth_client, async_db
    ):
        """非项目所有者查询返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.get(
            f"/api/v1/projects/{other_project.id}/impact-analysis/coverage"
        )
        assert resp.status_code == 403


# ============================================================================
# 覆盖率统计端点测试
# ============================================================================


class TestGetCoverageStats:
    """GET /projects/{id}/impact-analysis/stats 端点测试。"""

    async def test_stats_empty_project(
        self, async_auth_client, async_test_project
    ):
        """空项目统计返回全 0。"""
        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/stats"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["project_id"] == async_test_project.id
        assert data["total_mappings"] == 0
        assert data["unique_files"] == 0
        assert data["unique_test_cases"] == 0
        assert "tia_enabled" in data

    async def test_stats_with_data(
        self, async_auth_client, async_test_project, async_db
    ):
        """有数据时返回正确统计。"""
        case1 = await _create_test_case(async_db, async_test_project, title="c1")
        case2 = await _create_test_case(async_db, async_test_project, title="c2")
        await _create_coverage_map(
            async_db, async_test_project, case1.id, file_path="app/a.py"
        )
        await _create_coverage_map(
            async_db, async_test_project, case1.id, file_path="app/b.py"
        )
        await _create_coverage_map(
            async_db, async_test_project, case2.id, file_path="app/a.py"
        )

        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/stats"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_mappings"] == 3
        assert data["unique_files"] == 2  # app/a.py, app/b.py
        assert data["unique_test_cases"] == 2  # case1, case2

    async def test_stats_project_not_owner_403(
        self, async_auth_client, async_db
    ):
        """非项目所有者查询统计返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.get(
            f"/api/v1/projects/{other_project.id}/impact-analysis/stats"
        )
        assert resp.status_code == 403


# ============================================================================
# 覆盖率清空端点测试
# ============================================================================


class TestClearCoverageMaps:
    """DELETE /projects/{id}/impact-analysis/coverage 端点测试。"""

    async def test_clear_all(
        self, async_auth_client, async_test_project, async_db
    ):
        """清空项目全部覆盖率映射。"""
        case1 = await _create_test_case(async_db, async_test_project, title="c1")
        case2 = await _create_test_case(async_db, async_test_project, title="c2")
        await _create_coverage_map(
            async_db, async_test_project, case1.id, file_path="app/a.py"
        )
        await _create_coverage_map(
            async_db, async_test_project, case2.id, file_path="app/b.py"
        )

        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["rows_written"] == 2
        assert "已清空" in data["message"]

        # 验证清空后查询为空
        list_resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage"
        )
        assert list_resp.json()["data"]["total"] == 0

    async def test_clear_by_test_case_id(
        self, async_auth_client, async_test_project, async_db
    ):
        """按 test_case_id 清空指定用例的映射。"""
        case1 = await _create_test_case(async_db, async_test_project, title="c1")
        case2 = await _create_test_case(async_db, async_test_project, title="c2")
        await _create_coverage_map(
            async_db, async_test_project, case1.id, file_path="app/a.py"
        )
        await _create_coverage_map(
            async_db, async_test_project, case2.id, file_path="app/b.py"
        )

        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage",
            params={"test_case_id": case1.id},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["rows_written"] == 1

        # 验证 case1 已清空，case2 保留
        list_resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage"
        )
        list_data = list_resp.json()["data"]
        assert list_data["total"] == 1
        assert list_data["items"][0]["test_case_id"] == case2.id

    async def test_clear_empty_project(
        self, async_auth_client, async_test_project
    ):
        """空项目清空返回 0。"""
        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/impact-analysis/coverage"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["rows_written"] == 0

    async def test_clear_project_not_owner_403(
        self, async_auth_client, async_db
    ):
        """非项目所有者清空返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.delete(
            f"/api/v1/projects/{other_project.id}/impact-analysis/coverage"
        )
        assert resp.status_code == 403
