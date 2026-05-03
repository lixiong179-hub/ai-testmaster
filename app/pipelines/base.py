"""
Pipeline Step 基础接口与数据结构

本模块定义 Pipeline Step 的 Protocol 接口和执行结果数据类。

核心类概览：
    - PipelineStep(Protocol) : Step 接口，所有 Step 必须实现
    - StepResult : Step 执行结果，包含产物和状态信息

设计原则：
    - 每个 Step 声明 name/version/requires/produces
    - should_run 控制条件执行
    - cache_key 支持幂等缓存
    - fallback 提供失败兜底
"""
from typing import Protocol, ClassVar, Optional, Any, List, Dict, runtime_checkable
from dataclasses import dataclass, field


@dataclass
class StepResult:
    """Step 执行结果。

    Attributes:
        success: 是否成功。
        artifact_payload: 产物 JSON 载荷（成功时）。
        artifact_kind: 产物类型标识。
        artifact_confidence: 产物置信度（可选）。
        artifact_provenance: 产物来源信息（可选）。
        degraded: 是否降级完成。
        error: 错误信息（失败时）。
        pause_for_confirmation: 是否需要暂停等待用户确认。
        confirmation_reason: 暂停原因。
        confirmation_payload: 传给前端的确认数据。
    """
    success: bool = True
    artifact_payload: Optional[Dict[str, Any]] = None
    artifact_kind: str = ""
    artifact_confidence: Optional[float] = None
    artifact_provenance: Optional[Dict[str, Any]] = None
    degraded: bool = False
    error: Optional[str] = None
    pause_for_confirmation: bool = False
    confirmation_reason: Optional[str] = None
    confirmation_payload: Optional[Dict[str, Any]] = None


@runtime_checkable
class PipelineStep(Protocol):
    """Pipeline Step 接口协议。

    所有 Step 必须实现此 Protocol。Runner 通过此接口驱动 Step 执行。

    Class Variables:
        name: Step 名称（唯一标识）。
        version: Step 版本号（变更视为新 Step，强制重跑）。
        requires: 依赖的产物类型列表。
        produces: 产出的产物类型列表。
    """

    name: ClassVar[str]
    version: ClassVar[str]
    requires: ClassVar[List[str]]
    produces: ClassVar[List[str]]

    def should_run(self, ctx: "PipelineContext") -> bool:
        """判断此 Step 是否应该执行（条件执行）。"""
        ...

    def cache_key(self, ctx: "PipelineContext") -> str:
        """计算缓存键（用于幂等跳过）。"""
        ...

    def execute(self, ctx: "PipelineContext") -> StepResult:
        """执行 Step 逻辑。"""
        ...

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        """校验产物格式是否合法。"""
        ...

    def fallback(self, ctx: "PipelineContext", error: Exception) -> Optional[StepResult]:
        """失败兜底逻辑（重试耗尽后调用）。"""
        ...
