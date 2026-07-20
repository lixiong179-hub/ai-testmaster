from sqlalchemy import func, Integer, select, text
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PipelineRun


def duration_seconds(start_col, end_col, db):
    """计算时长（秒），跨数据库兼容，兼容 sync/async Session。"""
    dialect = get_dialect_name(db)
    if dialect == "sqlite":
        return func.cast(
            (func.julianday(end_col) - func.julianday(start_col)) * 86400,
            Integer,
        )
    return func.timestampdiff(text("SECOND"), start_col, end_col)


def get_dialect_name(db) -> str:
    """获取当前数据库方言名称，兼容 sync Session 与 AsyncSession。"""
    try:
        return db.bind.dialect.name
    except Exception:
        return "mysql"


def build_run_subquery(db, project_id: int):
    """构建按 project_id 过滤的 PipelineRun.id 子查询。

    兼容 sync Session 与 AsyncSession — 仅构建 SQL 表达式，不执行查询。
    返回 select() 子查询，可用 .in_() 进行过滤。
    """
    from app.models.iteration import Iteration
    return (
        select(PipelineRun.id)
        .join(Iteration, PipelineRun.iteration_id == Iteration.id)
        .where(Iteration.project_id == project_id)
        .subquery()
        .select()
    )
