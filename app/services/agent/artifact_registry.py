"""Artifact 注册表。

设计目的：
    ArtifactRegistry 集中管理所有 artifact 类，支持运行时注册、按
    artifact_type 校验数据、生成 prompt 头部 artifact 索引段。新增 artifact
    注册后，所有 Agent 的 prompt 自动包含其描述段。

设计原则：
    - 类型路由：validate(artifact_type, data) 按类型分发到对应 pydantic 类
    - schema 校验：调用 pydantic model_validate，畸形数据抛 ValidationError
    - prompt 注入：get_prompt_section() 输出所有已注册 artifact 的描述段
"""
from __future__ import annotations

from typing import Dict, List, Type

from pydantic import ValidationError

from app.services.agent.artifacts.base import Artifact


class ArtifactRegistry:
    """Artifact 注册表。

    使用方式：
        registry = ArtifactRegistry()
        registry.register(TestCaseArtifact)
        artifact = registry.validate("test_case", {"title": "...", "steps": []})
        prompt = registry.build_artifacts_index_prompt()
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Type[Artifact]] = {}

    def register(self, artifact_class: Type[Artifact]) -> None:
        """注册 artifact 类。

        Args:
            artifact_class: Artifact 子类，必须覆盖 artifact_type 类属性。

        Raises:
            ValueError: artifact_type 为空或重复注册。
        """
        artifact_type = artifact_class.artifact_type
        if not artifact_type:
            raise ValueError(
                f"Artifact 类 {artifact_class.__name__} 未覆盖 artifact_type 类属性"
            )
        if artifact_type in self._registry:
            raise ValueError(
                f"Artifact 类型 {artifact_type} 已注册"
                f"（{self._registry[artifact_type].__name__}）"
            )
        self._registry[artifact_type] = artifact_class

    def validate(self, artifact_type: str, data: dict) -> Artifact:
        """按类型校验数据并构造 artifact 实例。

        Args:
            artifact_type: 类型标识。
            data: 原始数据 dict。

        Returns:
            Artifact: 校验后的实例。

        Raises:
            KeyError: artifact_type 未注册。
            ValidationError: 数据不符合 schema。
        """
        artifact_class = self._registry.get(artifact_type)
        if artifact_class is None:
            raise KeyError(f"Artifact 类型未注册: {artifact_type}")
        return artifact_class.model_validate(data)

    def get_class(self, artifact_type: str) -> Type[Artifact]:
        """查询 artifact 类。"""
        return self._registry[artifact_type]

    def list_artifacts(self) -> List[str]:
        """列出所有已注册 artifact 类型，按字典序排序。"""
        return sorted(self._registry.keys())

    def build_artifacts_index_prompt(self) -> str:
        """构建所有已注册 artifact 的索引段，注入 system prompt。

        Returns:
            str: artifact 索引段文本，含每个 artifact 的类型与描述。
        """
        if not self._registry:
            return ""
        lines = ["# Available Artifacts", ""]
        for artifact_type in self.list_artifacts():
            artifact_class = self._registry[artifact_type]
            lines.append(f"- **{artifact_type}**: {artifact_class.description}")
        lines.append("")
        lines.append(
            "请根据任务需要选择合适的 artifact 作为输入或输出载体。"
        )
        return "\n".join(lines)


__all__ = ["ArtifactRegistry"]
