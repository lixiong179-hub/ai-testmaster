"""迭代异步调用 Mixin（R2-1 阶段三收敛：sync 实现 + 线程池薄壳）。

历史形态是从 sync 版本镜像出的完整 AsyncSession 实现（`await self.db.execute`）。
范式收敛（方案 a：全 sync + `asyncio.to_thread`）后，本 Mixin 退化为薄壳：
每个方法在线程池中调用同名 sync 实现，方法名与签名保持不变，避免改动调用点。

设计要点：
    - 要求 `self.db` 为**同步 Session**（`Depends(get_db)`）；
    - 阻塞 SQL 一律经 `asyncio.to_thread` 执行，事件循环不被阻塞；
    - `create_iteration_async` / `update_iteration_async` 在写操作后重查一次
      （`get_iteration` 带 `joinedload(inputs)`），保证返回对象可直接序列化，
      不依赖隐式懒加载；
    - sync 实现无法在模块顶层导入（会与 `iteration_service` 形成循环依赖），
      故在方法内延迟导入。

使用方式：
    async def endpoint(..., db: Session = Depends(get_db)):
        service = IterationService(db)
        iteration = await service.create_iteration_async(...)
"""

import asyncio

from app.models.iteration import Iteration, IterationInput


class IterationAsyncMixin:
    """迭代异步调用 Mixin，供 IterationService 继承。

    要求 self.db 为同步 Session 实例。
    """

    async def create_iteration_async(
        self,
        project_id: int,
        name: str,
        *,
        version: str = "v1.0",
        description: str | None = None,
        base_iteration_id: int | None = None,
        created_by: int | None = None,
        start_date=None,
        end_date=None,
    ) -> Iteration:
        """创建迭代。

        Raises:
            ValueError: 同项目下已存在同名迭代。
            BaseIterationValidationError: base_iteration_id 校验失败。
        """
        from app.services.iteration_service import create_iteration

        iteration = await asyncio.to_thread(
            create_iteration,
            self.db,
            project_id,
            name,
            version=version,
            description=description,
            base_iteration_id=base_iteration_id,
            created_by=created_by,
            start_date=start_date,
            end_date=end_date,
        )
        return await self.get_iteration_async(iteration.id)

    async def add_input_async(
        self,
        iteration_id: int,
        kind: str,
        *,
        file_id: int | None = None,
        payload: dict | None = None,
        hash_value: str | None = None,
    ) -> IterationInput:
        """添加迭代输入（含幂等校验）。

        Raises:
            IterationInputValidationError: kind 不合法、file_id 不存在或 hash_value 为空。
            ValueError: 迭代不存在。
            DuplicateInputHashError: 相同 hash 已存在。
        """
        from app.services.iteration_service import add_input

        return await asyncio.to_thread(
            add_input,
            self.db,
            iteration_id,
            kind,
            file_id=file_id,
            payload=payload,
            hash_value=hash_value,
        )

    async def list_iterations_async(
        self,
        project_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Iteration]:
        """按项目查询迭代列表（eager-load inputs）。"""
        from app.services.iteration_service import list_iterations

        return await asyncio.to_thread(list_iterations, self.db, project_id, skip=skip, limit=limit)

    async def get_iteration_async(self, iteration_id: int) -> Iteration | None:
        """获取迭代详情（含 inputs）。"""
        from app.services.iteration_service import get_iteration

        return await asyncio.to_thread(get_iteration, self.db, iteration_id)

    async def transition_iteration_status_async(
        self,
        iteration_id: int,
        to_status: str,
    ) -> Iteration:
        """执行迭代状态迁移。

        Raises:
            ValueError: 迭代不存在。
            IterationStatusTransitionError: 非法迁移路径。
        """
        from app.services.iteration_service import transition_iteration_status

        return await asyncio.to_thread(transition_iteration_status, self.db, iteration_id, to_status)

    async def finalize_iteration_async(self, iteration_id: int) -> Iteration:
        """定稿迭代。

        Raises:
            ValueError: 迭代不存在。
            IterationStatusTransitionError: 状态不允许定稿。
        """
        from app.services.iteration_service import finalize_iteration

        return await asyncio.to_thread(finalize_iteration, self.db, iteration_id)

    async def get_iterations_count_by_project_async(self, project_id: int) -> int:
        """获取项目的迭代数量（用于分页计算总条数）。"""
        from app.crud.iteration import get_iterations_count_by_project

        return await asyncio.to_thread(get_iterations_count_by_project, self.db, project_id)

    async def update_iteration_async(self, iteration_id: int, **kwargs) -> Iteration | None:
        """更新迭代。

        行为与 `crud.iteration.update_iteration` 一致（禁止直接改 status，
        重命名校验同名、仅更新非 None 字段），写后重查一次以获得 eager-load 结果。

        Raises:
            ValueError: 重命名时项目下已存在同名迭代，或尝试直接修改 status。
        """
        from app.crud.iteration import update_iteration

        updated = await asyncio.to_thread(update_iteration, self.db, iteration_id, **kwargs)
        if updated is None:
            return None
        return await self.get_iteration_async(iteration_id)

    async def delete_iteration_async(self, iteration_id: int) -> bool:
        """删除迭代（硬删除）。

        关联资源清理由调用方通过 `_cleanup_iteration_resources` 完成。

        Returns:
            bool: 删除成功返回 True，迭代不存在返回 False。
        """
        from app.crud.iteration import delete_iteration

        return await asyncio.to_thread(delete_iteration, self.db, iteration_id)
