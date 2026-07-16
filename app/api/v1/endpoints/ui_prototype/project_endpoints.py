"""
UI原型项目端点模块

本模块定义UI原型项目级管理的API端点，包括原型上传、列表查询和删除。

路由前缀: /ui-prototype（由父模块ui_prototype注册）
标签: UI原型管理

端点概览:
    - POST   /projects/{project_id}/upload  - 上传原型文件
    - GET    /projects/{project_id}/list     - 获取项目原型列表
    - DELETE /projects/{project_id}/{prototype_id} - 删除原型

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 支持上传HTML/PDF/图片等原型文件
    - 上传后自动创建页面记录
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_get_db, get_db
from app.schemas.ui_prototype import UIPrototypeProjectCreate, FlowDataSaveRequest
from app.models.user import User
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen, UIScreenTestCaseLink
from app.models.project_flow_data import ProjectFlowData
from app.api.v1.endpoints.auth import get_current_user
from app.crud import ui_prototype as ui_prototype_crud
from app.crud.project_flow_data import save_project_flow_data, get_project_flow_data
from app.core.exception import create_response
from loguru import logger

router = APIRouter(tags=["UI原型管理"])


def _count_navigation_edges(navigation_map: dict[str, Any]) -> int:
    edge_count = 0
    for mapping in navigation_map.values():
        if not isinstance(mapping, dict):
            continue
        can_go_to = mapping.get("can_go_to")
        back_to = mapping.get("back_to")
        edge_count += len(can_go_to) if isinstance(can_go_to, list) else 0
        edge_count += len(back_to) if isinstance(back_to, list) else 0
    return edge_count


def _build_flow_summary(merged_flow: Any) -> dict[str, Any]:
    if not isinstance(merged_flow, dict) or not merged_flow:
        return {
            "has_flow": False,
            "node_count": 0,
            "edge_count": 0,
            "entry_screen": "",
            "end_screens": [],
            "branch_count": 0,
            "exception_count": 0,
            "warning_count": 0,
            "key_path_count": 0,
        }

    page_flows = merged_flow.get("page_flows")
    navigation_map = merged_flow.get("navigation_map")
    end_screens = merged_flow.get("end_screens")
    key_user_paths = merged_flow.get("key_user_paths")
    warnings = merged_flow.get("warnings")

    flow_list = page_flows if isinstance(page_flows, list) else []
    nav_map = navigation_map if isinstance(navigation_map, dict) else {}
    end_list = end_screens if isinstance(end_screens, list) else []
    key_paths = key_user_paths if isinstance(key_user_paths, list) else []
    warning_list = warnings if isinstance(warnings, list) else []

    node_names: set[str] = set()
    entry_screen = merged_flow.get("entry_screen")
    if isinstance(entry_screen, str) and entry_screen:
        node_names.add(entry_screen)
    for flow in flow_list:
        if not isinstance(flow, dict):
            continue
        from_screen = flow.get("from_screen")
        to_screen = flow.get("to_screen")
        if isinstance(from_screen, str) and from_screen:
            node_names.add(from_screen)
        if isinstance(to_screen, str) and to_screen:
            node_names.add(to_screen)
    for screen_name, mapping in nav_map.items():
        if isinstance(screen_name, str) and screen_name:
            node_names.add(screen_name)
        if not isinstance(mapping, dict):
            continue
        for key in ("can_go_to", "back_to"):
            values = mapping.get(key)
            if isinstance(values, list):
                node_names.update(v for v in values if isinstance(v, str) and v)
    node_names.update(v for v in end_list if isinstance(v, str) and v)

    branch_count = sum(
        1
        for flow in flow_list
        if isinstance(flow, dict)
        and isinstance(flow.get("condition"), str)
        and flow.get("condition")
    )
    edge_count = len(flow_list) or _count_navigation_edges(nav_map)

    return {
        "has_flow": edge_count > 0 or bool(key_paths),
        "node_count": len(node_names),
        "edge_count": edge_count,
        "entry_screen": entry_screen if isinstance(entry_screen, str) else "",
        "end_screens": [v for v in end_list if isinstance(v, str)],
        "branch_count": branch_count,
        "exception_count": len(warning_list),
        "warning_count": len(warning_list),
        "key_path_count": len(key_paths),
    }


@router.post(
    "/project",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def create_prototype_project(
    project_data: UIPrototypeProjectCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _create(sync_db: Session):
            project = (
                sync_db.query(Project)
                .filter(
                    Project.id == project_data.project_id,
                    Project.user_id == current_user.id,
                )
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            return ui_prototype_crud.create_ui_prototype_project(
                db=sync_db,
                project_id=project_data.project_id,
                name=project_data.name,
                description=project_data.description,
                source=project_data.source,
                created_by=current_user.id,
            )

        data = await db.run_sync(_create)
        return create_response(data=data, msg="创建成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建UI原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建UI原型项目失败，请稍后重试"
        )


@router.get(
    "/project/list/{project_id}",
    response_model=dict,
)
async def get_prototype_projects(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    iteration_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _list(sync_db: Session):
            project = (
                sync_db.query(Project)
                .filter(Project.id == project_id, Project.user_id == current_user.id)
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            skip = (page - 1) * page_size
            db_projects = ui_prototype_crud.get_ui_prototype_projects_by_project(
                db=sync_db,
                project_id=project_id,
                user_id=current_user.id,
                skip=skip,
                limit=page_size,
                iteration_id=iteration_id,
            )

            total = ui_prototype_crud.get_ui_prototype_projects_count(
                db=sync_db,
                project_id=project_id,
                user_id=current_user.id,
                iteration_id=iteration_id,
            )

            items = []
            for p in db_projects:
                flow_summary = _build_flow_summary(p.merged_flow)
                items.append({
                    "id": p.id,
                    "project_id": p.project_id,
                    "name": p.name,
                    "description": p.description,
                    "source": p.source,
                    "screen_count": p.screen_count,
                    "parsed_count": p.parsed_count,
                    "parse_status": p.parse_status,
                    "iteration_id": p.iteration_id,
                    "has_flow": flow_summary["has_flow"],
                    "flow_summary": flow_summary,
                    "create_time": p.create_time.isoformat() if p.create_time else None,
                    "update_time": p.update_time.isoformat() if p.update_time else None,
                })

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        data = await db.run_sync(_list)
        return create_response(data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取UI原型项目列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取UI原型项目列表失败，请稍后重试"
        )


@router.delete("/project/{prototype_project_id}", response_model=dict)
async def delete_prototype_project(
    prototype_project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _delete(sync_db: Session):
            proto_project = (
                sync_db.query(UIPrototypeProject)
                .filter(UIPrototypeProject.id == prototype_project_id)
                .first()
            )

            if not proto_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
                )

            db_project = (
                sync_db.query(Project)
                .filter(
                    Project.id == proto_project.project_id,
                    Project.user_id == current_user.id,
                )
                .first()
            )

            if not db_project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            screens = (
                sync_db.query(UIPrototypeScreen)
                .filter(UIPrototypeScreen.prototype_project_id == prototype_project_id)
                .all()
            )

            deleted_screens = 0
            for screen in screens:
                if screen.original_file_path and os.path.exists(
                    screen.original_file_path
                ):
                    try:
                        os.remove(screen.original_file_path)
                    except OSError as e:
                        logger.warning(
                            f"删除UI原型文件失败: {screen.original_file_path}, 错误: {e}"
                        )
                sync_db.query(UIScreenTestCaseLink).filter(
                    UIScreenTestCaseLink.screen_id == screen.id
                ).delete()
                sync_db.delete(screen)
                deleted_screens += 1

            sync_db.delete(proto_project)
            sync_db.commit()

            return deleted_screens

        deleted_screens = await db.run_sync(_delete)
        return create_response(
            data={"deleted_screens": deleted_screens},
            msg=f"删除成功，共删除 {deleted_screens} 张图片"
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除UI原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除UI原型项目失败，请稍后重试"
        )


@router.put("/flow/{project_id}", response_model=dict)
async def save_flow_data(
    project_id: int,
    flow_request: FlowDataSaveRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """
    保存项目流程数据（upsert）

    根据project_id保存或更新项目的流程编辑数据（nodes/edges/module_info），
    每个项目仅保留一条记录。存在则更新，不存在则新增。
    """
    try:
        if (
            flow_request.project_id is not None
            and flow_request.project_id != project_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请求体项目ID与路径项目ID不一致",
            )

        def _save(sync_db: Session):
            project = (
                sync_db.query(Project)
                .filter(Project.id == project_id, Project.user_id == current_user.id)
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            result: ProjectFlowData = save_project_flow_data(
                db=sync_db,
                project_id=project_id,
                flow_data=flow_request.flow_data,
            )

            return _serialize_project_flow_data(result)

        data = await db.run_sync(_save)
        return create_response(data=data, msg="保存成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存项目流程数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存项目流程数据失败，请稍后重试"
        )


def _serialize_project_flow_data(pfd: ProjectFlowData) -> dict:
    return {
        "id": pfd.id,
        "project_id": pfd.project_id,
        "flow_data": pfd.flow_data,
        "create_time": pfd.create_time.isoformat() if pfd.create_time else None,
        "update_time": pfd.update_time.isoformat() if pfd.update_time else None,
    }


@router.get("/flow/{project_id}", response_model=dict)
async def get_flow_data(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取项目流程数据

    根据project_id查询项目的流程编辑数据。
    若存在已保存数据则返回完整数据，否则返回data=None及提示信息。
    """
    try:
        def _get(sync_db: Session):
            project = (
                sync_db.query(Project)
                .filter(Project.id == project_id, Project.user_id == current_user.id)
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            result: Optional[ProjectFlowData] = get_project_flow_data(
                db=sync_db,
                project_id=project_id,
            )

            if result:
                return _serialize_project_flow_data(result)
            return None

        data = await db.run_sync(_get)
        if data:
            return create_response(data=data)
        else:
            return create_response(data=None, msg="暂无保存数据")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目流程数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目流程数据失败，请稍后重试"
        )
