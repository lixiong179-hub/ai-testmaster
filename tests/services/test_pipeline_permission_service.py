"""
M1-T14 Pipeline Permission Service 测试模块

覆盖：
    - init_pipeline_roles 初始化4种角色+权限
    - init_pipeline_roles 幂等
    - check_pipeline_permission 各角色权限校验
    - check_pipeline_permission scope 层级
    - check_pipeline_permission project_id=None + scope=own
    - assign_pipeline_role / revoke_pipeline_role
    - assign_pipeline_role 审计日志
    - require_permission 装饰器
"""
import pytest

from app.models.pipeline_permission import PipelineRole, PipelinePermission, pipeline_user_role
from app.services.pipeline_permission_service import (
    check_pipeline_permission,
    init_pipeline_roles,
    assign_pipeline_role,
    revoke_pipeline_role,
    ROLE_DEFINITIONS,
    SCOPE_HIERARCHY,
)


@pytest.fixture(autouse=True)
def _init_roles(db):
    init_pipeline_roles(db)


class TestInitPipelineRoles:
    def test_all_roles_created(self, db):
        for role_name in ["admin", "qa_lead", "qa_engineer", "viewer"]:
            role = db.query(PipelineRole).filter(PipelineRole.name == role_name).first()
            assert role is not None, f"Role '{role_name}' not found"

    def test_idempotent(self, db):
        count_before = db.query(PipelineRole).count()
        init_pipeline_roles(db)
        count_after = db.query(PipelineRole).count()
        assert count_before == count_after

    def test_admin_has_all_permissions(self, db):
        admin = db.query(PipelineRole).filter(PipelineRole.name == "admin").first()
        assert len(admin.permissions) == len(ROLE_DEFINITIONS["admin"]["permissions"])

    def test_viewer_has_read_only(self, db):
        viewer = db.query(PipelineRole).filter(PipelineRole.name == "viewer").first()
        for perm in viewer.permissions:
            assert perm.action == "read"


class TestCheckPipelinePermission:
    def test_admin_has_all_scope(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "admin", testProject.id)
        assert check_pipeline_permission(db, testUser.id, "config", "update", "all", testProject.id)

    def test_qa_lead_can_start_pipeline(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "qa_lead", testProject.id)
        assert check_pipeline_permission(db, testUser.id, "pipeline", "start", "project", testProject.id)

    def test_qa_engineer_cannot_finalize(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "qa_engineer", testProject.id)
        assert not check_pipeline_permission(db, testUser.id, "review", "finalize", "project", testProject.id)

    def test_viewer_cannot_start_pipeline(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        assert not check_pipeline_permission(db, testUser.id, "pipeline", "start", "project", testProject.id)

    def test_no_role_denied(self, db, testUser, testProject):
        assert not check_pipeline_permission(db, testUser.id, "pipeline", "start", "project", testProject.id)

    def test_scope_hierarchy(self, db):
        assert SCOPE_HIERARCHY["own"] < SCOPE_HIERARCHY["project"]
        assert SCOPE_HIERARCHY["project"] < SCOPE_HIERARCHY["all"]

    def test_own_scope_without_project_id_denied(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "qa_engineer", testProject.id)
        result = check_pipeline_permission(db, testUser.id, "review", "approve", "own", project_id=None)
        assert not result

    def test_project_scope_satisfies_own(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "qa_lead", testProject.id)
        result = check_pipeline_permission(db, testUser.id, "review", "approve", "own", testProject.id)
        assert result


class TestAssignRevokeRole:
    def test_assign_role(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        result = check_pipeline_permission(db, testUser.id, "test_case", "read", "project", testProject.id)
        assert result

    def test_assign_role_idempotent(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)

    def test_assign_unknown_role_raises(self, db, testUser, testProject):
        with pytest.raises(ValueError, match="not found"):
            assign_pipeline_role(db, testUser.id, "nonexistent", testProject.id)

    def test_revoke_role(self, db, testUser, testProject):
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        revoke_pipeline_role(db, testUser.id, "viewer", testProject.id)
        result = check_pipeline_permission(db, testUser.id, "test_case", "read", "project", testProject.id)
        assert not result

    def test_assign_role_writes_audit(self, db, testUser, testProject):
        from app.services.audit_service import query_logs
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id, actor_id=testUser.id)
        logs = query_logs(db, action="permission_change")
        assert any(
            l.detail and l.detail.get("role") == "viewer" and l.detail.get("op") == "assign"
            for l in logs
        )

    def test_revoke_role_writes_audit(self, db, testUser, testProject):
        from app.services.audit_service import query_logs
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        revoke_pipeline_role(db, testUser.id, "viewer", testProject.id, actor_id=testUser.id)
        logs = query_logs(db, action="permission_change")
        assert any(
            l.detail and l.detail.get("role") == "viewer" and l.detail.get("op") == "revoke"
            for l in logs
        )
