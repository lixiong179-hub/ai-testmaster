import asyncio
import json

"""
测试用例工作流端点模块

本模块定义测试用例工作流和纠正状态管理的API端点。
与test_case_status模块功能重叠，保留以兼容旧版路由。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - GET  /{test_case_id}/workflow            - 获取工作流状态
    - POST /{test_case_id}/workflow/transition  - 工作流状态转换
    - GET  /{test_case_id}/correction-status    - 获取纠正状态
    - POST /{test_case_id}/start-correction     - 开始纠正
    - POST /{test_case_id}/submit-verification  - 提交验证

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.user import User
from app.services.test_case_view_service import TestCaseViewService
from app.api.v1.endpoints.auth import get_current_user
from app.core.permissions import require_technical_view
from app.utils.db_time import utcnow
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


@router.get("/{test_case_id}/technical-view")
async def get_test_case_technical_view(
    test_case_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_technical_view)
):
    try:
        service = TestCaseViewService(db)
        technical_view = await asyncio.to_thread(service.get_technical_view, test_case_id)
        if not technical_view:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")
        return create_response(data=technical_view)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取技术视图失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取技术视图失败")


@router.get("/{test_case_id}/business-view")
async def get_test_case_business_view(
    test_case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        service = TestCaseViewService(db)
        business_view = await asyncio.to_thread(service.get_business_view, test_case_id)
        if not business_view:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")
        return create_response(data=business_view.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取业务视图失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取业务视图失败")


@router.get("/{test_case_id}/locator-coverage")
async def get_locator_coverage(
    test_case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        service = TestCaseViewService(db)
        coverage = await asyncio.to_thread(service.get_locator_coverage, test_case_id)
        return create_response(data=coverage)
    except Exception as e:
        logger.error(f"获取定位覆盖率失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取定位覆盖率失败")


@router.get("/{test_case_id}/view-statistics")
async def get_view_statistics(
    test_case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        service = TestCaseViewService(db)
        statistics = await asyncio.to_thread(service.get_view_statistics, test_case_id)
        return create_response(data=statistics)
    except Exception as e:
        logger.error(f"获取视图统计失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取视图统计失败")


class BatchViewConfigRequest(BaseModel):
    view_type: str
    visible: bool

    @field_validator("view_type")
    @classmethod
    def validate_view_type(cls, v: str) -> str:
        if v not in ("business", "technical"):
            raise ValueError('view_type must be "business" or "technical"')
        return v


@router.put("/{test_case_id}/batch-view-config")
async def batch_update_view_config(
    test_case_id: int,
    config: BatchViewConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        service = TestCaseViewService(db)
        updated_count = await asyncio.to_thread(
            service.batch_update_view_config,
            test_case_id,
            config.view_type,
            config.visible,
        )
        return create_response(data={"updated_count": updated_count})
    except Exception as e:
        logger.error(f"批量更新视图配置失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="批量更新视图配置失败")


class StepViewConfigRequest(BaseModel):
    is_business_view: int | None = None
    is_technical_view: int | None = None


@router.put("/steps/{step_id}/view-config")
async def update_step_view_config(
    step_id: int,
    config: StepViewConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        service = TestCaseViewService(db)
        success = await asyncio.to_thread(
            service.update_step_view_config,
            step_id,
            config.is_business_view,
            config.is_technical_view,
        )
        return create_response(data={"success": success})
    except Exception as e:
        logger.error(f"更新步骤视图配置失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新步骤视图配置失败")


@router.post("/steps/{step_id}/locator")
async def add_step_locator(
    step_id: int,
    css_selector: str | None = None,
    xpath: str | None = None,
    element_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technical_view),
):
    result = await asyncio.to_thread(db.execute, select(TestStep).where(TestStep.id == step_id))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试步骤不存在")

    if not css_selector and not xpath:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供CSS选择器或XPath至少一种定位方式")

    try:
        result = await asyncio.to_thread(
            db.execute,
            select(ElementLocator).where(ElementLocator.step_id == step_id),
        )
        existing_locator = result.scalar_one_or_none()

        if existing_locator:
            if css_selector:
                existing_locator.css_selector = css_selector
            if xpath:
                existing_locator.xpath = xpath
            if element_type:
                existing_locator.element_type = element_type
            existing_locator.updated_at = utcnow()
            await asyncio.to_thread(db.commit)
            await asyncio.to_thread(db.refresh, existing_locator)
            step.has_locator = 1
            step.locator_status = "recorded"
            await asyncio.to_thread(db.commit)
            return {
                "locator_id": existing_locator.id,
                "message": "定位信息更新成功",
                "css_selector": existing_locator.css_selector,
                "xpath": existing_locator.xpath,
            }
        else:
            new_locator = ElementLocator(
                step_id=step_id,
                css_selector=css_selector,
                xpath=xpath,
                element_type=element_type or "unknown",
                ai_confidence=1.0,
                source="manual",
            )
            db.add(new_locator)
            await asyncio.to_thread(db.flush)
            step.has_locator = 1
            step.locator_status = "recorded"
            await asyncio.to_thread(db.commit)
            return {
                "locator_id": new_locator.id,
                "message": "定位信息添加成功",
                "css_selector": new_locator.css_selector,
                "xpath": new_locator.xpath,
            }
    except Exception as e:
        await asyncio.to_thread(db.rollback)
        logger.error(f"添加定位信息失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="添加定位信息失败")


class TechnicalViewEditRequest(BaseModel):
    steps: list | None = None
    exec_script: str | None = None
    locators: dict | None = None

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: list | None) -> list | None:
        if v is not None and len(v) > 200:
            raise ValueError(f"步骤数量不能超过200，当前: {len(v)}")
        return v


#: 技术视图编辑允许回写 TestStep 的字段白名单（顺序无关，仅出现才写）。
_STEP_EDITABLE_FIELDS = ("action_type", "input_value", "target_element", "action", "expected_result")


async def _lookup_step(db: Session, test_case_id: int, step_number: int):
    """按用例 + 步骤序号查 TestStep 记录。"""
    result = await asyncio.to_thread(
        db.execute,
        select(TestStep).where(TestStep.test_case_id == test_case_id, TestStep.step_number == step_number),
    )
    return result.scalar_one_or_none()


async def _lookup_locator(db: Session, step_id: int):
    """查步骤对应的元素定位记录。"""
    result = await asyncio.to_thread(
        db.execute,
        select(ElementLocator).where(ElementLocator.step_id == step_id),
    )
    return result.scalar_one_or_none()


def _assign_step_fields(db_step, updated_step: dict) -> None:
    """把编辑内容按白名单写入 TestStep（只写请求里出现的键）。"""
    for field_name in _STEP_EDITABLE_FIELDS:
        if field_name in updated_step:
            setattr(db_step, field_name, updated_step[field_name])


def _merge_step_json(existing_steps: list, step_id, updated_step: dict) -> None:
    """把编辑内容合并回 steps_json 中同 step_number 的项。"""
    for idx, existing in enumerate(existing_steps):
        if isinstance(existing, dict) and existing.get("step_number") == step_id:
            existing_steps[idx].update({k: v for k, v in updated_step.items() if k != "step_number"})


async def _apply_steps_update(db: Session, test_case, test_case_id: int, steps: list[dict]) -> None:
    """按 step_number 更新 TestStep 并同步 steps_json。"""
    existing_steps = (
        test_case.steps_json if isinstance(test_case.steps_json, list) else json.loads(test_case.steps_json or "[]")
    )
    for updated_step in steps:
        step_id = updated_step.get("step_number")
        if not step_id:
            continue
        db_step = await _lookup_step(db, test_case_id, step_id)
        if db_step:
            _assign_step_fields(db_step, updated_step)
        _merge_step_json(existing_steps, step_id, updated_step)
    test_case.steps_json = existing_steps


def _assign_locator_fields(existing_locator, locator_data: dict) -> None:
    """把定位字段写入已有 ElementLocator（只写请求里出现的键）。"""
    if "css_selector" in locator_data:
        existing_locator.css_selector = locator_data["css_selector"]
    if "xpath" in locator_data:
        existing_locator.xpath = locator_data["xpath"]
    if "element_type" in locator_data:
        existing_locator.element_type = locator_data["element_type"]


def _build_locator(step_id: int, locator_data: dict):
    """人工录入的元素定位默认值：置信度 1.0、来源 manual。"""
    return ElementLocator(
        step_id=step_id,
        css_selector=locator_data.get("css_selector"),
        xpath=locator_data.get("xpath"),
        element_type=locator_data.get("element_type", "unknown"),
        ai_confidence=1.0,
        source="manual",
    )


async def _apply_locators_update(db: Session, test_case_id: int, locators: dict) -> None:
    """按 step_number 新建/更新元素定位，并回写步骤定位状态。"""
    for step_number, locator_data in locators.items():
        db_step = await _lookup_step(db, test_case_id, int(step_number))
        if not db_step:
            continue
        existing_locator = await _lookup_locator(db, db_step.id)
        if existing_locator:
            _assign_locator_fields(existing_locator, locator_data)
            existing_locator.updated_at = utcnow()
        else:
            db.add(_build_locator(db_step.id, locator_data))
        db_step.has_locator = 1
        db_step.locator_status = "recorded"


@router.put("/{test_case_id}/technical-view")
async def update_technical_view(
    test_case_id: int,
    request: TechnicalViewEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technical_view),
):
    result = await asyncio.to_thread(
        db.execute,
        select(TestCase).where(TestCase.id == test_case_id, TestCase.is_deleted.is_(False)),
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")

    try:
        if request.exec_script is not None:
            test_case.exec_script = request.exec_script

        if request.steps is not None:
            await _apply_steps_update(db, test_case, test_case_id, request.steps)

        if request.locators is not None:
            await _apply_locators_update(db, test_case_id, request.locators)

        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, test_case)
        logger.info(f"[技术视图编辑] 用户ID={current_user.id}, 用例ID={test_case_id}")

        service = TestCaseViewService(db)
        technical_view = await asyncio.to_thread(service.get_technical_view, test_case_id)
        return create_response(data=technical_view)
    except HTTPException:
        raise
    except Exception as e:
        await asyncio.to_thread(db.rollback)
        logger.error(f"更新技术视图失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新技术视图失败")
