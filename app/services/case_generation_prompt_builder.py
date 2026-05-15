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
import json
from typing import List, Dict, Any, Optional

from app.services.prompt_builder.case_prompt import _build_graph_prompt
from app.services.prompt_builder.builder import PromptBuilder as UnifiedPromptBuilder


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
        include_images: bool = False,
        history_cases: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """构建流程图模式的Prompt。

        委托给 prompt_builder.case_prompt._build_graph_prompt 统一实现。

        Args:
            nodes: 节点列表。
            edges: 连线列表。
            module_info: 模块基础信息。
            requirement_content: 需求文档内容。
            test_point_json: 测试点JSON字符串。
            ui_specs_text: UI规格格式化文本。
            include_images: 是否在Prompt中包含图片URL。

        Returns:
            完整的Prompt字符串。
        """
        return _build_graph_prompt(
            nodes=nodes, edges=edges, module_info=module_info,
            requirement_content=requirement_content,
            test_point_json=test_point_json,
            ui_specs_text=ui_specs_text,
            include_images=include_images,
            history_cases=history_cases,
        )

    @staticmethod
    def build_multimodal_prompt(
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        module_info: Optional[Dict[str, Any]] = None,
        requirement_content: str = "",
        test_point_json: str = "",
        ui_specs_text: str = "",
        history_cases: Optional[List[Dict[str, Any]]] = None
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
            include_images=True,
            history_cases=history_cases,
        )

    @staticmethod
    def build_linear_prompt(
        requirement_content: str,
        ui_description: str,
        module: str,
        function: str,
        point: str,
        priority: int,
        ui_specs: Optional[List[Dict[str, Any]]] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建线性模式的Prompt（委托给统一PromptBuilder）。

        委托给 prompt_builder.PromptBuilder.for_test_case() 统一实现，
        保持与现有线性模式完全一致的行为。支持通过 extra_context 追加
        历史用例去重提示、变更指引、定位器修复指引等上下文段落。

        Args:
            requirement_content: 需求文档内容。
            ui_description: UI描述文本。
            module: 模块名称。
            function: 功能名称。
            point: 测试点描述。
            priority: 优先级。
            ui_specs: UI规格列表。
            extra_context: 额外上下文，包含 task_type / task_context / history_cases。

        Returns:
            完整的Prompt字符串。
        """
        prompt = UnifiedPromptBuilder.build_linear_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module,
            function=function,
            point=point,
            priority=priority,
            ui_specs=ui_specs
        )

        if not extra_context:
            return prompt

        task_type = extra_context.get("task_type")
        task_context = extra_context.get("task_context", {})
        sections: List[str] = [prompt]

        if task_type == "modify" and task_context.get("original_case"):
            original = task_context["original_case"]
            sections.append("## 原有用例（需基于此修改）")
            sections.append(f"### 原用例标题: {original.get('title', '')}")
            sections.append(f"### 原前置条件: {original.get('precondition', '')}")
            steps_json = original.get('steps_json')
            if isinstance(steps_json, str):
                try:
                    steps_json = json.loads(steps_json)
                except Exception:
                    pass
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

        if task_type == "create" and extra_context.get("history_cases"):
            history = extra_context["history_cases"]
            sections.append("## 项目已有用例（避免重复，以下为已有用例的标题和内容摘要）")
            for hc in history[:20]:
                sections.append(
                    f"- [{hc.get('module', '')}] {hc.get('title', '')}"
                )
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

        if task_type == "locator_fix" and task_context.get("original_case"):
            original = task_context["original_case"]
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

        return "\n\n".join(sections)
