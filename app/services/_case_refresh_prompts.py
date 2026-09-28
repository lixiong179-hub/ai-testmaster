"""用例保鲜服务的 AI 提示词模板与响应解析工具。

从 case_refresh_service.py 拆出，便于独立测试与模板复用。
"""
import json
import re
from typing import Any, Dict

from app.models.requirement import Requirement
from app.models.test_case import TestCase


REFRESH_PROMPT_TEMPLATE = """你是一名测试用例维护专家。请依据最新需求评估以下历史用例。

[最新需求]
{requirement_description}

[历史用例]
标题：{case_title}
步骤：{case_steps}
预期结果：{case_expected_result}

[任务]
1. 判断该用例在当前需求下是否仍然有效。
2. 若有效，输出建议更新内容和差异说明。
3. 若无效，输出建议废弃原因。
4. 不要引入需求中未提及的规则或UI元素。

请严格按以下JSON格式输出（不要添加markdown代码块标记）：
{{
  "is_valid": true或false,
  "suggested_title": "建议标题（若有效）",
  "suggested_steps": [步骤数组（若有效）],
  "suggested_expected_result": "建议预期结果（若有效）",
  "diff_description": "差异说明",
  "deprecation_reason": "废弃原因（若无效，否则为空字符串）"
}}"""


def build_refresh_prompt(case: TestCase, requirement: Requirement) -> str:
    """构建保鲜建议 AI 提示词。"""
    steps_text = ""
    if case.steps_json:
        if isinstance(case.steps_json, list):
            steps_text = json.dumps(case.steps_json, ensure_ascii=False, indent=2)
        else:
            steps_text = str(case.steps_json)
    # 模板为模块级常量，f-string 无法延迟求值，按项目规则例外使用 .format()
    return REFRESH_PROMPT_TEMPLATE.format(
        requirement_description=requirement.description or "",
        case_title=case.title or "",
        case_steps=steps_text,
        case_expected_result=case.expected_result or "",
    )


def parse_refresh_response(response_text: str) -> Dict[str, Any]:
    """解析 AI 保鲜响应文本为字典，失败时返回兜底结果。"""
    text = response_text.strip()
    code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
    if code_block_match:
        text = code_block_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
    return {"is_valid": True, "diff_description": "AI响应解析失败，需人工判断"}


__all__ = [
    "REFRESH_PROMPT_TEMPLATE",
    "build_refresh_prompt",
    "parse_refresh_response",
]
