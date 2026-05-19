from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
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


@router.post("/{review_id}/decisions/{decision_id}/decide", response_model=dict)
def decide_single(
    review_id: int,
    decision_id: int,
    body: DecideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _verify_review_access(db, review_id, current_user)

        decision = review_service.get_decisions(db, review_id)
        decision = next((d for d in decision if d.id == decision_id), None)
        if decision is None:
            raise HTTPException(status_code=404, detail="决策不存在")

        try:
            review_service.acquire_lock(
                db, review_id, decision.target_kind, decision.target_id,
            )
        except review_service.ReviewLockConflictError:
            raise HTTPException(status_code=409, detail="该决策目标已被其他用户锁定")
        except review_service.ReviewFinalizedError:
            raise HTTPException(status_code=400, detail="评审已最终化，无法修改")

        result = review_service.set_human_verdict(
            db=db,
            decision_id=decision_id,
            human_verdict=body.human_verdict,
            human_user_id=current_user.id,
            human_reason=body.human_reason,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="决策不存在")

        _check_zero_edit_confirmation(
            db, decision=result,
            ai_verdict=decision.ai_verdict,
            human_verdict=body.human_verdict,
            human_reason=body.human_reason,
        )

        db.commit()

        return create_response(
            data=_serialize_decision(result),
            msg="人工判定已提交",
        )
    except HTTPException:
        raise
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("提交人工判定失败: {}", e)
        raise HTTPException(status_code=500, detail="提交人工判定失败")


@router.post("/{review_id}/decisions/batch-decide", response_model=dict)
def decide_batch(
    review_id: int,
    body: BatchDecideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _verify_review_access(db, review_id, current_user)

        all_decisions = review_service.get_decisions(db, review_id)
        decision_map = {d.id: d for d in all_decisions}

        savepoint = db.begin_nested()

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
                    db, review_id, decision.target_kind, decision.target_id,
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
                    db=db,
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

        db.commit()

        return create_response(
            data={"decisions": results, "total": len(results)},
            msg="批量人工判定已提交",
        )
    except HTTPException:
        raise
    except review_service.ReviewError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error("批量人工判定失败: {}", e)
        raise HTTPException(status_code=500, detail="批量人工判定失败")


@router.post("/{review_id}/finalize", response_model=dict)
def finalize_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _verify_review_access(db, review_id, current_user)

        review = review_service.finalize_review(db, review_id, current_user.id)
        if review is None:
            raise HTTPException(status_code=404, detail="评审不存在")

        db.commit()

        return create_response(
            data={
                "review_id": review.id,
                "status": review.status,
                "finalized_at": review.finalized_at.isoformat() if review.finalized_at else None,
                "finalized_by": review.finalized_by,
            },
            msg="评审已最终化",
        )
    except HTTPException:
        raise
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("最终化评审失败: {}", e)
        raise HTTPException(status_code=500, detail="最终化评审失败")


@router.post(
    "/{review_id}/decisions/{decision_id}/rollback",
    response_model=dict,
)
def rollback_decision(
    review_id: int,
    decision_id: int,
    body: None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _verify_review_access(db, review_id, current_user)

        review_service.rollback_decision(
            db=db, decision_id=decision_id, user_id=current_user.id,
        )
        db.commit()
        return create_response(
            data={"success": True, "detail": "决策已回滚", "rolled_back_decision_ids": [decision_id]},
            msg="决策已回滚",
        )
    except HTTPException:
        raise
    except review_service.ReviewUndoWindowExpiredError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except review_service.ReviewNotFinalizedError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except review_service.ReviewError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error("回滚决策失败: {}", e)
        raise HTTPException(status_code=500, detail="回滚决策失败")


@router.post("/{review_id}/undo-decision/{decision_id}", response_model=dict)
def undo_decision(
    review_id: int,
    decision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _verify_review_access(db, review_id, current_user)

        decision = review_service.undo_decision(db=db, decision_id=decision_id, user_id=current_user.id)
        if decision is None:
            raise HTTPException(status_code=404, detail="决策不存在")
        db.commit()

        return create_response(
            data={
                "human_verdict": decision.human_verdict,
                "final_verdict": decision.final_verdict,
                "rolled_back_decision_ids": [decision_id],
            },
            msg="决策已撤销",
        )
    except HTTPException:
        raise
    except review_service.ReviewUndoWindowExpiredError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except review_service.ReviewNotFinalizedError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except review_service.ReviewError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error("撤销决策失败: {}", e)
        raise HTTPException(status_code=500, detail="撤销决策失败")


@router.post("/{review_id}/undo-finalize", response_model=dict)
def undo_finalize(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        review = review_service.undo_finalize(db=db, review_id=review_id, user_id=current_user.id)
        if review is None:
            raise HTTPException(status_code=404, detail="评审不存在")
        db.commit()

        return create_response(
            data={"status": review.status, "detail": "评审已撤销最终化", "undone_case_count": 0, "rolled_back_decision_ids": []},
            msg="评审已撤销最终化",
        )
    except HTTPException:
        raise
    except review_service.ReviewUndoWindowExpiredError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except review_service.ReviewNotFinalizedError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except review_service.ReviewError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error("撤销最终化失败: {}", e)
        raise HTTPException(status_code=500, detail="撤销最终化失败")


@router.post("/{review_id}/apply-decisions", response_model=dict)
def apply_decisions_endpoint(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _verify_review_access(db, review_id, current_user)
        review = review_service.get_review(db, review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="评审不存在")
        if not review.is_finalized():
            raise HTTPException(status_code=400, detail="评审未最终化，无法应用决策")

        from app.services.decision_application_service import apply_decisions
        results = apply_decisions(review_id=review_id, db=db, actor_id=current_user.id)
        db.commit()

        return create_response(
            data={
                "review_id": review_id,
                "applied_count": len(results),
                "success_count": sum(1 for r in results if r.success),
                "failed_count": sum(1 for r in results if not r.success),
            },
            msg="决策应用完成",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("手动应用决策失败: {}", e)
        raise HTTPException(status_code=500, detail="手动应用决策失败")
