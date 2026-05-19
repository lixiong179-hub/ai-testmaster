import pytest
from app.services.pipeline_permission_service import (
    check_pipeline_permission,
    init_pipeline_roles,
    assign_pipeline_role,
    revoke_pipeline_role,
    ROLE_DEFINITIONS,
    SCOPE_HIERARCHY,
)
from app.models.pipeline_permission import PipelineRole, PipelinePermission


class TestInitPipelineRoles:
    def test_init_creates_roles(self, db):
        init_pipeline_roles(db)
        for role_name in ROLE_DEFINITIONS:
            role = db.query(PipelineRole).filter(PipelineRole.name == role_name).first()
            assert role is not None

    def test_init_idempotent(self, db):
        init_pipeline_roles(db)
        init_pipeline_roles(db)
        count = db.query(PipelineRole).count()
        assert count == len(ROLE_DEFINITIONS)


class TestAssignPipelineRole:
    def test_assign_role(self, db, testUser, testProject):
        init_pipeline_roles(db)
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        assert check_pipeline_permission(
            db, testUser.id, "test_case", "read", "project", testProject.id,
        ) is True

    def test_assign_nonexistent_role_raises(self, db, testUser, testProject):
        with pytest.raises(ValueError, match="not found"):
            assign_pipeline_role(db, testUser.id, "nonexistent_role", testProject.id)

    def test_assign_idempotent(self, db, testUser, testProject):
        init_pipeline_roles(db)
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)


class TestRevokePipelineRole:
    def test_revoke_role(self, db, testUser, testProject):
        init_pipeline_roles(db)
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        revoke_pipeline_role(db, testUser.id, "viewer", testProject.id)
        assert check_pipeline_permission(
            db, testUser.id, "test_case", "read", "project", testProject.id,
        ) is False

    def test_revoke_nonexistent_role_raises(self, db, testUser, testProject):
        with pytest.raises(ValueError, match="not found"):
            revoke_pipeline_role(db, testUser.id, "nonexistent_role", testProject.id)


class TestCheckPipelinePermission:
    def test_admin_has_all_permissions(self, db, testUser, testProject):
        init_pipeline_roles(db)
        assign_pipeline_role(db, testUser.id, "admin", testProject.id)
        assert check_pipeline_permission(
            db, testUser.id, "iteration", "create", "all", testProject.id,
        ) is True

    def test_viewer_no_write_permission(self, db, testUser, testProject):
        init_pipeline_roles(db)
        assign_pipeline_role(db, testUser.id, "viewer", testProject.id)
        assert check_pipeline_permission(
            db, testUser.id, "iteration", "create", "project", testProject.id,
        ) is False

    def test_no_role_no_permission(self, db, testUser, testProject):
        init_pipeline_roles(db)
        assert check_pipeline_permission(
            db, testUser.id, "iteration", "create", "project", testProject.id,
        ) is False


class TestScopeHierarchy:
    def test_scope_ordering(self):
        assert SCOPE_HIERARCHY["own"] < SCOPE_HIERARCHY["project"]
        assert SCOPE_HIERARCHY["project"] < SCOPE_HIERARCHY["all"]
