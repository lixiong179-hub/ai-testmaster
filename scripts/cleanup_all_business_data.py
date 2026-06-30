"""清理全部业务数据（项目、用例、任务、结果、报告、缺陷、UI 原型等）

⚠️ 核弹级操作：清空 projects 表及其全部关联子表。
仅保留 users / roles / permissions / groups /
quality_rule_configs / prompt_templates / pipeline_config / enums 等系统配置。

⚠️ 默认 dry-run，仅打印每张表行数，不写入任何数据。
    必须显式传 --execute 才会执行 DELETE。

⚠️ 不可逆：执行后无回滚点，除非有数据库快照或备份。

用法:
    # 仅查看（推荐先跑一次）
    python scripts/cleanup_all_business_data.py

    # 真正执行删除
    python scripts/cleanup_all_business_data.py --execute

    # 执行后追加确认提示
    python scripts/cleanup_all_business_data.py --execute --yes

输出:
    - dry-run: 各表行数清单
    - execute: 删除前行数 → 删除后行数
"""
import argparse
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.cli_utils import build_session
from app.services.ops_service import (
    _TABLES_PRESERVED,
    _TABLES_TO_CLEAR,
    cleanup_all_business_data,
)


def _print_table(name: str, width: int = 36) -> None:
    """打印分隔行"""
    print(f"\n{'=' * width} {name} {'=' * width}")


def _print_stats(stats: Dict[str, int], header: str) -> None:
    """打印 {表: 行数} 字典为对齐文本"""
    print(f"\n[{header}]")
    if not stats:
        print("  (无数据)")
        return
    max_name_len = max(len(name) for name in stats)
    total = 0
    for name in sorted(stats):
        count = stats[name]
        total += count
        print(f"  {name:<{max_name_len}}  {count:>8d} 行")
    print(f"  {'-' * (max_name_len + 14)}")
    print(f"  {'合计':<{max_name_len}}  {total:>8d} 行")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "清理全部业务数据（核弹级）。默认 dry-run。\n"
            "传 --execute 才执行 DELETE，传 --yes 跳过确认提示。"
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="真正执行 DELETE（不可逆）",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="跳过执行前的二次确认（仅 --execute 时生效）",
    )
    args = parser.parse_args()

    db, engine = build_session()
    try:
        if not args.execute:
            # Dry-run 模式
            _print_table("DRY-RUN 模式（不写入任何数据）")
            stats = cleanup_all_business_data(db, dry_run=True)
            _print_stats(stats, "将删除（dry-run）")
            _print_table("保留的表（不删）")
            for t in _TABLES_PRESERVED:
                print(f"  ✓ {t}")
            print(
                "\n[下一步] 若确认无误，执行:\n"
                "  python scripts/cleanup_all_business_data.py --execute"
            )
            return

        # Execute 模式
        if not args.yes:
            # 先 dry-run 给清单，再问确认
            stats_before = cleanup_all_business_data(db, dry_run=True)
            _print_stats(stats_before, "将删除的行数")
            print(
                "\n⚠️  核弹级操作：执行后将不可逆。\n"
                "    数据库无回滚点，除非有备份。\n"
                "    users / roles / permissions / prompt_templates 等系统配置保留。\n"
            )
            answer = input("确认执行删除? 输入 YES 继续，其他任意键取消: ").strip()
            if answer != "YES":
                print("[cancelled] 已取消，未删除任何数据。")
                return

        # 真正执行
        _print_table("EXECUTING")
        stats = cleanup_all_business_data(db, dry_run=False)
        _print_stats(stats, "已删除行数")

        # 验证
        _print_table("验证（删除后行数应为 0）")
        for name in sorted(_TABLES_TO_CLEAR):
            result = db.execute(
                __import__("sqlalchemy").text(f"SELECT COUNT(*) FROM {name}")
            )
            remaining = result.scalar() or 0
            status = "✓" if remaining == 0 else "✗"
            print(f"  {status} {name:<36}  {remaining:>8d} 行")
        _print_table("保留的表（行数不验证）")
        for t in _TABLES_PRESERVED:
            print(f"  ✓ {t}")
    except Exception as exc:
        db.rollback()
        print(f"\n[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
