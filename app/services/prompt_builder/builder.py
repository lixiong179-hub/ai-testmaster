"""统一 Prompt 构建器 - 提供所有 Prompt 构建的入口类。

PromptBuilder 类支持:
    - for_test_case: 测试用例生成（graph/linear）
    - for_test_data: 测试数据生成
    - 静态兼容方法: build_graph_prompt / build_multimodal_prompt / build_linear_prompt
"""
import json
import logging
from typing import List, Dict, Any, Optional

from app.services.prompt_builder.case_prompt import _build_graph_prompt
from app.services.prompt_builder.linear_prompt import _build_linear_prompt
from app.services.prompt_builder.data_prompt import _build_test_data_prompt

logger = logging.getLogger(__name__)


def _append_extra_context_sections(
    prompt: str,
    extra_context: Optional[Dict[str, Any]] = None,
) -> str:
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
                logger.debug("解析原用例steps_json失败", exc_info=True)
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
            sections.append(f"- [{hc.get('module', '')}] {hc.get('title', '')}")
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

    if task_type == "migrate" and task_context.get("source_case"):
        from app.services.prompt_builder.migration_prompt import build_migration_prompt
        source_case = task_context["source_case"]
        source_device = task_context.get("source_device", "tablet")
        target_device = task_context.get("target_device", "phone")
        target_ui_specs = task_context.get("target_ui_specs", "")
        migration_prompt = build_migration_prompt(
            source_case=source_case,
            source_device=source_device,
            target_device=target_device,
            target_ui_specs=target_ui_specs,
        )
        sections.append(migration_prompt)

    return "\n\n".join(sections)


class PromptBuilder:
    """统一 Prompt 构建器 - 提供所有 Prompt 构建的链式入口。

    支持模式:
        - for_test_case: 测试用例生成（graph/linear）
        - for_test_data: 测试数据生成

    向后兼容静态方法:
        - build_graph_prompt: 流程图模式 Prompt
        - build_multimodal_prompt: 多模态 Prompt
        - build_linear_prompt: 线性模式 Prompt
    """

    def for_test_case(
        self,
        mode: str = 'linear',
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        module_info: Optional[Dict[str, Any]] = None,
        requirement_content: str = "",
        test_point_json: str = "",
        ui_specs_text: str = "",
        include_images: bool = False,
        ui_description: str = "",
        module: str = "",
        function: str = "",
        point: str = "",
        priority: int = 2,
        ui_specs: Optional[List[Dict[str, Any]]] = None,
        case_type: Optional[str] = None,
        test_username: str = "testuser",
        test_password: str = "TestPass123",
        min_case_count: int = 3,
    ) -> Dict[str, Any]:
        """构建测试用例生成 Prompt，支持 graph 和 linear 两种模式。

        Args:
            mode: 生成模式，'graph' 或 'linear'。
            nodes: 流程图节点列表（graph 模式必需）。
            edges: 流程图连线列表（graph 模式必需）。
            module_info: 模块基础信息（graph 模式）。
            requirement_content: 需求文档内容。
            test_point_json: 测试点 JSON 字符串（graph 模式）。
            ui_specs_text: UI 规格格式化文本（graph 模式）。
            include_images: 是否包含图片 URL（graph 模式）。
            ui_description: UI 描述文本（linear 模式）。
            module: 模块名称（linear 模式）。
            function: 功能名称（linear 模式）。
            point: 测试点描述（linear 模式）。
            priority: 优先级（linear 模式）。
            ui_specs: UI 规格列表（linear 模式）。

        Returns:
            包含 prompt 和 weight_hint 的字典。
        """
        if mode == 'graph':
            prompt = _build_graph_prompt(
                nodes=nodes or [], edges=edges or [],
                module_info=module_info,
                requirement_content=requirement_content,
                test_point_json=test_point_json,
                ui_specs_text=ui_specs_text,
                include_images=include_images,
                case_type=case_type,
                test_username=test_username,
                test_password=test_password,
                min_case_count=min_case_count,
            )
            return {'prompt': prompt, 'weight_hint': 'graph'}

        prompt = _build_linear_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module, function=function,
            point=point, priority=priority,
            ui_specs=ui_specs,
            case_type=case_type,
            min_case_count=min_case_count,
        )
        return {'prompt': prompt, 'weight_hint': 'linear'}

    def for_test_data(
        self,
        field_definitions: List[Dict[str, Any]],
        count: int = 1,
        context: Optional[str] = None,
        data_type: str = "normal"
    ) -> str:
        """构建测试数据生成 Prompt。

        Args:
            field_definitions: 字段定义列表。
            count: 生成记录数，默认 1。
            context: 业务上下文描述，可选。
            data_type: 数据类型（normal/boundary/invalid/special）。

        Returns:
            完整的 Prompt 字符串。
        """
        return _build_test_data_prompt(field_definitions, count, context, data_type)

    def for_self_test_case(
        self,
        requirement_content: str = "",
        ui_description: str = "",
        module: str = "",
        function: str = "",
        point: str = "",
        priority: int = 2,
        ui_specs: Optional[List[Dict[str, Any]]] = None,
        history_cases: Optional[List[Dict[str, Any]]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from app.services.prompt_builder.self_test_prompt import build_self_test_prompt

        prompt = build_self_test_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module,
            function=function,
            point=point,
            priority=priority,
            ui_specs=ui_specs,
            history_cases=history_cases,
            extra_context=extra_context,
        )
        return {"prompt": prompt, "weight_hint": "self_test"}

    # ------------------------------------------------------------------
    # 静态方法：保持与旧 PromptBuilder 的向后兼容
    # ------------------------------------------------------------------

    @staticmethod
    def build_graph_prompt(
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        module_info: Optional[Dict[str, Any]] = None,
        requirement_content: str = "",
        test_point_json: str = "",
        ui_specs_text: str = "",
        include_images: bool = False,
        history_cases: Optional[List[Dict[str, Any]]] = None,
        case_type: Optional[str] = None,
        test_username: str = "testuser",
        test_password: str = "TestPass123",
        min_case_count: int = 3,
    ) -> str:
        """构建流程图模式 Prompt（向后兼容接口）。

        Args:
            nodes: 节点列表。
            edges: 连线列表。
            module_info: 模块基础信息。
            requirement_content: 需求文档内容。
            test_point_json: 测试点 JSON 字符串。
            ui_specs_text: UI 规格格式化文本。
            include_images: 是否包含图片 URL。
            history_cases: 历史用例列表，提供时启用查漏补缺评审模式。
            case_type: 用例类型，提供时会在 Prompt 中增加约束。

        Returns:
            完整的 Prompt 字符串。
        """
        return _build_graph_prompt(
            nodes=nodes, edges=edges, module_info=module_info,
            requirement_content=requirement_content,
            test_point_json=test_point_json,
            ui_specs_text=ui_specs_text,
            include_images=include_images,
            history_cases=history_cases,
            case_type=case_type,
            test_username=test_username,
            test_password=test_password,
            min_case_count=min_case_count,
        )

    @staticmethod
    def build_multimodal_prompt(
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        module_info: Optional[Dict[str, Any]] = None,
        requirement_content: str = "",
        test_point_json: str = "",
        ui_specs_text: str = "",
        history_cases: Optional[List[Dict[str, Any]]] = None,
        min_case_count: int = 3,
    ) -> str:
        """构建多模态 Prompt（自动包含图片 URL，向后兼容接口）。

        Args:
            nodes: 节点列表，需包含 image_url 字段。
            edges: 连线列表。
            module_info: 模块基础信息。
            requirement_content: 需求文档内容。
            test_point_json: 测试点 JSON 字符串。
            ui_specs_text: UI 规格格式化文本。
            history_cases: 历史用例列表，提供时启用查漏补缺评审模式。

        Returns:
            包含图片 URL 引用的完整 Prompt 字符串。
        """
        return _build_graph_prompt(
            nodes=nodes, edges=edges, module_info=module_info,
            requirement_content=requirement_content,
            test_point_json=test_point_json,
            ui_specs_text=ui_specs_text,
            include_images=True,
            history_cases=history_cases,
            min_case_count=min_case_count,
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
        extra_context: Optional[Dict[str, Any]] = None,
        case_type: Optional[str] = None,
        min_case_count: int = 3,
    ) -> str:
        """构建线性模式 Prompt（向后兼容接口）。

        Args:
            requirement_content: 需求文档内容。
            ui_description: UI 描述文本。
            module: 模块名称。
            function: 功能名称。
            point: 测试点描述。
            priority: 优先级。
            ui_specs: UI 规格列表。

        Returns:
            完整的 Prompt 字符串。
        """
        prompt = _build_linear_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module, function=function,
            point=point, priority=priority,
            ui_specs=ui_specs,
            case_type=case_type,
        )
        return _append_extra_context_sections(prompt, extra_context)
