"""review_inbox 人工判定端点（mutations）。

review_service 为 sync 实现，端点使用 asyncio.to_thread + PrimarySessionLocal
在独立线程中执行 sync 业务逻辑，释放事件循环并避免与 AsyncSession 事务冲突。
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from app.db.database import async_get_db, PrimarySessionLocal
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.schemas.common import ApiResponse
from app.services import review_service
from app.api.v1.endpoints.review_inbox._schemas import (
    DecideRequest,
    BatchDecideRequest,
    _verify_review_access,
    _serialize_decision,
    _check_zero_edit_confirmation,
    require_admin,
)

router = APIRouter()


async def _run_review_mutation(fn):
    """在独立线程中执行 sync review_service 逻辑，释放事件循环。

    使用 PrimarySessionLocal 创建独立 sync 会话，避免与 AsyncSession 事务冲突。
    fn 接收 sync_db 参数，需自行管理 commit/rollback/savepoint。
    """
    sync_db = PrimarySessionLocal()
    try:
        return await asyncio.to_thread(fn, sync_db)
    finally:
        sync_db.close()


@router.post("/{review_id}/decisions/{decision_id}/decide", response_model=ApiResponse)
async def decide_single(
    review_id: int,
    decision_id: int,
    body: DecideRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _decide(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)

            decision = review_service.get_decisions(sync_db, review_id)
            decision = next((d for d in decision if d.id == decision_id), None)
            if decision is None:
                raise HTTPException(status_code=404, detail="决策不存在")

            try:
                review_service.acquire_lock(
                    sync_db, review_id, decision.target_kind, decision.target_id,
                )
            except review_service.ReviewLockConflictError:
                raise HTTPException(status_code=409, detail="该决策目标已被其他用户锁定")
            except review_service.ReviewFinalizedError:
                raise HTTPException(status_code=400, detail="评审已最终化，无法修改")

            result = review_service.set_human_verdict(
                db=sync_db,
                decision_id=decision_id,
                human_verdict=body.human_verdict,
                human_user_id=current_user.id,
                human_reason=body.human_reason,
            )
            if result is None:
                raise HTTPException(status_code=404, detail="决策不存在")

            _check_zero_edit_confirmation(
                sync_db, decision=result,
                ai_verdict=decision.ai_verdict,
                human_verdict=body.human_verdict,
                human_reason=body.human_reason,
            )

            sync_db.commit()

            return _serialize_decision(result)

        data = await _run_review_mutation(_decide)
        return create_response(data=data, msg="人工判定已提交")
    except HTTPException:
        raise
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("提交人工判定失败: {}", e)
        raise HTTPException(status_code=500, detail="提交人工判定失败")


@router.post("/{review_id}/decisions/batch-decide", response_model=ApiResponse)
async def decide_batch(
    review_id: int,
    body: BatchDecideRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _batch_decide(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)

            all_decisions = review_service.get_decisions(sync_db, review_id)
            decision_map = {d.id: d for d in all_decisions}

            savepoint = sync_db.begin_nested()

            for item in body.decisions:
                decision = decision_map.get(item.decision_id)
                if decision is None:
                    savepoint.rollback()
                    raise HTTPException(
                        status_code=404,
                        detail=f"决策 {item.decision_id} 不存在或不属于此评审",
                    )

                try:
                    review_service.acquire_lock(
                        sync_db, review_id, decision.target_kind, decision.target_id,
                    )
                except review_service.ReviewLockConflictError:
                    savepoint.rollback()
                    raise HTTPException(
                        status_code=409,
                        detail=f"决策目标 ({decision.target_kind}, {decision.target_id}) 已被锁定",
                    )
                except review_service.ReviewFinalizedError:
                    savepoint.rollback()
                    raise HTTPException(status_code=400, detail="评审已最终化，无法批量决策")

            results = []
            for item in body.decisions:
                try:
                    result = review_service.set_human_verdict(
                        db=sync_db,
                        decision_id=item.decision_id,
                        human_verdict=item.human_verdict,
                        human_user_id=current_user.id,
                        human_reason=item.human_reason,
                    )
                    results.append(_serialize_decision(result))
                except review_service.ReviewError:
                    savepoint.rollback()
                    raise HTTPException(
                        status_code=400,
                        detail=f"决策 {item.decision_id} 判定值无效",
                    )

            sync_db.commit()

            return {"decisions": results, "total": len(results)}

        data = await _run_review_mutation(_batch_decide)
        return create_response(data=data, msg="批量人工判定已提交")
    except HTTPException:
        raise
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("批量人工判定失败: {}", e)
        raise HTTPException(status_code=500, detail="批量人工判定失败")


@router.post("/{review_id}/finalize", response_model=ApiResponse)
async def finalize_review(
    review_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _finalize(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)

            review = review_service.finalize_review(sync_db, review_id, current_user.id)
            if review is None:
                raise HTTPException(status_code=404, detail="评审不存在")

            sync_db.commit()

            return {
                "review_id": review.id,
                "status": review.status,
                "finalized_at": review.finalized_at.isoformat() if review.finalized_at else None,
                "finalized_by": review.finalized_by,
            }

        data = await _run_review_mutation(_finalize)
        return create_response(data=data, msg="评审已最终化")
    except HTTPException:
        raise
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("最终化评审失败: {}", e)
        raise HTTPException(status_code=500, detail="最终化评审失败")


@router.post(
    "/{review_id}/decisions/{decision_id}/rollback",
    response_model=ApiResponse,
)
async def rollback_decision(
    review_id: int,
    decision_id: int,
    body: None = None,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _rollback(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)

            review_service.rollback_decision(
                db=sync_db, decision_id=decision_id, user_id=current_user.id,
            )
            sync_db.commit()
            return {"success": True, "detail": "决策已回滚", "rolled_back_decision_ids": [decision_id]}

        data = await _run_review_mutation(_rollback)
        return create_response(data=data, msg="决策已回滚")
    except HTTPException:
        raise
    except review_service.ReviewUndoWindowExpiredError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except review_service.ReviewNotFinalizedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("回滚决策失败: {}", e)
        raise HTTPException(status_code=500, detail="回滚决策失败")


@router.post("/{review_id}/undo-decision/{decision_id}", response_model=ApiResponse)
async def undo_decision(
    review_id: int,
    decision_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _undo(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)

            decision = review_service.undo_decision(db=sync_db, decision_id=decision_id, user_id=current_user.id)
            if decision is None:
                raise HTTPException(status_code=404, detail="决策不存在")
            sync_db.commit()

            return {
                "human_verdict": decision.human_verdict,
                "final_verdict": decision.final_verdict,
                "rolled_back_decision_ids": [decision_id],
            }

        data = await _run_review_mutation(_undo)
        return create_response(data=data, msg="决策已撤销")
    except HTTPException:
        raise
    except review_service.ReviewUndoWindowExpiredError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except review_service.ReviewNotFinalizedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("撤销决策失败: {}", e)
        raise HTTPException(status_code=500, detail="撤销决策失败")


@router.post("/{review_id}/undo-finalize", response_model=ApiResponse)
async def undo_finalize(
    review_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(require_admin),
):
    try:
        def _undo_finalize(sync_db: Session):
            review = review_service.undo_finalize(db=sync_db, review_id=review_id, user_id=current_user.id)
            if review is None:
                raise HTTPException(status_code=404, detail="评审不存在")
            sync_db.commit()

            return {"status": review.status, "detail": "评审已撤销最终化", "undone_case_count": 0, "rolled_back_decision_ids": []}

        data = await _run_review_mutation(_undo_finalize)
        return create_response(data=data, msg="评审已撤销最终化")
    except HTTPException:
        raise
    except review_service.ReviewUndoWindowExpiredError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except review_service.ReviewNotFinalizedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("撤销最终化失败: {}", e)
        raise HTTPException(status_code=500, detail="撤销最终化失败")


@router.post("/{review_id}/apply-decisions", response_model=ApiResponse)
async def apply_decisions_endpoint(
    review_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _apply(sync_db: Session):
            _verify_review_access(sync_db, review_id, current_user)
            review = review_service.get_review(sync_db, review_id)
            if review is None:
                raise HTTPException(status_code=404, detail="评审不存在")
            if not review.is_finalized():
                raise HTTPException(status_code=400, detail="评审未最终化，无法应用决策")

            from app.services.decision_application_service import apply_decisions
            results = apply_decisions(review_id=review_id, db=sync_db, actor_id=current_user.id)
            sync_db.commit()

            return {
                "review_id": review_id,
                "applied_count": len(results),
                "success_count": sum(1 for r in results if r.success),
                "failed_count": sum(1 for r in results if not r.success),
            }

        data = await _run_review_mutation(_apply)
        return create_response(data=data, msg="决策应用完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("手动应用决策失败: {}", e)
        raise HTTPException(status_code=500, detail="手动应用决策失败")
