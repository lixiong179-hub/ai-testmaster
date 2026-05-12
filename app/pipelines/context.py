"""
Pipeline 运行时上下文

本模块定义 PipelineContext，封装单次 Pipeline 运行的所有依赖注入。

核心类概览：
    - PipelineContext : 运行时上下文，注入 DB/AI/Config/Iteration/Run 等

设计原则：
    - 所有外部依赖通过 PipelineContext 注入，Step 不直接 import service
    - 产物通过 get_artifact / set_artifact 在 Step 间传递
    - 预算检查通过 ctx.check_budget() 统一入口
"""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.ai.client import AIClient
from app.models.pipeline import PipelineRun, PipelineStep as PipelineStepModel, Artifact
from app.utils.db_time import utcnow


class PipelineContext:
    """Pipeline 运行时上下文。

    封装单次 Pipeline 运行的所有依赖注入，Step 通过此上下文
    访问 DB、AI Client、配置、产物等。

    Attributes:
        db: 数据库会话。
        ai_client: AI 调用客户端。
        run: PipelineRun 数据库记录。
        iteration_id: 关联迭代 ID。
        step_records: 已执行的 PipelineStep 记录（按 step_name 索引）。
        artifacts: 已产出的 Artifact 记录（按 kind 索引）。
        config: 运行时配置（从 config_service 加载）。
        user_id: 触发运行的用户 ID。
    """

    def __init__(
        self,
        db: Session,
        ai_client: AIClient,
        run: PipelineRun,
        iteration_id: int,
        user_id: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.db = db
        self.ai_client = ai_client
        self.run = run
        self.iteration_id = iteration_id
        self.user_id = user_id
        self.config = config or {}

        self._step_records: Dict[str, PipelineStepModel] = {}
        self._artifacts: Dict[str, Artifact] = {}
        self._confirmation_payload: Optional[Dict[str, Any]] = None
        self._pause_info: Optional[Dict[str, Any]] = None
        self._cached_project_id: Optional[int] = None

    def get_artifact(self, kind: str) -> Optional[Dict[str, Any]]:
        """获取指定类型的产物载荷。

        Args:
            kind: 产物类型标识。

        Returns:
            产物 JSON 载荷，不存在返回 None。
        """
        artifact = self._artifacts.get(kind)
        if artifact is None:
            return None
        return artifact.payload

    def set_artifact(self, kind: str, artifact: Artifact) -> None:
        """注册产物到上下文。

        Args:
            kind: 产物类型标识。
            artifact: Artifact 数据库记录。
        """
        self._artifacts[kind] = artifact

    def register_step_record(self, step_name: str, record: PipelineStepModel) -> None:
        """注册 Step 执行记录到上下文。

        Args:
            step_name: Step 名称。
            record: PipelineStep 数据库记录。
        """
        self._step_records[step_name] = record

    def get_step_record(self, step_name: str) -> Optional[PipelineStepModel]:
        """获取 Step 执行记录。

        Args:
            step_name: Step 名称。

        Returns:
            PipelineStep 记录，不存在返回 None。
        """
        return self._step_records.get(step_name)

    def check_budget(self) -> bool:
        """检查 token 预算是否充足。

        Returns:
            True 表示预算充足，False 表示超限。
        """
        from app.ai.call_log import check_budget
        return check_budget(self.db, self.run.id)

    def get_config(self, key: str, default: Any = None) -> Any:
        """读取运行时配置。

        Args:
            key: 配置项键名。
            default: 默认值。

        Returns:
            配置项值。
        """
        if key in self.config:
            return self.config[key]
        from app.services.config_service import get_config
        return get_config(self.db, key, default)

    def set_confirmation_payload(self, payload: Dict[str, Any]) -> None:
        self._confirmation_payload = payload

    def get_confirmation_payload(self) -> Optional[Dict[str, Any]]:
        return self._confirmation_payload

    def set_pause_info(self, reason: str, step_name: str, schema: Optional[Dict[str, Any]] = None) -> None:
        self._pause_info = {
            "reason": reason,
            "step_name": step_name,
            "schema": schema,
            "paused_at": utcnow().isoformat(),
        }

    def get_pause_info(self) -> Optional[Dict[str, Any]]:
        return self._pause_info
