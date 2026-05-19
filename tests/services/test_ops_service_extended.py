import pytest
from app.services.ops_service import (
    archive_iterations,
    cleanup_audit_logs,
    backup_tables,
    migrate_artifacts,
    _migrate_1_0_to_2_0,
    _row_to_dict,
    _TABLES_FOR_BACKUP,
    _ALLOWED_TABLE_NAMES,
)
from datetime import datetime


class TestMigrate10To20:
    def test_adds_metadata(self):
        payload = {"key": "value"}
        result = _migrate_1_0_to_2_0(payload)
        assert "metadata" in result
        assert result["metadata"]["migrated_from"] == "1.0"

    def test_existing_metadata_preserved(self):
        payload = {"metadata": {"existing": True}}
        result = _migrate_1_0_to_2_0(payload)
        assert result["metadata"]["existing"] is True

    def test_non_dict_returns_unchanged(self):
        assert _migrate_1_0_to_2_0("string") == "string"
        assert _migrate_1_0_to_2_0(None) is None
        assert _migrate_1_0_to_2_0(42) == 42


class TestRowToDict:
    def test_basic_conversion(self):
        row = (1, "test", None)
        columns = ["id", "name", "value"]
        result = _row_to_dict(row, columns)
        assert result["id"] == 1
        assert result["name"] == "test"
        assert "value" not in result

    def test_datetime_conversion(self):
        now = datetime.now()
        row = (1, now)
        columns = ["id", "created_at"]
        result = _row_to_dict(row, columns)
        assert isinstance(result["created_at"], str)


class TestArchiveIterations:
    def test_archive_no_rows(self, db):
        count = archive_iterations(db, retention_days=30, dry_run=True)
        assert count == 0

    def test_archive_dry_run(self, db):
        count = archive_iterations(db, retention_days=99999, dry_run=True)
        assert count == 0


class TestCleanupAuditLogs:
    def test_cleanup_no_rows(self, db):
        count = cleanup_audit_logs(db, retention_days=30, dry_run=True)
        assert count == 0

    def test_cleanup_dry_run(self, db):
        count = cleanup_audit_logs(db, retention_days=99999, dry_run=True)
        assert count == 0


class TestBackupTables:
    def test_allowed_table_names(self):
        assert "pipeline_runs" in _ALLOWED_TABLE_NAMES
        assert "artifacts" in _ALLOWED_TABLE_NAMES
        assert "review_decision" in _ALLOWED_TABLE_NAMES

    def test_backup_creates_files(self, db, tmp_path):
        stats = backup_tables(db, output_dir=str(tmp_path))
        assert isinstance(stats, dict)
        for table_name in _ALLOWED_TABLE_NAMES:
            assert table_name in stats


class TestMigrateArtifacts:
    def test_migrate_unknown_version(self, db):
        count = migrate_artifacts(db, "9.0", "10.0", dry_run=True)
        assert count == 0

    def test_migrate_no_rows(self, db):
        count = migrate_artifacts(db, "1.0", "2.0", dry_run=True)
        assert count == 0
