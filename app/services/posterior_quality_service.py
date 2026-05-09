"""后验质量分采集服务

本模块实现后验质量分的自动采集和告警功能。

后验质量分公式（metrics_definition.md §4.2）：
    posterior = 0.5 * review_pass_rate + 0.3 * execution_pass_rate + 0.2 * (1 - modification_rate)

告警规则：
    当 review_rejection_rate > 30% 时记录 F17 告警指标。

核心函数概览：
    - compute_posterior_quality : 计算单个项目的后验质量分
    - compute_and_persist_posterior : 计算并回填后验质量分到 test_cases
    - check_review_rejection_alert : 检查评审拒绝率并触发告警

依赖关系：
    - app.models.test_case : TestCase, TestCaseExecution
    - app.services.metrics_service : record_metric
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, and_, case
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 评审拒绝率告警阈值
REVIEW_REJECTION_RATE_THRESHOLD = 0.30

# 后验质量分最低执行次数要求
POSTERIOR_MIN_EXECUTIONS = 3


def compute_posterior_quality(db: Session, project_id: int) -> Dict[str, Any]:
    """计算单个项目的后验质量分。

    公式:
        posterior = 0.5 * review_pass_rate + 0.3 * execution_pass_rate + 0.2 * (1 - modification_rate)

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        包含各指标和最终后验质量分的字典。
    """
    from app.models.test_case import TestCase

    # 1. 评审通过率（仅计算终态：approved + rejected，needs_optimization 为中间态不计入）
    review_stats = (
        db.query(
            func.count(TestCase.id).label("total_reviewed"),
            func.sum(case(
                (TestCase.review_status == "approved", 1),
                else_=0,
            )).label("approved_count"),
            func.sum(case(
                (TestCase.review_status == "rejected", 1),
                else_=0,
            )).label("rejected_count"),
        )
        .filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
            TestCase.review_status.in_(["approved", "rejected"]),
        )
        .first()
    )

    total_reviewed = review_stats.total_reviewed or 0
    approved_count = review_stats.approved_count or 0
    rejected_count = review_stats.rejected_count or 0

    review_pass_rate = (approved_count / total_reviewed) if total_reviewed > 0 else 0.0
    review_rejection_rate = (rejected_count / total_reviewed) if total_reviewed > 0 else 0.0

    # 2. 执行通过率
    from app.models.test_case import TestCaseExecution

    execution_stats = (
        db.query(
            func.count(TestCaseExecution.id).label("total_executed"),
            func.sum(case(
                (TestCaseExecution.status == "passed", 1),
                else_=0,
            )).label("passed_count"),
        )
        .join(TestCase, TestCaseExecution.test_case_id == TestCase.id)
        .filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
            TestCaseExecution.status.in_(["passed", "failed"]),
        )
        .first()
    )

    total_executed = execution_stats.total_executed or 0
    passed_count = execution_stats.passed_count or 0

    execution_pass_rate = (passed_count / total_executed) if total_executed > 0 else 0.0

    # 3. 用例修改率
    modification_stats = (
        db.query(
            func.count(TestCase.id).label("total_cases"),
            func.sum(case(
                (TestCase.update_time > TestCase.create_time, 1),
                else_=0,
            )).label("modified_count"),
        )
        .filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        )
        .first()
    )

    total_cases = modification_stats.total_cases or 0
    modified_count = modification_stats.modified_count or 0

    modification_rate = (modified_count / total_cases) if total_cases > 0 else 0.0

    # 4. 计算后验质量分
    posterior = (
        0.5 * review_pass_rate
        + 0.3 * execution_pass_rate
        + 0.2 * (1.0 - modification_rate)
    )
    posterior = round(posterior * 100, 2)  # 转换为 0-100 分制

    return {
        "project_id": project_id,
        "review_pass_rate": round(review_pass_rate, 4),
        "review_rejection_rate": round(review_rejection_rate, 4),
        "total_reviewed": total_reviewed,
        "execution_pass_rate": round(execution_pass_rate, 4),
        "total_executed": total_executed,
        "modification_rate": round(modification_rate, 4),
        "total_cases": total_cases,
        "posterior_quality_score": posterior,
        "meets_min_executions": total_executed >= POSTERIOR_MIN_EXECUTIONS,
    }


def compute_and_persist_posterior(db: Session, project_id: int) -> Dict[str, Any]:
    """计算后验质量分并回填到 test_cases.posterior_quality_score。

    仅对满足最低执行次数要求的用例回填后验质量分。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        采集结果字典。
    """
    from app.models.test_case import TestCase

    result = compute_posterior_quality(db, project_id)

    if not result["meets_min_executions"]:
        logger.info(
            "项目 %d 执行次数不足（%d < %d），跳过后验质量分回填",
            project_id, result["total_executed"], POSTERIOR_MIN_EXECUTIONS,
        )
        return result

    posterior_score = result["posterior_quality_score"]

    # 回填到该项目所有非删除用例
    updated = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        )
        .update({TestCase.posterior_quality_score: posterior_score}, synchronize_session="fetch")
    )

    db.flush()

    logger.info(
        "项目 %d 后验质量分回填完成：score=%.2f, updated=%d",
        project_id, posterior_score, updated,
    )

    # 记录 F16 指标
    try:
        from app.services.metrics_service import record_metric
        record_metric(
            "posterior_quality_score",
            value=posterior_score,
            project_id=project_id,
            detail={
                "review_pass_rate": result["review_pass_rate"],
                "execution_pass_rate": result["execution_pass_rate"],
                "modification_rate": result["modification_rate"],
                "total_reviewed": result["total_reviewed"],
                "total_executed": result["total_executed"],
                "total_cases": result["total_cases"],
            },
        )
    except Exception as e:
        logger.warning("后验质量分指标记录失败: %s", e)

    return result


def check_review_rejection_alert(db: Session, project_id: int) -> bool:
    """检查评审拒绝率是否超过阈值，超过则触发告警。

    当 review_rejection_rate > 30% 时记录 F17 告警指标。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        是否触发了告警。
    """
    result = compute_posterior_quality(db, project_id)
    rejection_rate = result.get("review_rejection_rate", 0.0)

    if rejection_rate > REVIEW_REJECTION_RATE_THRESHOLD and result["total_reviewed"] >= 5:
        logger.warning(
            "⚠️ 项目 %d 评审拒绝率 %.1f%% 超过阈值 %.0f%%（已评审 %d 条）",
            project_id,
            rejection_rate * 100,
            REVIEW_REJECTION_RATE_THRESHOLD * 100,
            result["total_reviewed"],
        )

        try:
            from app.services.metrics_service import record_metric
            record_metric(
                "review_rejection_rate_high",
                value=rejection_rate,
                project_id=project_id,
                detail={
                    "rejection_rate": rejection_rate,
                    "total_reviewed": result["total_reviewed"],
                    "rejected_count": int(rejection_rate * result["total_reviewed"]),
                    "threshold": REVIEW_REJECTION_RATE_THRESHOLD,
                },
            )
        except Exception as e:
            logger.warning("评审拒绝率告警指标记录失败: %s", e)

        return True

    return False


def run_posterior_quality_batch(db: Session, project_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """批量执行后验质量分采集和告警检查。

    可由定时任务调用，对指定项目（或所有有用例的项目）执行采集。

    Args:
        db: 数据库会话。
        project_ids: 项目 ID 列表，为空时自动检测所有有评审记录的项目。

    Returns:
        各项目的采集结果列表。
    """
    from app.models.test_case import TestCase

    if not project_ids:
        # 自动检测所有有评审记录的项目
        rows = (
            db.query(TestCase.project_id)
            .filter(
                TestCase.is_deleted == False,
                TestCase.review_status.in_(["approved", "rejected"]),
            )
            .group_by(TestCase.project_id)
            .all()
        )
        project_ids = [r.project_id for r in rows if r.project_id]

    if not project_ids:
        logger.info("无需要采集后验质量分的项目")
        return []

    results = []
    for pid in project_ids:
        try:
            result = compute_and_persist_posterior(db, pid)
            check_review_rejection_alert(db, pid)
            results.append(result)
        except Exception as e:
            logger.error("项目 %d 后验质量分采集失败: %s", pid, e)
            results.append({"project_id": pid, "error": str(e)})

    logger.info("后验质量分批量采集完成：共 %d 个项目", len(results))
    return results
