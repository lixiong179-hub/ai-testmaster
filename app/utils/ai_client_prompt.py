"""
AI提示词构建模块

本模块负责构建发送给AI模型的提示词（Prompt），是AI客户端分层架构中的"提示层"。
核心职责是根据不同的数据源组合（需求文档、UI原型图、测试点）动态调整提示词权重和内容，
确保AI生成符合业务预期的测试用例。

核心函数：
    - build_weight_model: 根据数据源可用性构建权重描述，控制AI对各类输入的侧重程度
    - sanitize_input: 清洗用户输入，防御提示词注入攻击
    - build_ui_spec_description: 将单个UI规格对象格式化为可读文本
    - build_ui_specs_description: 批量格式化多个UI规格对象
    - build_project_env_info: 构建项目环境配置信息

设计要点：
    - 权重模型采用"需求文档优先"策略，防止AI被测试点或UI原型图带偏
    - 输入清洗同时处理中英文提示词注入模式
    - UI描述支持两种格式：详细模式（含位置信息）和简洁模式（按页面分组）

依赖：
    - loguru.logger: 日志记录
"""
import re
from typing import Dict, Any, Optional, List


def build_weight_model(has_ui: bool, has_requirement: bool, has_test_point: bool) -> tuple:
    """根据数据源可用性构建权重描述模型

    根据需求文档、UI原型图、测试点三者的可用组合，生成对应的权重描述文本。
    核心原则是"需求文档优先"——需求文档定义"做什么"，测试点定义"测哪些"，
    UI原型图定义"怎么验"，三者冲突时以需求文档为准。

    权重分配策略（共5种组合）：
    - 三者齐全: 需求60% + 测试点25% + UI15%，附带防偏离规则
    - 需求+UI: 需求75% + UI25%，AI自动推断测试点
    - 需求+测试点: 需求70% + 测试点30%，测试点不得超出需求边界
    - 仅需求: 需求100%，AI自检覆盖完整性
    - 无需求: 警告模式，仅基于可用信息生成

    Args:
        has_ui: 是否有UI原型图数据
        has_requirement: 是否有需求文档数据
        has_test_point: 是否有测试点数据

    Returns:
        tuple: (weight_desc, weight_example, weight_warning)
            - weight_desc: 权重描述文本，嵌入到Prompt中
            - weight_example: 权重示例文本，帮助AI理解权重用法
            - weight_warning: 警告文本，提示数据源缺失风险
    """
    if has_requirement and has_ui and has_test_point:
        weight_desc = """## 数据源权重（需求文档优先模型）
- **需求文档（60% — 核心依据）**：定义"做什么"。必须逐条覆盖需求中每个功能点，每项功能至少对应一个测试用例，用例步骤必须对应需求的每项功能操作
- **测试点（25% — 生成范围）**：定义"测哪些"。从需求的每个功能中选取对应的测试点，**不能超出需求文档定义的功能边界**
- **UI原型图（15% — 验收标准）**：定义"怎么验"。验证步骤中的操作对象与UI元素一致，预期结果验证UI显示"""
        weight_example = """### 三者结合示例：
- 需求文档说："用户可点击新增按钮添加成员"
- UI原型图有元素: button(name="新增", text="添加人")
- 测试点是："链接管理模块-新增'添加人'字段验证"
- → 正确用例: [1] 点击"添加人"按钮 → [1] 弹窗出现，标题为"新增成员"

### ⚠️ 防偏离规则：
- 如果UI原型图中有需求未提及的按钮/功能 → **不要为其生成用例**
- 如果测试点描述了需求中没有的功能 → **以需求为准忽略超出的部分**
- 生成前必须确认已覆盖需求的每一个主要功能点"""
        weight_warning = ""
    elif has_requirement and has_ui and not has_test_point:
        weight_desc = """## 数据源权重（需求文档优先模型）
- **需求文档（75% — 核心依据）**：必须逐条覆盖需求中每个功能点，用例步骤必须对应需求的每项功能操作
- **UI原型图（25% — 验收标准）**：验证步骤中的操作对象与UI元素一致

### ⚠️ 注意：没有测试点时，AI应从需求文档的每个功能点自动推断需要生成的测试用例"""
        weight_example = ""
        weight_warning = ""
    elif has_requirement and not has_ui and has_test_point:
        weight_desc = """## 数据源权重（需求文档优先模型）
- **需求文档（70% — 核心依据）**：必须逐条覆盖需求中每个功能点。**测试点的范围不能超出需求文档定义的功能边界**
- **测试点（30% — 生成范围）**：从需求的每个功能中选取对应的测试点

### ⚠️ 防偏离规则：
- 如果测试点描述了需求中没有的功能 → 以需求为准忽略超出的部分
- 每个测试点必须能追溯到需求文档中的某个具体功能描述"""
        weight_example = ""
        weight_warning = ""
    elif has_requirement and not has_ui and not has_test_point:
        weight_desc = """## 数据源（需求文档100% — 唯一依据）
- **需求文档是唯一的真理来源**
- 必须逐条覆盖需求中描述的**每一个功能点**，确保无遗漏
- 为需求的每个功能点生成对应的测试用例，用例步骤从需求描述的功能操作中提取
- AI在输出前必须自检：是否已覆盖所有主要功能点？"""
        weight_example = ""
        weight_warning = ""
    elif not has_requirement:
        available = []
        if has_ui:
            available.append("UI原型图")
        if has_test_point:
            available.append("测试点")
        names = "、".join(available) if available else "测试点"
        weight_desc = f"""## 数据源（仅{names}，100%）
- ⚠️ **缺少需求文档**：可能导致生成的测试用例偏离实际业务功能
- 请基于现有信息生成合理的测试用例，但需注意可能无法完全贴合实际需求"""
        weight_example = ""
        weight_warning = "- ⚠️ 警告：当前未提供需求文档，建议上传需求文档以确保用例贴合实际功能"
    else:
        weight_desc = "## 数据源权重\n- 基于可用信息生成测试用例"
        weight_example = ""
        weight_warning = ""
    return (weight_desc, weight_example, weight_warning)


def sanitize_input(text: str, max_length: int = 50000) -> str:
    """清洗用户输入，防御提示词注入攻击

    检测并移除常见的提示词注入模式，包括中英文两种语言的注入手法。
    同时限制输入长度，防止超长输入导致AI处理异常。

    防御的注入模式：
    - 英文: "ignore previous instructions", "you are now a...", "system:..."
    - 中文: "忽略指令/规则", "你现在是", "忘记指令/规则"

    Args:
        text: 待清洗的输入文本
        max_length: 最大允许长度，默认50000字符

    Returns:
        str: 清洗后的安全文本
    """
    if not text or not isinstance(text, str):
        return ""
    text = text[:max_length]
    injection_patterns = [
        (r'ignore\s+(previous|above|all)\s+instructions?', ''),
        (r'forget\s+(previous|above|all)\s+instructions?', ''),
        (r'disregard\s+(previous|above|all)\s+instructions?', ''),
        (r'you\s+are\s+now\s+a\s+', ''),
        (r'system\s*:\s*', ''),
        (r'忽略.*(指令|规则|约束)', ''),
        (r'你现在是', ''),
        (r'忘记.*(指令|规则)', ''),
    ]
    for pattern, replacement in injection_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text.strip()


def build_ui_spec_description(ui_spec: Dict[str, Any], screen_name: Optional[str] = None) -> str:
    """将单个UI规格对象格式化为可读文本描述

    根据UI规格字典中的各个字段，生成结构化的文本描述，供AI理解页面布局和元素。
    支持两种输出格式：
    - 详细模式（screen_name=None）：包含位置信息，使用【】标记各区域
    - 简洁模式（screen_name指定）：按页面分组，省略位置信息，使用===标记页面

    Args:
        ui_spec: UI规格字典，包含screen_name、purpose、regions、elements、navigation等字段
        screen_name: 页面名称，指定时使用简洁模式

    Returns:
        str: 格式化后的UI描述文本，无有效数据时返回提示信息
    """
    if not ui_spec:
        return "无UI原型图解析结果"
    parts = []
    if screen_name:
        parts.append(f"=== 页面：{screen_name} ===")
    if ui_spec.get('screen_name') and not screen_name:
        parts.append(f"【屏幕名称】{ui_spec['screen_name']}")
    if ui_spec.get('purpose'):
        parts.append(f"{'页面功能' if screen_name else '【页面功能】'}：{ui_spec['purpose']}")
    regions = ui_spec.get('regions', {})
    if regions:
        region_items = regions.items() if isinstance(regions, dict) else regions
        parts.append(f"\n{'页面区域' if screen_name else '【页面区域结构】'}：")
        for item in region_items:
            if isinstance(item, tuple):
                region_name, region_desc = item
            else:
                region_name = item.get('name', '')
                region_desc = item.get('description', '')
            if region_desc:
                parts.append(f"  - {region_name}: {region_desc}")
    elements = ui_spec.get('elements', [])
    if elements:
        max_elements = 30 if screen_name else 20
        parts.append(f"\n{'页面元素' if screen_name else '【页面元素】'}（共{len(elements)}个）：")
        for elem in elements[:max_elements]:
            elem_type = elem.get('type', '未知')
            label = elem.get('label', '') or elem.get('semantic', '') or elem.get('name', '')
            position = elem.get('position', '')
            state = elem.get('state', 'normal')
            interactive = elem.get('interactive', False)
            desc = elem.get('description', '')
            if screen_name:
                parts.append(f"  - [{elem_type}] {label} | 状态:{state} | 可交互:{interactive} | {desc}")
            else:
                parts.append(f"  - [{elem_type}] {label} | 位置:{position} | 状态:{state} | 可交互:{interactive} | {desc}")
    navigation = ui_spec.get('navigation', {})
    if navigation:
        parts.append(f"\n{'导航结构' if screen_name else '【导航结构】'}：")
        for nav_key, nav_val in navigation.items():
            if nav_val:
                parts.append(f"  - {nav_key}: {nav_val}")
    layout_checks = ui_spec.get('layout_constraints', [])
    if layout_checks:
        parts.append(f"\n{'布局约束' if screen_name else '【布局约束】'}（共{len(layout_checks)}项）：")
        for check in layout_checks[:10]:
            check_type = check.get('type', '')
            desc = check.get('description', '')
            priority = check.get('priority', '')
            if screen_name:
                parts.append(f"  - [{check_type}] {desc} (优先级:{priority})")
            else:
                parts.append(f"  - [{check_type}][{priority}] {desc}")
    ui_checks = ui_spec.get('ui_adaptation_checks', [])
    if ui_checks:
        parts.append(f"\n【UI适配检查点】（共{len(ui_checks)}项）：")
        for check in ui_checks[:10]:
            check_type = check.get('check_type', '')
            desc = check.get('description', '')
            severity = check.get('severity', '')
            parts.append(f"  - [{check_type}][{severity}] {desc}")
    flows = ui_spec.get('flows', {})
    if flows:
        next_screens = flows.get('expected_next_screens', [])
        if next_screens:
            if isinstance(next_screens, list):
                screen_names = [str(s) if isinstance(s, dict) else str(s) for s in next_screens]
                parts.append(f"\n{'预期跳转页面' if screen_name else '【预期跳转页面】'}：{', '.join(screen_names)}")
            else:
                parts.append(f"\n{'预期跳转页面' if screen_name else '【预期跳转页面】'}：{str(next_screens)}")
    return '\n'.join(parts) if parts else "无有效UI原型图解析结果"


def build_ui_specs_description(ui_specs: List[Dict[str, Any]]) -> str:
    """批量格式化多个UI规格对象

    遍历UI规格列表，对每个规格调用build_ui_spec_description生成描述，
    最后用双换行拼接所有页面的描述文本。

    Args:
        ui_specs: UI规格列表，每项包含screen_name和ui_spec字段

    Returns:
        str: 所有页面的拼接描述文本，无有效数据时返回提示信息
    """
    if not ui_specs:
        return "无UI原型图解析结果"
    all_parts = []
    for spec_item in ui_specs:
        s_name = spec_item.get('screen_name', '未命名页面')
        ui_spec = spec_item.get('ui_spec', {})
        if not ui_spec:
            continue
        description = build_ui_spec_description(ui_spec, screen_name=s_name)
        if description and description != "无有效UI原型图解析结果":
            all_parts.append(description)
    return '\n\n'.join(all_parts) if all_parts else "无有效UI原型图解析结果"


def build_project_env_info(project_config: Dict[str, Any]) -> str:
    """构建项目环境配置信息

    生成项目环境描述文本，包含项目名称、类型，以及关于前置条件的重要说明。
    关键设计：明确告知AI不要在测试步骤中包含登录操作和账号密码，
    因为这些由测试执行框架在运行时自动完成。

    Args:
        project_config: 项目配置字典，包含project_name、project_type等字段

    Returns:
        str: 格式化后的项目环境信息文本
    """
    if not project_config:
        return "## 项目环境配置：未配置（请使用通用测试数据）"
    project_name = project_config.get('project_name', '未知项目')
    project_type = project_config.get('project_type', 'web')

    login_hint = "账号已登录"
    if project_type == 'web':
        env_hint = "浏览器网络正常"
    else:
        env_hint = "设备网络正常"

    parts = [
        "## 项目环境配置",
        f"- **项目名称**：{project_name}",
        f"- **项目类型**：{project_type}",
        "",
        "**重要说明（关于前置条件）：**",
        f"前置条件必须包含\"{login_hint}\"和\"{env_hint}\"，有权限相关场景必须补充权限状态。",
        "你编写的测试用例只需关注**业务测试步骤本身**。",
        "- 不要在步骤中描述登录操作或包含任何账号密码",
        f"- precondition 字段必须包含登录状态和网络环境，格式如：{login_hint}、{env_hint}、[业务权限]",
        "- 测试数据中不包含具体URL或密码"
    ]
    return '\n'.join(parts)
