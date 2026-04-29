"""
测试用例版本管理 + 导出端点模块

本模块定义测试用例版本管理与多格式导出的 API 端点。
路由前缀: /testCase（由父模块 test_case.py 注册）。
权限要求: 所有端点需要 Bearer 令牌认证。

详见各 @router 装饰器，主要包括:
    - 版本列表/详情/恢复
    - 单条用例 Markdown / HTML / Python / JSON / Excel 导出
    - 批量导出功能用例 Excel（按模块分组）
"""
import json
import os
import tempfile
import urllib.parse
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.db.database import get_db
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.utils.test_case_helpers import build_test_case_response
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


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


@router.get("/{test_case_id}/export-markdown")
async def export_markdown(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出Markdown格式
    将指定测试用例导出为Markdown格式文本。
    路径参数:
        - test_case_id: 测试用例ID
    权限要求: 需要Bearer令牌认证
    """
    from app.models.project import Project
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )
    
    try:
        from app.services.test_case_view_service import TestCaseViewService
        service = TestCaseViewService(db)
        markdown = service.export_business_view_to_markdown(test_case_id)
        return create_response(data={"content": markdown})
    except Exception as e:
        logger.error(f"导出Markdown失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出Markdown失败"
        )


@router.get("/{test_case_id}/export-html")
async def export_html(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出HTML格式
    将指定测试用例导出为HTML格式文本。
    路径参数:
        - test_case_id: 测试用例ID
    权限要求: 需要Bearer令牌认证
    """
    from app.models.project import Project
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )
    
    try:
        from app.services.test_case_view_service import TestCaseViewService
        service = TestCaseViewService(db)
        html = service.export_business_view_to_html(test_case_id)
        return create_response(data={"content": html})
    except Exception as e:
        logger.error(f"导出HTML失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出HTML失败"
        )


@router.get("/{test_case_id}/export-python")
async def export_python(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出Python自动化脚本
    将指定测试用例导出为Python自动化测试脚本。
    路径参数:
        - test_case_id: 测试用例ID
    权限要求: 需要Bearer令牌认证
    """
    from app.models.project import Project
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )
    
    try:
        from app.services.test_case_view_service import TestCaseViewService
        service = TestCaseViewService(db)
        python_code = service.export_technical_view_to_python(test_case_id)
        return create_response(data={"content": python_code})
    except Exception as e:
        logger.error(f"导出Python失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出Python失败"
        )


@router.get("/{test_case_id}/export-json")
async def export_json(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出JSON格式
    将指定测试用例的技术视图导出为JSON格式。
    路径参数:
        - test_case_id: 测试用例ID
    权限要求: 需要Bearer令牌认证
    """
    from app.models.project import Project
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )
    
    try:
        from app.services.test_case_view_service import TestCaseViewService
        service = TestCaseViewService(db)
        json_data = service.export_technical_view_to_json(test_case_id)
        return create_response(data=json_data)
    except Exception as e:
        logger.error(f"导出JSON失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出JSON失败"
        )


def _build_excel_filename(prefix: str) -> str:
    """生成下载用Excel文件名（含UTF-8编码的Content-Disposition）。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.xlsx"


def _excel_file_response(
    file_path: str,
    download_name: str,
    extra_headers: dict | None = None,
) -> FileResponse:
    """统一返回Excel文件流，并在响应结束后清理临时文件。

    Content-Disposition 同时输出 ASCII fallback (filename=) 和 RFC 5987
    UTF-8 (filename*=)，以兼容老浏览器并正确显示中文文件名。
    """
    quoted = urllib.parse.quote(download_name)
    ascii_fallback = download_name.encode("ascii", "ignore").decode().strip() or "export.xlsx"
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"
        ),
        # CORS 暴露：让前端 axios 能读到自定义响应头
        "Access-Control-Expose-Headers": "Content-Disposition, X-Export-Skipped-Count",
    }
    if extra_headers:
        headers.update(extra_headers)

    def _cleanup() -> None:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"清理临时Excel文件失败: {file_path}, {exc}")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
        background=BackgroundTask(_cleanup),
    )


@router.post("/{test_case_id}/export-excel")
async def export_excel(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导出单条测试用例为标准Excel（双Sheet：用例信息 + 测试步骤，包含定位信息）。
    路径参数:
        - test_case_id: 测试用例ID
    权限要求: 需要Bearer令牌认证
    """
    from app.models.project import Project
    from app.services.test_case_view_service import TestCaseViewService

    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        service = TestCaseViewService(db)
        ok = service.export_to_excel(test_case_id, tmp.name)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="导出Excel失败"
            )

        safe_title = (test_case.case_no or test_case.title or f"case_{test_case_id}").strip()
        for ch in '\\/:*?"<>|':
            safe_title = safe_title.replace(ch, "_")
        download_name = _build_excel_filename(safe_title)
        return _excel_file_response(tmp.name, download_name)
    except HTTPException:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        raise
    except Exception as e:
        logger.error(f"导出Excel失败: {e}")
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出Excel失败"
        )


class FunctionalExcelExportRequest(BaseModel):
    case_ids: List[int]


@router.post("/export-functional-excel")
async def export_functional_excel(
    payload: FunctionalExcelExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量导出测试用例为功能用例Excel（单Sheet，按模块分组，面向第三方公司）。
    请求体:
        - case_ids: 用例ID列表
    权限要求: 需要Bearer令牌认证；仅导出当前用户拥有项目下的用例。
    """
    from app.models.project import Project
    from app.services.test_case_view_service import TestCaseViewService

    if not payload.case_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要导出的用例"
        )

    owned_rows = db.query(TestCase.id).join(Project).filter(
        TestCase.id.in_(payload.case_ids),
        Project.user_id == current_user.id
    ).all()
    owned_ids = {row[0] for row in owned_rows}
    if not owned_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到可导出的测试用例"
        )

    # 保留前端传入顺序，仅过滤出有权限的部分
    ordered_ids = [cid for cid in payload.case_ids if cid in owned_ids]
    skipped_count = len(payload.case_ids) - len(ordered_ids)

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        service = TestCaseViewService(db)
        ok = service.export_to_functional_excel(ordered_ids, tmp.name)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="导出功能用例Excel失败"
            )

        download_name = _build_excel_filename("功能测试用例")
        extra_headers = {"X-Export-Skipped-Count": str(skipped_count)} if skipped_count else None
        return _excel_file_response(tmp.name, download_name, extra_headers=extra_headers)
    except HTTPException:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        raise
    except Exception as e:
        logger.error(f"导出功能用例Excel失败: {e}")
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出功能用例Excel失败"
        )
