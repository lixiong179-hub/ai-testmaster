"""CaseGeneration 输入归一与提前返回（G-8 B5g 从 `CaseGeneration.execute` 拆出）。

`execute` 原先把「取信号 → 拆任务 → 装历史 → 三种提前返回」挤在同一个分支链里；
这里拆成 5 个单一职责函数，`execute` 只按顺序调用：

1. `_signal_inputs`       raw_signals → 归一字段（缺产物时给出空默认）
2. `_build_ui_description` UI 描述拼接
3. `_split_tasks`         generation_tasks 产物 → (全量任务, deprecation, 可执行任务)
4. `_load_history_cases`  历史指纹 → 供 prompt 复用的历史用例（≤50）
5. `_early_exit_result`   无任务/无产物场景的三种提前返回
"""

from typing import Any

from app.pipelines.base import StepResult
from app.pipelines.context import PipelineContext

# 可执行任务类型（keep/skip/deprecate 不进入生成）
_ACTIONABLE_TASK_TYPES = ("create", "modify", "locator_fix")


def _signal_inputs(signals: dict[str, Any] | None) -> dict[str, Any]:
    """raw_signals → execute 需要的字段（无产物时全部给空值）。"""
    if not signals:
        return {
            "prd_content": "",
            "ui_specs": [],
            "ui_descriptions": [],
            "has_ui": False,
            "project_id": None,
        }
    return {
        "prd_content": signals.get("prd_content", ""),
        "ui_specs": signals.get("ui_specs", []),
        "ui_descriptions": signals.get("ui_descriptions", []),
        "has_ui": signals.get("has_ui", False),
        "project_id": signals.get("project_id"),
    }


def _build_ui_description(ui_descriptions: list[dict[str, Any]]) -> str:
    """UI 页面描述拼成一段文本（跳过既无 description 也无 summary 的项）。"""
    if not ui_descriptions:
        return ""
    return "\n".join(
        d.get("description", d.get("summary", "")) for d in ui_descriptions if d.get("description") or d.get("summary")
    )


def _split_tasks(
    tasks_artifact: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """generation_tasks 产物 → (全量任务, deprecation 建议, 可执行任务)。"""
    if tasks_artifact is None:
        return [], [], []
    generation_tasks = tasks_artifact.get("generation_tasks", [])
    deprecation_suggestions = tasks_artifact.get("deprecation_suggestions", [])
    actionable_tasks = [t for t in generation_tasks if t.get("task_type") in _ACTIONABLE_TASK_TYPES]
    return generation_tasks, deprecation_suggestions, actionable_tasks


def _load_history_cases(ctx: PipelineContext, actionable_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """无可执行任务时不读历史（保持原实现的惰性）。"""
    if not actionable_tasks:
        return []
    hf_artifact = ctx.get_artifact("history_fingerprints")
    if not hf_artifact:
        return []
    return [
        {
            "title": fp.get("title", fp.get("case_title", "")),
            "module": fp.get("module", ""),
            "summary": fp.get("summary", ""),
            "priority": fp.get("priority", 3),
        }
        for fp in hf_artifact.get("fingerprints", [])[:50]
    ]


def _empty_cases_payload(
    ctx: PipelineContext,
    inputs: dict[str, Any],
    deprecation_suggestions: list[dict[str, Any]],
) -> dict[str, Any]:
    """「0 条用例」产物载荷（提前返回与降级共用同一口径）。"""
    return {
        "iteration_id": ctx.iteration_id,
        "project_id": inputs["project_id"],
        "generated_cases": [],
        "total": 0,
        "success_count": 0,
        "failed_count": 0,
        "has_ui": inputs["has_ui"],
        "deprecation_suggestions": deprecation_suggestions,
    }


def _early_exit_result(
    ctx: PipelineContext,
    tasks_artifact: dict[str, Any] | None,
    actionable_tasks: list[dict[str, Any]],
    aligned: dict[str, Any] | None,
    signals: dict[str, Any] | None,
    inputs: dict[str, Any],
    deprecation_suggestions: list[dict[str, Any]],
) -> StepResult | None:
    """三种提前返回；可以继续走生成流程时返回 None。"""
    if actionable_tasks:
        return None
    # 有任务产物但全是 keep/skip/deprecate → 视为无可生成内容
    if tasks_artifact is not None:
        return StepResult(
            success=False,
            error="generation_tasks 中没有可执行的 create/modify/locator_fix 任务",
            artifact_payload=_empty_cases_payload(ctx, inputs, deprecation_suggestions),
            artifact_kind="generated_cases",
            artifact_confidence=0.0,
        )
    # 场景 4/5 的设计即「无任务」，按成功空结果放行
    if ctx.config.get("scenario") in (4, 5):
        return StepResult(
            success=True,
            artifact_payload=_empty_cases_payload(ctx, inputs, []),
            artifact_kind="generated_cases",
            artifact_confidence=0.0,
        )
    if not aligned and not signals:
        return StepResult(
            success=False,
            error="缺少 generation_tasks、aligned_testpoints 和 raw_signals 产物",
        )
    return None


__all__ = [
    "_build_ui_description",
    "_early_exit_result",
    "_empty_cases_payload",
    "_load_history_cases",
    "_signal_inputs",
    "_split_tasks",
]
