from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.pipeline import Artifact
from app.services.pipeline_service._errors import (
    PipelineRunValidationError,
    DuplicateArtifactHashError,
)


def create_artifact(
    db: Session,
    run_id: int,
    kind: str,
    content_hash: str,
    *,
    schema_version: str = "1.0",
    payload: Optional[dict] = None,
    confidence: Optional[float] = None,
    provenance: Optional[dict] = None,
) -> Artifact:
    from app.models.pipeline import PipelineRun
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run is None:
        raise PipelineRunValidationError(f"run_id={run_id} 不存在")

    existing = db.query(Artifact).filter(Artifact.content_hash == content_hash).first()
    if existing:
        raise DuplicateArtifactHashError(content_hash)

    artifact = Artifact(
        run_id=run_id,
        kind=kind,
        schema_version=schema_version,
        payload=payload,
        confidence=confidence,
        provenance=provenance,
        content_hash=content_hash,
    )
    db.add(artifact)
    db.flush()
    return artifact


def get_artifact_by_hash(db: Session, content_hash: str) -> Optional[Artifact]:
    return db.query(Artifact).filter(Artifact.content_hash == content_hash).first()
