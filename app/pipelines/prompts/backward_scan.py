"""BackwardScan Prompt 模板

反向扫描 prompt，将历史用例与变更信号对比，输出每条用例的 verdict。

5 种 verdict（对应 plan §6 合并矩阵）：
    - VALID: 用例仍然有效，无需修改
    - LOCATOR_ONLY: 仅定位器/元素引用失效，业务逻辑仍有效
    - NEEDS_MODIFY: 业务逻辑需更新（字段变更、流程变更等）
    - DEPRECATED: 用例已完全过时，应弃用
    - UNCERTAIN: AI 无法确定，需人工评审

模板支持模块切片占位符 {module_label}。
"""
import json
from typing import Any, Dict, List, Optional

BACKWARD_SCAN_SYSTEM_PROMPT = (
    "你是一个专业的测试用例评审专家。你的任务是对比现有测试用例与最新的需求变更，"
    "判断每条用例是否仍然有效。\n\n"
    "对于每条用例，你需要输出以下 JSON 结构：\n"
    "- case_id: 用例 ID（必须与输入一致）\n"
    "- verdict: 判定结果，必须是以下之一：\n"
    "  - VALID: 用例仍然有效，无需修改\n"
    "  - LOCATOR_ONLY: 仅 UI 定位器/元素引用失效，业务逻辑仍有效\n"
    "  - NEEDS_MODIFY: 业务逻辑需更新（字段变更、流程变更、断言需修改等）\n"
    "  - DEPRECATED: 用例已完全过时，应弃用\n"
    "  - UNCERTAIN: 无法确定，需人工评审\n"
    "- confidence: 置信度，0.0 到 1.0 之间的浮点数\n"
    "- hint: 简短说明判定理由（不超过100字）\n\n"
    "判定规则：\n"
    "1. 如果变更不影响该用例的任何步骤和断言 → VALID\n"
    "2. 如果仅影响 UI 元素定位器（如按钮 ID、选择器变更）→ LOCATOR_ONLY\n"
    "3. 如果业务逻辑步骤或断言需要更新 → NEEDS_MODIFY\n"
    "4. 如果功能已被移除或完全重构，用例无法复用 → DEPRECATED\n"
    "5. 如果信息不足无法判断 → UNCERTAIN\n\n"
    "请以 JSON 数组格式返回，每个元素包含 case_id、verdict、confidence、hint 四个字段。"
)

BACKWARD_SCAN_USER_TEMPLATE = (
    "## 变更信号\n\n"
    "{change_signals}\n\n"
    "## 现有测试用例（模块: {module_label}）\n\n"
    "{cases_text}\n\n"
    "请逐一评审以上用例，输出 JSON 数组。"
)


def build_backward_scan_prompt(
    change_signals: str,
    cases: List[Dict[str, Any]],
    module_label: Optional[str] = None,
) -> str:
    """构建反向扫描用户 prompt。

    Args:
        change_signals: 变更信号文本（PRD diff、接口变更等）。
        cases: 待评审用例列表，每条包含 case_id/title/module/summary 等字段。
        module_label: 模块标签，用于模块切片场景。

    Returns:
        完整的用户 prompt 字符串。
    """
    label = module_label or "全部"
    cases_text = _format_cases_for_prompt(cases)
    return BACKWARD_SCAN_USER_TEMPLATE.format(
        change_signals=change_signals,
        module_label=label,
        cases_text=cases_text,
    )


def _format_cases_for_prompt(cases: List[Dict[str, Any]]) -> str:
    """将用例列表格式化为 prompt 中的文本。

    Args:
        cases: 用例指纹列表。

    Returns:
        格式化后的文本。
    """
    if not cases:
        return "（无现有用例）"

    parts = []
    for case in cases:
        steps_text = _format_steps_json(case.get("steps_json"))
        lines = [
            f"### 用例 #{case.get('case_id', '?')}",
            f"- 标题: {case.get('title', '无标题')}",
            f"- 模块: {case.get('module', '未知')}",
            f"- 前置条件: {case.get('precondition', '无')}",
            f"- 摘要: {case.get('summary', '无')}",
            f"- 测试步骤: {steps_text}",
            f"- 优先级: {case.get('priority', 3)}",
            f"- 生命周期: {case.get('lifecycle_status', 'draft')}",
        ]
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _format_steps_json(steps_json: Any) -> str:
    """格式化 steps_json 字段为可读文本。"""
    if not steps_json:
        return "无"
    try:
        return json.dumps(steps_json, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(steps_json)
