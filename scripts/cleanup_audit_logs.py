"""清理 ≥ 1 年的 audit_log（导出后删除）

先将超期 audit_log 导出为 JSONL 文件，再从数据库删除。
AuditLog ORM 层禁止 UPDATE/DELETE，使用原生 SQL 绕过。

用法:
    python scripts/cleanup_audit_logs.py [--dry-run] [--retention-days 365] [--output-dir /tmp]

参数:
    --dry-run           仅预览不删除
    --retention-days    清理保留天数（默认 365，即 1 年）
    --output-dir        导出文件目录
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.cli_utils import build_session
from app.services.ops_service import cleanup_audit_logs
from app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="清理超期 audit_log（导出后删除）")
    parser.add_argument("--dry-run", action="store_true", default=False, help="仅预览不删除")
    parser.add_argument("--retention-days", type=int, default=settings.CLEANUP_AUDIT_LOG_DAYS, help="清理保留天数")
    parser.add_argument("--output-dir", type=str, default=settings.BACKUP_DIR, help="导出文件目录")
    args = parser.parse_args()

    db, engine = build_session()
    try:
        count = cleanup_audit_logs(db, args.retention_days, args.dry_run, args.output_dir)
        if args.dry_run:
            print(f"[dry-run] 将清理 {count} 条 audit_log")
        else:
            db.commit()
            print(f"[done] 已清理 {count} 条 audit_log")
    except Exception as exc:
        db.rollback()
        print(f"[error] {exc}", file=sys.stderr)
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
