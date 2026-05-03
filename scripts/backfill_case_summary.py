"""
历史用例 summary 回填脚本

为所有 summary 为空的 TestCase 生成 AI 摘要。
支持 --dry-run 预览模式、--batch-size 控制批次大小、--project-id 过滤项目。

使用方式：
    python -m scripts.backfill_case_summary --dry-run
    python -m scripts.backfill_case_summary --project-id 1
    python -m scripts.backfill_case_summary --batch-size 10

依赖关系：
    - app.models.test_case : TestCase
    - app.ai.client : AIClient
    - app.ai.mock_client : MockAIClient（dry-run 模式）
    - app.services.config_service : BATCH_SIZE_SUMMARY_BACKFILL
"""
import argparse
import json
import logging
import sys
from typing import Optional

from sqlalchemy import or_

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _build_prompt(test_case) -> str:
    """构建 summary 生成 prompt。"""
    parts = [
        f"用例标题: {test_case.title or '无标题'}",
        f"前置条件: {test_case.precondition or '无'}",
        f"测试步骤: {test_case.steps_json or '无'}",
        f"预期结果: {test_case.expected_result or '无'}",
    ]
    return (
        "请为以下测试用例生成一段简洁的中文摘要（不超过200字），"
        "概括用例的测试目的和关键验证点：\n\n"
        + "\n".join(parts)
    )


def _get_model_version(ai_client) -> str:
    """安全获取 AI 客户端的模型版本标识。"""
    for attr in ("model_name", "model", "_model"):
        val = getattr(ai_client, attr, None)
        if val is not None:
            return str(val)
    return "unknown"


def run_backfill(
    dry_run: bool = False,
    batch_size: int = 20,
    project_id: Optional[int] = None,
) -> dict:
    """执行 summary 回填。

    Args:
        dry_run: 预览模式，不实际写入 DB。
        batch_size: 每批处理数量。
        project_id: 限定项目 ID（None 表示全部）。

    Returns:
        统计信息字典。
    """
    from app.db.database import PrimarySessionLocal as SessionLocal
    from app.models.test_case import TestCase
    from app.ai.mock_client import MockAIClient
    from app.services.config_service import get_config

    with SessionLocal() as db:
        try:
            if batch_size <= 0:
                batch_size = get_config(db, "BATCH_SIZE_SUMMARY_BACKFILL", 20)

            ai_client = MockAIClient() if dry_run else _create_ai_client()

            query = db.query(TestCase).filter(
                or_(
                    TestCase.summary.is_(None),
                    TestCase.summary == "",
                ),
            )
            if project_id is not None:
                query = query.filter(TestCase.project_id == project_id)

            total = query.count()
            logger.info("待回填用例数: %d (dry_run=%s, batch_size=%d)", total, dry_run, batch_size)

            stats = {"total": total, "success": 0, "failed": 0, "skipped": 0}
            offset = 0

            while offset < total:
                cases = query.offset(offset).limit(batch_size).all()
                if not cases:
                    break

                for case in cases:
                    try:
                        prompt = _build_prompt(case)

                        if dry_run:
                            summary = f"[DRY-RUN] 为用例 #{case.id} 生成的摘要占位"
                            stats["skipped"] += 1
                        else:
                            response = ai_client.complete(
                                prompt=prompt,
                                system="你是一个测试用例摘要生成助手。",
                                temperature=0.3,
                                max_tokens=300,
                                metadata={"step_name": "backfill_summary", "case_id": case.id},
                            )
                            summary = response.content.strip()

                            if not summary:
                                stats["failed"] += 1
                                logger.warning("用例 #%d summary 生成结果为空", case.id)
                                continue

                        if not dry_run:
                            case.summary = summary
                            case.summary_version = (case.summary_version or 0) + 1
                            case.summary_model_version = _get_model_version(ai_client)
                            db.flush()

                        stats["success"] += 1
                        logger.info(
                            "用例 #%d summary 回填%s: %s",
                            case.id,
                            " (dry-run)" if dry_run else "",
                            summary[:80],
                        )

                    except Exception as e:
                        stats["failed"] += 1
                        logger.error("用例 #%d summary 回填失败: %s", case.id, e)
                        continue

                if not dry_run:
                    db.commit()

                offset += batch_size
                logger.info("进度: %d/%d", min(offset, total), total)

            if not dry_run:
                db.commit()

            logger.info("回填完成: %s", json.dumps(stats, ensure_ascii=False))
            return stats

        except Exception as e:
            db.rollback()
            logger.error("回填异常: %s", e)
            raise


def _create_ai_client():
    """创建 AI 客户端（非 dry-run 模式）。"""
    from app.ai.openai_client import OpenAIClient
    from app.ai.fallback_client import FallbackAIClient
    from app.core.config import settings

    primary = OpenAIClient()
    if settings.AI_FALLBACK_MODEL_NAME:
        fallback = OpenAIClient(model_name=settings.AI_FALLBACK_MODEL_NAME)
        return FallbackAIClient(primary=primary, fallback=fallback)
    return primary


def main():
    parser = argparse.ArgumentParser(description="历史用例 summary 回填")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入 DB")
    parser.add_argument("--batch-size", type=int, default=20, help="每批处理数量")
    parser.add_argument("--project-id", type=int, default=None, help="限定项目 ID")
    args = parser.parse_args()

    stats = run_backfill(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        project_id=args.project_id,
    )

    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
