"""
测试用例版本管理端点模块

本模块定义测试用例版本管理的 API 端点。
路由前缀: /testCase（由父模块 test_case.py 注册）。
权限要求: 所有端点需要 Bearer 令牌认证。

导出功能已拆分至 test_case_export 子模块。

详见各 @router 装饰器，主要包括:
    - 版本列表/详情/恢复
"""
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.utils.test_case_helpers import build_test_case_response
from app.core.exception import create_response
from loguru import logger

router = APIRouter()

# 将导出子模块路由注册到主路由
from app.api.v1.endpoints.test_case_export import router as export_router
router.include_router(export_router)


class TestCaseVersionResponse(BaseModel):
    id: int
    test_case_id: int
    version_number: int
    change_type: str
    change_description: str | None = None
    changed_fields: dict | None = None
    snapshot_data: dict | None = None
    operator_id: int | None = None
    operator_name: str | None = None
    created_at: str | None = None


@router.get("/{test_case_id}/versions")
async def get_test_case_versions(
    test_case_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取测试用例版本列表
    查询指定测试用例的所有历史版本，按创建时间倒序排列。
    路径参数:
        - test_case_id: 测试用例ID
    响应格式: 版本列表，包含版本号、创建时间和变更摘要
    权限要求: 需要Bearer令牌认证
    Raises:
        HTTPException 404: 测试用例不存在
    """
    from app.models.project import Project
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    from app.models.test_case_version import TestCaseVersion
    query = db.query(TestCaseVersion).filter(
        TestCaseVersion.test_case_id == test_case_id
    ).order_by(TestCaseVersion.version_number.desc())

    total = query.count()
    offset = (page - 1) * page_size
    versions = query.offset(offset).limit(page_size).all()

    items = []
    for v in versions:
        items.append({
            "id": v.id,
            "test_case_id": v.test_case_id,
            "version_number": v.version_number,
            "change_type": v.change_type,
            "change_description": v.change_description,
            "changed_fields": v.changed_fields if isinstance(v.changed_fields, dict) else json.loads(v.changed_fields or "{}"),
            "snapshot_data": v.snapshot_data if isinstance(v.snapshot_data, dict) else json.loads(v.snapshot_data or "{}"),
            "operator_id": v.operator_id,
            "operator_name": v.operator_name,
            "created_at": v.created_at.isoformat() if v.created_at else None
        })

    return create_response(data={
        "total": total,
        "items": items,
        "page": page,
        "page_size": page_size
    })


@router.get("/{test_case_id}/versions/{version_id}")
async def get_test_case_version_detail(
    test_case_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定版本详情
    查询测试用例指定版本的完整信息，包括步骤和测试数据。
    路径参数:
        - test_case_id: 测试用例ID
        - version_id: 版本ID
    权限要求: 需要Bearer令牌认证
    Raises:
        HTTPException 404: 版本不存在
    """
    from app.models.test_case_version import TestCaseVersion
    from app.models.project import Project
    # 首先验证用例所属项目是否属于当前用户
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    version = db.query(TestCaseVersion).filter(
        TestCaseVersion.id == version_id,
        TestCaseVersion.test_case_id == test_case_id
    ).first()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本记录不存在"
        )

    return create_response(data={
        "id": version.id,
        "test_case_id": version.test_case_id,
        "version_number": version.version_number,
        "change_type": version.change_type,
        "change_description": version.change_description,
        "changed_fields": version.changed_fields if isinstance(version.changed_fields, dict) else json.loads(version.changed_fields or "{}"),
        "snapshot_data": version.snapshot_data if isinstance(version.snapshot_data, dict) else json.loads(version.snapshot_data or "{}"),
        "operator_id": version.operator_id,
        "operator_name": version.operator_name,
        "created_at": version.created_at.isoformat() if version.created_at else None
    })


@router.post("/{test_case_id}/versions/{version_id}/restore")
async def restore_test_case_version(
    test_case_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    恢复到指定版本
    将测试用例恢复到指定历史版本的内容，同时创建新的版本记录。
    路径参数:
        - test_case_id: 测试用例ID
        - version_id: 目标版本ID
    权限要求: 需要Bearer令牌认证
    Raises:
        HTTPException 404: 用例或版本不存在
    """
    from app.models.test_case_version import TestCaseVersion
    from app.models.project import Project

    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    version = db.query(TestCaseVersion).filter(
        TestCaseVersion.id == version_id,
        TestCaseVersion.test_case_id == test_case_id
    ).first()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本记录不存在"
        )

    try:
        snapshot = version.snapshot_data
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)

        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该版本无快照数据，无法恢复"
            )

        restorable_fields = ["title", "module", "precondition", "expected_result", "priority", "case_type", "steps_json"]
        for field in restorable_fields:
            if field in snapshot:
                setattr(test_case, field, snapshot[field])

        if "steps_json" in snapshot and snapshot["steps_json"]:
            db.query(TestStep).filter(TestStep.test_case_id == test_case_id).delete()
            for i, step_data in enumerate(snapshot["steps_json"]):
                step = TestStep(
                    test_case_id=test_case_id,
                    step_number=i + 1,
                    action=step_data.get("action", ""),
                    expected_result=step_data.get("expected_result", ""),
                    action_type=step_data.get("action_type", ""),
                    input_value=step_data.get("input_value", ""),
                    target_element=step_data.get("target_element", "")
                )
                db.add(step)

        db.commit()
        db.refresh(test_case)

        logger.info(f"[版本恢复] 用户ID={current_user.id}, 用例ID={test_case_id}, 恢复到版本={version.version_number}")

        return create_response(data=build_test_case_response(test_case))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"恢复测试用例版本失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="恢复版本失败"
        )
