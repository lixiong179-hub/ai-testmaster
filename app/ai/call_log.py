"""
AI 调用日志模块

本模块定义 ai_call_log 表模型和调用记录/预算检查逻辑：
    - AICallLog 模型：记录每次 AI 调用的模型、Token、成本、延迟、step_name、run_id
    - record_call()：写入调用日志
    - check_budget()：检查 run 的 Token 预算是否超限

表结构：
    id, run_id FK, step_name, model, prompt_tokens, completion_tokens,
    cost_usd, latency_ms, status, error_message, created_at

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳
    - app.db.database.Base     : SQLAlchemy 声明性基类
    - app.core.config.settings : AI_TOKEN_BUDGET_PER_RUN
"""
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Numeric, text,
)
from sqlalchemy.orm import Session

from app.utils.db_time import utcnow
from app.db.database import Base
from app.core.config import settings


class AICallLog(Base):
    """AI 调用日志模型

    记录每次 AI API 调用的详细信息，支持成本追踪和预算控制。

    表关系：
        - 多对一 → PipelineRun（关联运行，可选）
    """
    __tablename__ = "ai_call_log"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    run_id = Column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="关联运行ID",
    )
    step_name = Column(String(64), nullable=True, comment="Step 名称")
    model = Column(String(64), nullable=False, comment="使用的AI模型")
    prompt_tokens = Column(Integer, nullable=False, default=0, comment="输入Token数")
    completion_tokens = Column(Integer, nullable=False, default=0, comment="输出Token数")
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0, comment="调用成本（美元）")
    latency_ms = Column(Integer, nullable=False, default=0, comment="调用耗时（毫秒）")
    status = Column(String(20), nullable=False, default="success", comment="状态: success/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(
        DateTime, nullable=False, default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"), comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<AICallLog(id={self.id}, model='{self.model}', cost={self.cost_usd})>"


def record_call(
    db: Optional[Session] = None,
    *,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    step_name: Optional[str] = None,
    run_id: Optional[int] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> AICallLog:
    """写入 AI 调用日志

    Args:
        db: 数据库会话（可选，None 时不写入 DB）
        model: 模型名称
        prompt_tokens: 输入 Token 数
        completion_tokens: 输出 Token 数
        cost_usd: 调用成本（美元）
        latency_ms: 调用耗时（毫秒）
        step_name: Step 名称
        run_id: 运行 ID
        status: 状态（success/failed）
        error_message: 错误信息

    Returns:
        AICallLog 实例
    """
    log = AICallLog(
        run_id=run_id,
        step_name=step_name,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
    )
    if db is not None:
        db.add(log)
        db.flush()
    return log


def check_budget(db: Session, run_id: int) -> bool:
    """检查 run 的 Token 预算是否超限

    汇总 run_id 下所有成功调用的 prompt_tokens + completion_tokens，
    与 AI_TOKEN_BUDGET_PER_RUN 比较。

    Args:
        db: 数据库会话
        run_id: 运行 ID

    Returns:
        True 表示预算充足，False 表示超限
    """
    from sqlalchemy import func

    total_tokens = (
        db.query(
            func.coalesce(func.sum(AICallLog.prompt_tokens), 0)
            + func.coalesce(func.sum(AICallLog.completion_tokens), 0)
        )
        .filter(
            AICallLog.run_id == run_id,
            AICallLog.status == "success",
        )
        .scalar()
    ) or 0

    budget = settings.AI_TOKEN_BUDGET_PER_RUN
    return total_tokens < budget


def get_run_cost(db: Session, run_id: int) -> float:
    """获取 run 的总成本

    Args:
        db: 数据库会话
        run_id: 运行 ID

    Returns:
        总成本（美元）
    """
    from sqlalchemy import func

    total = (
        db.query(func.coalesce(func.sum(AICallLog.cost_usd), 0))
        .filter(AICallLog.run_id == run_id)
        .scalar()
    ) or 0.0
    return float(total)
