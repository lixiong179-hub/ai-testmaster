"""
UI屏幕截图批量预览端点模块

本模块提供UI屏幕截图的批量预览接口，一次性返回多个屏幕ID对应的图片
data URL 映射，用于解决前端N+1串行请求问题（见 spec
optimize-case-generation-flow Task 6.1）。

路由前缀: /ui-screens（由 main.py 注册时添加 /api/v1 前缀）
标签: UI截图批量

端点概览:
    - GET /batch?ids=1,2,3 - 批量获取UI屏幕截图 data URL 映射

权限要求: 所有端点需要Bearer令牌认证，仅返回当前用户有权限访问的屏幕。

设计说明:
    - 现有单条接口 GET /api/v1/file/preview-screen/{screen_id} 返回图片字节流
      （FileResponse），前端需逐张请求，存在N+1问题。
    - 本批量接口将多张图片编码为 base64 data URL，在一次响应内返回
      {screen_id: data_url} 映射，前端可直接用于 <img :src>，实现单次请求。
    - 等价性：批量接口返回的某 id 的 data URL 解码后的字节，与单条接口
      返回该 id 的图片字节完全一致（同一文件）。
"""
import base64
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.schemas.common import ApiResponse
from app.db.database import async_get_db
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeScreen
from app.models.user import User

router: APIRouter = APIRouter(prefix="/ui-screens", tags=["UI截图批量"])

# 单次批量请求允许的最大ID数量，防止响应体过大与滥用
MAX_BATCH_IDS: int = 100


def _parse_screen_ids(raw_ids: str) -> list[int]:
    """解析并校验逗号分隔的屏幕ID列表。

    所有外部输入在此完成校验后才进入业务查询，确保仅合法正整数ID进入
    后续 SQL 参数化查询。

    Args:
        raw_ids: 逗号分隔的ID字符串，如 "1,2,3"。

    Returns:
        去重且保持顺序的正整数ID列表。

    Raises:
        HTTPException 422: 参数为空、含非数字、非正整数或超过上限。
    """
    if not raw_ids or not raw_ids.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ids 参数不能为空",
        )

    parts = [p.strip() for p in raw_ids.split(",") if p.strip()]
    if not parts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ids 参数不能为空",
        )

    if len(parts) > MAX_BATCH_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"单次批量最多 {MAX_BATCH_IDS} 个ID",
        )

    parsed: list[int] = []
    seen: set[int] = set()
    for part in parts:
        try:
            id_value = int(part)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"非法的ID: {part}",
            )
        if id_value <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"ID必须为正整数: {part}",
            )
        if id_value not in seen:
            seen.add(id_value)
            parsed.append(id_value)

    return parsed


def _build_data_url(screen: UIPrototypeScreen) -> str | None:
    """读取屏幕图片文件并编码为 base64 data URL。

    IO 统一用 with 管理，读取失败时记录日志并返回 None，不影响其他屏幕
    的批量结果。

    Args:
        screen: UI屏幕ORM对象。

    Returns:
        data URL 字符串（如 "data:image/png;base64,..."）；文件路径为空、
        文件不存在或读取失败时返回 None。
    """
    file_path = screen.original_file_path
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
    except OSError as e:
        logger.warning(
            f"读取UI截图文件失败: screen_id={screen.id}, "
            f"path={file_path}, error={e}"
        )
        return None

    ext = (screen.file_type or "png").lower()
    # jpg 在 data URL 中应使用 jpeg 以符合 MIME 规范
    if ext == "jpg":
        ext = "jpeg"
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return f"data:image/{ext};base64,{encoded}"


@router.get("/batch", response_model=ApiResponse)
async def batch_get_ui_screens(
    ids: str = Query(..., description="逗号分隔的UI屏幕ID列表，如 1,2,3，最多100个"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """批量获取UI屏幕截图预览 data URL 映射。

    一次请求返回多个屏幕ID对应的图片 data URL，仅返回当前用户有权限访问
    （所属项目）且文件存在的屏幕。解决前端 N+1 串行请求问题。

    Args:
        ids: 逗号分隔的屏幕ID列表，如 "1,2,3"。
        db: 数据库会话。
        current_user: 当前登录用户（依赖注入鉴权）。

    Returns:
        统一响应，data 为 {screen_id: data_url} 映射，例如：
        {
            "code": 200,
            "msg": "批量获取UI截图成功",
            "data": {"1": "data:image/png;base64,...", "2": "data:image/png;base64,..."},
            "timestamp": 1713600000
        }

    Raises:
        HTTPException 422: ids 参数非法（空、非数字、非正整数、超上限）。
        HTTPException 500: 服务器内部错误。
    """
    try:
        parsed_ids = _parse_screen_ids(ids)

        # 参数化批量查询：join Project 校验权限，使用 in_ 列表传参杜绝 SQL 注入
        # 单次查询返回所有所需屏幕，杜绝循环内执行 SQL 的 N+1 问题
        screens_result = await db.execute(
            select(UIPrototypeScreen)
            .join(Project, UIPrototypeScreen.project_id == Project.id)
            .where(
                UIPrototypeScreen.id.in_(parsed_ids),
                Project.user_id == current_user.id,
            )
        )
        screens = screens_result.scalars().all()

        result: dict[str, str] = {}
        for screen in screens:
            data_url = _build_data_url(screen)
            if data_url is not None:
                result[str(screen.id)] = data_url

        return create_response(data=result, msg="批量获取UI截图成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量获取UI截图失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量获取UI截图失败，请稍后重试",
        )
