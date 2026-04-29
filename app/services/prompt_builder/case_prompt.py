"""测试用例生成 Prompt 构建 - 流程图模式。

提供:
    - _build_graph_prompt: 流程图模式 Prompt 构建
"""
from typing import List, Dict, Any, Optional

from loguru import logger

from app.services.prompt_builder.helpers import _safe_int, _find_main_step


def _build_graph_prompt(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    module_info: Optional[Dict[str, Any]] = None,
    requirement_content: str = "",
    test_point_json: str = "",
    ui_specs_text: str = "",
    include_images: bool = False
) -> str:
    """构建流程图模式的 Prompt。

    Prompt 结构:
        1. 角色设定（资深测试工程师）
        2. 测试点信息（JSON 格式）
        3. 需求文档内容
        4. UI 原型图解析结果
        5. UI 原型图流程结构（主干/分支/异常/旁路）
        6. 输出格式要求

    Args:
        nodes: 节点列表，每个节点包含 screen_id/screen_order/flow_type 等。
        edges: 连线列表，每条连线包含 source/target/edge_type/condition 等。
        module_info: 模块基础信息，包含 name 和 description。
        requirement_content: 需求文档内容。
        test_point_json: 测试点 JSON 字符串。
        ui_specs_text: UI 规格格式化文本。
        include_images: 是否在 Prompt 中包含图片 URL。

    Returns:
        完整的 Prompt 字符串。
    """
    node_map = {n.get('screen_id'): n for n in nodes}
    main_nodes = sorted(
        [n for n in nodes if n.get('flow_type') == 'main'],
        key=lambda n: (
            n.get('main_order') or n.get('screen_order', 0),
            n.get('screen_order', 0)
        )
    )

    branch_edges = [e for e in edges if e.get('edge_type') == 'branch']
    exception_edges = [e for e in edges if e.get('edge_type') == 'exception']
    bypass_edges = [e for e in edges if e.get('edge_type') == 'bypass']

    parts = []
    parts.append("你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下多源信息生成详细的、可执行的测试用例。\n")

    if test_point_json:
        parts.append(f"## 测试点信息\n{test_point_json}\n")

    if requirement_content and requirement_content.strip():
        parts.append(f"## 需求文档内容\n{requirement_content}\n")
    else:
        parts.append("## 需求文档内容\n[无需求文档内容]\n")

    if module_info:
        parts.append("## 模块信息")
        parts.append(module_info.get('name', ''))
        parts.append(module_info.get('description', ''))
        parts.append("")

    if ui_specs_text:
        parts.append(f"## UI原型图解析结果（验收标准，优先参考）：\n{ui_specs_text}\n")

    _append_main_flow(parts, main_nodes, include_images)
    _append_branch_flow(parts, branch_edges, node_map, main_nodes, include_images)
    _append_exception_flow(parts, exception_edges, node_map, main_nodes, include_images)
    _append_bypass_flow(parts, bypass_edges, node_map, main_nodes, include_images)
    _append_generation_rules(parts)

    return "\n".join(parts)


def _format_node_elements(elements: Optional[List[Dict[str, Any]]]) -> str:
    """格式化节点的 UI 元素列表为简短描述。

    Args:
        elements: UI 元素列表。

    Returns:
        逗号分隔的元素描述字符串。
    """
    if not elements:
        return ""
    return ', '.join(
        [f"{e.get('type', '')}:{e.get('label', '')}" for e in elements if e.get('label')]
    )


def _build_image_ref(node: Dict[str, Any], include_images: bool) -> str:
    """构建节点的图片 URL 引用文本。

    Args:
        node: 节点字典，需包含 image_url 字段。
        include_images: 是否包含图片 URL。

    Returns:
        图片 URL 引用文本，不包含时返回空字符串。
    """
    if include_images and node.get('image_url'):
        return f" [图片URL: {node.get('image_url', '')}]"
    return ""


def _append_main_flow(
    parts: List[str],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加主干流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    parts.append("## UI原型图流程结构\n")
    parts.append("### 主干流程（按顺序执行，必须完整覆盖）")
    for i, node in enumerate(main_nodes, 1):
        elements = node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        image_ref = _build_image_ref(node, include_images)
        parts.append(f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}] 元素: {element_desc}{image_ref}")
    parts.append("")


def _append_branch_flow(
    parts: List[str],
    branch_edges: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加分支流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        branch_edges: 分支连线列表。
        node_map: 节点映射字典。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    if not branch_edges:
        return
    parts.append("### 分支流程（满足条件时执行，每个分支作为独立测试场景）")
    for idx, edge in enumerate(branch_edges):
        target_screen_id = _safe_int(edge.get('target'))
        source_screen_id = _safe_int(edge.get('source'))
        if target_screen_id is None or source_screen_id is None:
            continue
        target_node = node_map.get(target_screen_id, {})
        source_step = _find_main_step(main_nodes, source_screen_id)
        elements = target_node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        trigger_condition = (edge.get('condition') or '').strip()
        if not trigger_condition:
            logger.warning(f"branch edge missing condition: {edge}")
            trigger_condition = '未指定'
        image_ref = _build_image_ref(target_node, include_images)
        parts.append(
            f"分支 {chr(ord('A') + idx)}: 从步骤 {source_step} 分支，"
            f"触发条件「{trigger_condition}」"
        )
        parts.append(
            f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
        )
    parts.append("")


def _append_exception_flow(
    parts: List[str],
    exception_edges: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加异常流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        exception_edges: 异常连线列表。
        node_map: 节点映射字典。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    if not exception_edges:
        return
    parts.append("### 异常流程（异常场景下触发，需标注异常场景和预期错误提示）")
    for idx, edge in enumerate(exception_edges):
        target_screen_id = _safe_int(edge.get('target'))
        source_screen_id = _safe_int(edge.get('source'))
        if target_screen_id is None or source_screen_id is None:
            continue
        target_node = node_map.get(target_screen_id, {})
        source_step = _find_main_step(main_nodes, source_screen_id)
        elements = target_node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        exception_condition = (edge.get('condition') or '').strip()
        if not exception_condition:
            logger.warning(f"exception edge missing condition: {edge}")
            exception_condition = '未指定'
        image_ref = _build_image_ref(target_node, include_images)
        parts.append(
            f"异常 {chr(ord('A') + idx)}: 从步骤 {source_step} 异常跳转，"
            f"异常场景「{exception_condition}」"
        )
        parts.append(
            f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
        )
    parts.append("")


def _append_bypass_flow(
    parts: List[str],
    bypass_edges: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加旁路流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        bypass_edges: 旁路连线列表。
        node_map: 节点映射字典。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    if not bypass_edges:
        return
    parts.append("### 旁路流程（出现时机和关闭方式，不影响主流程）")
    for idx, edge in enumerate(bypass_edges):
        target_screen_id = _safe_int(edge.get('target'))
        source_screen_id = _safe_int(edge.get('source'))
        if target_screen_id is None or source_screen_id is None:
            continue
        target_node = node_map.get(target_screen_id, {})
        source_step = _find_main_step(main_nodes, source_screen_id)
        condition = (edge.get('condition') or '').strip()
        if not condition:
            logger.warning(f"bypass edge missing condition: {edge}")
            condition = '自动弹出'
        elements = target_node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        image_ref = _build_image_ref(target_node, include_images)
        parts.append(
            f"旁路 {chr(ord('A') + idx)}: 进入步骤 {source_step} 时"
            f"{condition}，关闭后继续主流程"
        )
        parts.append(
            f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
        )
    parts.append("")


def _append_generation_rules(parts: List[str]) -> None:
    """追加生成要求和输出格式到 parts 列表。

    Args:
        parts: Prompt 片段列表。
    """
    parts.append("## 生成要求")
    parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
    parts.append("2. 每个分支流程需标注触发条件，作为独立测试场景生成用例")
    parts.append("3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例")
    parts.append("4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理")
    parts.append("5. 若提供了需求文档，结合业务规则验证每个步骤的验收标准；若未提供，仅根据UI原型图推断业务逻辑")
    parts.append("6. 若提供了测试点，优先覆盖测试点中的测试维度；若未提供，根据UI元素自动生成测试点")
    parts.append("7. 只输出JSON格式内容，不要添加任何其他文字")
    parts.append("8. 标题必须具体明确，格式：「场景/条件」+「操作」+「验证重点」，如\"未选单词时纸张听写按钮置灰不可点击\"，禁止使用\"功能验证\"\"界面测试\"\"XX测试\"等模糊词，长度15-40字")
    parts.append("9. 前置条件必须包含\"账号已登录\"和网络环境（Web端写\"浏览器网络正常\"，App端写\"设备网络正常\"），有权限场景补充权限状态；禁止仅写\"账号已登录\"或\"APP运行正常\"；前置条件只约束环境与权限，禁止依赖特定业务数据（如\"列表有数据\"\"数据较多\"），确保用例任意环境可独立执行；如需特定数据才能测试（如编辑/删除场景），应在步骤中先创建数据，而非在前置中假设数据已存在；前置条件不能包含操作步骤或页面导航状态（如\"已进入详情页\"\"在列表页面\"），导航到达目标页面必须作为步骤体现，确保用例可独立自动化执行")
    parts.append("10. 操作步骤必须严谨可复现，禁止口语化如\"连续拍摄多张照片\"")
    parts.append("11. 预期结果必须有具体判定标准，禁止\"提交成功\"\"正常显示\"等模糊描述；必须包含交互校验点如弹窗文案、按钮跳转")
    parts.append("12. 未区分场景变体时需拆分，如\"无相机权限\"应区分临时拒绝/永久拒绝")
    parts.append("13. 步骤和预期必须支持自动化断言，预期需有可量化判定标准（如\"无白屏\"\"按钮置灰\"），禁止\"页面正常\"\"功能正常\"等无法断言的描述；步骤必须包含从登录后到达目标页面的完整导航操作，禁止将导航隐藏在前置条件中；弱网、异常条件等自动化无法实现的场景标注case_type为manual")
    parts.append("")
    parts.append("## 正反用例对比（学习优秀写法，避免差劲写法）")
    parts.append("")
    parts.append("【对比1-主流程】")
    parts.append("❌差劲：测试拍照提交作文功能 | 前置：账号已登录，APP运行正常 | 步骤：进入页面→拍摄裁剪→点击提交 | 预期：页面正常→拍照正常→提交成功显示结果")
    parts.append("问题：描述笼统无校验目标；前置条件缺网络/权限；步骤口语化；预期模糊无判定标准")
    parts.append("✅优秀：联网+已授权，验证拍照裁剪提交完整流程 | 前置：账号已登录、相机权限允许、设备网络正常 | 步骤：1.点击进入中文作文批改模块 2.点击拍照拍摄作文并完成裁剪确认 3.点击去批改按钮提交图片 | 预期：1.模块页面加载正常功能入口完整 2.相机正常唤起图片裁剪完成并本地保存 3.提交请求正常发起成功跳转展示批改报告")
    parts.append("优点：描述清晰目标明确；前置条件完整可稳定复现；步骤原子化；步骤与预期一一对应")
    parts.append("")
    parts.append("【对比2-边界值】")
    parts.append("❌差劲：测试拍照数量限制 | 前置：账号已登录 | 步骤：打开拍照页面→连续拍摄多张照片 | 预期：拍照页面正常→达到上限后禁止继续拍照")
    parts.append("问题：未明确页数上限无量化标准；步骤模糊无固定复现路径；预期缺弹窗文案等校验点")
    parts.append("✅优秀：验证最多3页拍摄限制，超出上限校验拦截提示 | 前置：账号已登录、相机权限开启、规则限制最多3页 | 步骤：1.进入作文拍照拍摄页面 2.依次拍摄并保存3张作文图片 3.再次点击拍摄按钮尝试拍摄第4页 | 预期：1.相机预览界面正常展示无闪退黑屏 2.3张图片全部保存成功底部预览栏正常展示 3.弹出页数上限提示无法触发第四次拍摄")
    parts.append("优点：精准覆盖边界值；操作步骤量化复现性强；预期含界面+数据+弹窗多重校验")
    parts.append("")
    parts.append("【对比3-异常场景】")
    parts.append("❌差劲：无相机权限测试拍照 | 前置：相机权限禁止 | 步骤：点击进入拍照功能 | 预期：无法打开相机弹出提示")
    parts.append("问题：未区分临时/永久拒绝场景覆盖不足；预期过于简单未校验弹窗按钮跳转")
    parts.append("✅优秀：相机权限永久拒绝，校验权限拦截与引导弹窗 | 前置：账号已登录、系统关闭APP相机权限 | 步骤：1.点击中文作文批改拍照入口 | 预期：1.无法唤起相机预览自动弹出权限引导弹窗 2.弹窗包含提示文案、取消、前往设置按钮功能可用")
    parts.append("优点：精准锁定异常场景；全量校验弹窗文案+按钮+跳转逻辑；预期具体可落地")
    parts.append("")
    parts.append("【对比4-网络异常】")
    parts.append("❌差劲：断网提交作文测试 | 前置：已拍好作文图片 | 步骤：关闭手机网络→点击提交批改 | 预期：网络关闭成功→提交失败提示网络错误")
    parts.append("问题：未明确断网时机复现性差；预期缺加载状态重试等交互校验；未校验APP容错防崩溃")
    parts.append("✅优秀：图片准备完成后断网，校验提交时网络异常处理 | 前置：账号已登录、已完成作文拍照保存 | 步骤：1.手动关闭WiFi与移动数据断开网络 2.点击去批改发起提交请求 | 预期：1.设备识别为无网络状态 2.请求终止弹出网络异常提示页面无卡死无长期加载")
    parts.append("优点：场景贴近真实使用；兼顾功能校验与容错性；步骤和预期严格绑定")
    parts.append("")
    parts.append("【对比5-引导弹窗】")
    parts.append("❌差劲：测试关闭首页引导弹窗 | 前置：首次进入作文页面 | 步骤：等待弹窗出现→点击关闭按钮 | 预期：弹窗正常弹出→弹窗关闭页面正常使用")
    parts.append("问题：前置条件不严谨无缓存限制说明；未校验UI文案样式；预期宽泛判定标准不一致")
    parts.append("✅优秀：首次进入模块，验证引导弹窗展示关闭交互 | 前置：首次进入该模块无弹窗关闭缓存记录 | 步骤：1.进入中文作文批改首页 2.查看页面弹窗内容 3.点击弹窗关闭按钮 | 预期：1.页面加载完成后自动弹出新手引导弹窗 2.弹窗文案图片展示完整样式符合设计 3.弹窗正常关闭首页所有功能按钮可正常点击操作")
    parts.append("优点：前置条件严谨区分首次/非首次；覆盖UI+文案+交互+联动多维度；标准统一适合团队协作")
    parts.append("")
    parts.append("【对比6-Web端列表页】")
    parts.append("❌差劲：测试版本列表页面加载 | 前置：账号已登录系统 | 步骤：1.点击左侧测试页面版本菜单 | 预期：1.页面可以正常打开没有报错")
    parts.append("问题：前置缺浏览器/网络约束无法稳定复现；步骤单一无元素检查动作；预期模糊笼统无具体校验点无法做自动化断言；覆盖极低UI错乱元素缺失无法发现")
    parts.append("✅优秀：验证测试页面版本列表页访问、元素及基础渲染展示 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常无弹窗遮罩阻挡 | 步骤：1.点击左侧导航栏「测试页面版本」菜单入口 2.等待页面全部资源加载完成 3.检查页面按钮、表格表头、分页控件展示状态 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.页面无白屏无接口报错无样式错乱 3.核心功能按钮、表格列表、分页组件正常渲染展示")
    parts.append("优点：前置只约束环境与权限不依赖业务数据任意环境可独立执行；步骤原子化动作清晰便于自动化元素定位；操作与预期逐条对应校验点明确可断言")
    parts.append("")
    parts.append("【对比7-Web端交互闭环】")
    parts.append("❌差劲：测试新建版本按钮功能 | 前置：进入版本管理列表页面 | 步骤：1.点击页面右上角新建版本按钮 | 预期：1.弹出新增窗口功能正常使用")
    parts.append("问题：前置含操作步骤而非环境状态自动化无法直接执行；操作流程不完整只点击不校验弹窗关闭按钮状态；预期口语化无明确判定标准不支持自动化落地")
    parts.append("✅优秀：验证新建版本按钮点击、弹窗弹出与取消关闭交互 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常 | 步骤：1.点击左侧导航栏「测试页面版本」菜单进入版本列表页面 2.点击页面右上角「新建版本」功能按钮 3.观察新增弹窗整体布局表单及操作按钮展示 4.点击弹窗取消按钮关闭新增弹窗 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.按钮点击无延迟无重复触发交互响应正常 3.新增弹窗正常居中弹出页面布局控件展示无误 4.取消按钮可正常关闭弹窗列表页面原有状态保持不变")
    parts.append("优点：步骤包含完整导航路径用例可独立自动化执行；全程仅操作前端控件无数据依赖用例完全解耦；交互流程完整闭环覆盖导航弹窗关闭全链路")

    parts.append("""
## 输出JSON格式：
{
  "title": "场景+操作+验证重点",
  "module": "模块名称",
  "precondition": "前置条件",
  "test_data": {"normal": {}, "boundary": {}, "abnormal": {}},
  "steps": [
    {"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}
  ],
  "expected_result": "总体预期结果",
  "case_type": "ui_automation",
  "case_category": "ui_automation",
  "priority": 2
}""")

