"""Artifact schema 迁移脚本

Pipeline 版本升级时，将 artifact 的 schema_version 和 payload 从旧版本格式
迁移到新版本格式。每个版本的迁移逻辑以函数注册到 _MIGRATIONS 映射中。

用法:
    python scripts/migrate_artifacts.py --from-version 1.0 --to-version 2.0 [--dry-run]

参数:
    --from-version   源 schema 版本
    --to-version     目标 schema 版本
    --dry-run        仅预览不写入数据库
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.cli_utils import build_session
from app.services.ops_service import migrate_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Artifact schema 迁移")
    parser.add_argument("--from-version", type=str, required=True, help="源 schema 版本")
    parser.add_argument("--to-version", type=str, required=True, help="目标 schema 版本")
    parser.add_argument("--dry-run", action="store_true", default=False, help="仅预览不写入数据库")
    args = parser.parse_args()

    db, engine = build_session()
    try:
        count = migrate_artifacts(db, args.from_version, args.to_version, args.dry_run)
        if args.dry_run:
            print(f"[dry-run] 将迁移 {count} 个 artifact（{args.from_version} → {args.to_version}）")
        else:
            db.commit()
            print(f"[done] 已迁移 {count} 个 artifact（{args.from_version} → {args.to_version}）")
    except Exception as exc:
        db.rollback()
        print(f"[error] {exc}", file=sys.stderr)
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
