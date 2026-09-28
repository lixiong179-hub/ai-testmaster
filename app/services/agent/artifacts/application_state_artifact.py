"""应用状态 Artifact。

承载被测应用的当前页面状态，用于 LocatorHealingAgent 与
VisualValidationAgent 感知「页面在哪、DOM 长什么样、视口多大」。
"""
from __future__ import annotations

from typing import ClassVar, Optional

from app.services.agent.artifacts.base import Artifact


class ApplicationStateArtifact(Artifact):
    """应用状态 Artifact。

    Attributes:
        url: 当前页面 URL。
        dom_snapshot: 当前 DOM 序列化（HTML 字符串或精简 selector 树）。
        tab_id: 浏览器 tab 标识，多 tab 场景下区分。
        viewport_size: 视口尺寸 dict，含 width/height（像素）。
    """

    artifact_type: ClassVar[str] = "application_state"
    description: ClassVar[str] = "被测应用状态，含 URL、DOM 快照、视口尺寸"

    url: str
    dom_snapshot: Optional[str] = None
    tab_id: Optional[str] = None
    viewport_size: Optional[dict] = None


__all__ = ["ApplicationStateArtifact"]
