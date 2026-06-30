"""流式与非流式 AI 生成质量等级分布一致性验证脚本。

业务原因：spec optimize-case-generation-flow Task 19.4 要求验证"流式 vs 非流式
生成同一组 10 个测试点，A/B 级占比差异 ≤ 5%"。Task 15 已让流式与非流式共用
`run_quality_feedback_loop`（结构性一致），本脚本通过真实 AI 采样经验性验证。

用法:
    python -m scripts.validate_stream_nonstream_quality_parity \\
        --project-id 11484 --user-id 1 [--runs 3] [--test-point-count 10]

前置条件:
    - .env 已配置 AI_API_KEY（真实 DeepSeek 或兼容 OpenAI 的密钥）
    - 项目中存在 ≥ test-point-count 个 active 测试点
    - 数据库可连接

执行流程:
    1. 拉取项目最新的 N 个 active 测试点（N=test-point-count，默认 10）
    2. 对每个 mode（stream/non_stream）执行 --runs 轮采样：
       - stream: 调用 service.generate_test_cases_batch（流式端点同款代码路径）
       - non_stream: 循环调用 service.generate_test_case_for_point + _save_test_case
       （非流式 /generate-single 同款代码路径）
    3. 每轮结束后查询本轮新增 TestCase.quality_grade 分布，计算 A/B 占比
    4. 删除本轮新增 TestCase（CASCADE 清理子表）
    5. 汇总各轮结果，对比 stream 与 non_stream 的平均 A/B 占比差异

输出:
    - 每轮详细分布表
    - 各模式平均 A/B 占比
    - 差异百分比与 PASS/FAIL 判定（≤ 5% 通过）
"""
import argparse
import asyncio
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import bindparam, text

from app.db.database import PrimarySessionLocal as SessionLocal
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.services.test_case_generation import TestCaseGenerationService

# 验证通过阈值：流式与非流式 A/B 占比差异 ≤ 5%
PARITY_THRESHOLD_PERCENT = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="流式与非流式 AI 生成质量等级分布一致性验证"
    )
    parser.add_argument("--project-id", type=int, required=True, help="项目 ID")
    parser.add_argument("--user-id", type=int, default=1, help="用户 ID（默认 1=admin）")
    parser.add_argument(
        "--runs", type=int, default=3,
        help="每个模式的采样轮数（默认 3）",
    )
    parser.add_argument(
        "--test-point-count", type=int, default=10,
        help="每轮使用的测试点数（默认 10）",
    )
    parser.add_argument(
        "--test-point-ids", type=str, default=None,
        help="显式指定测试点 ID 列表（逗号分隔），优先级高于 --test-point-count",
    )
    parser.add_argument(
        "--case-type", type=str, default=None,
        help="用例类型（可选，不指定由 AI 智能判断）",
    )
    parser.add_argument(
        "--skip-cleanup", action="store_true",
        help="跳过清理（保留生成的测试用例，仅调试用）",
    )
    return parser.parse_args()


def fetch_test_points(
    db, project_id: int, count: int, explicit_ids: Optional[List[int]] = None,
) -> List[TestPoint]:
    """获取测试点列表。显式 ID 优先；否则取项目最新的 N 个 active 测试点。"""
    query = db.query(TestPoint).filter(
        TestPoint.project_id == project_id,
        TestPoint.status == "active",
    )
    if explicit_ids:
        query = query.filter(TestPoint.id.in_(explicit_ids))
        return query.order_by(TestPoint.id).all()
    return query.order_by(TestPoint.id.desc()).limit(count).all()


def get_existing_case_ids(db, project_id: int) -> set:
    """获取当前项目所有未删除的 TestCase ID 集合（用于 BEFORE 快照）。"""
    rows = db.execute(
        text(
            "SELECT id FROM test_cases "
            "WHERE project_id = :pid AND is_deleted = 0"
        ),
        {"pid": project_id},
    ).fetchall()
    return {r[0] for r in rows}


def fetch_new_case_grades(
    db, project_id: int, before_ids: set
) -> Dict[str, int]:
    """查询 BEFORE 之后新增的 TestCase 的 quality_grade 分布。"""
    rows = db.execute(
        text(
            "SELECT id, quality_grade FROM test_cases "
            "WHERE project_id = :pid AND is_deleted = 0"
        ),
        {"pid": project_id},
    ).fetchall()
    new_rows = [r for r in rows if r[0] not in before_ids]
    grades = [r[1] if r[1] else "NONE" for r in new_rows]
    counter = Counter(grades)
    return dict(counter), [r[0] for r in new_rows]


def cleanup_cases(db, case_ids: List[int]) -> None:
    """删除指定 TestCase（CASCADE 自动清理 test_steps 等子表）。"""
    if not case_ids:
        return
    db.execute(
        text("DELETE FROM test_cases WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": case_ids},
    )
    db.commit()
    logger.info("已清理 {} 条本次验证生成的 TestCase", len(case_ids))


def compute_ab_ratio(grade_dist: Dict[str, int]) -> float:
    """计算 A/B 级占比 = (A + B) / total。

    None/NONE 视为未评分（理论上不应出现，因 _save_test_case 必写入 grade）。
    """
    total = sum(grade_dist.values())
    if total == 0:
        return 0.0
    ab_count = grade_dist.get("A", 0) + grade_dist.get("B", 0)
    return ab_count / total * 100.0


async def run_stream_mode(
    db, project_id: int, user_id: int,
    test_point_ids: List[int], case_type: Optional[str],
) -> Tuple[Dict[str, int], List[int]]:
    """流式模式：调用 service.generate_test_cases_batch（流式端点同款代码路径）。

    返回 (quality_grade 分布, 新增 TestCase IDs)。
    """
    before_ids = get_existing_case_ids(db, project_id)
    service = TestCaseGenerationService(db)
    failed_count = 0
    async for event in service.generate_test_cases_batch(
        project_id=project_id,
        user_id=user_id,
        test_point_ids=test_point_ids,
        case_type=case_type,
    ):
        status = event.get("status")
        if status == "error" or event.get("error"):
            failed_count += 1
        # 静默消费，进度由调用方决定是否打印
        progress = event.get("progress", 0)
        msg = event.get("message", "")
        if progress in (5, 10, 100) or status in ("error", "warning"):
            logger.info("[stream] {}% {}", progress, msg)
    # 提交后查询本轮新增
    db.commit()
    grade_dist, new_ids = fetch_new_case_grades(db, project_id, before_ids)
    logger.info(
        "[stream] 本轮完成: 生成 {} 条用例, 失败 {} 测试点, grade 分布={}",
        len(new_ids), failed_count, grade_dist,
    )
    return grade_dist, new_ids


async def run_non_stream_mode(
    db, project_id: int, user_id: int,
    test_point_ids: List[int], case_type: Optional[str],
) -> Tuple[Dict[str, int], List[int]]:
    """非流式模式：循环调用 generate_test_case_for_point + _save_test_case。

    模拟 /generate-single 端点逐条生成的代码路径。
    返回 (quality_grade 分布, 新增 TestCase IDs)。
    """
    before_ids = get_existing_case_ids(db, project_id)
    service = TestCaseGenerationService(db)
    # 一次性获取共享 context（与非流式 /generate-single 一致：每个请求独立 context，
    # 但本验证简化为共享 context 以减少 DB 查询开销，不影响质量分布）
    context = await service.get_context_for_generation(
        project_id=project_id, user_id=user_id,
        test_point_ids=test_point_ids,
    )
    if hasattr(service, "enrich_context_with_trust_and_scoring"):
        service.enrich_context_with_trust_and_scoring(context, project_id)

    test_points = context.get("test_points", [])
    if not test_points:
        logger.error("[non_stream] 未找到测试点")
        return {}, []

    success_count = 0
    failed_count = 0
    for idx, tp in enumerate(test_points, 1):
        try:
            generated = await service.generate_test_case_for_point(
                context=context, test_point=tp,
                project_id=project_id, case_type=case_type,
            )
            # _save_test_case 内部会做质量门禁校验，rejected 会抛 AIGenerationError
            await service._save_test_case(
                project_id=project_id,
                generated_case=generated,
                test_point=tp,
            )
            success_count += 1
        except Exception as e:
            failed_count += 1
            logger.warning(
                "[non_stream] 第 {}/{} 测试点生成失败: {}",
                idx, len(test_points), str(e)[:200],
            )
    db.commit()
    grade_dist, new_ids = fetch_new_case_grades(db, project_id, before_ids)
    logger.info(
        "[non_stream] 本轮完成: 生成 {} 条用例, 失败 {} 测试点, grade 分布={}",
        len(new_ids), failed_count, grade_dist,
    )
    return grade_dist, new_ids


def print_distribution_table(
    runs: List[Dict[str, Any]], mode_name: str,
) -> None:
    """打印某模式各轮的分布表。"""
    print(f"\n{'=' * 60}")
    print(f"  {mode_name} 模式各轮分布")
    print(f"{'=' * 60}")
    print(f"{'轮次':<6}{'A':<6}{'B':<6}{'C':<6}{'D':<6}{'NONE':<6}{'总数':<8}{'A/B%':<10}")
    for i, run in enumerate(runs, 1):
        d = run["grade_dist"]
        total = sum(d.values())
        ab_pct = compute_ab_ratio(d)
        print(
            f"{i:<6}{d.get('A', 0):<6}{d.get('B', 0):<6}{d.get('C', 0):<6}"
            f"{d.get('D', 0):<6}{d.get('NONE', 0):<6}{total:<8}{ab_pct:<10.2f}"
        )
    if runs:
        avg_ab = sum(compute_ab_ratio(r["grade_dist"]) for r in runs) / len(runs)
        print(f"  → 平均 A/B 占比: {avg_ab:.2f}%")


def main() -> int:
    args = parse_args()
    print(f"\n{'#' * 60}")
    print(f"  流式 vs 非流式 AI 生成质量等级一致性验证")
    print(f"{'#' * 60}")
    print(f"  项目 ID: {args.project_id}")
    print(f"  用户 ID: {args.user_id}")
    print(f"  采样轮数: {args.runs} (每模式)")
    print(f"  测试点数: {args.test_point_count}")
    print(f"  通过阈值: A/B 占比差异 ≤ {PARITY_THRESHOLD_PERCENT}%")
    print(f"{'#' * 60}")

    db = SessionLocal()
    try:
        explicit_ids = None
        if args.test_point_ids:
            explicit_ids = [
                int(x.strip()) for x in args.test_point_ids.split(",") if x.strip()
            ]
        test_points = fetch_test_points(
            db, args.project_id, args.test_point_count, explicit_ids,
        )
        if len(test_points) < args.test_point_count:
            logger.error(
                "测试点数不足: 需 {} 个，实际 {} 个",
                args.test_point_count, len(test_points),
            )
            return 1
        tp_ids = [tp.id for tp in test_points]
        logger.info("选取测试点 ID: {}", tp_ids)

        stream_runs: List[Dict[str, Any]] = []
        non_stream_runs: List[Dict[str, Any]] = []

        for run_idx in range(1, args.runs + 1):
            print(f"\n{'─' * 60}")
            print(f"  第 {run_idx}/{args.runs} 轮采样")
            print(f"{'─' * 60}")

            # 流式模式
            logger.info("[stream] 第 {}/{} 轮开始...", run_idx, args.runs)
            t0 = time.time()
            try:
                grade_dist, new_ids = asyncio.run(run_stream_mode(
                    db, args.project_id, args.user_id, tp_ids, args.case_type,
                ))
                elapsed = time.time() - t0
                logger.info("[stream] 第 {} 轮耗时 {:.1f}s", run_idx, elapsed)
                stream_runs.append({
                    "grade_dist": grade_dist,
                    "new_ids": new_ids,
                    "elapsed": elapsed,
                })
                if not args.skip_cleanup:
                    cleanup_cases(db, new_ids)
            except Exception as e:
                logger.exception("[stream] 第 {} 轮异常: {}", run_idx, e)
                stream_runs.append({
                    "grade_dist": {}, "new_ids": [], "elapsed": time.time() - t0,
                })

            # 非流式模式
            logger.info("[non_stream] 第 {}/{} 轮开始...", run_idx, args.runs)
            t0 = time.time()
            try:
                grade_dist, new_ids = asyncio.run(run_non_stream_mode(
                    db, args.project_id, args.user_id, tp_ids, args.case_type,
                ))
                elapsed = time.time() - t0
                logger.info("[non_stream] 第 {} 轮耗时 {:.1f}s", run_idx, elapsed)
                non_stream_runs.append({
                    "grade_dist": grade_dist,
                    "new_ids": new_ids,
                    "elapsed": elapsed,
                })
                if not args.skip_cleanup:
                    cleanup_cases(db, new_ids)
            except Exception as e:
                logger.exception("[non_stream] 第 {} 轮异常: {}", run_idx, e)
                non_stream_runs.append({
                    "grade_dist": {}, "new_ids": [], "elapsed": time.time() - t0,
                })

        # 汇总报告
        print_distribution_table(stream_runs, "流式 (stream)")
        print_distribution_table(non_stream_runs, "非流式 (non_stream)")

        if stream_runs and non_stream_runs:
            stream_avg = sum(
                compute_ab_ratio(r["grade_dist"]) for r in stream_runs
            ) / len(stream_runs)
            non_stream_avg = sum(
                compute_ab_ratio(r["grade_dist"]) for r in non_stream_runs
            ) / len(non_stream_runs)
            diff = abs(stream_avg - non_stream_avg)

            print(f"\n{'=' * 60}")
            print(f"  验证结论")
            print(f"{'=' * 60}")
            print(f"  流式平均 A/B 占比:   {stream_avg:.2f}%")
            print(f"  非流式平均 A/B 占比: {non_stream_avg:.2f}%")
            print(f"  差异:                {diff:.2f}%")
            print(f"  阈值:                {PARITY_THRESHOLD_PERCENT}%")
            if diff <= PARITY_THRESHOLD_PERCENT:
                print(f"  结论: PASS ✓ (差异 ≤ 阈值)")
                return 0
            else:
                print(f"  结论: FAIL ✗ (差异 > 阈值)")
                return 2
        else:
            print("\n  无有效数据，无法判定")
            return 3

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
