"""AI Prompt构建Mixin - 用例生成Prompt的构建与UI规格格式化。

本模块提供AI用例生成所需的Prompt构建逻辑，包括结构化Prompt组装
和UI规格数据格式化为Prompt友好文本。作为AIPromptMixin被AIMixin组合使用。

核心类:
    - AIPromptMixin: Prompt构建Mixin，提供_prompt相关方法

设计模式:
    作为Mixin模块，通过多继承组合到AIMixin中，提供:
    - _build_generation_prompt: 结构化Prompt构建
    - _format_ui_spec_for_prompt: UI规格格式化

依赖关系:
    - app.core.config: 配置管理
"""
import json
from typing import List, Dict, Any, Optional


class AIPromptMixin:
    """Prompt构建Mixin - 组装AI用例生成的结构化Prompt。

    职责:
        - 构建结构化的AI生成Prompt
        - 格式化UI规格数据为Prompt友好的文本描述

    设计意图:
        将Prompt构建逻辑从AI调用中抽离，便于:
        1. 独立调整Prompt模板和格式
        2. 支持不同AI模型的Prompt优化
        3. 统一管理UI信息的优先级和格式化
    """

    def _build_generation_prompt(
        self, requirement_content: str, ui_description: str,
        module: str, function: str, point: str, priority: int,
        ui_specs: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """构建AI用例生成的结构化Prompt。

        Prompt结构:
            1. 角色设定（资深测试工程师）
            2. 测试点信息（JSON格式，便于AI解析）
            3. 需求文档内容
            4. UI原型信息（规格优先，描述次之）
            5. 输出格式要求（JSON结构定义）
            6. 用例分类标签说明

        UI信息优先级:
            1. UI规格（解析后的结构化数据）-> 最详细
            2. UI描述（文本摘要）-> 次之
            3. 无UI信息 -> 标注"无UI原型图信息"

        Args:
            requirement_content: 需求文档内容。
            ui_description: UI描述文本。
            module: 模块名称。
            function: 功能名称（AI中间产物，不存库）。
            point: 测试点描述。
            priority: 优先级(1高/2中/3低)。
            ui_specs: UI规格列表，可选。

        Returns:
            完整的Prompt字符串。
        """
        # 格式化UI规格数据为Prompt文本
        ui_spec_text = ""
        if ui_specs:
            spec_parts = []
            for spec_item in ui_specs:
                screen_name = spec_item.get("screen_name", "未命名页面")
                spec = spec_item.get("ui_spec", {})
                if spec:
                    spec_parts.append(self._format_ui_spec_for_prompt(screen_name, spec))
            if spec_parts:
                ui_spec_text = "\n\n".join(spec_parts)

        # UI信息优先级：规格 > 描述 > 无
        ui_section = ""
        if ui_spec_text:
            ui_section = f"## UI原型图解析结果（验收标准，优先参考）：\n{ui_spec_text}"
        elif ui_description and ui_description.strip():
            ui_section = f"## UI原型图描述：\n{ui_description}"
        else:
            ui_section = "## UI原型图描述：[无UI原型图信息]"

        # 测试点信息序列化为JSON，便于AI准确解析
        test_point_json = json.dumps({
            "module": module, "function": function, "point": point, "priority": priority
        }, ensure_ascii=False)

        return f"""你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下信息为该测试点生成多条详细的、可执行的测试用例。

## 测试点信息（JSON格式）：
{test_point_json}

## 需求文档内容：
{requirement_content if requirement_content else '[无需求文档内容]'}

{ui_section}

## 覆盖要求（核心）：
你必须根据测试点的复杂度自行判断生成用例数量，最少3条，复杂测试点建议5-8条，且必须覆盖以下测试类型：
- 正向用例（Happy Path）：主流程正常操作，至少1条
- 边界值用例：输入/状态/数据的边界条件，至少1条
- 异常用例：错误输入、权限缺失、网络异常、容错等，至少1条
- 安全/性能用例（如涉及）：权限越权、并发、大数据量等，至少1条
如果测试点涉及安全或性能场景，也应补充对应用例。
每条用例必须覆盖不同的测试场景，禁止生成内容高度相似的重复用例。

## 输出要求：
1. 只输出JSON数组格式内容，不要添加任何其他文字
2. 数组中每个对象必须包含以下字段：
   - title: 用例标题（必须具体明确，格式：场景/条件+操作+验证重点，如"无网络时提交批改显示网络错误提示"，禁止"功能验证""界面测试"等模糊词，长度15-40字）
   - module: 模块名称
   - precondition: 前置条件（必须包含"账号已登录"和网络环境（Web端写"浏览器网络正常"，App端写"设备网络正常"），有权限场景补充权限状态；禁止仅写"账号已登录"或"APP运行正常"；前置条件只约束环境与权限，禁止依赖特定业务数据（如"列表有数据""数据较多"），确保用例任意环境可独立执行；如需特定数据才能测试（如编辑/删除场景），应在步骤中先创建数据，而非在前置中假设数据已存在；前置条件不能包含操作步骤或页面导航状态（如"已进入详情页""在列表页面"），导航到达目标页面必须作为步骤体现，确保用例可独立自动化执行）
   - test_data: 测试数据对象（可选，如有特定测试数据如输入值、文件类型等请填写，无则可省略该字段）
   - steps: 测试步骤数组，每个步骤必须包含：
     * step: 步骤序号（如"1"、"2"、"3"等）
     * description: 步骤描述（必须严谨可复现，禁止口语化如"连续拍摄多张照片"）
     * action: 具体操作
     * expected_result: 该步骤对应的预期结果（必须有具体判定标准，禁止"提交成功""正常显示"等模糊描述）
   - expected_result: 总体预期结果（必须包含交互校验点如弹窗文案、按钮跳转，禁止只写大致结果）
   - case_type: 用例类型（ui_automation/manual/api_automation/performance/security）
   - priority: 优先级（1高/2中/3低）
   - case_category: 用例分类标签（ui_automation=UI自动化测试, manual=手工测试, api_automation=接口自动化测试）
   - 自动化友好：步骤和预期必须支持自动化断言，预期需有可量化判定标准（如"无白屏""按钮置灰"），禁止"页面正常""功能正常"等无法断言的描述；步骤必须包含从登录后到达目标页面的完整导航操作，禁止将导航隐藏在前置条件中；弱网、异常条件等自动化无法实现的场景标注case_type为manual

## 正反用例对比（学习优秀写法，避免差劲写法）

【对比1-主流程】
❌差劲：测试拍照提交作文功能 | 前置：账号已登录，APP运行正常 | 步骤：进入页面→拍摄裁剪→点击提交 | 预期：页面正常→拍照正常→提交成功显示结果
问题：描述笼统无校验目标；前置条件缺网络/权限；步骤口语化；预期模糊无判定标准
✅优秀：联网+已授权，验证拍照裁剪提交完整流程 | 前置：账号已登录、相机权限允许、设备网络正常 | 步骤：1.点击进入中文作文批改模块 2.点击拍照拍摄作文并完成裁剪确认 3.点击去批改按钮提交图片 | 预期：1.模块页面加载正常功能入口完整 2.相机正常唤起图片裁剪完成并本地保存 3.提交请求正常发起成功跳转展示批改报告
优点：描述清晰目标明确；前置条件完整可稳定复现；步骤原子化；步骤与预期一一对应

【对比2-边界值】
❌差劲：测试拍照数量限制 | 前置：账号已登录 | 步骤：打开拍照页面→连续拍摄多张照片 | 预期：拍照页面正常→达到上限后禁止继续拍照
问题：未明确页数上限无量化标准；步骤模糊无固定复现路径；预期缺弹窗文案等校验点
✅优秀：验证最多3页拍摄限制，超出上限校验拦截提示 | 前置：账号已登录、相机权限开启、规则限制最多3页 | 步骤：1.进入作文拍照拍摄页面 2.依次拍摄并保存3张作文图片 3.再次点击拍摄按钮尝试拍摄第4页 | 预期：1.相机预览界面正常展示无闪退黑屏 2.3张图片全部保存成功底部预览栏正常展示 3.弹出页数上限提示无法触发第四次拍摄
优点：精准覆盖边界值；操作步骤量化复现性强；预期含界面+数据+弹窗多重校验

【对比3-异常场景】
❌差劲：无相机权限测试拍照 | 前置：相机权限禁止 | 步骤：点击进入拍照功能 | 预期：无法打开相机弹出提示
问题：未区分临时/永久拒绝场景覆盖不足；预期过于简单未校验弹窗按钮跳转
✅优秀：相机权限永久拒绝，校验权限拦截与引导弹窗 | 前置：账号已登录、系统关闭APP相机权限 | 步骤：1.点击中文作文批改拍照入口 | 预期：1.无法唤起相机预览自动弹出权限引导弹窗 2.弹窗包含提示文案、取消、前往设置按钮功能可用
优点：精准锁定异常场景；全量校验弹窗文案+按钮+跳转逻辑；预期具体可落地

【对比4-网络异常】
❌差劲：断网提交作文测试 | 前置：已拍好作文图片 | 步骤：关闭手机网络→点击提交批改 | 预期：网络关闭成功→提交失败提示网络错误
问题：未明确断网时机复现性差；预期缺加载状态重试等交互校验；未校验APP容错防崩溃
✅优秀：图片准备完成后断网，校验提交时网络异常处理 | 前置：账号已登录、已完成作文拍照保存 | 步骤：1.手动关闭WiFi与移动数据断开网络 2.点击去批改发起提交请求 | 预期：1.设备识别为无网络状态 2.请求终止弹出网络异常提示页面无卡死无长期加载
优点：场景贴近真实使用；兼顾功能校验与容错性；步骤和预期严格绑定

【对比5-引导弹窗】
❌差劲：测试关闭首页引导弹窗 | 前置：首次进入作文页面 | 步骤：等待弹窗出现→点击关闭按钮 | 预期：弹窗正常弹出→弹窗关闭页面正常使用
问题：前置条件不严谨无缓存限制说明；未校验UI文案样式；预期宽泛判定标准不一致
✅优秀：首次进入模块，验证引导弹窗展示关闭交互 | 前置：首次进入该模块无弹窗关闭缓存记录 | 步骤：1.进入中文作文批改首页 2.查看页面弹窗内容 3.点击弹窗关闭按钮 | 预期：1.页面加载完成后自动弹出新手引导弹窗 2.弹窗文案图片展示完整样式符合设计 3.弹窗正常关闭首页所有功能按钮可正常点击操作
优点：前置条件严谨区分首次/非首次；覆盖UI+文案+交互+联动多维度；标准统一适合团队协作

【对比6-Web端列表页】
❌差劲：测试版本列表页面加载 | 前置：账号已登录系统 | 步骤：1.点击左侧测试页面版本菜单 | 预期：1.页面可以正常打开没有报错
问题：前置缺浏览器/网络约束无法稳定复现；步骤单一无元素检查动作；预期模糊笼统无具体校验点无法做自动化断言；覆盖极低UI错乱元素缺失无法发现
✅优秀：验证测试页面版本列表页访问、元素及基础渲染展示 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常无弹窗遮罩阻挡 | 步骤：1.点击左侧导航栏「测试页面版本」菜单入口 2.等待页面全部资源加载完成 3.检查页面按钮、表格表头、分页控件展示状态 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.页面无白屏无接口报错无样式错乱 3.核心功能按钮、表格列表、分页组件正常渲染展示
优点：前置只约束环境与权限不依赖业务数据任意环境可独立执行；步骤原子化动作清晰便于自动化元素定位；操作与预期逐条对应校验点明确可断言

【对比7-Web端交互闭环】
❌差劲：测试新建版本按钮功能 | 前置：进入版本管理列表页面 | 步骤：1.点击页面右上角新建版本按钮 | 预期：1.弹出新增窗口功能正常使用
问题：前置含操作步骤而非环境状态自动化无法直接执行；操作流程不完整只点击不校验弹窗关闭按钮状态；预期口语化无明确判定标准不支持自动化落地
✅优秀：验证新建版本按钮点击、弹窗弹出与取消关闭交互 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常 | 步骤：1.点击左侧导航栏「测试页面版本」菜单进入版本列表页面 2.点击页面右上角「新建版本」功能按钮 3.观察新增弹窗整体布局表单及操作按钮展示 4.点击弹窗取消按钮关闭新增弹窗 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.按钮点击无延迟无重复触发交互响应正常 3.新增弹窗正常居中弹出页面布局控件展示无误 4.取消按钮可正常关闭弹窗列表页面原有状态保持不变
优点：步骤包含完整导航路径用例可独立自动化执行；全程仅操作前端控件无数据依赖用例完全解耦；交互流程完整闭环覆盖导航弹窗关闭全链路

## 用例分类标签说明：
- ui_automation: UI自动化测试用例 - 可通过Selenium/Appium等工具自动化执行
- manual: 手工测试用例 - 需要人工执行，无法自动化
- api_automation: 接口自动化测试用例 - 通过HTTP请求验证后端逻辑

根据测试点的性质和界面复杂度判断：
- 涉及UI交互（表单、按钮、输入）→ ui_automation（如果元素可定位）或 manual（如果元素难以定位）
- 纯后端逻辑验证（API调用、数据校验）→ api_automation
- 复杂用户体验测试 → manual

## 输出JSON格式（数组，最少3条，复杂测试点5-8条）：
[
  {{
    "title": "正向-场景+操作+验证重点",
    "module": "模块名称",
    "precondition": "前置条件",
    "steps": [
      {{"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}},
      {{"step": "2", "description": "步骤2描述", "action": "具体操作", "expected_result": "步骤2的预期结果"}}
    ],
    "expected_result": "总体预期结果",
    "case_type": "ui_automation",
    "case_category": "positive",
    "priority": 优先级
  }},
  {{
    "title": "边界值-场景+操作+验证重点",
    "module": "模块名称",
    "precondition": "前置条件",
    "test_data": {{"input": "边界值示例", "expected": "对应结果"}},
    "steps": [
      {{"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}}
    ],
    "expected_result": "总体预期结果",
    "case_type": "ui_automation",
    "case_category": "boundary",
    "priority": 优先级
  }},
  {{
    "title": "异常-场景+操作+验证重点",
    "module": "模块名称",
    "precondition": "前置条件",
    "steps": [
      {{"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}}
    ],
    "expected_result": "总体预期结果",
    "case_type": "manual",
    "case_category": "exception",
    "priority": 优先级
  }},
  {{
    "title": "安全-场景+操作+验证重点",
    "module": "模块名称",
    "precondition": "前置条件",
    "steps": [
      {{"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}}
    ],
    "expected_result": "总体预期结果",
    "case_type": "api_automation",
    "case_category": "exception",
    "priority": 优先级
  }}
]"""

    def _format_ui_spec_for_prompt(self, screen_name: str, ui_spec: Dict[str, Any]) -> str:
        """将UI规格数据格式化为Prompt友好的文本描述。

        格式化内容包括:
            - 页面功能描述
            - 页面区域划分
            - 页面元素列表（类型、标签、状态、交互性）
            - 导航结构
            - 布局约束
            - 页面跳转关系

        Args:
            screen_name: 页面名称。
            ui_spec: UI规格字典，包含purpose/regions/elements/navigation等。

        Returns:
            格式化后的文本描述。
        """
        parts = [f"【页面：{screen_name}】"]

        # 页面功能描述
        if ui_spec.get('purpose'):
            parts.append(f"页面功能：{ui_spec['purpose']}")

        # 页面区域划分
        regions = ui_spec.get('regions', {})
        if regions:
            parts.append("页面区域：")
            if isinstance(regions, dict):
                for region_name, region_desc in regions.items():
                    if region_desc:
                        parts.append(f"  - {region_name}: {region_desc}")
            elif isinstance(regions, list):
                for region in regions:
                    if isinstance(region, dict):
                        name = region.get('name', '')
                        desc = region.get('desc', region.get('description', ''))
                        if name or desc:
                            parts.append(f"  - {name}: {desc}")

        # 页面元素列表，限制最多30个避免Prompt过长
        elements = ui_spec.get('elements', [])
        if elements:
            parts.append(f"页面元素（共{len(elements)}个）：")
            for elem in elements[:30]:
                elem_type = elem.get('type', '未知')
                label = elem.get('label', '') or elem.get('semantic', '') or elem.get('name', '')
                state = elem.get('state', 'normal')
                interactive = elem.get('interactive', False)
                desc = elem.get('description', '')
                parts.append(f"  - [{elem_type}] {label} | 状态:{state} | 可交互:{interactive} | {desc}")

        # 导航结构
        navigation = ui_spec.get('navigation', {})
        if navigation:
            parts.append("导航结构：")
            for nav_key, nav_val in navigation.items():
                if nav_val:
                    parts.append(f"  - {nav_key}: {nav_val}")

        # 布局约束，限制最多10项
        layout_checks = ui_spec.get('layout_constraints', [])
        if layout_checks:
            parts.append(f"布局约束（共{len(layout_checks)}项）：")
            for check in layout_checks[:10]:
                desc = check.get('description', '')
                if desc:
                    parts.append(f"  - {desc}")

        # 页面跳转关系
        flows = ui_spec.get('flows', {})
        if flows:
            next_screens = flows.get('expected_next_screens', [])
            if next_screens:
                parts.append(f"预期跳转页面：{', '.join(next_screens)}")

        return "\n".join(parts)
