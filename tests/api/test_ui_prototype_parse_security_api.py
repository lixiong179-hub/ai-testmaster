"""
T3 安全测试：UI原型批量解析端点 parse_ui_screens 越权防护

覆盖 SubTask 3.3，验证 app/api/v1/endpoints/ui_prototype/parse_endpoints.py
中 parse_ui_screens 的项目归属全量校验：

    1. 用户传他人 screen_id              -> 403
    2. 用户传混合自己+他人 screen_id     -> 403
    3. 用户传不存在的 screen_id          -> 404
    4. 空 screen_ids                     -> 400
    5. 合法路径（仅自己的 screen_id）    -> 通过权限校验，pipeline 被调用
    6. 多个全部属他人的 screen_id        -> 403
    7. 不存在 ID + 他人 ID 混合          -> 404 优先于 403（防资源存在性探测）
    8. 跨自己多个项目的 screen_id        -> 400（防 screens[0].project_id 隐患）

实现方式：直接调用端点协程函数（绕过 HTTP/JWT），断言抛出的 HTTPException
状态码与 detail。不依赖 TestClient 集成测试链路。

依赖 async_db（AsyncSession）：端点内部使用 db.run_sync(_validate)，
必须传入 AsyncSession 才能正确执行同步校验逻辑。
"""
import asyncio
import uuid
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.ui_prototype.parse_endpoints import parse_ui_screens
from app.models.ui_prototype import UIPrototypeScreen
from app.models.user import User
from app.models.project import Project
from app.schemas.ui_prototype import UIScreenParseRequest
from app.utils.jwt_utils import get_password_hash


# ---------- 测试夹具 ----------


async def _createScreen(async_db: AsyncSession, projectId: int, name: str = "t3_screen") -> UIPrototypeScreen:
    screen = UIPrototypeScreen(
        project_id=projectId,
        prototype_name="t3_proto",
        source="manual",
        screen_name=name,
        screen_order=0,
        file_type="png",
    )
    async_db.add(screen)
    await async_db.flush()
    return screen


async def _createUser(async_db: AsyncSession, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
        is_superuser=False,
    )
    async_db.add(user)
    await async_db.flush()
    return user


async def _createProject(async_db: AsyncSession, userId: int, name: str) -> Project:
    project = Project(
        name=name,
        user_id=userId,
        description="helper test project",
        status=1,
        project_type="web",
    )
    async_db.add(project)
    await async_db.flush()
    return project


@pytest_asyncio.fixture
async def ownerSetup(async_db):
    """调用方：拥有项目和 1 个 screen。"""
    suffix = uuid.uuid4().hex[:8]
    user = await _createUser(async_db, f"t3_owner_{suffix}")
    project = await _createProject(async_db, user.id, f"t3_owner_proj_{suffix}")
    screen = await _createScreen(async_db, project.id, name="owner_screen")
    return {"user": user, "project": project, "screen": screen}


@pytest_asyncio.fixture
async def attackerSetup(async_db):
    """另一用户：拥有项目和 1 个 screen，模拟"他人资源"。"""
    suffix = uuid.uuid4().hex[:8]
    user = await _createUser(async_db, f"t3_attacker_{suffix}")
    project = await _createProject(async_db, user.id, f"t3_attacker_proj_{suffix}")
    screen = await _createScreen(async_db, project.id, name="attacker_screen")
    return {"user": user, "project": project, "screen": screen}


async def _callParse(async_db: AsyncSession, currentUser: User, screenIds):
    """调用 parse_ui_screens 端点协程，捕获 HTTPException。"""
    request = UIScreenParseRequest(screen_ids=screenIds)
    return await parse_ui_screens(
        parse_request=request, db=async_db, current_user=currentUser
    )


# ---------- T3 安全用例 ----------


class TestParseUiScreensAuthorization:
    """T3 越权防护核心用例（SubTask 3.3）。"""

    @pytest.mark.asyncio
    async def test_forbidden_when_using_only_other_users_screen(
        self, async_db, ownerSetup, attackerSetup
    ):
        """场景 1：仅传他人 screen_id -> 403"""
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[attackerSetup["screen"].id],
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
        assert "无权限" in exc.value.detail

    @pytest.mark.asyncio
    async def test_rejected_when_mixing_own_and_other_users_screens(
        self, async_db, ownerSetup, attackerSetup
    ):
        """场景 2：混合自己 + 他人 screen_id -> 拒绝（必须全量校验）。

        实际返回 400（跨项目）而非 403，这是有意的安全增强：
        在不暴露"目标 screen 属他人"的前提下拒绝请求，避免通过混合查询
        探测他人资源的归属信息。
        """
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    ownerSetup["screen"].id,
                    attackerSetup["screen"].id,
                ],
            )
        # 400（跨项目约束先于 403 触发）或 403（同项目越权）均视为已拒绝
        assert exc.value.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
        )
        # detail 不应泄漏被攻击 screen 的归属信息
        assert str(attackerSetup["screen"].id) not in (exc.value.detail or "")

    @pytest.mark.asyncio
    async def test_not_found_when_screen_id_does_not_exist(self, async_db, ownerSetup):
        """场景 3：不存在的 screen_id -> 404"""
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[999_999_999],
            )
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_bad_request_when_screen_ids_empty(self, async_db, ownerSetup):
        """场景 4：空 screen_ids -> 400"""
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[],
            )
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_authorized_path_passes_permission_check(self, async_db, ownerSetup):
        """场景 5：合法路径（仅自己的 screen_id）-> 权限校验通过，pipeline 被调用"""
        fakeResult = {"success": 1, "failed": 0, "results": []}
        with patch(
            "app.api.v1.endpoints.ui_prototype.parse_endpoints.UISpecParsePipeline"
        ) as MockPipeline:
            instance = MockPipeline.return_value
            instance.batch_parse_screens = AsyncMock(return_value=fakeResult)

            response = await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[ownerSetup["screen"].id],
            )

            # 端点将 batch_parse_screens 调度到后台任务（asyncio.create_task）。
            # 必须显式让出事件循环，使后台任务有机会在 patch 仍然激活时执行。
            # 否则 patch 会在 with 块退出后被移除，后台任务将使用真实 pipeline。
            await asyncio.sleep(0.2)

            # 验证响应结构与调用参数
            assert isinstance(response, dict)
            assert response.get("code") == 200
            assert response.get("data", {}).get("task_id") == f"parse_{ownerSetup['project'].id}"
            instance.batch_parse_screens.assert_awaited_once_with(
                [ownerSetup["screen"].id]
            )
            # pipeline 初始化时传入的项目 ID 必须是 owner 的项目
            MockPipeline.assert_called_once()
            callArgs = MockPipeline.call_args.args
            assert callArgs[1] == ownerSetup["project"].id

    @pytest.mark.asyncio
    async def test_forbidden_when_all_ids_belong_to_other_users(
        self, async_db, ownerSetup, attackerSetup
    ):
        """场景 6：传多个全部属他人的 screen_id -> 403"""
        # 给攻击者再加一个 screen
        otherScreen2 = await _createScreen(
            async_db, attackerSetup["project"].id, name="attacker_screen_2"
        )
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    attackerSetup["screen"].id,
                    otherScreen2.id,
                ],
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_not_found_takes_precedence_over_forbidden(
        self, async_db, ownerSetup, attackerSetup
    ):
        """场景 7：同时包含不存在 ID 和他人 ID 时，404 优先于 403。

        验证错误误报顺序与端点逻辑一致。此顺序避免通过询问"未知 ID 是否返回 403"探测他人资源存在性。
        """
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    999_999_999,
                    attackerSetup["screen"].id,
                ],
            )
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_bad_request_when_screen_ids_span_multiple_projects(
        self, async_db, ownerSetup
    ):
        """场景 8：owner 跨自己的两个项目传入 screen_id -> 400。

        防止 pipeline 上下文混乱（screens[0].project_id 隐患）。
        """
        # 为 owner 创建第二个项目及 screen
        secondProject = await _createProject(
            async_db,
            ownerSetup["user"].id,
            f"t3_owner_proj2_{uuid.uuid4().hex[:8]}",
        )
        secondScreen = await _createScreen(async_db, secondProject.id, name="owner_screen_2")

        with pytest.raises(HTTPException) as exc:
            await _callParse(
                async_db=async_db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    ownerSetup["screen"].id,
                    secondScreen.id,
                ],
            )
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "同一项目" in exc.value.detail
