"""
Pipeline 存储服务模块

本模块提供 Pipeline 运行时持久化的业务逻辑层，封装 Run/Step/Artifact 的
CRUD 操作和缓存/幂等机制。

核心函数概览：
    - create_run : 创建 PipelineRun（幂等：相同 input_hash + pipeline_version 返回已有 run）
    - get_run : 获取运行详情（含 steps + artifacts）
    - list_runs : 按迭代查询运行列表
    - update_run_status : 更新运行状态（含迁移校验）
    - create_step : 创建 Step 记录
    - find_cached_step : 按 cache_key 查找已完成的 step（缓存命中）
    - update_step_status : 更新 step 状态（含迁移校验）
    - create_artifact : 创建产物（hash 唯一约束防重复）
    - get_artifact_by_hash : 按 hash 查找产物
    - compute_input_hash : 计算迭代输入的聚合哈希
    - compute_cache_key : 计算 step 缓存键

依赖关系：
    - app.models.pipeline : PipelineRun, PipelineStep, Artifact
    - app.models.enums : PipelineRunStatus, PipelineStepStatus
    - app.models.iteration : Iteration, IterationInput
"""
import hashlib
import json
from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload
from app.models.pipeline import PipelineRun, PipelineStep, Artifact
from app.models.enums import PipelineRunStatus, PipelineStepStatus
from app.models.iteration import Iteration, IterationInput


class DuplicateArtifactHashError(ValueError):
    """重复产物哈希（唯一约束冲突）"""

    def __init__(self, content_hash: str):
        super().__init__(f"Duplicate artifact content_hash: {content_hash}")


class PipelineRunValidationError(ValueError):
    """PipelineRun 校验失败"""

    def __init__(self, detail: str):
        super().__init__(f"PipelineRun validation failed: {detail}")


class PipelineStepValidationError(ValueError):
    """PipelineStep 校验失败"""

    def __init__(self, detail: str):
        super().__init__(f"PipelineStep validation failed: {detail}")


class PipelineStatusTransitionError(ValueError):
    """非法 Pipeline 状态迁移"""

    def __init__(self, entity: str, from_status: str, to_status: str, detail: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Illegal {entity} status transition: {from_status} → {to_status}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


# 合法状态迁移路径
PIPELINE_RUN_TRANSITIONS = {
    (PipelineRunStatus.PENDING.value, PipelineRunStatus.RUNNING.value),
    (PipelineRunStatus.RUNNING.value, PipelineRunStatus.WAITING_FOR_USER.value),
    (PipelineRunStatus.RUNNING.value, PipelineRunStatus.COMPLETED.value),
    (PipelineRunStatus.RUNNING.value, PipelineRunStatus.FAILED.value),
    (PipelineRunStatus.WAITING_FOR_USER.value, PipelineRunStatus.RUNNING.value),
    (PipelineRunStatus.WAITING_FOR_USER.value, PipelineRunStatus.COMPLETED.value),
    (PipelineRunStatus.WAITING_FOR_USER.value, PipelineRunStatus.CANCELLED.value),
    (PipelineRunStatus.PENDING.value, PipelineRunStatus.CANCELLED.value),
}

PIPELINE_STEP_TRANSITIONS = {
    (PipelineStepStatus.PENDING.value, PipelineStepStatus.RUNNING.value),
    (PipelineStepStatus.PENDING.value, PipelineStepStatus.SKIPPED.value),
    (PipelineStepStatus.RUNNING.value, PipelineStepStatus.DONE.value),
    (PipelineStepStatus.RUNNING.value, PipelineStepStatus.FAILED.value),
    (PipelineStepStatus.RUNNING.value, PipelineStepStatus.DEGRADED.value),
    (PipelineStepStatus.FAILED.value, PipelineStepStatus.RUNNING.value),   # 重试
}


# ==================== 工具函数 ====================

def compute_input_hash(iteration_inputs: List[IterationInput]) -> str:
    """计算迭代输入的聚合哈希。

    将所有输入按 (kind, content_hash) 排序后拼接，计算 SHA-256。

    Args:
        iteration_inputs: 迭代输入列表。

    Returns:
        64 字符的十六进制 SHA-256 哈希字符串。
    """
    pairs = sorted(
        [(inp.kind, inp.content_hash) for inp in iteration_inputs],
        key=lambda p: (p[0], p[1]),
    )
    raw = json.dumps(pairs, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_cache_key(
    step_name: str,
    step_version: str,
    input_artifact_hashes: List[str],
) -> str:
    """计算 Step 缓存键。

    Args:
        step_name: Step 名称。
        step_version: Step 版本号。
        input_artifact_hashes: 输入产物的哈希列表（排序后）。

    Returns:
        64 字符的十六进制 SHA-256 哈希字符串。
    """
    parts = [step_name, step_version] + sorted(input_artifact_hashes)
    raw = json.dumps(parts, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


# ==================== PipelineRun ====================

def create_run(
    db: Session,
    iteration_id: int,
    input_hash: str,
    pipeline_version: str = "1.0",
) -> PipelineRun:
    """创建 PipelineRun（幂等：相同 iteration_id + input_hash + pipeline_version 返回已有 run）。

    pipeline_version 参与幂等校验：版本升级后强制重跑。

    Args:
        db: 数据库会话。
        iteration_id: 迭代 ID。
        input_hash: 输入内容哈希。
        pipeline_version: Pipeline 版本号。

    Returns:
        PipelineRun 实例（新建或已有）。

    Raises:
        PipelineRunValidationError: iteration_id 不存在。
    """
    # iteration_id 存在性校验
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if iteration is None:
        raise PipelineRunValidationError(f"iteration_id={iteration_id} 不存在")

    # 幂等校验：相同 input_hash + pipeline_version 的有效 run 直接返回
    existing = db.query(PipelineRun).filter(
        PipelineRun.iteration_id == iteration_id,
        PipelineRun.input_hash == input_hash,
        PipelineRun.pipeline_version == pipeline_version,
        PipelineRun.status.in_([
            PipelineRunStatus.COMPLETED.value,
            PipelineRunStatus.RUNNING.value,
            PipelineRunStatus.WAITING_FOR_USER.value,
        ]),
    ).first()
    if existing:
        return existing

    run = PipelineRun(
        iteration_id=iteration_id,
        input_hash=input_hash,
        pipeline_version=pipeline_version,
        status=PipelineRunStatus.PENDING.value,
    )
    db.add(run)
    db.flush()
    return run


def get_run(db: Session, run_id: int) -> Optional[PipelineRun]:
    """获取运行详情（含 steps + artifacts）。

    Args:
        db: 数据库会话。
        run_id: 运行 ID。

    Returns:
        PipelineRun 实例或 None。
    """
    return (
        db.query(PipelineRun)
        .options(
            joinedload(PipelineRun.steps),
            joinedload(PipelineRun.artifacts),
        )
        .filter(PipelineRun.id == run_id)
        .first()
    )


def list_runs(
    db: Session,
    iteration_id: int,
    *,
    skip: int = 0,
    limit: int = 100,
) -> List[PipelineRun]:
    """按迭代查询运行列表（按创建时间倒序）。

    Args:
        db: 数据库会话。
        iteration_id: 迭代 ID。
        skip: 分页偏移。
        limit: 返回上限。

    Returns:
        PipelineRun 列表。
    """
    return (
        db.query(PipelineRun)
        .filter(PipelineRun.iteration_id == iteration_id)
        .order_by(PipelineRun.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_run_status(
    db: Session,
    run_id: int,
    status: str,
    *,
    error: Optional[str] = None,
) -> Optional[PipelineRun]:
    """更新运行状态（含迁移校验）。

    Args:
        db: 数据库会话。
        run_id: 运行 ID。
        status: 目标状态。
        error: 错误信息（可选）。

    Returns:
        更新后的 PipelineRun 实例或 None。

    Raises:
        PipelineStatusTransitionError: 非法状态迁移。
    """
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run is None:
        return None

    from_status = run.status
    if (from_status, status) not in PIPELINE_RUN_TRANSITIONS:
        raise PipelineStatusTransitionError(
            "PipelineRun", from_status, status,
            detail=f"允许的迁移路径: {from_status} → {status} 不在允许列表中",
        )

    run.status = status
    if error is not None:
        run.error = error

    now = datetime.now(timezone.utc)
    if status == PipelineRunStatus.RUNNING.value and run.started_at is None:
        run.started_at = now
    if status in (PipelineRunStatus.COMPLETED.value, PipelineRunStatus.FAILED.value,
                  PipelineRunStatus.CANCELLED.value):
        run.finished_at = now

    db.flush()
    return run


# ==================== PipelineStep ====================

def create_step(
    db: Session,
    run_id: int,
    step_name: str,
    step_version: str = "1.0",
    cache_key: Optional[str] = None,
    input_artifact_ids: Optional[List[int]] = None,
) -> PipelineStep:
    """创建 Step 记录。

    Args:
        db: 数据库会话。
        run_id: 运行 ID。
        step_name: Step 名称。
        step_version: Step 版本号。
        cache_key: 缓存键。
        input_artifact_ids: 输入产物 ID 列表。

    Returns:
        PipelineStep 实例。

    Raises:
        PipelineStepValidationError: run_id 不存在。
    """
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run is None:
        raise PipelineStepValidationError(f"run_id={run_id} 不存在")

    step = PipelineStep(
        run_id=run_id,
        step_name=step_name,
        step_version=step_version,
        status=PipelineStepStatus.PENDING.value,
        cache_key=cache_key,
        input_artifact_ids=input_artifact_ids,
    )
    db.add(step)
    db.flush()
    return step


def find_cached_step(db: Session, cache_key: str) -> Optional[PipelineStep]:
    """按 cache_key 查找已完成的 step（缓存命中）。

    Args:
        db: 数据库会话。
        cache_key: 缓存键。

    Returns:
        已完成的 PipelineStep 实例或 None。
    """
    return (
        db.query(PipelineStep)
        .filter(
            PipelineStep.cache_key == cache_key,
            PipelineStep.status == PipelineStepStatus.DONE.value,
        )
        .first()
    )


def update_step_status(
    db: Session,
    step_id: int,
    status: str,
    *,
    error: Optional[str] = None,
    output_artifact_ids: Optional[List[int]] = None,
    retried_count: Optional[int] = None,
    degraded: Optional[bool] = None,
) -> Optional[PipelineStep]:
    """更新 step 状态（含迁移校验）。

    Args:
        db: 数据库会话。
        step_id: Step ID。
        status: 目标状态。
        error: 错误信息（可选）。
        output_artifact_ids: 输出产物 ID 列表（可选）。
        retried_count: 重试次数（可选）。
        degraded: 是否降级（可选）。

    Returns:
        更新后的 PipelineStep 实例或 None。

    Raises:
        PipelineStatusTransitionError: 非法状态迁移。
    """
    step = db.query(PipelineStep).filter(PipelineStep.id == step_id).first()
    if step is None:
        return None

    from_status = step.status
    if (from_status, status) not in PIPELINE_STEP_TRANSITIONS:
        raise PipelineStatusTransitionError(
            "PipelineStep", from_status, status,
            detail=f"允许的迁移路径: {from_status} → {status} 不在允许列表中",
        )

    step.status = status
    if error is not None:
        step.error = error
    if output_artifact_ids is not None:
        step.output_artifact_ids = output_artifact_ids
    if retried_count is not None:
        step.retried_count = retried_count
    if degraded is not None:
        step.degraded = degraded

    now = datetime.now(timezone.utc)
    if status == PipelineStepStatus.RUNNING.value and step.started_at is None:
        step.started_at = now
    if status in (PipelineStepStatus.DONE.value, PipelineStepStatus.FAILED.value,
                  PipelineStepStatus.SKIPPED.value, PipelineStepStatus.DEGRADED.value):
        step.finished_at = now

    db.flush()
    return step


# ==================== Artifact ====================

def create_artifact(
    db: Session,
    run_id: int,
    kind: str,
    content_hash: str,
    *,
    schema_version: str = "1.0",
    payload: Optional[dict] = None,
    confidence: Optional[float] = None,
    provenance: Optional[dict] = None,
) -> Artifact:
    """创建产物（hash 唯一约束防重复落库）。

    Args:
        db: 数据库会话。
        run_id: 运行 ID。
        kind: 产物类型。
        content_hash: 产物内容哈希。
        schema_version: schema 版本。
        payload: JSON 载荷。
        confidence: 置信度。
        provenance: 来源信息。

    Returns:
        Artifact 实例。

    Raises:
        PipelineRunValidationError: run_id 不存在。
        DuplicateArtifactHashError: hash 已存在。
    """
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run is None:
        raise PipelineRunValidationError(f"run_id={run_id} 不存在")

    existing = db.query(Artifact).filter(Artifact.content_hash == content_hash).first()
    if existing:
        raise DuplicateArtifactHashError(content_hash)

    artifact = Artifact(
        run_id=run_id,
        kind=kind,
        schema_version=schema_version,
        payload=payload,
        confidence=confidence,
        provenance=provenance,
        content_hash=content_hash,
    )
    db.add(artifact)
    db.flush()
    return artifact


def get_artifact_by_hash(db: Session, content_hash: str) -> Optional[Artifact]:
    """按 hash 查找产物。

    Args:
        db: 数据库会话。
        content_hash: 产物内容哈希。

    Returns:
        Artifact 实例或 None。
    """
    return db.query(Artifact).filter(Artifact.content_hash == content_hash).first()
