"""TIA（Test Impact Analysis）管理端点。

提供 TIA 调度计划生成、覆盖率映射查询/写入、项目级统计 API。

路由（由 main.py 以 prefix=/api/v1 挂载）:
    - POST /projects/{project_id}/impact-analysis/schedule   生成 TIA 调度计划
    - GET  /projects/{project_id}/impact-analysis/coverage   分页查询覆盖率映射
    - GET  /projects/{project_id}/impact-analysis/stats      项目级覆盖率统计
    - POST /projects/{project_id}/impact-analysis/coverage   写入覆盖率映射
    - DELETE /projects/{project_id}/impact-analysis/coverage  清空项目覆盖率映射

权限: 所有端点需 Bearer 令牌认证；项目端点额外校验项目归属（owner/admin）。

设计说明:
    service 层（TIAIntegrationService）接受 sync Session，端点采用
    async + asyncio.to_thread 模式，为每次调用新建独立 sync 会话，
    避免与 get_current_user 注入的 async 会话混用。
"""
import asyncio
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.core.exception import create_response
from app.db.database import PrimarySessionLocal, async_get_db
from app.models.project import Project
from app.models.test_coverage_map import TestCoverageMap
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.impact_analysis import (
    CoverageIngestRequest,
    CoverageIngestResponse,
    CoverageListResponse,
    CoverageMapItem,
    CoverageStatsResponse,
    SchedulePlanRequest,
    SchedulePlanResponse,
)
from app.services.impact_analysis.integration_service import TIAIntegrationService

router = APIRouter(tags=["TIA智能调度"])


async def _verify_project_owner(
    db: AsyncSession, project_id: int, user_id: int
) -> None:
    """校验项目归属当前用户，不存在或无权限抛 403。"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == user_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )


def _run_sync(fn: Callable[[Session], Any]) -> Any:
    """在线程池中执行 sync service 调用，独立 sync 会话，结束即关闭。

    service 内部自管事务，故为每次调用新建独立 sync 会话；
    HTTPException/ValueError 等异常原样向上抛出，由端点层统一捕获转译。
    """
    sync_db = PrimarySessionLocal()
    try:
        return fn(sync_db)
    finally:
        sync_db.close()


@router.post(
    "/projects/{project_id}/impact-analysis/schedule",
    response_model=ApiResponse[SchedulePlanResponse],
    summary="生成 TIA 调度计划",
)
async def build_schedule_plan(
    project_id: int,
    body: SchedulePlanRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据代码变更与覆盖率映射生成 TIA 调度计划。

    业务用途：测试执行前调用，获取受影响的测试用例 ID 列表。
    边界场景：
    1. TIA_ENABLED=False → 返回全量执行计划（fallback_reason 标注）；
    2. 覆盖率数据冷启动 → 返回全量执行计划；
    3. git diff 失败 → 返回全量执行计划。
    """
    try:
        await _verify_project_owner(db, project_id, current_user.id)

        def _do(sync_db: Session) -> Any:
            service = TIAIntegrationService(db=sync_db)
            return service.build_schedule_plan(
                project_id=project_id,
                total_test_count=body.total_test_count,
                base_ref=body.base_ref,
                target_ref=body.target_ref,
                avg_test_duration_seconds=body.avg_test_duration_seconds,
            )

        plan = await asyncio.to_thread(_run_sync, _do)
        data = SchedulePlanResponse(
            test_case_ids=plan.test_case_ids,
            is_full_run=plan.is_full_run,
            fallback_reason=plan.fallback_reason,
            reduction_ratio=plan.reduction_ratio,
            estimated_saved_seconds=plan.estimated_saved_seconds,
            is_effective=plan.is_effective,
            tia_enabled=settings.TIA_ENABLED,
            total_test_count=body.total_test_count,
        )
        return create_response(data=data.model_dump(), msg="调度计划生成成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成 TIA 调度计划失败 project_id={project_id}: {e}")
        raise HTTPException(status_code=500, detail="生成 TIA 调度计划失败")


@router.get(
    "/projects/{project_id}/impact-analysis/coverage",
    response_model=ApiResponse[CoverageListResponse],
    summary="分页查询覆盖率映射",
)
async def list_coverage_maps(
    project_id: int,
    test_case_id: int | None = Query(None, description="按用例 ID 过滤"),
    file_path: str | None = Query(None, description="按文件路径过滤（精确匹配）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """分页查询项目覆盖率映射，支持按用例 ID / 文件路径过滤。"""
    try:
        await _verify_project_owner(db, project_id, current_user.id)

        def _do(sync_db: Session) -> tuple[list[TestCoverageMap], int]:
            query = select(TestCoverageMap).where(
                TestCoverageMap.project_id == project_id
            )
            if test_case_id is not None:
                query = query.where(
                    TestCoverageMap.test_case_id == test_case_id
                )
            if file_path is not None:
                query = query.where(TestCoverageMap.file_path == file_path)

            count_query = select(func.count()).select_from(query.subquery())
            total = sync_db.execute(count_query).scalar() or 0

            rows = (
                sync_db.execute(
                    query.order_by(TestCoverageMap.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                .scalars()
                .all()
            )
            return list(rows), int(total)

        rows, total = await asyncio.to_thread(_run_sync, _do)
        items = [CoverageMapItem.model_validate(r) for r in rows]
        data = CoverageListResponse(
            items=items, total=total, page=page, page_size=page_size
        )
        return create_response(data=data.model_dump(), msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询覆盖率映射失败 project_id={project_id}: {e}")
        raise HTTPException(status_code=500, detail="查询覆盖率映射失败")


@router.get(
    "/projects/{project_id}/impact-analysis/stats",
    response_model=ApiResponse[CoverageStatsResponse],
    summary="项目级覆盖率统计",
)
async def get_coverage_stats(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询项目级覆盖率统计：映射总数、唯一文件数、唯一用例数。"""
    try:
        await _verify_project_owner(db, project_id, current_user.id)

        def _do(sync_db: Session) -> dict:
            base_query = select(TestCoverageMap).where(
                TestCoverageMap.project_id == project_id
            )
            total_mappings = sync_db.execute(
                select(func.count()).select_from(base_query.subquery())
            ).scalar() or 0
            unique_files = sync_db.execute(
                select(func.count(func.distinct(TestCoverageMap.file_path)))
                .where(TestCoverageMap.project_id == project_id)
            ).scalar() or 0
            unique_cases = sync_db.execute(
                select(func.count(func.distinct(TestCoverageMap.test_case_id)))
                .where(TestCoverageMap.project_id == project_id)
            ).scalar() or 0
            return {
                "total_mappings": int(total_mappings),
                "unique_files": int(unique_files),
                "unique_test_cases": int(unique_cases),
            }

        stats = await asyncio.to_thread(_run_sync, _do)
        data = CoverageStatsResponse(
            project_id=project_id,
            tia_enabled=settings.TIA_ENABLED,
            **stats,
        )
        return create_response(data=data.model_dump(), msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取覆盖率统计失败 project_id={project_id}: {e}")
        raise HTTPException(status_code=500, detail="获取覆盖率统计失败")


@router.post(
    "/projects/{project_id}/impact-analysis/coverage",
    response_model=ApiResponse[CoverageIngestResponse],
    summary="写入覆盖率映射",
)
async def ingest_coverage(
    project_id: int,
    body: CoverageIngestRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """写入覆盖率映射：支持 coverage.json 文件路径或直接传 JSON 内容。

    业务用途：测试执行后采集覆盖率，调用本端点持久化到 test_coverage_maps 表。
    实现采用 delete + insert 模式保证幂等：同用例重跑覆盖率时不会残留过期行。
    """
    try:
        await _verify_project_owner(db, project_id, current_user.id)

        if not body.json_path and not body.json_content:
            raise HTTPException(
                status_code=400,
                detail="json_path 与 json_content 至少需提供一项",
            )

        def _do(sync_db: Session) -> int:
            service = TIAIntegrationService(db=sync_db)
            if body.json_path:
                return service.ingest_coverage_json(
                    project_id=project_id,
                    test_case_id=body.test_case_id,
                    json_path=body.json_path,
                    test_name=body.test_name,
                )
            # json_content 路径：直接解析字典并写入
            collector = service._collector  # noqa: SLF001
            entries = collector.parse_coverage_data(
                data=body.json_content or {},
                test_case_id=body.test_case_id,
                test_name=body.test_name,
            )
            return service.upsert_coverage_entries(
                project_id=project_id,
                test_case_id=body.test_case_id,
                entries=entries,
            )

        rows = await asyncio.to_thread(_run_sync, _do)
        data = CoverageIngestResponse(
            test_case_id=body.test_case_id,
            rows_written=rows,
            message=f"写入 {rows} 条覆盖率映射" if rows > 0 else "无有效覆盖率数据",
        )
        return create_response(data=data.model_dump(), msg="覆盖率写入成功")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"写入覆盖率映射失败 project_id={project_id}: {e}")
        raise HTTPException(status_code=500, detail="写入覆盖率映射失败")


@router.delete(
    "/projects/{project_id}/impact-analysis/coverage",
    response_model=ApiResponse[CoverageIngestResponse],
    summary="清空项目覆盖率映射",
)
async def clear_coverage_maps(
    project_id: int,
    test_case_id: int | None = Query(None, description="仅清空指定用例的映射，不传则清空项目全部"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """清空项目（或指定用例）的覆盖率映射。

    业务用途：覆盖率数据过期或重置 TIA 时调用。
    """
    try:
        await _verify_project_owner(db, project_id, current_user.id)

        def _do(sync_db: Session) -> int:
            query = select(TestCoverageMap).where(
                TestCoverageMap.project_id == project_id
            )
            if test_case_id is not None:
                query = query.where(
                    TestCoverageMap.test_case_id == test_case_id
                )
            rows = sync_db.execute(query).scalars().all()
            count = len(rows)
            for row in rows:
                sync_db.delete(row)
            sync_db.commit()
            return count

        deleted = await asyncio.to_thread(_run_sync, _do)
        data = CoverageIngestResponse(
            test_case_id=test_case_id or 0,
            rows_written=deleted,
            message=f"已清空 {deleted} 条覆盖率映射",
        )
        return create_response(data=data.model_dump(), msg="清空成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空覆盖率映射失败 project_id={project_id}: {e}")
        raise HTTPException(status_code=500, detail="清空覆盖率映射失败")


__all__ = ["router"]
