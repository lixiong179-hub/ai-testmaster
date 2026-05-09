"""运维脚本核心逻辑 — 归档/清理/备份/迁移

所有函数接收 db session 参数，由脚本 CLI 或测试直接调用。
"""
import gzip
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings

_logger = logging.getLogger(__name__)

_TABLES_FOR_BACKUP = [
    {"name": "pipeline_runs", "columns": "id, iteration_id, input_hash, pipeline_version, status, started_at, finished_at, error"},
    {"name": "artifacts", "columns": "id, run_id, kind, schema_version, confidence, content_hash, created_at"},
    {"name": "review_decision", "columns": "id, review_id, target_kind, target_id, target_version, ai_verdict, ai_confidence, "
                "ai_reason, modification_hint, deprecate_reason, human_verdict, human_user_id, "
                "human_reason, final_verdict, decided_at, conflict_marker, accepted_low_confidence"},
]

_ALLOWED_TABLE_NAMES = {t["name"] for t in _TABLES_FOR_BACKUP}


def archive_iterations(db: Session, retention_days: Optional[int] = None, dry_run: bool = False) -> int:
    """归档超期 finalized 迭代

    将 finalized_at 超过 retention_days 的迭代状态改为 archived，
    同时将关联的 Artifact payload 压缩存档（gzip），减少存储占用。

    Args:
        db: 数据库会话
        retention_days: 归档保留天数，默认取 settings.ARCHIVE_RETENTION_DAYS
        dry_run: 仅预览不写入数据库

    Returns:
        归档的迭代数量
    """
    if retention_days is None:
        retention_days = settings.ARCHIVE_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    rows = db.execute(
        text(
            "SELECT id, name, finalized_at FROM iterations "
            "WHERE status = 'finalized' AND finalized_at IS NOT NULL "
            "AND finalized_at < :cutoff"
        ),
        {"cutoff": cutoff},
    ).fetchall()

    if not rows:
        return 0

    if dry_run:
        return len(rows)

    now_utc = datetime.now(timezone.utc)
    for r in rows:
        iteration_id = r.id
        db.execute(
            text("UPDATE iterations SET status = 'archived' WHERE id = :id"),
            {"id": iteration_id},
        )

        artifacts = db.execute(
            text("SELECT id, payload FROM artifacts WHERE run_id IN "
                 "(SELECT id FROM pipeline_runs WHERE iteration_id = :iid)"),
            {"iid": iteration_id},
        ).fetchall()

        for art in artifacts:
            if art.payload is None:
                continue
            payload_str = json.dumps(art.payload, ensure_ascii=False) if not isinstance(art.payload, str) else art.payload
            compressed = gzip.compress(payload_str.encode("utf-8"))
            if len(compressed) < len(payload_str.encode("utf-8")):
                db.execute(
                    text("UPDATE artifacts SET payload = :payload WHERE id = :id"),
                    {"payload": json.dumps({"__compressed__": compressed.hex()}), "id": art.id},
                )

        db.execute(
            text(
                "INSERT INTO audit_log (action, actor_id, target_kind, target_id, detail, iteration_id, created_at) "
                "VALUES ('lifecycle_transition', NULL, 'iteration', :iid, :detail, :iid, :now)"
            ),
            {"iid": iteration_id, "detail": json.dumps({"from": "finalized", "to": "archived"}), "now": now_utc},
        )

    db.flush()
    return len(rows)


def cleanup_audit_logs(db: Session, retention_days: Optional[int] = None, dry_run: bool = False, output_dir: Optional[str] = None) -> int:
    """清理超期 audit_log（导出后删除）

    先将超期 audit_log 导出为 JSONL 文件，再从数据库删除。
    dry_run 模式下仅返回数量，不导出也不删除。

    Args:
        db: 数据库会话
        retention_days: 清理保留天数，默认取 settings.CLEANUP_AUDIT_LOG_DAYS
        dry_run: 仅预览，不导出不删除
        output_dir: 导出文件目录

    Returns:
        清理的记录数量
    """
    if retention_days is None:
        retention_days = settings.CLEANUP_AUDIT_LOG_DAYS
    if output_dir is None:
        output_dir = settings.BACKUP_DIR
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    rows = db.execute(
        text(
            "SELECT id, action, actor_id, target_kind, target_id, detail, "
            "run_id, iteration_id, created_at FROM audit_log "
            "WHERE created_at < :cutoff ORDER BY id"
        ),
        {"cutoff": cutoff},
    ).fetchall()

    if not rows:
        return 0

    if dry_run:
        return len(rows)

    output_path = Path(output_dir)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _logger.error("创建导出目录失败: %s", exc)
        raise
    export_file = output_path / f"audit_log_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"

    try:
        with open(export_file, "w", encoding="utf-8") as f:
            for r in rows:
                record = {
                    "id": r.id,
                    "action": r.action,
                    "actor_id": r.actor_id,
                    "target_kind": r.target_kind,
                    "target_id": r.target_id,
                    "detail": r.detail,
                    "run_id": r.run_id,
                    "iteration_id": r.iteration_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        _logger.error("导出 audit_log 到文件失败: %s", exc)
        raise

    min_id = rows[0].id
    max_id = rows[-1].id
    db.execute(
        text("DELETE FROM audit_log WHERE id BETWEEN :min_id AND :max_id AND created_at < :cutoff"),
        {"min_id": min_id, "max_id": max_id, "cutoff": cutoff},
    )
    db.flush()
    return len(rows)


def _row_to_dict(row, columns: list) -> dict:
    result = {}
    for col_name, value in zip(columns, row):
        if isinstance(value, datetime):
            result[col_name] = value.isoformat()
        elif value is not None:
            result[col_name] = value
    return result


def backup_tables(db: Session, output_dir: Optional[str] = None) -> Dict[str, int]:
    """全量备份 pipeline_runs + artifacts + review_decision

    将三张表的数据导出为 JSONL 文件，支持恢复演练。

    Args:
        db: 数据库会话
        output_dir: 备份输出目录

    Returns:
        各表备份行数统计
    """
    if output_dir is None:
        output_dir = settings.BACKUP_DIR

    output_path = Path(output_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = output_path / f"pipeline_backup_{timestamp}"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _logger.error("创建备份目录失败: %s", exc)
        raise

    stats: Dict[str, int] = {}
    for table_info in _TABLES_FOR_BACKUP:
        table_name = table_info["name"]
        if table_name not in _ALLOWED_TABLE_NAMES:
            _logger.warning("跳过未授权的表名: %s", table_name)
            continue
        columns = [c.strip() for c in table_info["columns"].split(",")]
        col_list = ", ".join(f"`{c.strip()}`" for c in table_info["columns"].split(","))
        rows = db.execute(text(f"SELECT {col_list} FROM `{table_name}`")).fetchall()

        export_file = backup_dir / f"{table_name}.jsonl"
        try:
            with open(export_file, "w", encoding="utf-8") as f:
                for row in rows:
                    record = _row_to_dict(row, columns)
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            _logger.error("备份表 %s 到文件失败: %s", table_name, exc)
            raise

        stats[table_name] = len(rows)

    manifest = {"backup_time": datetime.now(timezone.utc).isoformat(), "tables": stats}
    manifest_file = backup_dir / "manifest.json"
    try:
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        _logger.error("写入 manifest.json 失败: %s", exc)
        raise

    return stats


def _migrate_1_0_to_2_0(payload: dict) -> dict:
    """示例迁移：为 case_generation 类型的 artifact 添加 metadata 字段"""
    if not isinstance(payload, dict):
        return payload
    if "metadata" not in payload:
        payload["metadata"] = {"migrated_from": "1.0", "migration_time": "auto"}
    return payload


_MIGRATIONS = {
    ("1.0", "2.0"): _migrate_1_0_to_2_0,
}


def migrate_artifacts(db: Session, from_version: str, to_version: str, dry_run: bool = False) -> int:
    """Artifact schema 迁移

    将指定 schema_version 的 artifact payload 从旧版本格式迁移到新版本格式。

    Args:
        db: 数据库会话
        from_version: 源 schema 版本
        to_version: 目标 schema 版本
        dry_run: 仅预览不写入数据库

    Returns:
        迁移的 artifact 数量
    """
    migration_key = (from_version, to_version)
    if migration_key not in _MIGRATIONS:
        return 0

    migrate_fn = _MIGRATIONS[migration_key]
    rows = db.execute(
        text("SELECT id, kind, payload FROM artifacts WHERE schema_version = :ver"),
        {"ver": from_version},
    ).fetchall()

    if not rows:
        return 0

    if dry_run:
        return len(rows)

    now_utc = datetime.now(timezone.utc)
    migrated = 0
    for r in rows:
        if r.payload is None:
            continue
        try:
            payload = r.payload if isinstance(r.payload, dict) else json.loads(r.payload)
        except (json.JSONDecodeError, TypeError):
            _logger.warning("artifact id=%s payload 解析失败，跳过", r.id)
            continue
        new_payload = migrate_fn(payload)
        db.execute(
            text("UPDATE artifacts SET payload = :payload, schema_version = :ver WHERE id = :id"),
            {"payload": json.dumps(new_payload, ensure_ascii=False), "ver": to_version, "id": r.id},
        )
        migrated += 1

    db.execute(
        text(
            "INSERT INTO audit_log (action, actor_id, target_kind, target_id, detail, created_at) "
            "VALUES ('config_change', NULL, 'artifact_schema', 0, :detail, :now)"
        ),
        {"detail": json.dumps({"from_version": from_version, "to_version": to_version, "count": migrated}), "now": now_utc},
    )

    db.flush()
    return migrated
