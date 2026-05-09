"""后验质量分回填脚本 — 手动/定时触发后验质量分计算并写入 test_cases 表

用法:
    python scripts/compute_posterior_score.py [--case-ids 1,2,3] [--min-executions 3] [--dry-run]

参数:
    --case-ids       指定用例ID列表（逗号分隔），不传则处理所有有执行记录的用例
    --min-executions 最低执行次数要求，不传则取配置值 POSTERIOR_MIN_EXECUTIONS
    --dry-run        仅计算不写入数据库
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.posterior_score_service import (
    fetch_posterior_inputs,
    compute_posterior_score,
    backfill_posterior_scores,
)


def _build_session():
    db_url = settings.DATABASE_URL
    engine = create_engine(
        db_url,
        connect_args={"init_command": "SET sql_mode='NO_ENGINE_SUBSTITUTION'"},
        pool_pre_ping=True,
    )
    session_cls = sessionmaker(bind=engine)
    return session_cls(), engine


def main() -> None:
    parser = argparse.ArgumentParser(description="后验质量分回填脚本")
    parser.add_argument(
        "--case-ids",
        type=str,
        default=None,
        help="指定用例ID列表（逗号分隔），不传则处理所有有执行记录的用例",
    )
    parser.add_argument(
        "--min-executions",
        type=int,
        default=None,
        help="最低执行次数要求，不传则取配置值 POSTERIOR_MIN_EXECUTIONS",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="仅计算不写入数据库",
    )
    args = parser.parse_args()

    case_ids = None
    if args.case_ids:
        case_ids = [int(cid.strip()) for cid in args.case_ids.split(",") if cid.strip()]

    min_exec = args.min_executions

    db, engine = _build_session()
    try:
        if args.dry_run:
            inputs = fetch_posterior_inputs(db, case_ids=case_ids)
            print(f"[dry-run] 查询到 {len(inputs)} 条用例")
            for inp in inputs:
                result = compute_posterior_score(inp, min_executions=min_exec)
                status = "SKIP" if result.skipped else f"score={result.score}"
                no_rev = " [no_review]" if result.no_review_data else ""
                print(
                    f"  case_id={inp.case_id}: {status}{no_rev} "
                    f"(review_pass={result.review_pass_rate}, "
                    f"exec_pass={result.execution_pass_rate}, "
                    f"mod_rate={result.modification_rate})"
                )
                if result.skip_reason:
                    print(f"    skip_reason: {result.skip_reason}")
        else:
            results = backfill_posterior_scores(db, case_ids=case_ids)
            db.commit()
            computed = sum(1 for r in results if not r.skipped)
            skipped = sum(1 for r in results if r.skipped)
            print(f"[done] {computed} computed, {skipped} skipped, {len(results)} total")
            for r in results:
                if r.skipped:
                    print(f"  case_id={r.case_id}: SKIP ({r.skip_reason})")
                else:
                    print(f"  case_id={r.case_id}: score={r.score}")
    except Exception as exc:
        db.rollback()
        print(f"[error] {exc}", file=sys.stderr)
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
