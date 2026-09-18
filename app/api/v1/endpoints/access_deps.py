"""项目 / 任务级「归属校验」统一入口（R0-3）。

## 为什么存在

重构前，同一套校验逻辑在以下位置各有逐字重复的实现：

    - app/api/v1/endpoints/test_task_helpers.py（4 个：project/task × sync/async）
    - app/api/v1/endpoints/test_task_exec.py     （2 个副本，且 sync 版无调用点）
    - app/api/v1/endpoints/pipeline_deps.py      （project 级 sync + async）

本模块作为**唯一实现源**，其余位置改为引用这里。

## 校验语义

本模块做的是**项目归属校验**（`Project.user_id == current_user.id`），
不是 RBAC 角色校验——角色/权限码校验见 `app/core/permissions.py`。

## 两种形态与选用规则

    - `verify_project_access[_async]`：项目 ID 来自 request body / query 参数时使用
      （不是路径参数，无法写成依赖注入），端点内直接 await 调用；
    - `require_task_access`：路径参数为 `task_id` 时使用的依赖注入形态，
      一次性完成「任务存在性 → 项目归属」校验并注入任务对象，
      省去端点里重复的「查询 + 404 + 校验」三连。
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth_deps import get_current_user
from app.db.database import async_get_db
from app.models.project import Project
from app.models.test_task import TestTask
from app.models.user import User

__all__ = [
    "verify_project_access",
    "verify_project_access_async",
    "require_task_access",
]


def verify_project_access(
    db: Session, project_id: int, current_user: User
) -> None:
    """sync 版项目归属校验：当前用户须为 project_id 的所有者，否则 403。

    保留 sync 形态是为兼容既有 import 方（如 pipeline.py 的
    `verify_project_access as _verify_project_access`）。
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )


async def verify_project_access_async(
    db: AsyncSession, project_id: int, current_user: User
) -> None:
    """async 版项目归属校验：当前用户须为 project_id 的所有者，否则 403。

    适用于项目 ID 来自 request body / query 的场景（非路径参数，
    无法用依赖注入），端点内 `await verify_project_access_async(...)` 调用。
    """
    project = (
        await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )


async def require_task_access(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> TestTask:
    """任务归属校验依赖：路径参数 task_id → 返回任务对象。

    用法::

        @router.post("/{task_id}/run")
        async def run(task_id: int, task: TestTask = Depends(require_task_access),
                      db: AsyncSession = Depends(async_get_db)):
            ...

    语义（与重构前的端点内联实现等价）：

        - 任务不存在            → 404「测试任务不存在」
        - 任务不属于当前用户项目 → 403「无权限操作此任务」

    说明：
        1. 依赖内部使用的 `async_get_db` / `get_current_user` 与端点使用的是
           同一对象，FastAPI 按请求缓存依赖结果，因此返回的 task 与端点 `db`
           绑定同一会话，访问 `task.project_id` 等属性安全；
        2. 404 文案统一为「测试任务不存在」（重构前部分端点写作「任务不存在」），
           403 文案保持原样。
    """
    task = (
        await db.execute(select(TestTask).where(TestTask.id == task_id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="测试任务不存在"
        )

    project = (
        await db.execute(
            select(Project).where(
                Project.id == task.project_id,
                Project.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此任务"
        )
    return task
