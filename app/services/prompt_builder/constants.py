"""UI 解析 Prompt 常量 - 单图解析、多图流转、批量摘要、OCR 文本结构化。

原 ui_spec_prompts.py，合并到统一 prompt_builder 包中。
"""

SINGLE_IMAGE_PROMPT = """你是一个专业的UI/UX分析师。请仔细分析这张UI截图，并严格按照以下JSON格式输出结构化数据。

重要要求：
1. 只输出纯JSON，不要用```json...```包裹，不要输出任何解释性文字。
2. 字符串值如无内容请用""，数组为空请用[]，无法确定的字段用null。
3. 对于无法确定或存在歧义的内容，请在warnings数组中说明原因。
4. 充分利用你的视觉能力：描述颜色、图标、字体大小相对关系、间距、对齐方式等。
5. state字段必须如实反映元素当前状态：若按钮置灰则填"disabled"，若输入框标红则填"error"，若Tab被选中则填"selected"，若开关打开则填"active"；仅当元素完全正常且无特殊状态时才填"normal"。
6. description字段必须包含元素的视觉特征和交互行为描述：形状（圆角/直角）、边框（颜色/粗细）、背景色、阴影、占位文本、点击后的预期行为等，禁止留空。
7. semantic_hint字段必须提供元素的语义化描述：用简短短语说明该元素在业务流程中的作用（如"提交登录表单"、"切换到注册页"、"输入验证码"），与label字段的区别是semantic_hint描述功能意图而非显示文本。

输出格式：
{
  "screen_name": "从页面内容推断的页面名称",
  "purpose": "页面的主要功能和目的",
  "regions": {
    "header": {"exists": true, "height_approx": "low|medium|high", "content": "顶部区域内容描述，包括颜色、背景等"},
    "content": {"scrollable": true/false, "layout_type": "list|grid|form|mixed", "description": "内容区域描述，包括背景色、间距等"},
    "footer": {"exists": false, "content": ""},
    "overlay": {"exists": false, "type": "dialog|drawer|popup", "description": ""}
  },
  "elements": [
    {
      "type": "button|input|text|icon|navigation|list_item|checkbox|radio|switch|slider|form|dropdown|image|video|container",
      "label": "可见的标签文字",
      "semantic_hint": "语义化描述该元素的业务功能意图，如：提交登录表单、切换到注册页、输入手机号",
      "position": "top_left|top_center|top_right|center|bottom_left|bottom_center|bottom_right|full_width",
      "state": "normal|disabled|selected|active|error|hidden",
      "interactive": true/false,
      "color": "前景色或背景色描述，如 '蓝色文字'、'白色背景'",
      "font_size": "small|medium|large 或相对描述（如 '比正文大'）",
      "icon": "图标描述（如 '左箭头'、'搜索图标'），无图标则为 null",
      "description": "详细描述元素的视觉特征和交互行为：形状（圆角/直角）、边框（颜色/粗细）、背景色、阴影、占位文本、点击后预期行为等"
    }
  ],
  "navigation": {
    "back_button": {"visible": true/false, "position": "top_left|...", "label": "返回|←|... "},
    "tab_bar": {"visible": true/false, "items": ["首页", "我的"], "active_index": 0},
    "swipe_enabled": true/false,
    "nested_navigation": "其他导航元素描述或null"
  },
  "layout_constraints": [
    {
      "type": "alignment/spacing/sizing/color_contrast/fixed_position/overlay/safe_area",
      "description": "布局约束的具体描述，例如 '登录按钮水平居中，与输入框间距16dp'",
      "priority": "high/medium/low",
      "check_point": "可验证的检查点描述"
    }
  ],
  "flows": {
    "expected_next_screens": ["根据UI内容推断的可能跳转页面名称"],
    "trigger_actions": ["触发跳转的动作，如：点击提交按钮、选择列表项"]
  },
  "ui_adaptation_checks": [
    {
      "check_type": "element_visibility/text_overflow/layout_break/icon_size/button_tap_area/color_blind",
      "description": "UI适配检查项描述",
      "severity": "critical/major/minor"
    }
  ],
  "visual_style": {
    "background_color": "页面主背景色",
    "primary_color": "主题色（如按钮、链接颜色）",
    "border_radius": "全局圆角风格（无/小/中/大）",
    "shadow_usage": "是否有阴影效果"
  },
  "warnings": ["任何不确定或需要人工确认的内容"]
}

示例输出（仅供参考，请勿照抄）：
{
  "screen_name": "登录页",
  "purpose": "用户输入账号密码进行登录",
  "regions": {
    "header": {"exists": true, "height_approx": "low", "content": "白色背景，左侧返回箭头，中间标题'登录'"},
    "content": {"scrollable": false, "layout_type": "form", "description": "浅灰色背景，包含手机号输入框、密码输入框、登录按钮"},
    "footer": {"exists": false, "content": ""},
    "overlay": {"exists": false}
  },
  "elements": [
    {
      "type": "icon",
      "label": "",
      "semantic_hint": "返回上一页",
      "position": "top_left",
      "state": "normal",
      "interactive": true,
      "color": "灰色",
      "font_size": null,
      "icon": "左箭头",
      "description": "左上角箭头图标，灰色，点击后返回上一页"
    },
    {
      "type": "input",
      "label": "手机号",
      "semantic_hint": "输入注册手机号",
      "position": "center",
      "state": "normal",
      "interactive": true,
      "color": "#333333 文字",
      "font_size": "medium",
      "icon": "手机图标",
      "description": "带手机图标前缀，占位文本'请输入手机号'，底部灰色分割线，输入时文字为深色"
    },
    {
      "type": "input",
      "label": "密码",
      "semantic_hint": "输入登录密码",
      "position": "center",
      "state": "normal",
      "interactive": true,
      "color": "#333333 文字",
      "font_size": "medium",
      "icon": "锁图标",
      "description": "带锁图标前缀，占位文本'请输入密码'，右侧有眼睛切换显示/隐藏，底部灰色分割线"
    },
    {
      "type": "button",
      "label": "登录",
      "semantic_hint": "提交登录表单",
      "position": "center",
      "state": "disabled",
      "interactive": true,
      "color": "白色文字，灰色背景（因未填写表单而置灰）",
      "font_size": "large",
      "icon": null,
      "description": "圆角按钮（8px圆角），全宽，内边距12px，当前因手机号和密码为空而处于置灰不可点击状态，填写后变为蓝色可点击"
    },
    {
      "type": "text",
      "label": "忘记密码？",
      "semantic_hint": "跳转到密码重置页",
      "position": "center",
      "state": "normal",
      "interactive": true,
      "color": "#1890ff 蓝色",
      "font_size": "small",
      "icon": null,
      "description": "右对齐蓝色链接文字，点击后跳转到找回密码页面"
    }
  ],
  "navigation": {
    "back_button": {"visible": true, "position": "top_left", "label": "←"},
    "tab_bar": {"visible": false},
    "swipe_enabled": false,
    "nested_navigation": null
  },
  "layout_constraints": [
    {
      "type": "alignment",
      "description": "所有表单控件水平居中，宽度为屏幕宽度的90%",
      "priority": "high",
      "check_point": "输入框和按钮水平居中对齐"
    },
    {
      "type": "spacing",
      "description": "输入框之间间距16px，按钮与上一个输入框间距24px",
      "priority": "medium",
      "check_point": "垂直间距符合设计规范"
    }
  ],
  "flows": {
    "expected_next_screens": ["首页", "注册页", "找回密码页"],
    "trigger_actions": ["点击登录按钮", "点击注册链接", "点击忘记密码"]
  },
  "ui_adaptation_checks": [
    {
      "check_type": "element_visibility",
      "description": "在窄屏幕（宽度<320px）下，输入框和按钮不应被截断",
      "severity": "major"
    },
    {
      "check_type": "color_contrast",
      "description": "蓝色按钮上的白色文字对比度足够",
      "severity": "minor"
    }
  ],
  "visual_style": {
    "background_color": "#F5F5F5",
    "primary_color": "#1890ff",
    "border_radius": "中等圆角（8px）",
    "shadow_usage": "按钮无阴影，卡片有轻微阴影"
  },
  "warnings": []
}

请开始分析这张UI截图："""

MULTI_IMAGE_FLOW_PROMPT = """你是一个专业的业务流程分析师。请根据以下UI截图序列，分析页面之间的流转关系。

截图序列（共{count}张）：

{image_descriptions}

请严格输出JSON格式：
{{
  "entry_screen": "入口页面名称",
  "end_screens": ["可能的结束页面列表"],
  "page_flows": [
    {{
      "from_screen": "来源页面",
      "to_screen": "目标页面",
      "trigger_action": "触发动作",
      "condition": "触发条件（如有）"
    }}
  ],
  "navigation_map": {{
    "页面A": {{"can_go_to": ["页面B", "页面C"], "back_to": ["页面D"]}}
  }},
  "key_user_paths": [
    {{"path_name": "主要用户路径", "steps": ["页面1", "页面2", "页面3"]}}
  ],
  "warnings": ["任何不确定或缺失的流转信息"]
}}

请开始分析："""

BATCH_SUMMARY_PROMPT = """你是一个测试用例生成专家。请根据以下已解析的UI屏幕规格，生成针对UI适配问题的专项测试用例检查点。

UI屏幕规格列表：
{ui_specs}

要求：
1. 每个屏幕的 ui_adaptation_test_points 应基于其 layout_constraints 生成具体的检查点。
2. 如果 layout_constraints 中存在 alignment、spacing、sizing 等约束，必须转化为对应的适配测试点。
3. 输出格式严格如下：

[
  {
    "screen_id": "屏幕ID",
    "ui_adaptation_test_points": [
      {
        "check_type": "layout/element_visibility/text_overflow/color_contrast/responsive_design/safe_area",
        "description": "检查项描述",
        "test_method": "测试方法（如：改变窗口宽度、使用大字体）",
        "expected_result": "预期结果",
        "severity": "critical/major/minor"
      }
    ]
  }
]

请开始补充："""

TEXT_STRUCTURE_PROMPT = """你是一个专业的UI/UX分析师。以下是从UI截图中通过OCR提取的文字内容，每行前面的`[位置:数值]`表示该文本在垂直方向上的相对坐标（数值越小越靠近屏幕顶部）。请根据这些文字和位置信息，推断页面结构和元素，严格按照以下JSON格式输出。

{
  "screen_name": "从页面内容推断的页面名称",
  "purpose": "页面的主要功能和目的",
  "elements": [
    {
      "type": "button|input|text|link|dropdown|checkbox|switch|icon|container|list_item|radio|slider|form|image|video",
      "label": "可见的标签文字",
      "semantic_hint": "语义化描述该元素的业务功能意图，如：提交登录表单、切换到注册页、输入手机号",
      "position": "top|center|bottom（根据位置数值判断）",
      "state": "normal|disabled|selected|active|error|hidden（根据上下文推断，如按钮通常为normal，已选中的Tab为selected）",
      "interactive": true/false,
      "description": "详细描述元素的视觉特征和交互行为：根据文字内容和常见UI模式推断形状、边框、背景色、占位文本、点击后预期行为等"
    }
  ],
  "navigation": {
    "back_button": "返回按钮文字（如有）",
    "tab_bar": "Tab栏内容（如有）",
    "swipe_enabled": true/false
  },
  "flows": {
    "expected_next_screens": ["根据文字内容推断的可能跳转页面"],
    "trigger_actions": ["触发跳转的动作"]
  },
  "warnings": ["任何无法确定或缺失的信息"]
}

注意事项：
1. 如果文字内容无法确定类型，type 使用 "text"。
2. 根据常见的 UI 模式推断：例如"登录"、"注册"通常是按钮，"用户名"、"密码"通常是输入框标签。
3. 位置字段根据提供的数值粗略判断：top（前20%）、center（20%-80%）、bottom（80%以后）。
4. state字段必须如实推断：若按钮文字暗示不可操作（如"确认"但缺少必要条件）则填"disabled"，若Tab文字是当前激活项则填"selected"，否则填"normal"。
5. description字段禁止留空，必须根据文字内容和常见UI模式推断元素的视觉特征和交互行为。
6. semantic_hint字段必须提供元素的业务功能意图，与label字段的区别是semantic_hint描述功能意图而非显示文本。
7. 仅输出纯JSON，不要输出解释。

以下是OCR提取的文字（带位置标记）：

{ocr_text}

请开始分析："""
