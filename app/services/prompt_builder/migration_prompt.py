"""跨设备用例迁移Prompt构建器。"""
import json
from typing import Dict, Any


DEVICE_DIFF_RULES = {
    "tablet_to_phone": [
        "1. 导航方式：侧边栏/多Tab → 底部Tab栏/抽屉菜单",
        "2. 页面布局：多栏并排 → 单栏滚动，可能拆分为多页",
        "3. 弹窗形式：居中对话框 → 底部Sheet/全屏页面",
        "4. 操作方式：大触控区点击 → 手势操作（滑动/长按）",
        "5. 输入方式：外接键盘 → 软键盘（注意键盘遮挡）",
        "6. 列表展示：表格/Grid → 单列列表/卡片",
        "7. 分屏功能：支持 → 不支持",
        "8. 前置条件：设备相关描述需同步改写（如'在平板端已登录'→'在手机端已登录'）",
    ],
    "phone_to_tablet": [
        "1. 导航方式：底部Tab栏/抽屉菜单 → 侧边栏/多Tab",
        "2. 页面布局：单栏滚动 → 多栏并排",
        "3. 弹窗形式：底部Sheet/全屏页面 → 居中对话框",
        "4. 操作方式：手势操作（滑动/长按） → 大触控区点击",
        "5. 输入方式：软键盘 → 外接键盘",
        "6. 列表展示：单列列表/卡片 → 表格/Grid",
        "7. 分屏功能：不支持 → 支持",
        "8. 前置条件：设备相关描述需同步改写",
    ],
}


def _build_migration_prompt(
    source_case: Dict[str, Any],
    source_device: str = "tablet",
    target_device: str = "phone",
    target_ui_specs: str = "",
) -> str:
    diff_key = f"{source_device}_to_{target_device}"
    diff_rules = DEVICE_DIFF_RULES.get(diff_key, [])
    steps_json = source_case.get("steps_json", [])
    if isinstance(steps_json, str):
        try:
            steps_json = json.loads(steps_json)
        except (json.JSONDecodeError, TypeError):
            steps_json = []
    steps_text = json.dumps(steps_json, ensure_ascii=False, indent=2) if steps_json else "无"
    ui_section = ""
    if target_ui_specs:
        ui_section = f"\n## 目标设备UI信息\n{target_ui_specs}\n"
    prompt = f"""你是一个专业的跨设备测试用例迁移专家。现在需要将一条{source_device}端测试用例迁移到{target_device}端。

## 源用例信息
- 标题：{source_case.get('title', '')}
- 前置条件：{source_case.get('precondition', '')}
- 步骤：{steps_text}
- 预期结果：{source_case.get('expected_result', '')}
- 优先级：{source_case.get('priority', 2)}
- 用例类型：{source_case.get('case_type', 'ui_automation')}

## 设备差异规则
{source_device}→{target_device}的典型差异：
{chr(10).join(diff_rules) if diff_rules else '无预设差异规则，请根据通用设备差异判断'}
{ui_section}
## 迁移要求
1. 首先判断迁移类型：
   - cloned：仅限API/接口测试用例，不涉及任何UI交互
   - adapted：业务逻辑不变，操作步骤/前置条件/预期结果需因设备差异调整
   - split：一条{source_device}用例需拆为多条{target_device}用例（如{source_device}同屏多区域→{target_device}分页跳转）
   - new：{target_device}独有的新场景（如手势操作、软键盘交互）
   - deprecated：{source_device}独有功能，{target_device}端不存在

2. 对于adapted/split类型，必须审查并改写以下所有字段：
   a. 前置条件（precondition）：
      - 设备相关描述必须改写（如"在{source_device}端"→"在{target_device}端"）
      - 设备特有条件必须删除或替换
   b. 操作步骤（steps）：
      - 逐步骤标注变更：unchanged/modified/added/removed
      - 每个modified步骤必须标注调整原因
   c. 预期结果（expected_result）：
      - 设备相关描述必须同步改写
      - 弹窗/面板描述必须调整
   d. 优先级（priority）：
      - 评估{target_device}端交互复杂度是否变化
      - 若操作更复杂或风险更高，建议提升优先级

3. 对于split类型，输出多条目标用例：
   - 每条用例独立完整（标题、前置条件、步骤、预期结果）
   - 标注拆分原因和各子用例的覆盖范围

4. 同时输出{target_device}端独有场景发现（new_scenarios）：
   - 基于该用例涉及的功能，推断{target_device}端需要额外覆盖的场景

5. 输出JSON格式：
```json
{{
  "migration_type": "cloned|adapted|split|new|deprecated",
  "confidence": 0.0-1.0,
  "adapted_cases": [
    {{
      "title": "...",
      "precondition": "...",
      "precondition_changes": [
        {{"original": "原前置条件片段", "adapted": "改写后片段", "reason": "改写原因"}}
      ],
      "steps": [
        {{"step": 1, "action": "...", "expected_result": "...", "action_type": "click"}}
      ],
      "expected_result": "...",
      "expected_result_changes": [
        {{"original": "原预期结果片段", "adapted": "改写后片段", "reason": "改写原因"}}
      ],
      "priority": 2,
      "priority_change": {{"original": 2, "adapted": 1, "reason": "手机端操作更复杂"}}
    }}
  ],
  "step_changes": [
    {{
      "case_index": 0,
      "step_index": 0,
      "change_type": "unchanged|modified|added|removed",
      "reason": "变更原因",
      "original_step": "原步骤内容",
      "new_step": "新步骤内容"
    }}
  ],
  "split_reason": "拆分原因（仅split类型）",
  "new_scenarios": [
    "{target_device}端需要额外覆盖的场景描述"
  ],
  "deprecated_scenarios": [
    "{source_device}端独有、{target_device}端不存在的场景描述"
  ]
}}
```

请严格按照以上JSON格式输出，不要添加任何其他文字说明。"""
    return prompt


def build_migration_prompt(
    source_case: Dict[str, Any],
    source_device: str = "tablet",
    target_device: str = "phone",
    target_ui_specs: str = "",
) -> str:
    return _build_migration_prompt(
        source_case=source_case,
        source_device=source_device,
        target_device=target_device,
        target_ui_specs=target_ui_specs,
    )
