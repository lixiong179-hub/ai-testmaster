"""
迭代服务模块

本模块提供迭代（Iteration）的业务逻辑层，封装流水线上下文相关的操作。
所有迭代状态变更必须通过此服务，禁止直接 SQL update。

核心函数概览：
    - create_iteration : 创建迭代（含 base_iteration_id 校验）
    - add_input : 添加迭代输入（幂等校验 + file_id/kind 校验）
    - list_iterations : 按项目查询迭代列表（eager-load inputs）
    - get_iteration : 获取迭代详情（含 inputs）
    - finalize_iteration : 定稿迭代（委托 transition_iteration_status）

状态迁移规则：
    draft → in_pipeline（Pipeline 启动时）
    in_pipeline → in_review（Pipeline 完成时）
    in_review → finalized（评审 finalize 时）
    finalized → archived（归档）

依赖关系：
    - app.models.iteration : Iteration, IterationInput
    - app.models.enums : IterationPipelineStatus, IterationInputKind
    - app.models.project : ProjectFile
"""
from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload
from app.models.iteration import Iteration, IterationInput
from app.models.enums import IterationPipelineStatus, IterationInputKind
from app.models.project import ProjectFile


class IterationStatusTransitionError(ValueError):
    """非法迭代状态迁移"""

    def __init__(self, from_status: str, to_status: str, detail: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Illegal iteration status transition: {from_status} → {to_status}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class BaseIterationValidationError(ValueError):
    """基线迭代校验失败"""

    def __init__(self, detail: str):
        super().__init__(f"Base iteration validation failed: {detail}")


class DuplicateInputHashError(ValueError):
    """重复输入哈希（幂等校验失败）"""

    def __init__(self, hash_value: str):
        super().__init__(f"Duplicate input hash: {hash_value}")


class IterationInputValidationError(ValueError):
    """迭代输入校验失败"""

    def __init__(self, detail: str):
        super().__init__(f"Iteration input validation failed: {detail}")


# 合法状态迁移路径
ITERATION_STATUS_TRANSITIONS = {
    (IterationPipelineStatus.DRAFT.value, IterationPipelineStatus.IN_PIPELINE.value),
    (IterationPipelineStatus.IN_PIPELINE.value, IterationPipelineStatus.IN_REVIEW.value),
    (IterationPipelineStatus.IN_REVIEW.value, IterationPipelineStatus.FINALIZED.value),
    (IterationPipelineStatus.FINALIZED.value, IterationPipelineStatus.ARCHIVED.value),
}

# IterationInputKind 合法值集合
VALID_INPUT_KINDS = {k.value for k in IterationInputKind}


def create_iteration(
    db: Session,
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
    """创建迭代。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        name: 迭代名称（同项目下唯一）。
        version: 版本号，默认 v1.0。
        description: 迭代描述。
        base_iteration_id: 基线迭代 ID，必须属于同 project 且 status=finalized。
        created_by: 创建人 ID。
        start_date: 开始日期。
        end_date: 结束日期。

    Returns:
        创建后的 Iteration 实例。

    Raises:
        ValueError: 同项目下已存在同名迭代。
        BaseIterationValidationError: base_iteration_id 校验失败。
    """
    # 同名校验
    existing = db.query(Iteration).filter(
        Iteration.project_id == project_id,
        Iteration.name == name,
    ).first()
    if existing:
        raise ValueError(f"项目下已存在同名迭代: {name}")

    # base_iteration_id 校验
    if base_iteration_id is not None:
        base_iter = db.query(Iteration).filter(Iteration.id == base_iteration_id).first()
        if base_iter is None:
            raise BaseIterationValidationError(f"基线迭代 id={base_iteration_id} 不存在")
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
    db.add(iteration)
    db.flush()
    return iteration


def add_input(
    db: Session,
    iteration_id: int,
    kind: str,
    *,
    file_id: Optional[int] = None,
    payload: Optional[dict] = None,
    hash_value: str = None,
) -> IterationInput:
    """添加迭代输入。

    幂等校验：相同 iteration_id + content_hash 的输入不会重复添加。

    Args:
        db: 数据库会话。
        iteration_id: 迭代 ID。
        kind: 输入类型（IterationInputKind 枚举值）。
        file_id: 关联项目文件 ID（可选，需存在于 project_files 表）。
        payload: 非文件型输入的 JSON 载荷（可选）。
        hash_value: 输入内容哈希，用于幂等校验（必填）。

    Returns:
        创建后的 IterationInput 实例。

    Raises:
        ValueError: 迭代不存在。
        DuplicateInputHashError: 相同 hash 已存在。
        IterationInputValidationError: kind 不合法、file_id 不存在或 hash_value 为空。
    """
    if not hash_value:
        raise IterationInputValidationError("hash_value 不能为空")

    # kind 枚举校验
    if kind not in VALID_INPUT_KINDS:
        raise IterationInputValidationError(
            f"kind='{kind}' 不合法，允许值: {sorted(VALID_INPUT_KINDS)}"
        )

    iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if iteration is None:
        raise ValueError(f"Iteration id={iteration_id} not found")

    # file_id 存在性校验
    if file_id is not None:
        pf = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
        if pf is None:
            raise IterationInputValidationError(
                f"file_id={file_id} 不存在于 project_files 表"
            )

    # 幂等校验
    existing = db.query(IterationInput).filter(
        IterationInput.iteration_id == iteration_id,
        IterationInput.content_hash == hash_value,
    ).first()
    if existing:
        raise DuplicateInputHashError(hash_value)

    inp = IterationInput(
        iteration_id=iteration_id,
        kind=kind,
        file_id=file_id,
        payload=payload,
        content_hash=hash_value,
    )
    db.add(inp)
    db.flush()
    return inp


def list_iterations(
    db: Session,
    project_id: int,
    *,
    skip: int = 0,
    limit: int = 100,
) -> List[Iteration]:
    """按项目查询迭代列表（按创建时间倒序，eager-load inputs）。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        skip: 分页偏移。
        limit: 返回上限。

    Returns:
        迭代列表。
    """
    return (
        db.query(Iteration)
        .options(joinedload(Iteration.inputs))
        .filter(Iteration.project_id == project_id)
        .order_by(Iteration.create_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_iteration(db: Session, iteration_id: int) -> Optional[Iteration]:
    """获取迭代详情（含 inputs）。

    Args:
        db: 数据库会话。
        iteration_id: 迭代 ID。

    Returns:
        Iteration 实例或 None。
    """
    return (
        db.query(Iteration)
        .options(joinedload(Iteration.inputs))
        .filter(Iteration.id == iteration_id)
        .first()
    )


def finalize_iteration(db: Session, iteration_id: int) -> Iteration:
    """定稿迭代。

    仅 in_review 状态的迭代可定稿。委托 transition_iteration_status 执行。

    Args:
        db: 数据库会话。
        iteration_id: 迭代 ID。

    Returns:
        更新后的 Iteration 实例。

    Raises:
        ValueError: 迭代不存在。
        IterationStatusTransitionError: 状态不允许定稿。
    """
    return transition_iteration_status(
        db, iteration_id, IterationPipelineStatus.FINALIZED.value
    )


def transition_iteration_status(
    db: Session,
    iteration_id: int,
    to_status: str,
) -> Iteration:
    """执行迭代状态迁移（系统内部调用）。

    Args:
        db: 数据库会话。
        iteration_id: 迭代 ID。
        to_status: 目标状态。

    Returns:
        更新后的 Iteration 实例。

    Raises:
        ValueError: 迭代不存在。
        IterationStatusTransitionError: 非法迁移路径。
    """
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if iteration is None:
        raise ValueError(f"Iteration id={iteration_id} not found")

    from_status = iteration.status
    if (from_status, to_status) not in ITERATION_STATUS_TRANSITIONS:
        raise IterationStatusTransitionError(
            from_status, to_status,
            detail=f"只有特定路径允许迁移，当前 {from_status} → {to_status} 不在允许列表中",
        )

    iteration.status = to_status

    # 定稿时自动设置 finalized_at
    if to_status == IterationPipelineStatus.FINALIZED.value:
        iteration.finalized_at = datetime.now(timezone.utc)

    db.flush()
    return iteration
