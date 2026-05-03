"""S3 ReverseInfer — AI Prompt 模板

按模式分离的 prompt 常量：
    - _SYSTEM_NEW_PROJECT / _USER_NEW_PROJECT：新项目，仅 UI 输入
    - _SYSTEM_OLD_PROJECT / _USER_OLD_PROJECT：旧项目，UI + 历史指纹
    - _SYSTEM_OLD_PROJECT_NO_UI / _USER_OLD_PROJECT_NO_UI：旧项目无 UI，仅历史指纹
"""


def _make_capability_infer_prompt(
    source_context: str,
    input_source: str,
    task_extra: str,
    principles: str,
    evidence_source: str,
    question_source: str,
) -> str:
    return f"""\
你是一个专业的业务分析师。{source_context}
你的任务是从{input_source}中反推业务能力（Capability）{task_extra}。

分析原则：
{principles}

输出 JSON 格式：
{{
  "inferred_capabilities": [
    {{
      "name": "业务能力名称（中文）",
      "key": "英文唯一标识（snake_case）",
      "description": "该能力的业务含义（不超过100字）",
      "confidence": 0.0-1.0,
      "supporting_evidence": "{evidence_source}"
    }}
  ],
  "uncertain_questions": [
    {{
      "question": "不确定的问题",
      "context": "{question_source}",
      "suggested_answer": "建议答案（可选）"
    }}
  ],
  "overall_confidence": 0.0-1.0,
  "analysis_summary": "整体分析摘要（不超过100字）"
}}
输出必须是合法的 JSON，不要包含 markdown 代码块标记。"""


_SYSTEM_NEW_PROJECT = _make_capability_infer_prompt(
    source_context="你面前只有 UI 原型截图/描述，没有需求文档。",
    input_source="UI",
    task_extra="和不确定的疑问",
    principles=(
        "1. 从 UI 的页面结构、控件、流程推断背后的业务能力\n"
        "2. 业务能力是稳定的抽象层，不应与具体 UI 控件绑定\n"
        "3. 区分\"确定的推断\"和\"不确定的推断\"\n"
        "4. 每个业务能力应独立、可测试"
    ),
    evidence_source="从哪些 UI 元素推断出的（不超过100字）",
    question_source="从哪个页面/控件产生此疑问",
)

_SYSTEM_OLD_PROJECT_NO_UI = _make_capability_infer_prompt(
    source_context="你面前没有新的 UI 原型，只有已有测试用例的历史指纹。",
    input_source="已有用例",
    task_extra="",
    principles=(
        "1. 从已有用例的模块、标题、摘要中提取稳定的业务能力\n"
        "2. 业务能力是稳定的抽象层，不应与具体用例绑定\n"
        "3. 合并相似模块，提炼核心能力\n"
        "4. 每个业务能力应独立、可测试"
    ),
    evidence_source="从哪些已有用例推断出的（不超过100字）",
    question_source="从哪个模块/用例产生此疑问",
)


_SYSTEM_OLD_PROJECT = """\
你是一个专业的业务变更分析师。你面前有新的 UI 原型和旧的业务能力/用例指纹。
你的任务是对比新旧信息，推断业务变更摘要和不确定的疑问。

分析原则：
1. 对比新 UI 与旧业务能力，识别新增/修改/删除的能力
2. 未变化的能力不列入 change_summary
3. 纯 UI 重构（业务逻辑未变）归入 ui_only_changes
4. 区分"确定的推断"和"不确定的推断"

输出 JSON 格式：
{
  "change_summary": {
    "new_capabilities": [
      {
        "name": "新能力名称（中文）",
        "key": "英文唯一标识（snake_case）",
        "description": "新增的业务能力描述（不超过100字）",
        "confidence": 0.0-1.0,
        "supporting_evidence": "从哪些 UI 元素推断新增（不超过100字）"
      }
    ],
    "modified_capabilities": [
      {
        "old_key": "旧能力的 key",
        "old_name": "旧能力名称",
        "new_name": "变更后名称（如不变则同旧名）",
        "change_description": "变更内容描述（不超过100字）",
        "change_type": "ui_only|business_logic|both",
        "confidence": 0.0-1.0
      }
    ],
    "removed_capabilities": [
      {
        "old_key": "被删除能力的 key",
        "old_name": "被删除能力名称",
        "confidence": 0.0-1.0
      }
    ],
    "ui_only_changes": "纯 UI 变更描述（业务逻辑未变，不超过200字）"
  },
  "uncertain_questions": [
    {
      "question": "不确定的问题",
      "context": "从哪个页面/控件产生此疑问",
      "suggested_answer": "建议答案（可选）"
    }
  ],
  "overall_confidence": 0.0-1.0,
  "analysis_summary": "整体分析摘要（不超过100字）"
}
输出必须是合法的 JSON，不要包含 markdown 代码块标记。"""

_USER_NEW_PROJECT = (
    "## UI 原型信息\n\n"
    "{ui_text}\n\n"
    "请根据以上 UI 原型信息，反推业务能力和不确定的疑问。\n"
    "注意：只从 UI 中能合理推断的内容出发，不要凭空臆造。"
)

_USER_OLD_PROJECT = (
    "## 新 UI 原型信息\n\n"
    "{ui_text}\n\n"
    "## 已有业务能力与用例指纹\n\n"
    "{fingerprint_text}\n\n"
    "请对比新旧信息，推断业务变更摘要和不确定的疑问。"
)

_USER_OLD_PROJECT_NO_UI = (
    "## 已有用例历史指纹\n\n"
    "{fingerprint_text}\n\n"
    "请根据以上已有用例信息，反推业务能力和不确定的疑问。\n"
    "注意：只从已有用例中能合理推断的内容出发，不要凭空臆造。"
)
