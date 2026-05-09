"""后验质量分采集脚本

定时执行后验质量分采集和评审拒绝率告警检查。
可配合 cron 或 GitHub Actions 定时调用。

使用方式：
    python -m scripts.collect_posterior_quality --project-id 1
    python -m scripts.collect_posterior_quality --all-projects

依赖关系：
    - app.services.posterior_quality_service : 后验质量分采集服务
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="后验质量分采集")
    parser.add_argument("--project-id", type=int, help="指定项目 ID")
    parser.add_argument("--all-projects", action="store_true", help="采集所有有评审记录的项目")
    args = parser.parse_args()

    if not args.project_id and not args.all_projects:
        parser.error("请指定 --project-id 或 --all-projects")

    from app.db.database import get_db_context
    from app.services.posterior_quality_service import (
        compute_and_persist_posterior,
        check_review_rejection_alert,
        run_posterior_quality_batch,
    )

    with get_db_context() as db:
        if args.project_id:
            result = compute_and_persist_posterior(db, args.project_id)
            alerted = check_review_rejection_alert(db, args.project_id)

            print(f"\n项目 {args.project_id} 后验质量分采集结果：")
            print(f"  后验质量分: {result.get('posterior_quality_score', 'N/A')}")
            print(f"  评审通过率: {result.get('review_pass_rate', 'N/A')}")
            print(f"  执行通过率: {result.get('execution_pass_rate', 'N/A')}")
            print(f"  修改率: {result.get('modification_rate', 'N/A')}")
            print(f"  已评审: {result.get('total_reviewed', 0)}")
            print(f"  已执行: {result.get('total_executed', 0)}")
            print(f"  告警: {'⚠️ 评审拒绝率超阈值' if alerted else '无'}")
        else:
            results = run_posterior_quality_batch(db)
            print(f"\n批量采集完成：{len(results)} 个项目")
            for r in results:
                if "error" in r:
                    print(f"  项目 {r['project_id']}: 失败 - {r['error']}")
                else:
                    print(f"  项目 {r['project_id']}: score={r.get('posterior_quality_score', 'N/A')}")


if __name__ == "__main__":
    main()
