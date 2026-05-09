"""评审 Inbox 后端 API

提供迭代评审的决策列表查询、人工判定提交（单个/批量）、最终化等功能。
每个决策在提交人工判定时获取 ReviewLock，finalize 后释放锁。

端点:
    GET    /review/{review_id}/decisions       — 查询决策列表
    POST   /review/{review_id}/decisions/{decision_id}/decide — 单条人工判定
    POST   /review/{review_id}/decisions/batch-decide         — 批量人工判定
    POST   /review/{review_id}/finalize                       — 最终化评审
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.review import IterationReview, ReviewDecision
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.services import review_service

router = APIRouter(prefix="/review", tags=["评审Inbox"])


class DecisionOut(BaseModel):
    id: int
    target_kind: str
    target_id: int
    target_version: Optional[int] = None
    ai_verdict: Optional[str] = None
    ai_confidence: Optional[int] = None
    ai_reason: Optional[str] = None
    modification_hint: Optional[str] = None
    deprecate_reason: Optional[str] = None
    human_verdict: Optional[str] = None
    human_user_id: Optional[int] = None
    human_reason: Optional[str] = None
    final_verdict: Optional[str] = None
    conflict_marker: bool = False
    accepted_low_confidence: bool = False
    decided_at: Optional[str] = None

    model_config = {"from_attributes": True}


class DecideRequest(BaseModel):
    human_verdict: str = Field(..., description="人工判定: keep/modify/deprecate")
    human_reason: Optional[str] = Field(None, description="判定理由")


class BatchDecideItem(BaseModel):
    decision_id: int
    human_verdict: str = Field(..., description="人工判定: keep/modify/deprecate")
    human_reason: Optional[str] = Field(None)


class BatchDecideRequest(BaseModel):
    decisions: List[BatchDecideItem] = Field(..., min_length=1, max_length=500)


def _verify_review_access(
    db: Session, review_id: int, current_user: User
) -> IterationReview:
    review = db.get(IterationReview, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="评审不存在")
    iteration = db.get(Iteration, review.iteration_id)
    if iteration is None:
        raise HTTPException(status_code=404, detail="迭代不存在")
    project = db.query(Project).filter(
        Project.id == iteration.project_id,
        Project.user_id == current_user.id,
    ).first()
    if project is None:
        raise HTTPException(status_code=403, detail="无权限操作此评审")
    return review


def _serialize_decision(d: ReviewDecision) -> dict:
    return {
        "id": d.id,
        "target_kind": d.target_kind,
        "target_id": d.target_id,
        "target_version": d.target_version,
        "ai_verdict": d.ai_verdict,
        "ai_confidence": d.ai_confidence,
        "ai_reason": d.ai_reason,
        "modification_hint": d.modification_hint,
        "deprecate_reason": d.deprecate_reason,
        "human_verdict": d.human_verdict,
        "human_user_id": d.human_user_id,
        "human_reason": d.human_reason,
        "final_verdict": d.final_verdict,
        "conflict_marker": d.conflict_marker,
        "accepted_low_confidence": d.accepted_low_confidence,
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
    }


@router.get("/{review_id}/decisions", response_model=dict)
def list_decisions(
    review_id: int,
    verdict: Optional[str] = None,
    target_kind: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _verify_review_access(db, review_id, current_user)

        decisions = review_service.get_decisions(db, review_id, target_kind=target_kind)

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

        return create_response(
            data={
                "decisions": [_serialize_decision(d) for d in decisions],
                "total": len(decisions),
            },
            msg="获取成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取决策列表失败: {}", e)
        raise HTTPException(status_code=500, detail=f"获取决策列表失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"提交人工判定失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"批量人工判定失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"最终化评审失败: {str(e)}")


class RollbackRequest(BaseModel):
    reason: Optional[str] = Field(None, description="回滚原因")


class FinalizeResponse(BaseModel):
    success: bool
    detail: str = ""
    undone_case_count: int = 0
    rolled_back_decision_ids: List[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}


@router.post(
    "/{review_id}/decisions/{decision_id}/rollback",
    response_model=dict,
)
def rollback_decision(
    review_id: int,
    decision_id: int,
    body: RollbackRequest = RollbackRequest(),
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
        raise HTTPException(status_code=500, detail=f"回滚决策失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"撤销决策失败: {str(e)}")


def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return current_user


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
        raise HTTPException(status_code=500, detail=f"撤销最终化失败: {str(e)}")


def _check_zero_edit_confirmation(
    db: Session,
    decision: ReviewDecision,
    ai_verdict: Optional[str],
    human_verdict: str,
    human_reason: Optional[str],
) -> None:
    """检测 F5 敷衍确认（用户直接采纳 AI 判定且无理由）。"""
    if ai_verdict == human_verdict and not human_reason:
        try:
            from app.services.metrics_service import record_metric
            from app.models.test_case import TestCase
            project_id = None
            if decision.target_kind == "case" and decision.target_id:
                case = db.query(TestCase).filter(
                    TestCase.id == decision.target_id,
                ).first()
                if case:
                    project_id = case.project_id
            record_metric(
                "confirmed_zero_edit",
                project_id=project_id,
                detail={
                    "decision_id": decision.id,
                    "ai_verdict": ai_verdict,
                    "human_verdict": human_verdict,
                },
            )
        except Exception:
            pass
