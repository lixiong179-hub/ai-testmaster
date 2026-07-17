"""迭代异步服务 Mixin。

从 sync 版本（iteration_service 模块函数）镜像出 async 方法，
供 async 端点直接调用，消除 db.run_sync 线程池桥接开销。

设计要点：
    - 与 sync 函数共存（hybrid 模式），sync 端点继续用模块函数；
    - async 方法使用 AsyncSession + select()/await db.execute()；
    - 纯计算逻辑（状态迁移规则校验）复用 sync 模块的常量与异常类；
    - 方法名加 _async 后缀避免与 sync 函数冲突；
    - 由 IterationService 类继承，self.db 运行时为 AsyncSession。

使用方式：
    async def endpoint(..., db: AsyncSession):
        service = IterationService(db)  # db 为 AsyncSession
        iteration = await service.create_iteration_async(...)
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.models.iteration import Iteration, IterationInput
from app.models.enums import IterationPipelineStatus
from app.models.project import ProjectFile
from app.utils.db_time import utcnow
from app.services.iteration_service import (
    IterationStatusTransitionError,
    BaseIterationValidationError,
    DuplicateInputHashError,
    IterationInputValidationError,
    ITERATION_STATUS_TRANSITIONS,
    VALID_INPUT_KINDS,
)
from app.crud.iteration import _normalize_iteration_name


class IterationAsyncMixin:
    """迭代异步操作 Mixin，供 IterationService 继承。

    要求 self.db 为 AsyncSession 实例。
    """

    async def create_iteration_async(
        self,
        project_id: int,
        name: str,
        *,
        version: str = "v1.0",
        description: Optional[str] = None,
        base_iteration_id: Optional[int] = None,
        created_by: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Iteration:
        """创建迭代（异步版本）。

        Raises:
            ValueError: 同项目下已存在同名迭代。
            BaseIterationValidationError: base_iteration_id 校验失败。
        """
        existing_result = await self.db.execute(
            select(Iteration).where(
                Iteration.project_id == project_id,
                Iteration.name == name,
            )
        )
        if existing_result.scalars().first():
            raise ValueError(f"项目下已存在同名迭代: {name}")

        if base_iteration_id is not None:
            base_result = await self.db.execute(
                select(Iteration).where(Iteration.id == base_iteration_id)
            )
            base_iter = base_result.scalars().first()
            if base_iter is None:
                raise BaseIterationValidationError(
                    f"基线迭代 id={base_iteration_id} 不存在"
                )
            if base_iter.project_id != project_id:
                raise BaseIterationValidationError(
                    f"基线迭代 id={base_iteration_id} 不属于项目 id={project_id}"
                )
            if base_iter.status != IterationPipelineStatus.FINALIZED.value:
                raise BaseIterationValidationError(
                    f"基线迭代 id={base_iteration_id} 状态为 {base_iter.status}，"
                    f"必须为 finalized 才能作为基线"
                )

        iteration = Iteration(
            project_id=project_id,
            name=name,
            version=version,
            description=description,
            status=IterationPipelineStatus.DRAFT.value,
            base_iteration_id=base_iteration_id,
            created_by=created_by,
            start_date=start_date,
            end_date=end_date,
        )
        self.db.add(iteration)
        await self.db.flush()
        # eager-load inputs 以便调用方安全访问：AsyncSession 下无法懒加载，
        # 新创建对象的 inputs 关系未加载，_iteration_to_dict 访问时会触发
        # MissingGreenlet。复用 get_iteration_async（含 joinedload）重新查询，
        # identity map 返回同一实例且 inputs 已加载（新迭代为空列表）。
        loaded = await self.get_iteration_async(iteration.id)
        return loaded

    async def add_input_async(
        self,
        iteration_id: int,
        kind: str,
        *,
        file_id: Optional[int] = None,
        payload: Optional[dict] = None,
        hash_value: Optional[str] = None,
    ) -> IterationInput:
        """添加迭代输入（异步版本，含幂等校验）。

        Raises:
            IterationInputValidationError: kind 不合法、file_id 不存在或 hash_value 为空。
            ValueError: 迭代不存在。
            DuplicateInputHashError: 相同 hash 已存在。
        """
        if not hash_value:
            raise IterationInputValidationError("hash_value 不能为空")

        if kind not in VALID_INPUT_KINDS:
            raise IterationInputValidationError(
                f"kind='{kind}' 不合法，允许值: {sorted(VALID_INPUT_KINDS)}"
            )

        iter_result = await self.db.execute(
            select(Iteration).where(Iteration.id == iteration_id)
        )
        if iter_result.scalars().first() is None:
            raise ValueError(f"Iteration id={iteration_id} not found")

        if file_id is not None:
            pf_result = await self.db.execute(
                select(ProjectFile).where(ProjectFile.id == file_id)
            )
            if pf_result.scalars().first() is None:
                raise IterationInputValidationError(
                    f"file_id={file_id} 不存在于 project_files 表"
                )

        existing_result = await self.db.execute(
            select(IterationInput).where(
                IterationInput.iteration_id == iteration_id,
                IterationInput.content_hash == hash_value,
            )
        )
        if existing_result.scalars().first():
            raise DuplicateInputHashError(hash_value)

        inp = IterationInput(
            iteration_id=iteration_id,
            kind=kind,
            file_id=file_id,
            payload=payload,
            content_hash=hash_value,
        )
        self.db.add(inp)
        await self.db.flush()
        return inp

    async def list_iterations_async(
        self,
        project_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Iteration]:
        """按项目查询迭代列表（异步版本，eager-load inputs）。"""
        result = await self.db.execute(
            select(Iteration)
            .options(joinedload(Iteration.inputs))
            .where(Iteration.project_id == project_id)
            .order_by(Iteration.create_time.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.unique().scalars().all()

    async def get_iteration_async(self, iteration_id: int) -> Optional[Iteration]:
        """获取迭代详情（异步版本，含 inputs）。"""
        result = await self.db.execute(
            select(Iteration)
            .options(joinedload(Iteration.inputs))
            .where(Iteration.id == iteration_id)
        )
        return result.unique().scalars().first()

    async def transition_iteration_status_async(
        self,
        iteration_id: int,
        to_status: str,
    ) -> Iteration:
        """执行迭代状态迁移（异步版本）。

        Raises:
            ValueError: 迭代不存在。
            IterationStatusTransitionError: 非法迁移路径。
        """
        result = await self.db.execute(
            select(Iteration).where(Iteration.id == iteration_id)
        )
        iteration = result.scalars().first()
        if iteration is None:
            raise ValueError(f"Iteration id={iteration_id} not found")

        from_status = iteration.status
        if (from_status, to_status) not in ITERATION_STATUS_TRANSITIONS:
            raise IterationStatusTransitionError(
                from_status, to_status,
                detail=f"只有特定路径允许迁移，当前 {from_status} → {to_status} 不在允许列表中",
            )

        iteration.status = to_status
        if to_status == IterationPipelineStatus.FINALIZED.value:
            iteration.finalized_at = utcnow()

        await self.db.flush()
        return iteration

    async def finalize_iteration_async(self, iteration_id: int) -> Iteration:
        """定稿迭代（异步版本）。

        Raises:
            ValueError: 迭代不存在。
            IterationStatusTransitionError: 状态不允许定稿。
        """
        return await self.transition_iteration_status_async(
            iteration_id, IterationPipelineStatus.FINALIZED.value
        )

    async def get_iterations_count_by_project_async(self, project_id: int) -> int:
        """获取项目的迭代数量（异步版本，用于分页计算总条数）。"""
        result = await self.db.execute(
            select(func.count())
            .select_from(Iteration)
            .where(Iteration.project_id == project_id)
        )
        return result.scalar_one()

    async def update_iteration_async(
        self, iteration_id: int, **kwargs
    ) -> Optional[Iteration]:
        """更新迭代（异步版本）。

        镜像 crud.update_iteration：禁止直接修改 status，重命名时校验同名
        （排除自身），仅更新非 None 字段，自动更新 update_time。

        Raises:
            ValueError: 重命名时项目下已存在同名迭代，或尝试直接修改 status。
        """
        result = await self.db.execute(
            select(Iteration).where(Iteration.id == iteration_id)
        )
        db_iteration = result.scalars().first()
        if not db_iteration:
            return None

        # 禁止直接修改 status，必须通过 transition_iteration_status_async
        if "status" in kwargs:
            raise ValueError(
                "禁止直接修改 iteration.status，请使用 iteration_service.transition_iteration_status()"
            )

        # 重命名校验：若更新name字段，检查项目下是否存在同名迭代（排除自身）
        if "name" in kwargs and kwargs["name"] is not None:
            kwargs["name"] = _normalize_iteration_name(kwargs["name"])
            existing_result = await self.db.execute(
                select(Iteration).where(
                    Iteration.project_id == db_iteration.project_id,
                    Iteration.name == kwargs["name"],
                    Iteration.id != iteration_id,  # 排除自身，允许保持原名称
                )
            )
            if existing_result.scalars().first():
                raise ValueError(f"项目下已存在同名迭代: {kwargs['name']}")

        # 仅更新值为非None的字段
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_iteration, key, value)

        db_iteration.update_time = utcnow()
        await self.db.commit()
        # 不调用 refresh：AsyncSession 配置 expire_on_commit=False，commit 后属性
        # 不会被过期；refresh 反而会使已 eager-load 的 inputs 关系失效，导致
        # _iteration_to_dict 访问 inputs 时触发 async 懒加载（MissingGreenlet）。
        return db_iteration

    async def delete_iteration_async(self, iteration_id: int) -> bool:
        """删除迭代（异步版本，硬删除）。

        关联资源清理由调用方通过 _cleanup_iteration_resources_async 完成，
        本方法仅负责删除迭代记录并提交事务。

        Returns:
            bool: 删除成功返回True，迭代不存在返回False。
        """
        result = await self.db.execute(
            select(Iteration).where(Iteration.id == iteration_id)
        )
        db_iteration = result.scalars().first()
        if not db_iteration:
            return False

        try:
            await self.db.delete(db_iteration)
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            raise
