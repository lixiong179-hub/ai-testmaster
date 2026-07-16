"""
测试数据API

提供测试数据的CRUD接口
"""
from typing import Optional, List
"""
测试数据端点模块

本模块定义测试数据管理的API端点，支持测试数据的创建、查询、更新和删除。

路由前缀: /testData
标签: 测试数据管理

端点概览:
    - POST   /                    - 创建测试数据
    - GET    /list                - 获取测试数据列表
    - GET    /{test_data_id}      - 获取测试数据详情
    - PUT    /{test_data_id}      - 更新测试数据
    - DELETE /{test_data_id}      - 删除测试数据
    - POST   /generate            - AI生成测试数据

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 测试数据关联测试步骤
    - 支持多种数据类型：字符串/数字/日期/枚举等
    - AI生成基于字段规则自动构造测试数据
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from loguru import logger

from app.db.database import async_get_db
from app.models.user import User
from app.models.test_data import DataType, GenerationRule
from app.api.v1.endpoints.auth import get_current_user
from app.services.test_data_service import TestDataService

router = APIRouter(prefix="/test-data", tags=["测试数据"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class TestDataCreateRequest(BaseModel):
    """创建测试数据请求"""
    step_id: int = Field(..., description="步骤ID")
    field_name: str = Field(..., description="字段名称")
    field_type: DataType = Field(default=DataType.TEXT, description="字段类型")
    generation_rule: GenerationRule = Field(default=GenerationRule.RANDOM, description="生成规则")
    data_value: Optional[str] = Field(None, description="数据值（自定义规则时使用）")
    rule_config: Optional[dict] = Field(None, description="规则配置")
    min_length: Optional[int] = Field(None, description="最小长度")
    max_length: Optional[int] = Field(None, description="最大长度")
    min_value: Optional[int] = Field(None, description="最小值")
    max_value: Optional[int] = Field(None, description="最大值")
    enum_values: Optional[List[str]] = Field(None, description="枚举值列表")
    description: Optional[str] = Field(None, description="描述")
    is_required: bool = Field(default=True, description="是否必填")
    sort_order: int = Field(default=0, description="排序顺序")


class TestDataUpdateRequest(BaseModel):
    """更新测试数据请求"""
    field_name: Optional[str] = Field(None, description="字段名称")
    field_type: Optional[DataType] = Field(None, description="字段类型")
    generation_rule: Optional[GenerationRule] = Field(None, description="生成规则")
    data_value: Optional[str] = Field(None, description="数据值")
    rule_config: Optional[dict] = Field(None, description="规则配置")
    min_length: Optional[int] = Field(None, description="最小长度")
    max_length: Optional[int] = Field(None, description="最大长度")
    min_value: Optional[int] = Field(None, description="最小值")
    max_value: Optional[int] = Field(None, description="最大值")
    enum_values: Optional[List[str]] = Field(None, description="枚举值列表")
    description: Optional[str] = Field(None, description="描述")
    is_required: Optional[bool] = Field(None, description="是否必填")
    sort_order: Optional[int] = Field(None, description="排序顺序")


class TestDataResponse(BaseModel):
    """测试数据响应"""
    id: int
    step_id: int
    field_name: str
    field_type: str
    data_value: Optional[str]
    generation_rule: str
    rule_config: Optional[dict]
    min_length: Optional[int]
    max_length: Optional[int]
    min_value: Optional[int]
    max_value: Optional[int]
    enum_values: Optional[List[str]]
    description: Optional[str]
    is_required: bool
    sort_order: int

    class Config:
        from_attributes = True


class StepTestDataResponse(BaseModel):
    """步骤测试数据响应"""
    step_id: int
    data_list: List[TestDataResponse]


class GenerateStepDataResponse(BaseModel):
    """生成步骤数据响应"""
    step_id: int
    generated_data: dict


# ============================================================================
# API端点
# ============================================================================

@router.post("/", response_model=TestDataResponse)
async def create_test_data(
    request: TestDataCreateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """创建测试数据"""
    try:
        def _create(sync_db):
            service = TestDataService(sync_db)
            return service.create_test_data(**request.model_dump())
        test_data = await db.run_sync(_create)
        return test_data.to_dict()
    except Exception as e:
        logger.error(f"创建测试数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建失败"
        )


@router.get("/{test_data_id}", response_model=TestDataResponse)
async def get_test_data(
    test_data_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个测试数据"""
    def _get(sync_db):
        service = TestDataService(sync_db)
        return service.get_test_data(test_data_id)
    test_data = await db.run_sync(_get)
    if not test_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试数据不存在"
        )
    return test_data.to_dict()


@router.get("/step/{step_id}", response_model=StepTestDataResponse)
async def get_test_data_by_step(
    step_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取步骤的所有测试数据"""
    def _get(sync_db):
        service = TestDataService(sync_db)
        return service.get_test_data_by_step(step_id)
    data_list = await db.run_sync(_get)
    return {
        "step_id": step_id,
        "data_list": [data.to_dict() for data in data_list]
    }


@router.put("/{test_data_id}", response_model=TestDataResponse)
async def update_test_data(
    test_data_id: int,
    request: TestDataUpdateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """更新测试数据"""
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    def _update(sync_db):
        service = TestDataService(sync_db)
        return service.update_test_data(test_data_id, **update_data)
    test_data = await db.run_sync(_update)
    if not test_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试数据不存在"
        )
    return test_data.to_dict()


@router.delete("/{test_data_id}")
async def delete_test_data(
    test_data_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """删除测试数据"""
    def _delete(sync_db):
        service = TestDataService(sync_db)
        return service.delete_test_data(test_data_id)
    success = await db.run_sync(_delete)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试数据不存在"
        )
    return {"success": True, "message": "删除成功"}


@router.post("/step/{step_id}/generate", response_model=GenerateStepDataResponse)
async def generate_step_data(
    step_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """生成步骤的测试数据"""
    try:
        def _generate(sync_db):
            service = TestDataService(sync_db)
            return service.generate_step_data(step_id)
        generated_data = await db.run_sync(_generate)
        return {
            "step_id": step_id,
            "generated_data": generated_data
        }
    except Exception as e:
        logger.error(f"生成步骤数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成失败"
        )


@router.post("/step/{step_id}/auto-generate")
async def auto_generate_test_data(
    step_id: int,
    action_description: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """根据操作描述自动推断生成测试数据"""
    try:
        def _auto_generate(sync_db):
            service = TestDataService(sync_db)
            return service.auto_generate_for_step(step_id, action_description)
        created_list = await db.run_sync(_auto_generate)
        return {
            "success": True,
            "count": len(created_list),
            "data_list": [data.to_dict() for data in created_list]
        }
    except Exception as e:
        logger.error(f"自动生成测试数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成失败"
        )
