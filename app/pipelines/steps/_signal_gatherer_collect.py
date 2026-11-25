"""SignalGatherer 输入采集与产物组装。

从 `SignalGatherer.execute` 拆出（G-8 B5f）：
- 按输入 `kind` 查表分派到单一职责 handler，替换 `execute` 内的 5 段 if/elif 链；
- 采集结果统一收敛到 `_SignalBundle`，「是否有有效信号」与「产物组装」各自独立可测。
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.pipelines.context import PipelineContext
from app.pipelines.steps._signal_gatherer_helpers import (
    _load_change_notes_from_input,
    _load_file_content,
    _load_test_points_from_input,
    _load_ui_from_input,
    _parse_xmind_to_testpoints,
)


@dataclass
class _SignalBundle:
    """一次信号采集的累积结果（保持原 execute 中各列表的追加顺序语义）。"""

    prd_parts: list[str] = field(default_factory=list)
    ui_descriptions: list[dict[str, Any]] = field(default_factory=list)
    ui_specs: list[dict[str, Any]] = field(default_factory=list)
    test_points: list[dict[str, Any]] = field(default_factory=list)
    change_notes_parts: list[str] = field(default_factory=list)
    file_ids_used: list[int] = field(default_factory=list)

    @property
    def prd_content(self) -> str:
        return "".join(self.prd_parts)

    @property
    def change_notes(self) -> str:
        return "\n\n".join(self.change_notes_parts).strip()

    def is_empty(self) -> bool:
        """PRD / UI / 测试点 / 变更说明全空（老项目判定由调用方另行负责）。"""
        return not (self.prd_content.strip() or self.ui_descriptions or self.test_points or self.change_notes)

    def to_payload(self, ctx: PipelineContext, project_id: int, is_old_project: bool) -> dict[str, Any]:
        prd = self.prd_content.strip()
        return {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "prd_content": prd,
            "ui_descriptions": self.ui_descriptions,
            "ui_specs": self.ui_specs,
            "test_points": self.test_points,
            "change_notes": self.change_notes,
            "file_ids_used": self.file_ids_used,
            "has_ui": len(self.ui_specs) > 0,
            "has_prd": bool(prd),
            "has_testpoints": len(self.test_points) > 0,
            "has_change_notes": bool(self.change_notes),
            "is_old_project": is_old_project,
        }


def _apply_prd_input(bundle: _SignalBundle, ctx: PipelineContext, inp: Any, project_id: int) -> None:
    content = _load_file_content(ctx, inp.file_id, project_id)
    if content:
        bundle.prd_parts.append(f"\n\n{content}")
    if inp.file_id:
        bundle.file_ids_used.append(inp.file_id)


def _apply_prototype_input(bundle: _SignalBundle, ctx: PipelineContext, inp: Any, project_id: int) -> None:
    ui_descriptions, ui_specs, file_ids = _load_ui_from_input(ctx, inp, project_id)
    bundle.ui_descriptions.extend(ui_descriptions)
    bundle.ui_specs.extend(ui_specs)
    bundle.file_ids_used.extend(file_ids)


def _apply_testpoint_input(bundle: _SignalBundle, ctx: PipelineContext, inp: Any, project_id: int) -> None:
    bundle.test_points.extend(_load_test_points_from_input(ctx, inp, project_id))


def _apply_change_notes_input(bundle: _SignalBundle, ctx: PipelineContext, inp: Any, project_id: int) -> None:
    notes = _load_change_notes_from_input(inp)
    if notes:
        bundle.change_notes_parts.append(notes)


def _apply_xmind_input(bundle: _SignalBundle, ctx: PipelineContext, inp: Any, project_id: int) -> None:
    content = _load_file_content(ctx, inp.file_id, project_id)
    if not content:
        return
    payload: dict[str, Any] = {}
    if inp.payload and isinstance(inp.payload, dict):
        payload = dict(inp.payload)
    payload["xmind_content"] = content
    bundle.test_points.extend(_parse_xmind_to_testpoints(payload, project_id))


# kind → 单一职责 handler；未知 kind 直接忽略（原实现即无 else 分支）
_INPUT_HANDLERS: dict[str, Callable[[_SignalBundle, PipelineContext, Any, int], None]] = {
    "prd": _apply_prd_input,
    "prototype": _apply_prototype_input,
    "testpoint": _apply_testpoint_input,
    "change_notes": _apply_change_notes_input,
    "xmind": _apply_xmind_input,
}


def _collect_input_signals(ctx: PipelineContext, inputs: Iterable[Any], project_id: int) -> _SignalBundle:
    """逐条输入分派采集；单条失败只记日志，不影响其余输入（与原实现一致）。"""
    bundle = _SignalBundle()
    for inp in inputs:
        handler = _INPUT_HANDLERS.get(getattr(inp, "kind", None))
        if handler is None:
            continue
        try:
            handler(bundle, ctx, inp, project_id)
        except Exception as e:
            logger.error(
                "信号采集失败 kind={} file_id={}: {}",
                getattr(inp, "kind", None),
                getattr(inp, "file_id", None),
                e,
            )
    return bundle


__all__ = ["_SignalBundle", "_collect_input_signals"]
