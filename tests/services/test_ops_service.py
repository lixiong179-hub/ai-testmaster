import pytest
from app.services.ops_service import (
    archive_iterations,
    cleanup_audit_logs,
    backup_tables,
    _TABLES_FOR_BACKUP,
    _ALLOWED_TABLE_NAMES,
    _COLUMN_NAME_PATTERN,
)


class TestArchiveIterations:
    def test_dry_run(self, db):
        count = archive_iterations(db, retention_days=365, dry_run=True)
        assert isinstance(count, int)
        assert count == 0

    def test_default_retention(self, db):
        count = archive_iterations(db, dry_run=True)
        assert isinstance(count, int)


class TestCleanupAuditLogs:
    def test_dry_run(self, db):
        count = cleanup_audit_logs(db, retention_days=365, dry_run=True)
        assert isinstance(count, int)


class TestBackupTables:
    def test_dry_run(self, db, tmp_path):
        result = backup_tables(db, output_dir=str(tmp_path))
        assert isinstance(result, dict)


class TestAllowedTableNames:
    def test_contains_expected(self):
        assert "pipeline_runs" in _ALLOWED_TABLE_NAMES
        assert "artifacts" in _ALLOWED_TABLE_NAMES


class TestColumnNamePattern:
    def test_valid_names(self):
        assert _COLUMN_NAME_PATTERN.match("id")
        assert _COLUMN_NAME_PATTERN.match("pipeline_version")

    def test_invalid_names(self):
        assert not _COLUMN_NAME_PATTERN.match("1invalid")
        assert not _COLUMN_NAME_PATTERN.match("")
