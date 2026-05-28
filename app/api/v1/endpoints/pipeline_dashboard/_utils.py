from sqlalchemy import func, Integer, text
from sqlalchemy.orm import Session

from app.models.pipeline import PipelineRun


def duration_seconds(start_col, end_col, db: Session):
    dialect = get_dialect_name(db)
    if dialect == "sqlite":
        return func.cast(
            (func.julianday(end_col) - func.julianday(start_col)) * 86400,
            Integer,
        )
    return func.timestampdiff(text("SECOND"), start_col, end_col)


def get_dialect_name(db: Session) -> str:
    try:
        return db.bind.dialect.name
    except Exception:
        return "mysql"


def build_run_subquery(db: Session, project_id: int):
    from app.models.iteration import Iteration
    return (
        db.query(PipelineRun.id)
        .join(Iteration, PipelineRun.iteration_id == Iteration.id)
        .filter(Iteration.project_id == project_id)
        .subquery()
        .select()
    )
