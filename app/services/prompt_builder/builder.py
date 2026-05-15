"""统一 Prompt 构建器 - 提供所有 Prompt 构建的入口类。

PromptBuilder 类支持:
    - for_test_case: 测试用例生成（graph/linear）
    - for_test_data: 测试数据生成
    - 静态兼容方法: build_graph_prompt / build_multimodal_prompt / build_linear_prompt
"""
from typing import List, Dict, Any, Optional

from app.services.prompt_builder.case_prompt import _build_graph_prompt
from app.services.prompt_builder.linear_prompt import _build_linear_prompt
from app.services.prompt_builder.data_prompt import _build_test_data_prompt


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
        case_type: Optional[str] = None
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
                case_type=case_type
            )
            return {'prompt': prompt, 'weight_hint': 'graph'}

        prompt = _build_linear_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module, function=function,
            point=point, priority=priority,
            ui_specs=ui_specs
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
        case_type: Optional[str] = None
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
            case_type=case_type
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
            history_cases=history_cases
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
        return _build_linear_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module, function=function,
            point=point, priority=priority,
            ui_specs=ui_specs
        )
