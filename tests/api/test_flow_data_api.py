"""
流程数据 API 端点测试

覆盖范围:
    - PUT  /api/v1/ui-prototype/flow/{project_id}  保存/更新/无权403
    - GET  /api/v1/ui-prototype/flow/{project_id}  查询已有数据/无数据返回空字典/无权403

采用直接调用端点协程的方式，绕过 TestClient 与 rate limit 中间件的兼容性问题。
401（无认证）和 422/400（空数据校验）分别由 FastAPI get_current_user 依赖和 Pydantic schema
层覆盖，在 schema 测试中已单独验证。

注意: 直接调用端点函数时，create_response 中的 data 为序列化后的 dict
（经过 _serialize_project_flow_data 处理），通过字典访问（["project_id"]）。
"""
import pytest
from fastapi import HTTPException, status

from app.api.v1.endpoints.ui_prototype.project_endpoints import save_flow_data, get_flow_data
from app.models.project import Project
from app.models.user import User
from app.schemas.ui_prototype import FlowDataSaveRequest
from app.utils.jwt_utils import get_password_hash


class _AsyncSessionWrapper:
    """轻量级 AsyncSession 包装器，仅委托 run_sync 给 sync Session。

    用于直接调用 async 端点函数（端点内部用 db.run_sync(fn) 执行同步查询）。
    """

    def __init__(self, sync_session) -> None:
        self._sync = sync_session

    async def run_sync(self, fn, *args, **kwargs):
        return fn(self._sync, *args, **kwargs)


@pytest.fixture
def api_project(db, testUser):
    """为测试创建属于 testUser 的项目"""
    project = Project(
        name="api_flow_proj",
        user_id=testUser.id,
        description="project for flow data API tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    return project


@pytest.fixture
def other_user(db):
    """创建另一个用户及其项目（用于 403 测试）"""
    user = User(
        username="api_flow_other_user",
        email="api_flow_other@test.com",
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()

    project = Project(
        name="api_flow_other_proj",
        user_id=user.id,
        description="another user's project",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()

    return {"user": user, "project": project}


def _make_request(project_id: int, flow_data: dict) -> FlowDataSaveRequest:
    return FlowDataSaveRequest(project_id=project_id, flow_data=flow_data)


# ==================== PUT /api/v1/ui-prototype/flow/{project_id} ====================


class TestPutFlowData:
    """PUT 保存流程数据端点测试"""

    @pytest.mark.asyncio
    async def test_save_returns_200(self, db, api_project, testUser):
        request = _make_request(api_project.id, {
            "nodes": [{"id": "1", "name": "登录"}],
            "edges": [{"from": "1", "to": "2"}],
        })
        response = await save_flow_data(
            project_id=api_project.id,
            flow_request=request,
            db=_AsyncSessionWrapper(db),
            current_user=testUser,
        )
        assert response["code"] == 200
        assert response["data"] is not None
        # 直接调用时 data 为序列化后的 dict，使用字典访问
        assert response["data"]["project_id"] == api_project.id

    @pytest.mark.asyncio
    async def test_update_returns_200(self, db, api_project, testUser):
        req1 = _make_request(api_project.id, {"nodes": [{"id": "a"}], "edges": []})
        r1 = await save_flow_data(
            project_id=api_project.id,
            flow_request=req1,
            db=_AsyncSessionWrapper(db),
            current_user=testUser,
        )
        assert r1["code"] == 200

        req2 = _make_request(api_project.id, {
            "nodes": [{"id": "b"}],
            "edges": [{"from": "b", "to": "c"}],
        })
        r2 = await save_flow_data(
            project_id=api_project.id,
            flow_request=req2,
            db=_AsyncSessionWrapper(db),
            current_user=testUser,
        )
        assert r2["code"] == 200
        assert r2["data"]["project_id"] == api_project.id

    @pytest.mark.asyncio
    async def test_body_project_id_is_optional(self, db, api_project, testUser):
        request = FlowDataSaveRequest(
            flow_data={
                "nodes": [{"id": "1", "name": "登录"}],
                "edges": [],
            }
        )
        response = await save_flow_data(
            project_id=api_project.id,
            flow_request=request,
            db=_AsyncSessionWrapper(db),
            current_user=testUser,
        )
        assert response["code"] == 200
        assert response["data"]["project_id"] == api_project.id

    @pytest.mark.asyncio
    async def test_mismatched_body_project_id_returns_400(self, db, api_project, testUser):
        request = _make_request(api_project.id + 1, {"nodes": [{"id": "1"}], "edges": []})
        with pytest.raises(HTTPException) as exc:
            await save_flow_data(
                project_id=api_project.id,
                flow_request=request,
                db=_AsyncSessionWrapper(db),
                current_user=testUser,
            )
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_wrong_user_returns_403(self, db, other_user, testUser):
        request = _make_request(other_user["project"].id, {"nodes": [{"id": "1"}], "edges": []})
        with pytest.raises(HTTPException) as exc:
            await save_flow_data(
                project_id=other_user["project"].id,
                flow_request=request,
                db=_AsyncSessionWrapper(db),
                current_user=testUser,
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== GET /api/v1/ui-prototype/flow/{project_id} ====================


class TestGetFlowData:
    """GET 查询流程数据端点测试"""

    @pytest.mark.asyncio
    async def test_returns_saved_data(self, db, api_project, testUser):
        # 先保存数据
        request = _make_request(api_project.id, {
            "nodes": [{"id": "1", "name": "首页"}],
            "edges": [{"from": "1", "to": "2"}],
        })
        await save_flow_data(
            project_id=api_project.id,
            flow_request=request,
            db=_AsyncSessionWrapper(db),
            current_user=testUser,
        )

        # 再查询
        response = await get_flow_data(
            project_id=api_project.id,
            db=_AsyncSessionWrapper(db),
            current_user=testUser,
        )
        assert response["code"] == 200
        assert response["data"] is not None
        assert response["data"]["project_id"] == api_project.id

    @pytest.mark.asyncio
    async def test_returns_null_when_no_data(self, db, api_project, testUser):
        response = await get_flow_data(
            project_id=api_project.id,
            db=_AsyncSessionWrapper(db),
            current_user=testUser,
        )
        assert response["code"] == 200
        # create_response 将 None 转为 {}
        assert response["data"] == {}
        assert response["msg"] == "暂无保存数据"

    @pytest.mark.asyncio
    async def test_wrong_user_returns_403(self, db, other_user, testUser):
        with pytest.raises(HTTPException) as exc:
            await get_flow_data(
                project_id=other_user["project"].id,
                db=_AsyncSessionWrapper(db),
                current_user=testUser,
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
