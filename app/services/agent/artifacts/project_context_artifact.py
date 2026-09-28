"""项目上下文 Artifact。

承载被测项目的基础信息，所有 Agent 在首轮迭代都需要此 artifact 来理解
「这是什么东西、技术栈、环境配置、入口 URL」。
"""
from __future__ import annotations

from typing import ClassVar, List, Optional

from app.services.agent.artifacts.base import Artifact


class ProjectContextArtifact(Artifact):
    """项目上下文 Artifact。

    Attributes:
        project_id: 项目 ID。
        name: 项目名称。
        tech_stack: 技术栈列表（如 ["Vue3", "FastAPI", "MySQL"]）。
        env_config: 环境配置 dict（如 {"base_url": "...", "api_version": "v1"}）。
        base_url: 被测应用入口 URL，env_config.base_url 的快捷字段。
    """

    artifact_type: ClassVar[str] = "project_context"
    description: ClassVar[str] = "被测项目上下文，含技术栈、环境配置、入口 URL"

    project_id: int
    name: str
    tech_stack: List[str] = []
    env_config: dict = {}
    base_url: Optional[str] = None


__all__ = ["ProjectContextArtifact"]
