"""归档 ≥ 6 个月的 finalized 迭代

将 finalized_at 超过 ARCHIVE_RETENTION_DAYS 的迭代状态改为 archived，
同时将关联的 Artifact payload 压缩存档（gzip），减少存储占用。

用法:
    python scripts/archive_old_iterations.py [--dry-run] [--retention-days 180]

参数:
    --dry-run           仅预览不写入数据库
    --retention-days    归档保留天数（默认 180，即 6 个月）
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.cli_utils import build_session
from app.services.ops_service import archive_iterations
from app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="归档超期的 finalized 迭代")
    parser.add_argument("--dry-run", action="store_true", default=False, help="仅预览不写入数据库")
    parser.add_argument("--retention-days", type=int, default=settings.ARCHIVE_RETENTION_DAYS, help="归档保留天数")
    args = parser.parse_args()

    db, engine = build_session()
    try:
        count = archive_iterations(db, args.retention_days, args.dry_run)
        if args.dry_run:
            print(f"[dry-run] 将归档 {count} 个迭代")
        else:
            db.commit()
            print(f"[done] 已归档 {count} 个迭代")
    except Exception as exc:
        db.rollback()
        print(f"[error] {exc}", file=sys.stderr)
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
