"""项目成员管理端点集成测试。

覆盖 /api/v1/projects/{project_id}/members 下 5 个端点:
    - POST   /members                    添加成员
    - GET    /members                    成员列表
    - PUT    /members/{user_id}          修改角色
    - DELETE /members/{user_id}          移除成员
    - POST   /transfer-ownership         转让所有权

使用 async_auth_client 真实 HTTP 调用, 测试数据经 async_db 共享事务,
覆盖正常/权限/异常/边界场景。用例执行后随 async_db rollback 自动清理。
"""
import uuid

from sqlalchemy import select

from app.models.project_member import ProjectMember
from app.models.user import User
from app.utils.jwt_utils import get_password_hash


# ── 测试数据辅助函数 ──


async def _create_other_user(async_db, *, is_superuser=False) -> User:
    """创建另一个用户并 flush, 用于成员管理测试。"""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"member_test_{suffix}",
        email=f"member_test_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"),
        is_active=True,
        is_superuser=is_superuser,
    )
    async_db.add(user)
    await async_db.flush()
    return user


async def _add_member(async_db, project_id, user_id, role="member") -> ProjectMember:
    """通过 async_db 直接创建成员记录。"""
    member = ProjectMember(
        project_id=project_id, user_id=user_id, role=role,
    )
    async_db.add(member)
    await async_db.flush()
    return member


# ── 1. POST /projects/{project_id}/members 添加成员 ──


class TestAddProjectMember:
    async def test_add_member_success(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """owner 添加新成员成功。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/members",
            json={"user_id": other_user.id, "role": "member"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["user_id"] == other_user.id
        assert data["role"] == "member"
        assert data["username"] == other_user.username
        assert data["project_id"] == async_test_project.id

    async def test_add_member_with_admin_role(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """admin 也可以添加成员。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "admin",
        )
        other_user = await _create_other_user(async_db)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/members",
            json={"user_id": other_user.id, "role": "viewer"},
        )
        assert resp.status_code == 201

    async def test_add_member_as_member_forbidden(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """普通 member 无权添加成员。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "member",
        )
        other_user = await _create_other_user(async_db)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/members",
            json={"user_id": other_user.id, "role": "member"},
        )
        assert resp.status_code == 403

    async def test_add_member_with_owner_role_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """不能直接添加 owner 角色。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/members",
            json={"user_id": other_user.id, "role": "owner"},
        )
        assert resp.status_code == 400
        assert "transfer-ownership" in resp.json()["msg"]

    async def test_add_member_duplicate(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """重复添加成员返回 400。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/members",
            json={"user_id": other_user.id, "role": "member"},
        )
        assert resp.status_code == 400
        assert "已存在" in resp.json()["msg"]

    async def test_add_member_nonexistent_user(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """添加不存在的用户返回 404。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/members",
            json={"user_id": 999999, "role": "member"},
        )
        assert resp.status_code == 404

    async def test_add_member_nonexistent_project(
        self, async_auth_client
    ):
        """项目不存在返回 404。"""
        resp = await async_auth_client.post(
            "/api/v1/projects/999999/members",
            json={"user_id": 1, "role": "member"},
        )
        assert resp.status_code == 404

    async def test_add_member_invalid_role(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """非法角色返回 400。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/members",
            json={"user_id": other_user.id, "role": "superadmin"},
        )
        assert resp.status_code == 400


# ── 2. GET /projects/{project_id}/members 成员列表 ──


class TestListProjectMembers:
    async def test_list_members_success(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """查询成员列表成功。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/members",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        members = body["data"]
        assert len(members) == 2
        usernames = {m["username"] for m in members}
        assert async_test_user.username in usernames
        assert other_user.username in usernames

    async def test_list_members_as_viewer_allowed(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """viewer 也能查看成员列表。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "viewer",
        )
        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/members",
        )
        assert resp.status_code == 200

    async def test_list_members_non_member_forbidden(
        self, async_auth_client, async_db, async_test_project
    ):
        """非成员无权查看。"""
        # 不添加任何成员记录，async_test_user 也没有 ProjectMember 记录
        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/members",
        )
        assert resp.status_code == 403

    async def test_list_members_nonexistent_project(
        self, async_auth_client
    ):
        """项目不存在返回 404。"""
        resp = await async_auth_client.get(
            "/api/v1/projects/999999/members",
        )
        assert resp.status_code == 404


# ── 3. PUT /projects/{project_id}/members/{user_id} 修改角色 ──


class TestUpdateMemberRole:
    async def test_update_role_success(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """owner 修改成员角色成功。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
            json={"role": "admin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["role"] == "admin"

    async def test_update_role_to_owner_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """不能直接将成员升级为 owner。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
            json={"role": "owner"},
        )
        assert resp.status_code == 400

    async def test_update_self_role_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """不能修改自己的角色。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "admin",
        )
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/members/{async_test_user.id}",
            json={"role": "viewer"},
        )
        assert resp.status_code == 400
        assert "自己" in resp.json()["msg"]

    async def test_update_owner_role_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """不能直接降级 owner。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "owner",
        )

        # async_test_user 是 owner，但不能修改 other_user 的 owner 角色
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
            json={"role": "admin"},
        )
        assert resp.status_code == 400
        assert "owner" in resp.json()["msg"]

    async def test_update_role_member_nonexistent(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """修改不存在的成员返回 404。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        # other_user 不是项目成员
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
            json={"role": "admin"},
        )
        assert resp.status_code == 404

    async def test_update_role_invalid_role(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """非法角色返回 400。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
            json={"role": "superadmin"},
        )
        assert resp.status_code == 400

    async def test_update_role_as_member_forbidden(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """member 无权修改他人角色。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "member",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
            json={"role": "admin"},
        )
        assert resp.status_code == 403


# ── 4. DELETE /projects/{project_id}/members/{user_id} 移除成员 ──


class TestRemoveProjectMember:
    async def test_remove_member_success(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """owner 移除成员成功。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
        )
        assert resp.status_code == 200

        # 验证成员已被移除
        result = await async_db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == async_test_project.id,
                ProjectMember.user_id == other_user.id,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_remove_self_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """不能移除自己。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "admin",
        )
        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/members/{async_test_user.id}",
        )
        assert resp.status_code == 400
        assert "自己" in resp.json()["msg"]

    async def test_remove_owner_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """不能移除 owner。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "owner",
        )

        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
        )
        assert resp.status_code == 400
        assert "owner" in resp.json()["msg"]

    async def test_remove_member_nonexistent(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """移除不存在的成员返回 404。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
        )
        assert resp.status_code == 404

    async def test_remove_member_as_member_forbidden(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """member 无权移除成员。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "member",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )
        resp = await async_auth_client.delete(
            f"/api/v1/projects/{async_test_project.id}/members/{other_user.id}",
        )
        assert resp.status_code == 403


# ── 5. POST /projects/{project_id}/transfer-ownership 转让所有权 ──


class TestTransferOwnership:
    async def test_transfer_ownership_success(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """owner 转让所有权成功, 原 owner 降级为 admin。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )

        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/transfer-ownership",
            json={"new_owner_user_id": other_user.id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["user_id"] == other_user.id
        assert body["data"]["role"] == "owner"

        # 验证原 owner 已降级为 admin
        result = await async_db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == async_test_project.id,
                ProjectMember.user_id == async_test_user.id,
            )
        )
        former_owner = result.scalar_one()
        assert former_owner.role == "admin"

    async def test_transfer_ownership_as_admin_forbidden(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """admin 无权转让所有权。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "admin",
        )
        other_user = await _create_other_user(async_db)
        await _add_member(
            async_db, async_test_project.id, other_user.id, "member",
        )
        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/transfer-ownership",
            json={"new_owner_user_id": other_user.id},
        )
        assert resp.status_code == 403

    async def test_transfer_to_self_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """不能转让给自己。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/transfer-ownership",
            json={"new_owner_user_id": async_test_user.id},
        )
        assert resp.status_code == 400
        assert "自己" in resp.json()["msg"]

    async def test_transfer_to_non_member_rejected(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """目标用户不是项目成员返回 404。"""
        await _add_member(
            async_db, async_test_project.id, async_test_user.id, "owner",
        )
        other_user = await _create_other_user(async_db)
        # other_user 未添加为项目成员
        resp = await async_auth_client.post(
            f"/api/v1/projects/{async_test_project.id}/transfer-ownership",
            json={"new_owner_user_id": other_user.id},
        )
        assert resp.status_code == 404
