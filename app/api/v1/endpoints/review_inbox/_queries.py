from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.schemas.common import ApiResponse
from app.services import review_service
from app.api.v1.endpoints.review_inbox._schemas import (
    _verify_review_access,
    _serialize_decision,
)

router = APIRouter()


@router.get("/{review_id}/decisions", response_model=ApiResponse)
async def list_decisions(
    review_id: int,
    verdict: Optional[str] = None,
    target_kind: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "desc",
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _list(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)

            # P2-3: verdict 过滤 + 排序下推至 SQL（原在 Python 内存中执行）
            decisions = review_service.get_decisions(
                sync_db,
                review_id,
                target_kind=target_kind,
                verdict=verdict,
                sort_by=sort_by,
                order=order,
            )

            # P2-4: 分页（service 返回 Python list，按切片分页）
            total = len(decisions)
            skip = (page - 1) * page_size
            page_decisions = decisions[skip:skip + page_size]

            return {
                "decisions": [_serialize_decision(d) for d in page_decisions],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        data = await db.run_sync(_list)
        return create_response(data=data, msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取决策列表失败: {}", e)
        raise HTTPException(status_code=500, detail="获取决策列表失败")
