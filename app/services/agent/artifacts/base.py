"""Artifact 抽象基类。

设计目的：
    Artifact 是 Agent 上下文的自描述单元，取代早期巨型 state 字典。每个
    artifact 通过 pydantic schema 校验数据完整性，通过 artifact_type 标识
    类型，通过 to_prompt_section() 输出注入 LLM prompt 的文本段。

设计原则：
    - 自描述：每个 artifact 类携带 description 类属性，说明用途
    - schema 校验：继承 pydantic BaseModel，畸形数据在 validate 时抛
        ValidationError，会话状态置为 failed
    - 可独立演进：新增 artifact 仅需新增文件 + 注册到 ArtifactRegistry，
        所有 Agent 的 prompt 自动包含新 artifact 描述段
"""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class Artifact(BaseModel):
    """Artifact 抽象基类。

    子类必须覆盖类属性：
        - artifact_type: 类型标识，全进程唯一，用于 ArtifactRegistry 路由
        - description: 人类可读用途描述，注入 prompt 顶部说明段

    子类通常无需覆盖 to_prompt_section()，默认实现返回 JSON 序列化结果。
    若需更友好的 prompt 格式（如 Markdown 表格），可覆盖此方法。

    Attributes:
        artifact_type: 类型标识（如 "test_case" / "execution_state"）。
        description: 用途描述，用于 prompt 头部 artifact 索引段。
    """

    model_config = ConfigDict(
        # 严格模式：拒绝未知字段，避免 artifact 数据漂移
        extra="forbid",
        # 允许从 ORM 对象构造（如从 AgentMessage.artifact_refs 反序列化）
        from_attributes=True,
    )

    # 类属性：子类必须覆盖
    artifact_type: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def to_prompt_section(self) -> str:
        """输出注入 LLM prompt 的文本段。

        默认实现返回缩进 JSON，便于 LLM 解析。子类可覆盖为 Markdown 表格、
        bullet list 等更友好的格式。

        Returns:
            str: 注入 prompt 的文本段，格式自定。
        """
        import json

        # exclude_unset=False 保证默认值也输出，避免 LLM 误判字段缺失
        data: dict[str, Any] = self.model_dump(mode="json")
        pretty = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        return f"[Artifact: {self.artifact_type}]\n{self.description}\n\n```json\n{pretty}\n```"


__all__ = ["Artifact"]
