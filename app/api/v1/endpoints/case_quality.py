"""
用例质量模块（聚合入口）

本模块为用例质量功能的聚合入口，将质量检查和报告子模块统一注册到同一路由前缀下。

路由前缀: /caseQuality
标签: 用例质量

子模块概览:
    - case_quality_check: 用例质量检查（规则检查/评分）
    - case_quality_report: 用例质量报告（统计/趋势）

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter
from app.api.v1.endpoints.case_quality_check import router as check_router
from app.api.v1.endpoints.case_quality_report import router as report_router
from app.api.v1.endpoints.case_quality_posterior import router as posterior_router

router = APIRouter(prefix="/quality", tags=["用例质量"])

router.include_router(check_router)
router.include_router(report_router)
router.include_router(posterior_router)
