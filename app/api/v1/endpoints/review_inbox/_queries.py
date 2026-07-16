from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.services import review_service
from app.api.v1.endpoints.review_inbox._schemas import (
    _verify_review_access,
    _serialize_decision,
)

router = APIRouter()


@router.get("/{review_id}/decisions", response_model=dict)
async def list_decisions(
    review_id: int,
    verdict: Optional[str] = None,
    target_kind: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "desc",
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _list(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)

            decisions = review_service.get_decisions(sync_db, review_id, target_kind=target_kind)

            if verdict is not None:
                decisions = [d for d in decisions if d.final_verdict == verdict]

            if sort_by == "confidence":
                reverse = order != "asc"
                decisions = sorted(
                    decisions,
                    key=lambda d: d.ai_confidence if d.ai_confidence is not None else 0,
                    reverse=reverse,
                )
            elif sort_by == "decided_at":
                reverse = order != "asc"
                decisions = sorted(
                    decisions,
                    key=lambda d: d.decided_at if d.decided_at else None,
                    reverse=reverse,
                )

            return {
                "decisions": [_serialize_decision(d) for d in decisions],
                "total": len(decisions),
            }

        data = await db.run_sync(_list)
        return create_response(data=data, msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取决策列表失败: {}", e)
        raise HTTPException(status_code=500, detail="获取决策列表失败")
