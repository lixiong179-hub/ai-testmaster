"""UI原型项目端点流程数据路由处理函数。

包含保存与查询项目流程数据的路由处理函数，以普通 async 函数形式定义，
由 project_endpoints.py 通过 router.add_api_route 注册，保持 router 定义在原文件中。
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.ui_prototype._project_endpoints_helpers import (
    _serialize_project_flow_data,
)
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.project import Project
from app.models.project_flow_data import ProjectFlowData
from app.models.user import User
from app.schemas.ui_prototype import FlowDataSaveRequest
from app.utils.db_time import utcnow


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

        # 内联 async 实现, 替代 db.run_sync(_save) + sync crud
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        existing_result = await db.execute(
            select(ProjectFlowData).where(
                ProjectFlowData.project_id == project_id
            )
        )
        existing = existing_result.scalars().first()
        if existing:
            existing.flow_data = flow_request.flow_data
            existing.update_time = utcnow()
            await db.commit()
            await db.refresh(existing)
            result = existing
        else:
            record = ProjectFlowData(
                project_id=project_id,
                flow_data=flow_request.flow_data,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            result = record

        data = _serialize_project_flow_data(result)
        return create_response(data=data, msg="保存成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存项目流程数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存项目流程数据失败，请稍后重试"
        )


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
        # 内联 async 实现, 替代 db.run_sync(_get) + sync crud
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        flow_result = await db.execute(
            select(ProjectFlowData).where(
                ProjectFlowData.project_id == project_id
            )
        )
        result: Optional[ProjectFlowData] = flow_result.scalars().first()

        if result:
            data = _serialize_project_flow_data(result)
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
