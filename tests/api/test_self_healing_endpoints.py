"""自愈管理端点 async 测试。

覆盖 /api/v1/self-healing/* 与 /api/v1/projects/{id}/self-healing-config 端点，
使用 tests/api/conftest.py 的 async_auth_client fixture（httpx.AsyncClient +
override async_get_db + get_current_user）。

测试用例:
    - 审计列表: 空列表 / 有数据 / project_id 过滤 / test_case_id 过滤 / 分页
    - 审计详情: 存在 / 不存在 404
    - 回滚: 成功 / 不存在 404 / old_selector 空 400
    - 项目配置查询: 成功 / 项目不存在 403 / 无权限 403
    - 项目配置更新: 成功 / 部分更新 / 非法 strategies 400 / 非法 token_limit / 无权限 403

事务隔离: async_db 外层事务包裹整个测试，结束 rollback 不落库，自动清理。

greenlet 适配: self_healing 端点使用 asyncio.to_thread + PrimarySessionLocal()
在线程池中执行 sync service。PrimarySessionLocal 被 patch 为绑定到 async_db 的
sync session，在线程池中使用时需要 greenlet 上下文（async connection 的 sync
代理依赖 greenlet）。autouse fixture 用 greenlet_spawn 替换 to_thread，在事件
循环线程的 greenlet 中执行 sync 调用。
"""
import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.util.concurrency import greenlet_spawn

from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.self_healing_audit import SelfHealingAudit
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.utils.jwt_utils import get_password_hash


@pytest.fixture(autouse=True)
def _patch_to_thread_for_greenlet():
    """patch asyncio.to_thread 使用 greenlet_spawn 执行 sync service 调用。

    self_healing 端点使用 asyncio.to_thread(_run_sync, _do) 在线程池中执行
    sync service。_run_sync 中 PrimarySessionLocal() 被 patch 为绑定到 async_db
    的 sync session，其 connection 是 async connection 的 sync 代理，在线程池
    中执行 IO 时缺少 greenlet 上下文导致 MissingGreenlet 错误。

    用 greenlet_spawn 替换 to_thread，在事件循环线程的 greenlet 中执行 sync
    调用，使 async/sync 桥接可用。fixture 在 yield 后恢复原值。
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
        username=f"other_user_sh_{suffix}",
        email=f"other_sh_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"),
        is_active=True,
        is_superuser=False,
    )
    async_db.add(other_user)
    await async_db.flush()

    other_project = Project(
        name=f"other_project_sh_{suffix}",
        user_id=other_user.id,
        description="other project for permission test",
        status=1,
        project_type="web",
    )
    async_db.add(other_project)
    await async_db.flush()
    return other_user, other_project


async def _create_case(async_db, project, *, case_no=None, title=None):
    """创建测试用例并 flush，返回 TestCase 对象。"""
    suffix = uuid.uuid4().hex[:8]
    case = TestCase(
        project_id=project.id,
        case_no=case_no or f"SH-API-{suffix}",
        module="自愈端点测试",
        title=title or f"端点测试用例-{suffix}",
        precondition="无",
        steps_json=[],
        expected_result="成功",
        priority=1,
        case_type="UI",
        generate_status=1,
    )
    async_db.add(case)
    await async_db.flush()
    return case


async def _create_step(async_db, case, *, step_number=1):
    """创建测试步骤并 flush，返回 TestStep 对象。"""
    step = TestStep(
        test_case_id=case.id,
        step_number=step_number,
        action="点击登录按钮",
        action_type="click",
        expected_result="跳转首页",
    )
    async_db.add(step)
    await async_db.flush()
    return step


async def _create_locator(async_db, step, *, css_selector=".new-btn", version=1):
    """创建元素定位器并 flush，返回 ElementLocator 对象。"""
    locator = ElementLocator(
        step_id=step.id,
        element_description="测试按钮",
        element_type="button",
        css_selector=css_selector,
        source="ai_self_healing",
        version=version,
    )
    async_db.add(locator)
    await async_db.flush()
    return locator


async def _create_audit(
    async_db,
    case,
    *,
    step_index=0,
    locator_id=None,
    old_selector=".old-btn",
    new_selector=".new-btn",
    failure_type="element_gone",
    strategy="mcp",
    confidence=0.9,
    token_cost=100,
    low_confidence=False,
):
    """创建审计记录并 flush，返回 SelfHealingAudit 对象。"""
    audit = SelfHealingAudit(
        test_case_id=case.id,
        step_index=step_index,
        locator_id=locator_id,
        old_selector=old_selector,
        new_selector=new_selector,
        failure_type=failure_type,
        strategy=strategy,
        confidence=confidence,
        token_cost=token_cost,
        low_confidence=low_confidence,
    )
    async_db.add(audit)
    await async_db.flush()
    return audit


# ============================================================================
# 审计列表端点测试
# ============================================================================


class TestSelfHealingAuditList:
    """GET /api/v1/self-healing/audits 分页查询审计记录。"""

    async def test_empty_list(self, async_auth_client):
        """空列表场景：无审计记录时返回空 items 与 total=0。"""
        resp = await async_auth_client.get("/api/v1/self-healing/audits")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 20

    async def test_list_with_data(
        self, async_auth_client, async_db, async_test_project
    ):
        """有数据场景：创建审计后列表返回对应记录。"""
        case = await _create_case(async_db, async_test_project)
        audit = await _create_audit(async_db, case)

        resp = await async_auth_client.get("/api/v1/self-healing/audits")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] >= 1
        ids = [item["id"] for item in body["data"]["items"]]
        assert audit.id in ids

    async def test_filter_by_project_id(
        self, async_auth_client, async_db, async_test_project
    ):
        """project_id 过滤：仅返回该项目的审计记录。"""
        case = await _create_case(async_db, async_test_project)
        audit = await _create_audit(async_db, case)

        resp = await async_auth_client.get(
            f"/api/v1/self-healing/audits?project_id={async_test_project.id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] >= 1
        ids = [item["id"] for item in body["data"]["items"]]
        assert audit.id in ids

    async def test_filter_by_project_id_no_permission(
        self, async_auth_client, async_db
    ):
        """project_id 过滤无权限：他人项目返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.get(
            f"/api/v1/self-healing/audits?project_id={other_project.id}"
        )
        assert resp.status_code == 403

    async def test_filter_by_test_case_id(
        self, async_auth_client, async_db, async_test_project
    ):
        """test_case_id 过滤：仅返回该用例的审计记录。"""
        case = await _create_case(async_db, async_test_project)
        audit = await _create_audit(async_db, case)

        resp = await async_auth_client.get(
            f"/api/v1/self-healing/audits?test_case_id={case.id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = [item["id"] for item in body["data"]["items"]]
        assert audit.id in ids
        for item in body["data"]["items"]:
            assert item["test_case_id"] == case.id

    async def test_pagination(
        self, async_auth_client, async_db, async_test_project
    ):
        """分页：page_size=2 时首页最多返回 2 条，total 反映总数。"""
        case = await _create_case(async_db, async_test_project)
        for i in range(5):
            await _create_audit(async_db, case, step_index=i)

        resp = await async_auth_client.get(
            "/api/v1/self-healing/audits?page=1&page_size=2"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]["items"]) <= 2
        assert body["data"]["page"] == 1
        assert body["data"]["page_size"] == 2
        assert body["data"]["total"] >= 5

        resp2 = await async_auth_client.get(
            "/api/v1/self-healing/audits?page=2&page_size=2"
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["data"]["page"] == 2

    async def test_unauthenticated_returns_401(self, async_client):
        """未认证请求返回 401 或 403。"""
        resp = await async_client.get("/api/v1/self-healing/audits")
        assert resp.status_code in (401, 403)


# ============================================================================
# 审计详情端点测试
# ============================================================================


class TestSelfHealingAuditDetail:
    """GET /api/v1/self-healing/audits/{audit_id} 审计详情。"""

    async def test_get_existing_audit(
        self, async_auth_client, async_db, async_test_project
    ):
        """存在的审计记录返回详情。"""
        case = await _create_case(async_db, async_test_project)
        audit = await _create_audit(async_db, case)

        resp = await async_auth_client.get(
            f"/api/v1/self-healing/audits/{audit.id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == audit.id
        assert body["data"]["test_case_id"] == case.id
        assert body["data"]["failure_type"] == "element_gone"
        assert body["data"]["strategy"] == "mcp"

    async def test_get_nonexistent_audit_404(self, async_auth_client):
        """不存在的审计记录返回 404。

        HTTPException 经 http_exception_handler 转为统一错误响应格式
        {"code","msg","message","data","timestamp"}，故断言 msg 字段。
        """
        resp = await async_auth_client.get(
            "/api/v1/self-healing/audits/99999999"
        )
        assert resp.status_code == 404
        assert "不存在" in resp.json()["msg"]


# ============================================================================
# 回滚端点测试
# ============================================================================


class TestSelfHealingRollback:
    """POST /api/v1/self-healing/audits/{audit_id}/rollback 回滚自愈变更。"""

    async def test_rollback_success(
        self, async_auth_client, async_db, async_test_project
    ):
        """回滚成功：恢复旧选择器，写入回滚审计。"""
        case = await _create_case(async_db, async_test_project)
        step = await _create_step(async_db, case)
        locator = await _create_locator(
            async_db, step, css_selector=".new-btn", version=1
        )
        audit = await _create_audit(
            async_db, case,
            locator_id=locator.id,
            old_selector=".old-btn",
            new_selector=".new-btn",
        )

        resp = await async_auth_client.post(
            f"/api/v1/self-healing/audits/{audit.id}/rollback"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["audit_id"] == audit.id
        assert body["data"]["restored_selector"] == ".old-btn"
        assert body["data"]["new_audit_id"] > 0

        # 验证定位器已恢复旧选择器。
        # rollback_audit 通过共享 sync session 执行原生 SQL UPDATE，
        # async_db 的 identity map 仍缓存 locator 旧值（.new-btn）。
        # 使用 populate_existing=True 强制用 DB 最新数据覆盖 identity map
        # 中已缓存对象的属性，避免读到陈旧值。不可用 expire_all()，否则
        # 后续访问 locator.id 会触发 sync 懒加载抛 MissingGreenlet。
        result = await async_db.execute(
            select(ElementLocator)
            .where(ElementLocator.id == locator.id)
            .execution_options(populate_existing=True)
        )
        updated_locator = result.scalar_one()
        assert updated_locator.css_selector == ".old-btn"

        # 验证回滚审计已写入
        result = await async_db.execute(
            select(SelfHealingAudit).where(
                SelfHealingAudit.id == body["data"]["new_audit_id"]
            )
        )
        rollback_audit = result.scalar_one()
        assert rollback_audit.strategy == "rollback"
        assert rollback_audit.new_selector == ".old-btn"

    async def test_rollback_nonexistent_404(self, async_auth_client):
        """回滚不存在的审计记录返回 404。"""
        resp = await async_auth_client.post(
            "/api/v1/self-healing/audits/99999999/rollback"
        )
        assert resp.status_code == 404
        assert "不存在" in resp.json()["msg"]

    async def test_rollback_empty_old_selector_400(
        self, async_auth_client, async_db, async_test_project
    ):
        """old_selector/locator_id 为空时返回 400。"""
        case = await _create_case(async_db, async_test_project)
        # 创建 old_selector=None 且 locator_id=None 的审计
        audit = await _create_audit(
            async_db, case,
            locator_id=None,
            old_selector=None,
            new_selector=None,
            failure_type="env_noise",
            strategy="skip",
        )

        resp = await async_auth_client.post(
            f"/api/v1/self-healing/audits/{audit.id}/rollback"
        )
        assert resp.status_code == 400
        assert "为空" in resp.json()["msg"]


# ============================================================================
# 项目自愈配置查询端点测试
# ============================================================================


class TestSelfHealingConfigGet:
    """GET /api/v1/projects/{project_id}/self-healing-config 查询配置。"""

    async def test_get_config_success(
        self, async_auth_client, async_test_project
    ):
        """成功查询配置：返回含 enabled/strategies/token_limit 的默认配置。"""
        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "enabled" in body["data"]
        assert "strategies" in body["data"]
        assert "token_limit" in body["data"]
        assert isinstance(body["data"]["strategies"], list)
        assert isinstance(body["data"]["token_limit"], int)

    async def test_get_config_nonexistent_project_403(
        self, async_auth_client
    ):
        """项目不存在时 _verify_project_owner 校验失败返回 403。"""
        resp = await async_auth_client.get(
            "/api/v1/projects/99999/self-healing-config"
        )
        assert resp.status_code == 403

    async def test_get_config_no_permission_403(
        self, async_auth_client, async_db
    ):
        """无权限访问他人项目返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.get(
            f"/api/v1/projects/{other_project.id}/self-healing-config"
        )
        assert resp.status_code == 403


# ============================================================================
# 项目自愈配置更新端点测试
# ============================================================================


class TestSelfHealingConfigUpdate:
    """PUT /api/v1/projects/{project_id}/self-healing-config 更新配置。"""

    async def test_update_config_success(
        self, async_auth_client, async_test_project
    ):
        """成功更新全部字段。"""
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config",
            json={
                "enabled": True,
                "strategies": ["mcp", "vision"],
                "token_limit": 3000,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["token_limit"] == 3000
        assert body["data"]["strategies"] == ["mcp", "vision"]

    async def test_partial_update_keeps_existing(
        self, async_auth_client, async_test_project
    ):
        """部分更新：仅传 token_limit，strategies 保持原值。"""
        # 先全量更新一次
        await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config",
            json={
                "enabled": True,
                "strategies": ["mcp", "vision"],
                "token_limit": 3000,
            },
        )
        # 部分更新
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config",
            json={"token_limit": 5000},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["token_limit"] == 5000
        # strategies 应保持原值
        assert body["data"]["strategies"] == ["mcp", "vision"]

    async def test_invalid_strategies_400(
        self, async_auth_client, async_test_project
    ):
        """非法 strategies 值返回 400（service 层校验）。"""
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config",
            json={"strategies": ["invalid_strategy"]},
        )
        assert resp.status_code == 400
        assert "strategies" in resp.json()["msg"] or "非法" in resp.json()["msg"]

    async def test_invalid_token_limit(
        self, async_auth_client, async_test_project
    ):
        """非法 token_limit（超出范围）被拒绝。

        Pydantic 层 ge=1/le=10000 会拦截返回 422；
        service 层 TOKEN_LIMIT_MIN/MAX 校验返回 400。
        端点层两者均视为拒绝。
        """
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config",
            json={"token_limit": 0},
        )
        assert resp.status_code in (400, 422)

    async def test_invalid_token_limit_exceed_max(
        self, async_auth_client, async_test_project
    ):
        """token_limit 超过上限 10000 被拒绝。"""
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config",
            json={"token_limit": 10001},
        )
        assert resp.status_code in (400, 422)

    async def test_no_permission_403(self, async_auth_client, async_db):
        """无权限更新他人项目配置返回 403。"""
        _, other_project = await _create_other_user_project(async_db)

        resp = await async_auth_client.put(
            f"/api/v1/projects/{other_project.id}/self-healing-config",
            json={"enabled": True},
        )
        assert resp.status_code == 403

    async def test_update_strategies_with_stagehand(
        self, async_auth_client, async_test_project
    ):
        """更新 strategies 包含 stagehand（合法值）成功。"""
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/self-healing-config",
            json={"strategies": ["mcp", "vision", "stagehand"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "stagehand" in body["data"]["strategies"]
