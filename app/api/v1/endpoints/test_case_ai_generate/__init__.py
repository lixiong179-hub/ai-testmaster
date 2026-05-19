from fastapi import APIRouter

from app.api.v1.endpoints.test_case_ai_generate._generate import router as generate_router
from app.api.v1.endpoints.test_case_ai_generate._context import router as context_router
from app.api.v1.endpoints.test_case_ai_generate._precondition import router as precondition_router

router = APIRouter()

router.include_router(generate_router)
router.include_router(context_router)
router.include_router(precondition_router)
