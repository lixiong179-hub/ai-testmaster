"""额外上下文渲染器 - 将 extra_context 中的多种 task_type 分支渲染为 Prompt 段落。

主入口 _append_extra_context_sections(prompt, extra_context) 按 task_type 调度子渲染函数：
- _render_quality_feedback / _render_quality_signals：质量闭环信号（与 task_type 正交）
- _render_modify_context：task_type="modify" 修改模式
- _render_create_context：task_type="create" 创建模式（含历史用例去重）
- _render_locator_fix_context：task_type="locator_fix" 定位器修复模式
- _render_migrate_context：task_type="migrate" 跨设备迁移模式
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _render_quality_feedback(
    extra_context: Dict[str, Any], sections: List[str],
) -> None:
    """注入上轮校验问题供AI修复（与task_type正交，优先级最高）。"""
    quality_feedback = extra_context.get("quality_feedback")
    if not quality_feedback:
        return
    sections.append("## 质量反馈")
    sections.append(str(quality_feedback))
    sections.append("")


def _render_quality_signals(
    extra_context: Dict[str, Any], sections: List[str],
) -> None:
    """注入质量信号（具体问题+低分维度），与 quality_feedback 正交。

    禁止盲重试：quality_signals 携带具体失败原因（历史避坑要点 4）。
    """
    quality_signals = extra_context.get("quality_signals")
    if not quality_signals:
        return
    from app.services.case_quality.quality_signals import format_quality_signals
    signals_text = format_quality_signals(quality_signals)
    if signals_text:
        sections.append(signals_text)
        sections.append("")


def _render_modify_context(
    task_context: Dict[str, Any], sections: List[str],
) -> None:
    """渲染 task_type="modify" 修改模式：注入原有用例 + 变更指引。"""
    original = task_context.get("original_case")
    if not original:
        return
    sections.append("## 原有用例（需基于此修改）")
    sections.append(f"### 原用例标题: {original.get('title', '')}")
    sections.append(f"### 原前置条件: {original.get('precondition', '')}")
    steps_json = original.get('steps_json')
    if isinstance(steps_json, str):
        try:
            steps_json = json.loads(steps_json)
        except Exception:
            logger.debug("解析原用例steps_json失败", exc_info=True)
    sections.append(f"### 原步骤: {json.dumps(steps_json, ensure_ascii=False)}")
    sections.append(f"### 原预期结果: {original.get('expected_result', '')}")
    sections.append("")
    sections.append("## 变更指引")
    if task_context.get("modification_hint"):
        sections.append(f"- 修改原因: {task_context['modification_hint']}")
    if task_context.get("need_locator_fix"):
        sections.append("- 注意: UI元素定位器已变更，请使用新的UI元素描述")
    sections.append("")
    sections.append(
        "请在原有用例基础上修改，保持未变更部分不变，仅更新与变更指引相关的内容。"
    )
    sections.append("输出完整的修改后用例（而非diff），包含所有字段。")


def _render_create_context(
    extra_context: Dict[str, Any], sections: List[str],
) -> None:
    """渲染 task_type="create" 创建模式：注入历史用例避免重复。"""
    history = extra_context.get("history_cases")
    if not history:
        return
    sections.append("## 项目已有用例（避免重复，以下为已有用例的标题和内容摘要）")
    for hc in history[:20]:
        sections.append(f"- [{hc.get('module', '')}] {hc.get('title', '')}")
        if hc.get("summary"):
            sections.append(f"  摘要: {hc['summary']}")
    sections.append("")
    sections.append("请确保新生成的用例不与以上已有用例重复：")
    sections.append(
        "1. 若新用例与已有用例覆盖同一场景但UI变更，生成新用例并标注变更点"
    )
    sections.append("2. 若新用例是全新的测试场景，正常生成")
    sections.append(
        "3. 若已有用例已完整覆盖，可在case_category中标注existing_covered"
        "并说明对应的已有用例"
    )


def _render_locator_fix_context(
    task_context: Dict[str, Any], sections: List[str],
) -> None:
    """渲染 task_type="locator_fix" 定位器修复模式：注入原用例 + 修复指引。"""
    original = task_context.get("original_case")
    if not original:
        return
    sections.append("## 需要修复定位器的原有用例")
    sections.append(f"### 原用例标题: {original.get('title', '')}")
    sections.append("")
    sections.append("## 定位器修复指引")
    sections.append(
        "该用例的UI元素定位器可能已因UI变更而失效，请基于新的UI描述修复定位器信息。"
    )
    sections.append("修复要求：")
    sections.append("1. 使用新UI描述中的元素名称和定位策略")
    sections.append("2. 保持用例的业务逻辑和预期结果不变")
    sections.append(
        "3. 在steps中更新所有涉及UI交互的action描述，使用新的元素名称"
    )
    if task_context.get("locator_hint"):
        sections.append(f"4. 额外指引: {task_context['locator_hint']}")


def _render_migrate_context(
    task_context: Dict[str, Any], sections: List[str],
) -> None:
    """渲染 task_type="migrate" 跨设备迁移模式：注入源用例 + 设备差异规则。"""
    source_case = task_context.get("source_case")
    if not source_case:
        return
    from app.services.prompt_builder.migration_prompt import build_migration_prompt
    source_device = task_context.get("source_device", "tablet")
    target_device = task_context.get("target_device", "phone")
    target_ui_specs = task_context.get("target_ui_specs", "")
    migration_prompt = build_migration_prompt(
        source_case=source_case,
        source_device=source_device,
        target_device=target_device,
        target_ui_specs=target_ui_specs,
    )
    sections.append(migration_prompt)


def _append_extra_context_sections(
    prompt: str,
    extra_context: Optional[Dict[str, Any]] = None,
) -> str:
    """将 extra_context 渲染为附加段落并拼接到 prompt 之后。

    Args:
        prompt: 基础 Prompt 文本。
        extra_context: 额外上下文字典，可包含 quality_feedback / quality_signals /
            task_type / task_context / history_cases 等键。

    Returns:
        拼接后的完整 Prompt 字符串；extra_context 为空时原样返回。
    """
    if not extra_context:
        return prompt

    task_type = extra_context.get("task_type")
    task_context = extra_context.get("task_context", {})
    sections: List[str] = [prompt]

    _render_quality_feedback(extra_context, sections)
    _render_quality_signals(extra_context, sections)

    if task_type == "modify":
        _render_modify_context(task_context, sections)
    elif task_type == "create":
        _render_create_context(extra_context, sections)
    elif task_type == "locator_fix":
        _render_locator_fix_context(task_context, sections)
    elif task_type == "migrate":
        _render_migrate_context(task_context, sections)

    return "\n\n".join(sections)


__all__ = ["_append_extra_context_sections"]
