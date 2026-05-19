from fastapi import APIRouter

from app.api.v1.endpoints.review_inbox._queries import router as queries_router
from app.api.v1.endpoints.review_inbox._mutations import router as mutations_router
from app.api.v1.endpoints.review_inbox._schemas import (
    DecisionOut,
    DecideRequest,
    BatchDecideItem,
    BatchDecideRequest,
    RollbackRequest,
    FinalizeResponse,
    require_admin,
)

router = APIRouter(prefix="/review", tags=["评审Inbox"])

router.include_router(queries_router)
router.include_router(mutations_router)
