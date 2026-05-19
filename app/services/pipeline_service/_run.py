import hashlib
import json
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload

from app.models.pipeline import PipelineRun
from app.models.enums import PipelineRunStatus
from app.models.iteration import Iteration, IterationInput
from app.utils.db_time import utcnow
from app.services.pipeline_service._errors import (
    PipelineRunValidationError,
    PipelineStatusTransitionError,
    PIPELINE_RUN_TRANSITIONS,
)


def compute_input_hash(iteration_inputs: List[IterationInput]) -> str:
    pairs = sorted(
        [(inp.kind, inp.content_hash) for inp in iteration_inputs],
        key=lambda p: (p[0], p[1]),
    )
    raw = json.dumps(pairs, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def create_run(
    db: Session,
    iteration_id: int,
    input_hash: str,
    pipeline_version: str = "1.0",
) -> PipelineRun:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if iteration is None:
        raise PipelineRunValidationError(f"iteration_id={iteration_id} 不存在")

    existing = db.query(PipelineRun).filter(
        PipelineRun.iteration_id == iteration_id,
        PipelineRun.input_hash == input_hash,
        PipelineRun.pipeline_version == pipeline_version,
        PipelineRun.status.in_([
            PipelineRunStatus.COMPLETED.value,
            PipelineRunStatus.RUNNING.value,
            PipelineRunStatus.WAITING_FOR_USER.value,
        ]),
    ).first()
    if existing:
        return existing

    run = PipelineRun(
        iteration_id=iteration_id,
        input_hash=input_hash,
        pipeline_version=pipeline_version,
        status=PipelineRunStatus.PENDING.value,
    )
    db.add(run)
    db.flush()
    return run


def get_run(db: Session, run_id: int) -> Optional[PipelineRun]:
    return (
        db.query(PipelineRun)
        .options(
            joinedload(PipelineRun.steps),
            joinedload(PipelineRun.artifacts),
        )
        .filter(PipelineRun.id == run_id)
        .first()
    )


def list_runs(
    db: Session,
    iteration_id: int,
    *,
    skip: int = 0,
    limit: int = 100,
) -> List[PipelineRun]:
    return (
        db.query(PipelineRun)
        .filter(PipelineRun.iteration_id == iteration_id)
        .order_by(PipelineRun.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_run_status(
    db: Session,
    run_id: int,
    status: str,
    *,
    error: Optional[str] = None,
) -> Optional[PipelineRun]:
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run is None:
        return None

    from_status = run.status
    if (from_status, status) not in PIPELINE_RUN_TRANSITIONS:
        raise PipelineStatusTransitionError(
            "PipelineRun", from_status, status,
            detail=f"允许的迁移路径: {from_status} → {status} 不在允许列表中",
        )

    run.status = status
    if error is not None:
        run.error = error

    now = utcnow()
    if status == PipelineRunStatus.RUNNING.value and run.started_at is None:
        run.started_at = now
    if status in (PipelineRunStatus.COMPLETED.value, PipelineRunStatus.FAILED.value,
                  PipelineRunStatus.CANCELLED.value):
        run.finished_at = now

    db.flush()
    return run
