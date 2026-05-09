"""每周全量备份 pipeline_run + artifact + review_decision

将三张表的数据导出为 JSONL 文件，支持恢复演练。

用法:
    python scripts/backup_pipeline_data.py [--output-dir /tmp/backup]

参数:
    --output-dir    备份输出目录（默认 /tmp/ai-testmaster-backup）
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.cli_utils import build_session
from app.services.ops_service import backup_tables
from app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="全量备份 pipeline 数据")
    parser.add_argument("--output-dir", type=str, default=settings.BACKUP_DIR, help="备份输出目录")
    args = parser.parse_args()

    db, engine = build_session()
    try:
        stats = backup_tables(db, args.output_dir)
        for table_name, count in stats.items():
            print(f"[info] {table_name}: {count} 行已备份")
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
