"""项目成员管理端点模块。

提供基于 ProjectMember 模型的成员 CRUD 与所有权转让 REST 接口。

路由（由 main.py 以 prefix=/api/v1 挂载，本路由器自带 prefix=/projects）：
    - POST   /projects/{project_id}/members                  添加成员
    - GET    /projects/{project_id}/members                  成员列表
    - PUT    /projects/{project_id}/members/{user_id}        修改成员角色
    - DELETE /projects/{project_id}/members/{user_id}        移除成员
    - POST   /projects/{project_id}/transfer-ownership       转让所有权

权限语义：
    - 添加/移除/修改成员：调用者需 admin 或 owner 角色
    - 转让所有权：仅 owner 可发起；目标用户必须已是项目成员
    - 成员列表：项目任意成员均可查看
    - 超级管理员自动绕过所有校验

设计说明：
    - 端点接收 AsyncSession 且仅 flush，由端点显式 await db.commit() 落库。
    - 复用 ProjectAccessService 完成角色层级校验，避免在本模块重复实现。
    - ProjectMember.role 为 owner/admin/member/viewer 四级，层级数值由 ROLE_LEVEL 定义。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.project import (
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    TransferOwnershipRequest,
)
from app.services.project_access_service import ProjectAccessService

router = APIRouter(prefix="/projects", tags=["项目成员管理"])


async def _ensure_user_exists_async(db: AsyncSession, user_id: int) -> User:
    """校验用户存在并返回 User 对象，不存在抛 404。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 不存在",
        )
    return user


async def _ensure_project_exists_async(db: AsyncSession, project_id: int) -> Project:
    """校验项目存在并返回 Project 对象，不存在抛 404。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 不存在",
        )
    return project


def _member_to_response(member: ProjectMember, user: User) -> ProjectMemberResponse:
    """组装成员响应对象（合并 ProjectMember 与 User 字段）。"""
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        username=user.username,
        email=user.email,
        role=member.role,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


async def _load_member_with_user(
    db: AsyncSession, project_id: int, user_id: int
) -> tuple[ProjectMember, User]:
    """加载成员记录及关联用户，成员不存在抛 404。"""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成员不存在",
        )
    user = await _ensure_user_exists_async(db, member.user_id)
    return member, user


@router.post(
    "/{project_id}/members",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """添加项目成员（需 admin 或 owner 角色）。

    业务规则：
        - role 不能直接设为 owner（所有权转让走 transfer-ownership 端点）
        - 同一用户不能重复添加（unique 约束）
        - 目标用户必须存在于 users 表
    """
    await _ensure_project_exists_async(db, project_id)
    await ProjectAccessService.check_project_access_async(
        db, project_id, current_user, "admin",
    )

    if payload.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能直接添加 owner，请使用 transfer-ownership 端点转让所有权",
        )
    if not ProjectMember.is_valid_role(payload.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法角色: {payload.role}",
        )

    await _ensure_user_exists_async(db, payload.user_id)

    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == payload.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="成员已存在",
        )

    member = ProjectMember(
        project_id=project_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    db.add(member)
    await db.flush()

    user = await _ensure_user_exists_async(db, member.user_id)
    await db.commit()
    logger.info(
        f"用户 {current_user.id} 添加成员 {payload.user_id} 到项目 {project_id}，角色={payload.role}"
    )
    return create_response(
        data=_member_to_response(member, user).model_dump(mode="json"),
        msg="成员添加成功",
    )


@router.get("/{project_id}/members", response_model=ApiResponse)
async def list_project_members(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """查询项目成员列表（项目任意成员均可查看）。"""
    await _ensure_project_exists_async(db, project_id)
    await ProjectAccessService.check_project_access_async(
        db, project_id, current_user, "viewer",
    )

    result = await db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.id)
    )
    rows = result.all()
    members = [_member_to_response(m, u) for m, u in rows]
    return create_response(
        data=[item.model_dump(mode="json") for item in members],
        msg="成员列表查询成功",
    )


@router.put("/{project_id}/members/{user_id}", response_model=ApiResponse)
async def update_project_member_role(
    project_id: int,
    user_id: int,
    payload: ProjectMemberUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """修改成员角色（需 admin 或 owner 角色）。

    业务规则：
        - 不能通过此端点将成员提升为 owner（使用 transfer-ownership）
        - 不能修改自己的角色（避免越权提权/降级）
        - owner 角色不能被降级（需先转让所有权）
    """
    await _ensure_project_exists_async(db, project_id)
    await ProjectAccessService.check_project_access_async(
        db, project_id, current_user, "admin",
    )

    if payload.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能直接设为 owner，请使用 transfer-ownership 端点",
        )
    if not ProjectMember.is_valid_role(payload.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法角色: {payload.role}",
        )
    if user_id == current_user.id and not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色",
        )

    member, _ = await _load_member_with_user(db, project_id, user_id)
    if member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能直接降级 owner，请先转让所有权",
        )

    member.role = payload.role
    await db.flush()
    user = await _ensure_user_exists_async(db, member.user_id)
    await db.commit()
    logger.info(
        f"用户 {current_user.id} 修改项目 {project_id} 成员 {user_id} 角色为 {payload.role}"
    )
    return create_response(
        data=_member_to_response(member, user).model_dump(mode="json"),
        msg="成员角色更新成功",
    )


@router.delete("/{project_id}/members/{user_id}", response_model=ApiResponse)
async def remove_project_member(
    project_id: int,
    user_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """移除项目成员（需 admin 或 owner 角色）。

    业务规则：
        - 不能移除 owner（需先转让所有权）
        - 不能移除自己（避免误操作把自己踢出项目）
    """
    await _ensure_project_exists_async(db, project_id)
    await ProjectAccessService.check_project_access_async(
        db, project_id, current_user, "admin",
    )

    if user_id == current_user.id and not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除自己，如需退出请联系项目 owner",
        )

    member, _ = await _load_member_with_user(db, project_id, user_id)
    if member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除 owner，请先转让所有权",
        )

    await db.delete(member)
    await db.commit()
    logger.info(
        f"用户 {current_user.id} 从项目 {project_id} 移除成员 {user_id}"
    )
    return create_response(data=None, msg="成员移除成功")


@router.post("/{project_id}/transfer-ownership", response_model=ApiResponse)
async def transfer_project_ownership(
    project_id: int,
    payload: TransferOwnershipRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """转让项目所有权（仅 owner 可发起）。

    业务规则：
        - 仅当前项目 owner（或超级管理员）可发起
        - 目标用户必须已是项目成员
        - 转让后：新 owner 升级为 owner，原 owner 降级为 admin
        - 不能转让给自己
    """
    await _ensure_project_exists_async(db, project_id)
    current_member = await ProjectAccessService.check_project_access_async(
        db, project_id, current_user, "owner",
    )

    if payload.new_owner_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能转让给自己",
        )

    target_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == payload.new_owner_user_id,
        )
    )
    target_member = target_result.scalar_one_or_none()
    if target_member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标用户不是项目成员，请先添加为成员",
        )

    # 双向更新：原 owner → admin，目标成员 → owner
    target_member.role = "owner"
    current_member.role = "admin"
    await db.flush()

    target_user = await _ensure_user_exists_async(db, target_member.user_id)
    await db.commit()
    logger.info(
        f"项目 {project_id} 所有权由用户 {current_user.id} 转让给用户 {payload.new_owner_user_id}"
    )
    return create_response(
        data=_member_to_response(target_member, target_user).model_dump(mode="json"),
        msg="所有权转让成功",
    )
