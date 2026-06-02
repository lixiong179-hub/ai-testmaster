"""后验质量分服务 — 基于评审+执行+修改率计算用例的后验质量分

公式（plan §7.2）:
    posterior = W_review * review_pass_rate
              + W_execution * execution_pass_rate
              + W_modification * (1 - modification_rate)

    其中:
    - review_pass_rate = final_verdict 为 "keep" 的决策占比
    - execution_pass_rate = status 为 "passed" 的执行占比
    - modification_rate = final_verdict 为 modify/needs_modify/locator_broken/locator_and_modify 的决策占比
    - 最低样本要求: execution 次数 >= POSTERIOR_MIN_EXECUTIONS

    权重默认值:
    - W_review = 0.5
    - W_execution = 0.3
    - W_modification = 0.2
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.review import ReviewDecision
from app.models.test_case import TestCase, TestCaseExecution
from app.pipelines.steps.reconciliation import MergedAction

KEEP_VERDICTS = frozenset({MergedAction.KEEP.value})
MODIFY_VERDICTS = frozenset({
    MergedAction.NEEDS_MODIFY.value,
    MergedAction.LOCATOR_BROKEN.value,
    MergedAction.LOCATOR_AND_MODIFY.value,
})
PASSED_STATUSES = frozenset({"passed"})

_REVIEW_ABSENT_DEFAULT_RATE = 0.5


@dataclass
class PosteriorInput:
    """单个用例的后验质量分输入数据"""
    case_id: int
    review_total: int
    review_keep_count: int
    review_modify_count: int
    execution_total: int
    execution_passed_count: int


@dataclass
class PosteriorResult:
    """单个用例的后验质量分计算结果"""
    case_id: int
    score: Optional[float]
    review_pass_rate: float
    execution_pass_rate: float
    modification_rate: float
    skipped: bool
    skip_reason: Optional[str]
    no_review_data: bool = False


def compute_posterior_score(
    inp: PosteriorInput,
    w_review: Optional[float] = None,
    w_execution: Optional[float] = None,
    w_modification: Optional[float] = None,
    min_executions: Optional[int] = None,
) -> PosteriorResult:
    """计算单个用例的后验质量分

    Args:
        inp: 后验质量分输入数据
        w_review: 评审通过率权重，None 时取 settings
        w_execution: 执行通过率权重，None 时取 settings
        w_modification: 修改率权重，None 时取 settings
        min_executions: 最低执行次数要求，None 时取 settings

    Returns:
        PosteriorResult 包含分数和明细
    """
    _w_review = w_review if w_review is not None else settings.POSTERIOR_REVIEW_WEIGHT
    _w_execution = w_execution if w_execution is not None else settings.POSTERIOR_EXECUTION_WEIGHT
    _w_modification = w_modification if w_modification is not None else settings.POSTERIOR_MODIFICATION_WEIGHT
    _min_exec = min_executions if min_executions is not None else settings.POSTERIOR_MIN_EXECUTIONS

    if inp.execution_total < _min_exec:
        return PosteriorResult(
            case_id=inp.case_id,
            score=None,
            review_pass_rate=0.0,
            execution_pass_rate=0.0,
            modification_rate=0.0,
            skipped=True,
            skip_reason=f"execution_total({inp.execution_total}) < min({_min_exec})",
        )

    no_review = inp.review_total == 0
    review_pass_rate = (
        inp.review_keep_count / inp.review_total if not no_review else _REVIEW_ABSENT_DEFAULT_RATE
    )
    execution_pass_rate = (
        inp.execution_passed_count / inp.execution_total if inp.execution_total > 0 else 0.0
    )
    modification_rate = (
        inp.review_modify_count / inp.review_total if not no_review else 0.0
    )

    score = (
        _w_review * review_pass_rate
        + _w_execution * execution_pass_rate
        + _w_modification * (1.0 - modification_rate)
    ) * 100.0

    score = round(max(0.0, min(100.0, score)), 2)

    return PosteriorResult(
        case_id=inp.case_id,
        score=score,
        review_pass_rate=round(review_pass_rate, 4),
        execution_pass_rate=round(execution_pass_rate, 4),
        modification_rate=round(modification_rate, 4),
        skipped=False,
        skip_reason=None,
        no_review_data=no_review,
    )


def fetch_posterior_inputs(
    db: Session,
    case_ids: Optional[List[int]] = None,
) -> List[PosteriorInput]:
    """批量查询用例的后验质量分输入数据

    Args:
        db: 数据库会话
        case_ids: 指定用例ID列表，None 表示查询所有有执行记录的用例

    Returns:
        PosteriorInput 列表
    """
    query = (
        db.query(
            TestCaseExecution.test_case_id.label("case_id"),
            func.count(TestCaseExecution.id).label("execution_total"),
            func.sum(
                case(
                    (TestCaseExecution.status.in_(PASSED_STATUSES), 1),
                    else_=0,
                )
            ).label("execution_passed_count"),
        )
        .group_by(TestCaseExecution.test_case_id)
    )
    if case_ids is not None:
        if not case_ids:
            return []
        query = query.filter(TestCaseExecution.test_case_id.in_(case_ids))

    exec_stats = query.all()

    case_id_set = {row.case_id for row in exec_stats}
    if not case_id_set:
        return []

    review_query = (
        db.query(
            ReviewDecision.target_id.label("case_id"),
            func.count(ReviewDecision.id).label("review_total"),
            func.sum(
                case(
                    (ReviewDecision.final_verdict.in_(KEEP_VERDICTS), 1),
                    else_=0,
                )
            ).label("review_keep_count"),
            func.sum(
                case(
                    (ReviewDecision.final_verdict.in_(MODIFY_VERDICTS), 1),
                    else_=0,
                )
            ).label("review_modify_count"),
        )
        .filter(
            ReviewDecision.target_kind == "case",
            ReviewDecision.target_id.in_(case_id_set),
        )
        .group_by(ReviewDecision.target_id)
    )

    review_map: dict[int, Tuple[int, int, int]] = {}
    for row in review_query.all():
        review_map[row.case_id] = (
            int(row.review_total),
            int(row.review_keep_count),
            int(row.review_modify_count),
        )

    inputs: List[PosteriorInput] = []
    for row in exec_stats:
        r_total, r_keep, r_modify = review_map.get(row.case_id, (0, 0, 0))
        inputs.append(PosteriorInput(
            case_id=row.case_id,
            review_total=r_total,
            review_keep_count=r_keep,
            review_modify_count=r_modify,
            execution_total=row.execution_total,
            execution_passed_count=int(row.execution_passed_count or 0),
        ))

    return inputs


def backfill_posterior_scores(
    db: Session,
    case_ids: Optional[List[int]] = None,
) -> List[PosteriorResult]:
    """批量回填用例的后验质量分

    Args:
        db: 数据库会话
        case_ids: 指定用例ID列表，None 表示查询所有有执行记录的用例

    Returns:
        PosteriorResult 列表，包含每个用例的计算结果
    """
    inputs = fetch_posterior_inputs(db, case_ids=case_ids)
    results: List[PosteriorResult] = []

    score_map: dict[int, float] = {}
    for inp in inputs:
        result = compute_posterior_score(inp)
        results.append(result)
        if result.score is not None:
            score_map[inp.case_id] = result.score

    if score_map:
        _batch_update_posterior_scores(db, score_map)

    db.flush()
    computed = sum(1 for r in results if not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    logger.info(
        f"Posterior score backfill: {computed} computed, {skipped} skipped, "
        f"{len(results)} total"
    )

    return results


def _batch_update_posterior_scores(
    db: Session,
    score_map: dict[int, float],
) -> None:
    """批量更新后验质量分（ORM 逐条更新，确保 before_flush event 触发版本快照）

    Args:
        db: 数据库会话
        score_map: {case_id: score} 映射
    """
    if not score_map:
        return

    cases = (
        db.query(TestCase)
        .filter(
            TestCase.id.in_(list(score_map.keys())),
            TestCase.is_deleted.is_(False),
        )
        .all()
    )
    for case in cases:
        target_score = score_map.get(case.id)
        if target_score is not None and case.posterior_quality_score != target_score:
            case.posterior_quality_score = target_score
