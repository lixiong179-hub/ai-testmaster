from fastapi import APIRouter

from app.api.v1.endpoints.test_point._queries import router as queries_router
from app.api.v1.endpoints.test_point._mutations import router as mutations_router
from app.api.v1.endpoints.test_point._management import router as management_router
from app.api.v1.endpoints.test_point._helpers import check_project_permission

router = APIRouter(prefix="/test-point", tags=["测试点管理"])

router.include_router(queries_router)
router.include_router(mutations_router)
router.include_router(management_router)

from app.api.v1.endpoints.test_point_extract import router as extract_router
from app.api.v1.endpoints.test_point_import import router as import_router
from app.api.v1.endpoints.test_point_import_stream import router as import_stream_router

router.include_router(extract_router)
router.include_router(import_router)
router.include_router(import_stream_router)
