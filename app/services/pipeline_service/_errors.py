from app.models.enums import PipelineRunStatus, PipelineStepStatus


class DuplicateArtifactHashError(ValueError):
    def __init__(self, content_hash: str):
        super().__init__(f"Duplicate artifact content_hash: {content_hash}")


class PipelineRunValidationError(ValueError):
    def __init__(self, detail: str):
        super().__init__(f"PipelineRun validation failed: {detail}")


class PipelineStepValidationError(ValueError):
    def __init__(self, detail: str):
        super().__init__(f"PipelineStep validation failed: {detail}")


class PipelineStatusTransitionError(ValueError):
    def __init__(self, entity: str, from_status: str, to_status: str, detail: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Illegal {entity} status transition: {from_status} → {to_status}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


PIPELINE_RUN_TRANSITIONS = {
    (PipelineRunStatus.PENDING.value, PipelineRunStatus.RUNNING.value),
    (PipelineRunStatus.RUNNING.value, PipelineRunStatus.WAITING_FOR_USER.value),
    (PipelineRunStatus.RUNNING.value, PipelineRunStatus.COMPLETED.value),
    (PipelineRunStatus.RUNNING.value, PipelineRunStatus.FAILED.value),
    (PipelineRunStatus.WAITING_FOR_USER.value, PipelineRunStatus.RUNNING.value),
    (PipelineRunStatus.WAITING_FOR_USER.value, PipelineRunStatus.COMPLETED.value),
    (PipelineRunStatus.WAITING_FOR_USER.value, PipelineRunStatus.CANCELLED.value),
    (PipelineRunStatus.PENDING.value, PipelineRunStatus.CANCELLED.value),
}

PIPELINE_STEP_TRANSITIONS = {
    (PipelineStepStatus.PENDING.value, PipelineStepStatus.RUNNING.value),
    (PipelineStepStatus.PENDING.value, PipelineStepStatus.SKIPPED.value),
    (PipelineStepStatus.PENDING.value, PipelineStepStatus.DONE.value),
    (PipelineStepStatus.RUNNING.value, PipelineStepStatus.DONE.value),
    (PipelineStepStatus.RUNNING.value, PipelineStepStatus.FAILED.value),
    (PipelineStepStatus.RUNNING.value, PipelineStepStatus.DEGRADED.value),
    (PipelineStepStatus.FAILED.value, PipelineStepStatus.RUNNING.value),
    (PipelineStepStatus.FAILED.value, PipelineStepStatus.DEGRADED.value),
    (PipelineStepStatus.FAILED.value, PipelineStepStatus.FAILED.value),
}
