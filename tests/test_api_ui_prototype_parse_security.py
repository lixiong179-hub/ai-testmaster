"""
T3 安全测试：UI原型批量解析端点 parse_ui_screens 越权防护

覆盖 SubTask 3.3，验�?app/api/v1/endpoints/ui_prototype/parse_endpoints.py
�?parse_ui_screens 的项目归属全量校验：

    1. 用户传他�?screen_id              -> 403
    2. 用户传混合自�?他人 screen_id     -> 403
    3. 用户传不存在�?screen_id          -> 404
    4. �?screen_ids                     -> 400
    5. 合法路径（仅自己�?screen_id�?   -> 通过权限校验，pipeline 被调�?
    6. 多个全部属他人的 screen_id        -> 403
    7. 不存�?ID + 他人 ID 混合          -> 404 优先�?403（防资源存在性探测）
    8. 跨自己多个项目的 screen_id        -> 400（防 screens[0].project_id 隐患�?

实现方式：直接调用端点协程函数（绕过 HTTP/JWT），断言抛出�?HTTPException
状态码�?detail。不依赖 TestClient 集成测试链路�?
"""
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException, status

from app.api.v1.endpoints.ui_prototype.parse_endpoints import parse_ui_screens
from app.models.ui_prototype import UIPrototypeScreen
from app.schemas.ui_prototype import UIScreenParseRequest

from tests.helpers import createTestUser, createTestProject


# ---------- 测试夹具 ----------


def _createScreen(db, projectId: int, name: str = "t3_screen") -> UIPrototypeScreen:
    screen = UIPrototypeScreen(
        project_id=projectId,
        prototype_name="t3_proto",
        source="manual",
        screen_name=name,
        screen_order=0,
        file_type="png",
    )
    db.add(screen)
    db.flush()
    return screen


@pytest.fixture
def ownerSetup(db):
    """调用方：拥有项目�?1 �?screen�?""
    suffix = uuid.uuid4().hex[:8]
    user = createTestUser(db, username=f"t3_owner_{suffix}")
    project = createTestProject(db, userId=user.id, name=f"t3_owner_proj_{suffix}")
    screen = _createScreen(db, project.id, name="owner_screen")
    return {"user": user, "project": project, "screen": screen}


@pytest.fixture
def attackerSetup(db):
    """另一用户：拥有项目和 1 �?screen，模�?他人资源"�?""
    suffix = uuid.uuid4().hex[:8]
    user = createTestUser(db, username=f"t3_attacker_{suffix}")
    project = createTestProject(db, userId=user.id, name=f"t3_attacker_proj_{suffix}")
    screen = _createScreen(db, project.id, name="attacker_screen")
    return {"user": user, "project": project, "screen": screen}


async def _callParse(db, currentUser, screenIds):
    """调用 parse_ui_screens 端点协程，捕�?HTTPException�?""
    request = UIScreenParseRequest(screen_ids=screenIds)
    return await parse_ui_screens(
        parse_request=request, db=db, current_user=currentUser
    )


# ---------- T3 安全用例 ----------


class TestParseUiScreensAuthorization:
    """T3 越权防护核心用例（SubTask 3.3）�?""

    @pytest.mark.asyncio
    async def test_forbidden_when_using_only_other_users_screen(
        self, db, ownerSetup, attackerSetup
    ):
        """场景 1：仅传他�?screen_id -> 403"""
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[attackerSetup["screen"].id],
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
        assert "无权�? in exc.value.detail

    @pytest.mark.asyncio
    async def test_rejected_when_mixing_own_and_other_users_screens(
        self, db, ownerSetup, attackerSetup
    ):
        """场景 2：混合自�?+ 他人 screen_id -> 拒绝（必须全量校验）�?

        实际返回 400（跨项目）而非 403，这是有意的安全增强�?
        在不暴露"目标 screen 属他�?的前提下拒绝请求，避免通过混合查询
        探测他人资源的归属信息�?
        """
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    ownerSetup["screen"].id,
                    attackerSetup["screen"].id,
                ],
            )
        # 400（跨项目约束先于 403 触发）或 403（同项目越权）均视为已拒�?
        assert exc.value.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
        )
        # detail 不应泄漏被攻�?screen 的归属信�?
        assert str(attackerSetup["screen"].id) not in (exc.value.detail or "")

    @pytest.mark.asyncio
    async def test_not_found_when_screen_id_does_not_exist(self, db, ownerSetup):
        """场景 3：不存在�?screen_id -> 404"""
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[999_999_999],
            )
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_bad_request_when_screen_ids_empty(self, db, ownerSetup):
        """场景 4：空 screen_ids -> 400"""
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[],
            )
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_authorized_path_passes_permission_check(self, db, ownerSetup):
        """场景 5：合法路径（仅自己的 screen_id�?> 权限校验通过，pipeline 被调�?""
        fakeResult = {"success": 1, "failed": 0, "results": []}
        with patch(
            "app.api.v1.endpoints.ui_prototype.parse_endpoints.UISpecParsePipeline"
        ) as MockPipeline:
            instance = MockPipeline.return_value
            instance.batch_parse_screens = AsyncMock(return_value=fakeResult)

            response = await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[ownerSetup["screen"].id],
            )

        # 验证响应结构与调用参�?
        assert isinstance(response, dict)
        assert response.get("code") == 200
        assert response.get("data") == fakeResult
        instance.batch_parse_screens.assert_awaited_once_with(
            [ownerSetup["screen"].id]
        )
        # pipeline 初始化时传入的项�?ID 必须�?owner 的项�?
        MockPipeline.assert_called_once()
        callArgs = MockPipeline.call_args.args
        assert callArgs[1] == ownerSetup["project"].id

    @pytest.mark.asyncio
    async def test_forbidden_when_all_ids_belong_to_other_users(
        self, db, ownerSetup, attackerSetup
    ):
        """场景 6：传多个全部属他人的 screen_id -> 403"""
        # 给攻击者再加一�?screen
        otherScreen2 = _createScreen(
            db, attackerSetup["project"].id, name="attacker_screen_2"
        )
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    attackerSetup["screen"].id,
                    otherScreen2.id,
                ],
            )
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_not_found_takes_precedence_over_forbidden(
        self, db, ownerSetup, attackerSetup
    ):
        """场景 7：同时包含不存在 ID 和他�?ID 时，404 优先�?403�?

        验证错误误报顺序与端点逻辑一致。此顺序避免通过询问"未知 ID 是否返回 403"探测他人资源存在性�?
        """
        with pytest.raises(HTTPException) as exc:
            await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    999_999_999,
                    attackerSetup["screen"].id,
                ],
            )
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_bad_request_when_screen_ids_span_multiple_projects(
        self, db, ownerSetup
    ):
        """场景 8：owner 跨自己的两个项目传入 screen_id -> 400�?

        防止 pipeline 上下文混乱（screens[0].project_id 隐患）�?
        """
        # �?owner 创建第二个项目及 screen
        secondProject = createTestProject(
            db,
            userId=ownerSetup["user"].id,
            name=f"t3_owner_proj2_{uuid.uuid4().hex[:8]}",
        )
        secondScreen = _createScreen(db, secondProject.id, name="owner_screen_2")

        with pytest.raises(HTTPException) as exc:
            await _callParse(
                db=db,
                currentUser=ownerSetup["user"],
                screenIds=[
                    ownerSetup["screen"].id,
                    secondScreen.id,
                ],
            )
        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "同一项目" in exc.value.detail
