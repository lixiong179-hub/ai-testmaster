"""流程图模式Prompt构建器 - 将流程结构数据融合为AI可理解的结构化Prompt。

本模块提供流程图模式的Prompt构建逻辑，将前端传递的节点/连线数据
解析为主干/分支/异常/旁路流程，构建结构化Prompt供AI模型使用。

核心类:
    - PromptBuilder: Prompt构建器，提供graph和linear两种模式的Prompt构建

设计模式:
    作为独立服务模块，被API端点或生成服务调用，提供:
    - build_graph_prompt: 流程图模式Prompt构建
    - build_linear_prompt: 线性模式Prompt构建（复用现有逻辑）

依赖关系:
    - app.schemas.test_case: FlowSortDataSchema数据校验
"""
from typing import List, Dict, Any, Optional

from loguru import logger


class PromptBuilder:
    """测试用例生成Prompt构建器 - 支持流程图和线性两种模式。

    职责:
        - 流程图模式：解析nodes/edges为主干/分支/异常/旁路流程
        - 线性模式：复用现有Prompt构建逻辑
        - 多源数据融合：整合测试点、需求文档、UI原型信息

    设计意图:
        将Prompt构建逻辑从API端点中抽离，便于:
        1. 独立调整Prompt模板和格式
        2. 支持不同排序模式的Prompt优化
        3. 统一管理流程信息的渲染逻辑
    """

    @staticmethod
    def build_graph_prompt(
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        module_info: Optional[Dict[str, Any]] = None,
        requirement_content: str = "",
        test_point_json: str = "",
        ui_specs_text: str = "",
        include_images: bool = False
    ) -> str:
        """构建流程图模式的Prompt。

        Prompt结构:
            1. 角色设定（资深测试工程师）
            2. 测试点信息（JSON格式）
            3. 需求文档内容
            4. UI原型图解析结果
            5. UI原型图流程结构（主干/分支/异常/旁路）
            6. 输出格式要求

        Args:
            nodes: 节点列表，每个节点包含screen_id/screen_order/flow_type/screen_name/ui_spec_elements/image_url等。
            edges: 连线列表，每条连线包含source/target/edge_type/condition/label等。
            module_info: 模块基础信息，包含name和description。
            requirement_content: 需求文档内容。
            test_point_json: 测试点JSON字符串。
            ui_specs_text: UI规格格式化文本。
            include_images: 是否在Prompt中包含图片URL（多模态模型支持）。

        Returns:
            完整的Prompt字符串。
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

        parts.append("## UI原型图流程结构\n")
        parts.append("### 主干流程（按顺序执行，必须完整覆盖）")
        for i, node in enumerate(main_nodes, 1):
            elements = node.get('ui_spec_elements', []) or []
            element_desc = ', '.join(
                [f"{e.get('type', '')}:{e.get('label', '')}" for e in elements if e.get('label')]
            )
            image_ref = f" [图片URL: {node.get('image_url', '')}]" if include_images and node.get('image_url') else ""
            parts.append(f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}] 元素: {element_desc}{image_ref}")
        parts.append("")

        if branch_edges:
            parts.append("### 分支流程（满足条件时执行，每个分支作为独立测试场景）")
            for idx, edge in enumerate(branch_edges):
                target_screen_id = _safe_int(edge.get('target'))
                source_screen_id = _safe_int(edge.get('source'))
                if target_screen_id is None or source_screen_id is None:
                    continue
                target_node = node_map.get(target_screen_id, {})
                source_step = _find_main_step(main_nodes, source_screen_id)
                elements = target_node.get('ui_spec_elements', []) or []
                element_desc = ', '.join(
                    [f"{e.get('type', '')}:{e.get('label', '')}" for e in elements if e.get('label')]
                )
                trigger_condition = (edge.get('condition') or '').strip()
                if not trigger_condition:
                    logger.warning(f"branch edge missing condition: {edge}")
                    trigger_condition = '未指定'
                image_ref = f" [图片URL: {target_node.get('image_url', '')}]" if include_images and target_node.get('image_url') else ""
                parts.append(
                    f"分支 {chr(ord('A') + idx)}: 从步骤 {source_step} 分支，"
                    f"触发条件「{trigger_condition}」"
                )
                parts.append(
                    f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
                )
            parts.append("")

        if exception_edges:
            parts.append("### 异常流程（异常场景下触发，需标注异常场景和预期错误提示）")
            for idx, edge in enumerate(exception_edges):
                target_screen_id = _safe_int(edge.get('target'))
                source_screen_id = _safe_int(edge.get('source'))
                if target_screen_id is None or source_screen_id is None:
                    continue
                target_node = node_map.get(target_screen_id, {})
                source_step = _find_main_step(main_nodes, source_screen_id)
                elements = target_node.get('ui_spec_elements', []) or []
                element_desc = ', '.join(
                    [f"{e.get('type', '')}:{e.get('label', '')}" for e in elements if e.get('label')]
                )
                exception_condition = (edge.get('condition') or '').strip()
                if not exception_condition:
                    logger.warning(f"exception edge missing condition: {edge}")
                    exception_condition = '未指定'
                image_ref = f" [图片URL: {target_node.get('image_url', '')}]" if include_images and target_node.get('image_url') else ""
                parts.append(
                    f"异常 {chr(ord('A') + idx)}: 从步骤 {source_step} 异常跳转，"
                    f"异常场景「{exception_condition}」"
                )
                parts.append(
                    f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
                )
            parts.append("")

        if bypass_edges:
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
                element_desc = ', '.join(
                    [f"{e.get('type', '')}:{e.get('label', '')}" for e in elements if e.get('label')]
                )
                image_ref = f" [图片URL: {target_node.get('image_url', '')}]" if include_images and target_node.get('image_url') else ""
                parts.append(
                    f"旁路 {chr(ord('A') + idx)}: 进入步骤 {source_step} 时"
                    f"{condition}，关闭后继续主流程"
                )
                parts.append(
                    f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
                )
            parts.append("")

        parts.append("## 生成要求")
        parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
        parts.append("2. 每个分支流程需标注触发条件，作为独立测试场景生成用例")
        parts.append("3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例")
        parts.append("4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理")
        parts.append("5. 若提供了需求文档，结合业务规则验证每个步骤的验收标准；若未提供，仅根据UI原型图推断业务逻辑")
        parts.append("6. 若提供了测试点，优先覆盖测试点中的测试维度；若未提供，根据UI元素自动生成测试点")
        parts.append("7. 只输出JSON格式内容，不要添加任何其他文字")

        parts.append("""
## 输出JSON格式：
{
  "title": "用例标题",
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

        return "\n".join(parts)

    @staticmethod
    def build_multimodal_prompt(
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        module_info: Optional[Dict[str, Any]] = None,
        requirement_content: str = "",
        test_point_json: str = "",
        ui_specs_text: str = ""
    ) -> str:
        """构建多模态Prompt（自动包含图片URL）。

        此方法是对build_graph_prompt的包装，默认启用include_images=True，
        适用于支持多模态输入的AI模型（如GPT-4V、Claude Vision等）。

        Args:
            nodes: 节点列表，需包含image_url字段。
            edges: 连线列表。
            module_info: 模块基础信息。
            requirement_content: 需求文档内容。
            test_point_json: 测试点JSON字符串。
            ui_specs_text: UI规格格式化文本。

        Returns:
            包含图片URL引用的完整Prompt字符串。
        """
        return PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=module_info,
            requirement_content=requirement_content,
            test_point_json=test_point_json,
            ui_specs_text=ui_specs_text,
            include_images=True
        )

    @staticmethod
    def build_linear_prompt(
        requirement_content: str,
        ui_description: str,
        module: str,
        function: str,
        point: str,
        priority: int,
        ui_specs: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """构建线性模式的Prompt（复用现有逻辑）。

        此方法委托给AIPromptMixin._build_generation_prompt的独立实现，
        保持与现有线性模式完全一致的行为。

        Args:
            requirement_content: 需求文档内容。
            ui_description: UI描述文本。
            module: 模块名称。
            function: 功能名称。
            point: 测试点描述。
            priority: 优先级。
            ui_specs: UI规格列表。

        Returns:
            完整的Prompt字符串。
        """
        from app.services.case_generation.ai_prompt_mixin import AIPromptMixin

        mixin = AIPromptMixin.__new__(AIPromptMixin)
        return mixin._build_generation_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module,
            function=function,
            point=point,
            priority=priority,
            ui_specs=ui_specs
        )


def _safe_int(value: Any) -> Optional[int]:
    """安全地将值转换为整数。

    Args:
        value: 待转换的值，支持int/str类型。

    Returns:
        转换后的整数，失败时返回None。
    """
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"连线source/target格式错误: {value}")
        return None


def _find_main_step(main_nodes: List[Dict[str, Any]], screen_id: int) -> str:
    """在主干流程中查找指定screen_id对应的步骤序号。

    Args:
        main_nodes: 主干流程节点列表（已按screen_order排序）。
        screen_id: 待查找的屏幕ID。

    Returns:
        步骤序号字符串，未找到时返回'?'。
    """
    for i, node in enumerate(main_nodes, 1):
        if node.get('screen_id') == screen_id:
            return str(i)
    return '?'
