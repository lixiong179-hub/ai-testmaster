"""
AI 调用审计查询端点模块（R2-1：同步 Session + 线程池执行）

本模块提供 AIInvocationGateway 审计增强的查询 API：
    - GET /stats  — 项目维度成本聚合（按模型/策略/日期）
    - GET /list   — 调用记录分页查询

路由前缀: /ai-invocation（由 main.py 注册）
标签: AI调用审计

实现说明（R2-1 阶段三 W2-5）:
    本端点无独立 service 层。改为同步 `Depends(get_db)` 后：
    1. 查询统一经模块级 `_execute(db, stmt)`（内部 `asyncio.to_thread`）在线程池执行；
    2. 仍需原生 SQL 表达式（`select(col).subquery()`、`in_(select(subq.c.id))`）；
    3. 端点保持 `async def`，测试仍可用 `httpx.AsyncClient` 或直调。
"""

import asyncio
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import get_db
from app.models.generation_batch import GenerationBatch
from app.models.user import User
from app.ai.call_log import AICallLog
from app.schemas.ai_invocation import (
    AIInvocationListItem,
    AIInvocationStatsResponse,
)


async def _execute(db: Session, stmt):
    """同步 Session 的查询在线程池执行，避免阻塞事件循环（R2-1）。"""
    return await asyncio.to_thread(db.execute, stmt)


router = APIRouter(tags=["AI调用审计"])


@router.get("/stats")
async def get_ai_invocation_stats(
    project_id: int = Query(..., gt=0, description="项目ID"),
    start_date: date | None = Query(None, description="起始日期（含）"),
    end_date: date | None = Query(None, description="截止日期（含）"),
    group_by: str = Query("model", pattern="^(model|strategy|date)$", description="聚合维度"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """项目维度 AI 调用成本聚合

    通过 generation_batch 间接关联 project_id，
    按 group_by 维度聚合 total_calls / tokens / cost。

    Args:
        project_id: 项目ID（必填）
        start_date: 起始日期，默认近30天
        end_date: 截止日期，默认今天
        group_by: 聚合维度 model/strategy/date
        db: 异步数据库会话
        current_user: 当前用户

    Returns:
        聚合结果列表
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    # 子查询：获取项目下的所有 generation_batch_id
    batch_ids_subq = select(GenerationBatch.id).where(GenerationBatch.project_id == project_id).subquery()

    # 按维度聚合
    if group_by == "model":
        group_col = AICallLog.model
    elif group_by == "strategy":
        group_col = AICallLog.generation_strategy
    else:
        group_col = func.date(AICallLog.created_at)

    rows = (
        await _execute(
            db,
            select(
                group_col.label("group_key"),
                func.count(AICallLog.id).label("total_calls"),
                func.coalesce(func.sum(AICallLog.prompt_tokens), 0).label("total_prompt_tokens"),
                func.coalesce(func.sum(AICallLog.completion_tokens), 0).label("total_completion_tokens"),
                func.coalesce(func.sum(AICallLog.cost_usd), 0).label("total_cost_usd"),
            )
            .where(
                AICallLog.generation_batch_id.in_(select(batch_ids_subq.c.id)),
                AICallLog.created_at >= start_dt,
                AICallLog.created_at <= end_dt,
            )
            .group_by(group_col),
        )
    ).all()

    results = [
        AIInvocationStatsResponse(
            group_key=str(row.group_key) if row.group_key is not None else "",
            total_calls=row.total_calls,
            total_prompt_tokens=int(row.total_prompt_tokens),
            total_completion_tokens=int(row.total_completion_tokens),
            total_cost_usd=float(row.total_cost_usd),
        )
        for row in rows
    ]
    return create_response(data={"items": [r.model_dump() for r in results]})


@router.get("/list")
async def get_ai_invocation_list(
    batch_id: int | None = Query(None, description="生成批次ID"),
    project_id: int | None = Query(None, gt=0, description="项目ID"),
    run_id: int | None = Query(None, description="Pipeline 运行ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 调用记录分页查询

    支持按 run_id / batch_id / project_id 筛选，
    project_id 通过 generation_batch 间接关联。

    Args:
        batch_id: 生成批次ID
        project_id: 项目ID
        run_id: Pipeline 运行ID（AICallLog.run_id，用于成本累计查询）
        page: 页码
        page_size: 每页条数
        db: 异步数据库会话
        current_user: 当前用户

    Returns:
        分页调用记录列表
    """
    # 未提供筛选条件时返回空列表，避免全表扫描
    if batch_id is None and project_id is None and run_id is None:
        return create_response(data={"items": [], "total": 0, "page": page, "page_size": page_size})

    # 构建过滤条件
    filters = []
    if run_id is not None:
        filters.append(AICallLog.run_id == run_id)
    if batch_id is not None:
        filters.append(AICallLog.generation_batch_id == batch_id)
    elif project_id is not None:
        batch_ids_subq = select(GenerationBatch.id).where(GenerationBatch.project_id == project_id).subquery()
        filters.append(AICallLog.generation_batch_id.in_(select(batch_ids_subq.c.id)))

    # 统计总数
    total = (await _execute(db, select(func.count()).select_from(AICallLog).where(*filters))).scalar_one()

    # 分页查询
    offset = (page - 1) * page_size
    rows = (
        (
            await _execute(
                db,
                select(AICallLog).where(*filters).order_by(AICallLog.created_at.desc()).offset(offset).limit(page_size),
            )
        )
        .scalars()
        .all()
    )

    items = [
        AIInvocationListItem(
            id=r.id,
            run_id=r.run_id,
            step_name=r.step_name,
            model=r.model,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            cost_usd=float(r.cost_usd) if r.cost_usd is not None else 0.0,
            latency_ms=r.latency_ms,
            status=r.status,
            error_message=r.error_message,
            created_at=r.created_at,
            generation_batch_id=r.generation_batch_id,
            scenario_type=r.scenario_type,
            generation_strategy=r.generation_strategy,
            prompt_key=r.prompt_key,
            prompt_version=r.prompt_version,
            prompt_hash=r.prompt_hash,
            error_code=r.error_code,
        )
        for r in rows
    ]
    return create_response(
        data={
            "items": [item.model_dump() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
