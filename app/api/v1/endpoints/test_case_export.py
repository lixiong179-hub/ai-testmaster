"""测试用例多格式导出端点

提供 Markdown / HTML / Python / JSON / Excel / 功能用例Excel 等多格式导出功能。
路由前缀: /testCase（由父模块 test_case.py 注册）。
"""
import os
import tempfile
import urllib.parse
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.db.database import get_db
from app.models.test_case import TestCase
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


class FunctionalExcelExportRequest(BaseModel):
    case_ids: List[int]


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
