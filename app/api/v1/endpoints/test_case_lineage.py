"""用例血缘 API — 暴露用例血缘树查询接口

端点:
    GET /{test_case_id}/lineage - 返回血缘树（祖先 + 后代）
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import async_get_db, PrimarySessionLocal
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.lineage_service import get_lineage, LineageResult

router = APIRouter()


@router.get("/{test_case_id}/lineage", response_model=LineageResult)
async def get_case_lineage(
    test_case_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> LineageResult:
    """获取用例血缘树

    Args:
        test_case_id: 用例ID

    Returns:
        血缘树数据，包含祖先链、后代子树、链长度和警告信息
    """
    # get_lineage 是 sync 读操作，使用独立 sync 会话 + to_thread 释放事件循环
    def _do_get_lineage(sync_db) -> Optional[LineageResult]:
        return get_lineage(sync_db, test_case_id)

    sync_db = PrimarySessionLocal()
    try:
        result: Optional[LineageResult] = await asyncio.to_thread(_do_get_lineage, sync_db)
    finally:
        sync_db.close()
    if result is None:
        raise HTTPException(status_code=404, detail=f"TestCase {test_case_id} not found")
    return result
