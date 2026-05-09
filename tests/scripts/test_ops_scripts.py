"""运维脚本单元测试 �?真实 DB，零 Mock

覆盖 archive_iterations / cleanup_audit_logs / backup_tables / migrate_artifacts
核心逻辑，验证归档、清理、备份、迁移的正确性�?"""
import json
import os
import stat
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.iteration import Iteration
from app.models.pipeline import PipelineRun, Artifact
from app.models.audit_log import AuditLog
from app.models.review import IterationReview, ReviewDecision
from app.services.ops_service import (
    archive_iterations,
    cleanup_audit_logs,
    backup_tables,
    migrate_artifacts,
    _migrate_1_0_to_2_0,
)


class TestArchiveOldIterations:
    """归档超期 finalized 迭代"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject):
        self.old_iteration = Iteration(
            project_id=testProject.id,
            name="old_finalized",
            status="finalized",
            finalized_at=datetime.now(timezone.utc) - timedelta(days=200),
        )
        db.add(self.old_iteration)
        db.flush()

        self.recent_iteration = Iteration(
            project_id=testProject.id,
            name="recent_finalized",
            status="finalized",
            finalized_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        db.add(self.recent_iteration)
        db.flush()

        self.draft_iteration = Iteration(
            project_id=testProject.id,
            name="still_draft",
            status="draft",
        )
        db.add(self.draft_iteration)
        db.flush()

    def test_dry_run_does_not_modify(self, db):
        count = archive_iterations(db, retention_days=180, dry_run=True)
        assert count == 1

        old = db.query(Iteration).filter(Iteration.name == "old_finalized").first()
        assert old.status == "finalized"

    def test_archive_old_iteration(self, db):
        count = archive_iterations(db, retention_days=180, dry_run=False)
        assert count == 1

        db.expire_all()
        old = db.query(Iteration).filter(Iteration.name == "old_finalized").first()
        assert old.status == "archived"

    def test_recent_iteration_not_archived(self, db):
        archive_iterations(db, retention_days=180, dry_run=False)

        recent = db.query(Iteration).filter(Iteration.name == "recent_finalized").first()
        assert recent.status == "finalized"

    def test_draft_iteration_not_archived(self, db):
        archive_iterations(db, retention_days=180, dry_run=False)

        draft = db.query(Iteration).filter(Iteration.name == "still_draft").first()
        assert draft.status == "draft"

    def test_audit_log_created_on_archive(self, db):
        archive_iterations(db, retention_days=180, dry_run=False)

        log = db.query(AuditLog).filter(
            AuditLog.target_kind == "iteration",
            AuditLog.action == "lifecycle_transition",
        ).first()
        assert log is not None
        detail = log.detail if isinstance(log.detail, dict) else json.loads(log.detail)
        assert detail["from"] == "finalized"
        assert detail["to"] == "archived"

    def test_no_iterations_to_archive(self, db):
        count = archive_iterations(db, retention_days=9999, dry_run=False)
        assert count == 0

    def test_default_retention_days(self, db):
        count = archive_iterations(db, dry_run=True)
        assert count == 1

    def test_artifact_payload_compressed(self, db, testProject):
        run = PipelineRun(
            iteration_id=self.old_iteration.id,
            input_hash="compress_test_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        large_payload = {"data": "x" * 1000}
        artifact = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload=large_payload,
            confidence=0.9,
            content_hash="compress_artifact_hash",
        )
        db.add(artifact)
        db.flush()

        archive_iterations(db, retention_days=180, dry_run=False)

        db.expire_all()
        updated = db.query(Artifact).filter(Artifact.id == artifact.id).first()
        assert updated.payload is not None
        if isinstance(updated.payload, dict):
            assert "__compressed__" in updated.payload

    def test_artifact_payload_none_skipped(self, db):
        run = PipelineRun(
            iteration_id=self.old_iteration.id,
            input_hash="none_payload_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        artifact = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload=None,
            confidence=0.5,
            content_hash="none_payload_artifact_hash",
        )
        db.add(artifact)
        db.flush()

        archive_iterations(db, retention_days=180, dry_run=False)

        db.expire_all()
        updated = db.query(Artifact).filter(Artifact.id == artifact.id).first()
        assert updated.payload is None

    def test_small_payload_not_compressed(self, db):
        run = PipelineRun(
            iteration_id=self.old_iteration.id,
            input_hash="small_payload_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        small_payload = {"a": 1}
        artifact = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload=small_payload,
            confidence=0.9,
            content_hash="small_artifact_hash",
        )
        db.add(artifact)
        db.flush()

        archive_iterations(db, retention_days=180, dry_run=False)

        db.expire_all()
        updated = db.query(Artifact).filter(Artifact.id == artifact.id).first()
        assert updated.payload is not None
        if isinstance(updated.payload, dict):
            assert "__compressed__" not in updated.payload

    def test_artifact_no_runs_not_affected(self, db):
        archive_iterations(db, retention_days=180, dry_run=False)
        assert db.query(Artifact).count() == 0


class TestCleanupAuditLogs:
    """清理超期 audit_log"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject):
        self.old_log = AuditLog(
            action="pipeline_start",
            target_kind="iteration",
            target_id=1,
            created_at=datetime.now(timezone.utc) - timedelta(days=400),
        )
        db.add(self.old_log)
        db.flush()

        self.recent_log = AuditLog(
            action="pipeline_start",
            target_kind="iteration",
            target_id=2,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        db.add(self.recent_log)
        db.flush()

    def test_dry_run_does_not_delete(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            count = cleanup_audit_logs(db, retention_days=365, dry_run=True, output_dir=tmpdir)
            assert count == 1

            remaining = db.query(AuditLog).count()
            assert remaining == 2

    def test_dry_run_does_not_create_export_file(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            cleanup_audit_logs(db, retention_days=365, dry_run=True, output_dir=tmpdir)
            files = [f for f in os.listdir(tmpdir) if f.endswith(".jsonl")]
            assert len(files) == 0

    def test_cleanup_old_logs(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            count = cleanup_audit_logs(db, retention_days=365, dry_run=False, output_dir=tmpdir)
            assert count == 1

    def test_export_file_created(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            cleanup_audit_logs(db, retention_days=365, dry_run=False, output_dir=tmpdir)
            files = [f for f in os.listdir(tmpdir) if f.endswith(".jsonl")]
            assert len(files) == 1

    def test_recent_log_not_cleaned(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            cleanup_audit_logs(db, retention_days=365, dry_run=False, output_dir=tmpdir)

            recent = db.query(AuditLog).filter(AuditLog.target_id == 2).first()
            assert recent is not None

    def test_no_logs_to_cleanup(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            count = cleanup_audit_logs(db, retention_days=500, dry_run=False, output_dir=tmpdir)
            assert count == 0

    def test_default_params(self, db):
        count = cleanup_audit_logs(db, dry_run=True)
        assert count == 1

    def test_mkdir_oserror(self, db):
        with patch("app.services.ops_service.Path.mkdir", side_effect=OSError("permission denied")):
            with pytest.raises(OSError, match="permission denied"):
                cleanup_audit_logs(db, retention_days=365, dry_run=False, output_dir="/tmp/test_ops")

    def test_write_oserror(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("builtins.open", side_effect=OSError("disk full")):
                with pytest.raises(OSError, match="disk full"):
                    cleanup_audit_logs(db, retention_days=365, dry_run=False, output_dir=tmpdir)

    def test_export_file_content_valid(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            cleanup_audit_logs(db, retention_days=365, dry_run=False, output_dir=tmpdir)
            files = [f for f in os.listdir(tmpdir) if f.endswith(".jsonl")]
            jsonl_path = os.path.join(tmpdir, files[0])
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line.strip())
                    assert "id" in record
                    assert "action" in record


class TestBackupPipelineData:
    """全量备份 pipeline 数据"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        iteration = Iteration(
            project_id=testProject.id,
            name="backup_test",
            status="finalized",
        )
        db.add(iteration)
        db.flush()

        run = PipelineRun(
            iteration_id=iteration.id,
            input_hash="backup_test_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        artifact = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload={"test": True},
            confidence=0.9,
            content_hash="backup_artifact_hash",
        )
        db.add(artifact)
        db.flush()

        review = IterationReview(
            iteration_id=iteration.id,
            kind="forward",
            status="finalized",
        )
        db.add(review)
        db.flush()

        decision = ReviewDecision(
            review_id=review.id,
            target_kind="case",
            target_id=1,
            ai_verdict="keep",
            ai_confidence=90,
            final_verdict="keep",
        )
        db.add(decision)
        db.flush()

    def test_backup_creates_files(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = backup_tables(db, tmpdir)
            assert "pipeline_runs" in stats
            assert "artifacts" in stats
            assert "review_decision" in stats

    def test_backup_jsonl_not_empty(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_tables(db, tmpdir)
            backup_dirs = [d for d in os.listdir(tmpdir) if d.startswith("pipeline_backup_")]
            assert len(backup_dirs) == 1
            backup_dir = os.path.join(tmpdir, backup_dirs[0])
            for table_name in ["pipeline_runs", "artifacts", "review_decision"]:
                jsonl_file = os.path.join(backup_dir, f"{table_name}.jsonl")
                assert os.path.exists(jsonl_file)
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    assert len(lines) >= 1

    def test_manifest_created(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_tables(db, tmpdir)
            backup_dirs = [d for d in os.listdir(tmpdir) if d.startswith("pipeline_backup_")]
            manifest_file = os.path.join(tmpdir, backup_dirs[0], "manifest.json")
            assert os.path.exists(manifest_file)
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            assert "backup_time" in manifest
            assert "tables" in manifest

    def test_backup_empty_tables(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = os.path.join(tmpdir, "empty_test")
            os.makedirs(empty_dir)
            stats = backup_tables(db, empty_dir)
            for table_name in ["pipeline_runs", "artifacts", "review_decision"]:
                assert table_name in stats

    def test_default_output_dir(self, db):
        stats = backup_tables(db)
        assert "pipeline_runs" in stats

    def test_unauthorized_table_name_skipped(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.services.ops_service._ALLOWED_TABLE_NAMES", set()):
                stats = backup_tables(db, tmpdir)
                for table_name in ["pipeline_runs", "artifacts", "review_decision"]:
                    assert stats.get(table_name, 0) == 0

    def test_mkdir_oserror(self, db):
        with patch("app.services.ops_service.Path.mkdir", side_effect=OSError("no space")):
            with pytest.raises(OSError, match="no space"):
                backup_tables(db, "/tmp/test_backup_ops")

    def test_write_jsonl_oserror(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("builtins.open", side_effect=OSError("write error")):
                with pytest.raises(OSError, match="write error"):
                    backup_tables(db, tmpdir)

    def test_write_manifest_oserror(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_open = open
            call_count = {"n": 0}

            def selective_open(*args, **kwargs):
                if args and "manifest.json" in str(args[0]):
                    call_count["n"] += 1
                    raise OSError("manifest write failed")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=selective_open):
                with pytest.raises(OSError, match="manifest write failed"):
                    backup_tables(db, tmpdir)


class TestMigrateArtifacts:
    """Artifact schema 迁移"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject):
        iteration = Iteration(
            project_id=testProject.id,
            name="migrate_test",
            status="finalized",
        )
        db.add(iteration)
        db.flush()

        run = PipelineRun(
            iteration_id=iteration.id,
            input_hash="migrate_test_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        self.artifact_v1 = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload={"title": "test case", "steps": []},
            confidence=0.9,
            content_hash="migrate_artifact_hash",
        )
        db.add(self.artifact_v1)
        db.flush()

    def test_dry_run_does_not_modify(self, db):
        count = migrate_artifacts(db, "1.0", "2.0", dry_run=True)
        assert count >= 1

        art = db.query(Artifact).filter(Artifact.id == self.artifact_v1.id).first()
        assert art.schema_version == "1.0"

    def test_migrate_updates_version(self, db):
        migrate_artifacts(db, "1.0", "2.0", dry_run=False)

        db.expire_all()
        art = db.query(Artifact).filter(Artifact.id == self.artifact_v1.id).first()
        assert art.schema_version == "2.0"

    def test_migrate_adds_metadata(self, db):
        migrate_artifacts(db, "1.0", "2.0", dry_run=False)

        db.expire_all()
        art = db.query(Artifact).filter(Artifact.id == self.artifact_v1.id).first()
        payload = art.payload if isinstance(art.payload, dict) else json.loads(art.payload)
        assert "metadata" in payload

    def test_unsupported_migration_path(self, db):
        count = migrate_artifacts(db, "3.0", "4.0", dry_run=False)
        assert count == 0

    def test_migrate_payload_none_skipped(self, db, testProject):
        iteration = Iteration(
            project_id=testProject.id,
            name="migrate_none_test",
            status="finalized",
        )
        db.add(iteration)
        db.flush()

        run = PipelineRun(
            iteration_id=iteration.id,
            input_hash="migrate_none_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        artifact_none = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload=None,
            confidence=0.5,
            content_hash="migrate_none_artifact_hash",
        )
        db.add(artifact_none)
        db.flush()

        count = migrate_artifacts(db, "1.0", "2.0", dry_run=False)
        assert count >= 1

        db.expire_all()
        none_art = db.query(Artifact).filter(Artifact.id == artifact_none.id).first()
        assert none_art.payload is None

    def test_no_artifacts_to_migrate(self, db):
        count = migrate_artifacts(db, "9.0", "10.0", dry_run=False)
        assert count == 0

    def test_valid_path_no_matching_rows(self, db, testProject):
        with patch("app.services.ops_service._MIGRATIONS", {("5.0", "6.0"): lambda p: p}):
            count = migrate_artifacts(db, "5.0", "6.0", dry_run=False)
            assert count == 0

    def test_migrate_payload_json_decode_error(self, db, testProject):
        iteration = Iteration(
            project_id=testProject.id,
            name="migrate_bad_json_test",
            status="finalized",
        )
        db.add(iteration)
        db.flush()

        run = PipelineRun(
            iteration_id=iteration.id,
            input_hash="migrate_bad_json_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        artifact_bad = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload="not_valid_json{{{",
            confidence=0.5,
            content_hash="migrate_bad_json_artifact_hash",
        )
        db.add(artifact_bad)
        db.flush()

        with patch("app.services.ops_service.json.loads", side_effect=json.JSONDecodeError("test", "doc", 0)):
            count = migrate_artifacts(db, "1.0", "2.0", dry_run=False)
            assert count == 0

        db.expire_all()
        bad_art = db.query(Artifact).filter(Artifact.id == artifact_bad.id).first()
        assert bad_art.schema_version == "1.0"

    def test_migrate_existing_metadata_not_overwritten(self, db, testProject):
        iteration = Iteration(
            project_id=testProject.id,
            name="migrate_meta_test",
            status="finalized",
        )
        db.add(iteration)
        db.flush()

        run = PipelineRun(
            iteration_id=iteration.id,
            input_hash="migrate_meta_hash",
            pipeline_version="1.0",
            status="completed",
        )
        db.add(run)
        db.flush()

        artifact_meta = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload={"title": "test", "metadata": {"custom": True}},
            confidence=0.9,
            content_hash="migrate_meta_artifact_hash",
        )
        db.add(artifact_meta)
        db.flush()

        migrate_artifacts(db, "1.0", "2.0", dry_run=False)

        db.expire_all()
        art = db.query(Artifact).filter(Artifact.id == artifact_meta.id).first()
        payload = art.payload if isinstance(art.payload, dict) else json.loads(art.payload)
        assert payload["metadata"] == {"custom": True}

    def test_migrate_audit_log_created(self, db):
        migrate_artifacts(db, "1.0", "2.0", dry_run=False)

        log = db.query(AuditLog).filter(
            AuditLog.action == "config_change",
            AuditLog.target_kind == "artifact_schema",
        ).first()
        assert log is not None
        detail = log.detail if isinstance(log.detail, dict) else json.loads(log.detail)
        assert detail["from_version"] == "1.0"
        assert detail["to_version"] == "2.0"


class TestMigrateHelper:
    """迁移辅助函数测试"""

    def test_migrate_1_0_to_2_0_non_dict_payload(self):
        result = _migrate_1_0_to_2_0("not_a_dict")
        assert result == "not_a_dict"

    def test_migrate_1_0_to_2_0_adds_metadata(self):
        result = _migrate_1_0_to_2_0({"title": "test"})
        assert "metadata" in result
        assert result["metadata"]["migrated_from"] == "1.0"

    def test_migrate_1_0_to_2_0_preserves_existing_metadata(self):
        result = _migrate_1_0_to_2_0({"title": "test", "metadata": {"custom": True}})
        assert result["metadata"] == {"custom": True}
