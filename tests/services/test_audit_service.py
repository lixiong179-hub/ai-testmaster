"""
M1-T16 Audit Service 测试模块

覆盖：
    - log_action 正常写入
    - log_action 非法 action 抛 ValueError
    - query_logs 多维度过滤
    - count_logs 统计
    - AuditLog 不可变性（UPDATE/DELETE 抛 RuntimeError）
    - _build_filters 共享逻辑
"""
import pytest
from datetime import timedelta

from app.utils.db_time import utcnow

from app.models.audit_log import AuditLog
from app.services.audit_service import (
    log_action,
    query_logs,
    count_logs,
    _build_filters,
    VALID_ACTIONS,
)


class TestLogAction:
    def test_log_action_success(self, db, testUser):
        record = log_action(
            db=db,
            action="lifecycle_transition",
            actor_id=testUser.id,
            target_kind="test_case",
            target_id=1,
            detail={"from": "draft", "to": "active"},
        )
        assert record.id is not None
        assert record.action == "lifecycle_transition"
        assert record.actor_id == testUser.id
        assert record.target_kind == "test_case"
        assert record.target_id == 1
        assert record.detail == {"from": "draft", "to": "active"}

    def test_log_action_invalid_action_raises(self, db):
        with pytest.raises(ValueError, match="Invalid audit action"):
            log_action(
                db=db,
                action="invalid_action",
                actor_id=None,
                target_kind="test_case",
                target_id=1,
            )

    def test_log_action_with_optional_fields(self, db, testUser):
        record = log_action(
            db=db,
            action="pipeline_start",
            actor_id=testUser.id,
            target_kind="pipeline_run",
            target_id=42,
            run_id=None,
            iteration_id=None,
        )
        assert record.run_id is None
        assert record.iteration_id is None

    def test_log_action_actor_id_none(self, db):
        record = log_action(
            db=db,
            action="config_change",
            actor_id=None,
            target_kind="pipeline_config",
            target_id=1,
        )
        assert record.actor_id is None


class TestQueryLogs:
    def test_query_all(self, db, testUser):
        log_action(db, "lifecycle_transition", testUser.id, "test_case", 1)
        log_action(db, "config_change", testUser.id, "pipeline_config", 1)
        results = query_logs(db)
        assert len(results) >= 2

    def test_query_by_target_kind(self, db, testUser):
        log_action(db, "lifecycle_transition", testUser.id, "test_case", 99)
        results = query_logs(db, target_kind="test_case")
        assert all(r.target_kind == "test_case" for r in results)

    def test_query_by_action(self, db, testUser):
        log_action(db, "review_decide", testUser.id, "review", 1)
        results = query_logs(db, action="review_decide")
        assert all(r.action == "review_decide" for r in results)

    def test_query_by_actor(self, db, testUser):
        log_action(db, "pipeline_start", testUser.id, "pipeline_run", 1)
        results = query_logs(db, actor_id=testUser.id)
        assert all(r.actor_id == testUser.id for r in results)

    def test_query_by_time_range(self, db, testUser):
        now = utcnow()
        log_action(db, "config_change", testUser.id, "pipeline_config", 1)
        since = now - timedelta(hours=1)
        until = now + timedelta(hours=1)
        results = query_logs(db, since=since, until=until)
        assert len(results) >= 1

    def test_query_limit_and_offset(self, db, testUser):
        for i in range(5):
            log_action(db, "lifecycle_transition", testUser.id, "test_case", i)
        page1 = query_logs(db, limit=2, offset=0)
        page2 = query_logs(db, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2

    def test_query_limit_capped_at_500(self, db):
        results = query_logs(db, limit=9999)
        assert len(results) <= 500


class TestCountLogs:
    def test_count_all(self, db, testUser):
        log_action(db, "lifecycle_transition", testUser.id, "test_case", 1)
        log_action(db, "config_change", testUser.id, "pipeline_config", 1)
        total = count_logs(db)
        assert total >= 2

    def test_count_by_action(self, db, testUser):
        log_action(db, "pipeline_start", testUser.id, "pipeline_run", 1)
        total = count_logs(db, action="pipeline_start")
        assert total >= 1


class TestImmutability:
    def test_update_audit_log_raises(self, db, testUser):
        record = log_action(db, "lifecycle_transition", testUser.id, "test_case", 1)
        record.action = "tampered"
        with pytest.raises(RuntimeError, match="UPDATE on audit_log is forbidden"):
            db.flush()

    def test_delete_audit_log_raises(self, db, testUser):
        record = log_action(db, "config_change", testUser.id, "pipeline_config", 1)
        db.delete(record)
        with pytest.raises(RuntimeError, match="DELETE on audit_log is forbidden"):
            db.flush()


class TestBuildFilters:
    def test_empty_filters(self):
        filters = _build_filters()
        assert filters == []

    def test_all_filters(self):
        now = utcnow()
        filters = _build_filters(
            target_kind="test_case",
            target_id=1,
            actor_id=2,
            action="lifecycle_transition",
            since=now,
            until=now,
        )
        assert len(filters) == 6


class TestValidActions:
    def test_all_expected_actions_present(self):
        expected = {
            "lifecycle_transition", "capability_archive", "capability_deprecate",
            "capability_status_change", "review_decide", "review_rollback", "review_undo", "review_finalize",
            "pipeline_start", "pipeline_step_complete", "pipeline_pause",
            "pipeline_resume", "pipeline_cancel", "pipeline_cancel_timeout",
            "permission_change", "config_change", "case_version_create",
            "locator_version_create", "force_cancel_review",
        }
        assert expected == VALID_ACTIONS
