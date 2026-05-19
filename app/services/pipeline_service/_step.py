import hashlib
import json
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.pipeline import PipelineStep
from app.models.enums import PipelineStepStatus
from app.utils.db_time import utcnow
from app.services.pipeline_service._errors import (
    PipelineStepValidationError,
    PipelineStatusTransitionError,
    PIPELINE_STEP_TRANSITIONS,
)


def compute_cache_key(
    step_name: str,
    step_version: str,
    input_artifact_hashes: List[str],
) -> str:
    parts = [step_name, step_version] + sorted(input_artifact_hashes)
    raw = json.dumps(parts, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def create_step(
    db: Session,
    run_id: int,
    step_name: str,
    step_version: str = "1.0",
    cache_key: Optional[str] = None,
    input_artifact_ids: Optional[List[int]] = None,
) -> PipelineStep:
    from app.models.pipeline import PipelineRun
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run is None:
        raise PipelineStepValidationError(f"run_id={run_id} 不存在")

    step = PipelineStep(
        run_id=run_id,
        step_name=step_name,
        step_version=step_version,
        status=PipelineStepStatus.PENDING.value,
        cache_key=cache_key,
        input_artifact_ids=input_artifact_ids,
    )
    db.add(step)
    db.flush()
    return step


def find_cached_step(db: Session, cache_key: str) -> Optional[PipelineStep]:
    return (
        db.query(PipelineStep)
        .filter(
            PipelineStep.cache_key == cache_key,
            PipelineStep.status == PipelineStepStatus.DONE.value,
        )
        .first()
    )


def update_step_status(
    db: Session,
    step_id: int,
    status: str,
    *,
    error: Optional[str] = None,
    output_artifact_ids: Optional[List[int]] = None,
    retried_count: Optional[int] = None,
    degraded: Optional[bool] = None,
) -> Optional[PipelineStep]:
    step = db.query(PipelineStep).filter(PipelineStep.id == step_id).first()
    if step is None:
        return None

    from_status = step.status
    if (from_status, status) not in PIPELINE_STEP_TRANSITIONS:
        raise PipelineStatusTransitionError(
            "PipelineStep", from_status, status,
            detail=f"允许的迁移路径: {from_status} → {status} 不在允许列表中",
        )

    step.status = status
    if error is not None:
        step.error = error
    if output_artifact_ids is not None:
        step.output_artifact_ids = output_artifact_ids
    if retried_count is not None:
        step.retried_count = retried_count
    if degraded is not None:
        step.degraded = degraded

    now = utcnow()
    if status == PipelineStepStatus.RUNNING.value and step.started_at is None:
        step.started_at = now
    if status in (PipelineStepStatus.DONE.value, PipelineStepStatus.FAILED.value,
                  PipelineStepStatus.SKIPPED.value, PipelineStepStatus.DEGRADED.value):
        step.finished_at = now

    db.flush()
    return step


def increment_step_retried_count(db: Session, step_id: int) -> None:
    step = db.query(PipelineStep).filter(PipelineStep.id == step_id).first()
    if step is not None:
        step.retried_count = (step.retried_count or 0) + 1
        db.flush()


def update_step_output_artifact_ids(
    db: Session, step_id: int, artifact_ids: List[int],
) -> None:
    step = db.query(PipelineStep).filter(PipelineStep.id == step_id).first()
    if step is not None:
        step.output_artifact_ids = artifact_ids
        db.flush()
