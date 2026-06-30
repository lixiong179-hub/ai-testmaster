"""统一 Prompt 构建器 - 提供所有 Prompt 构建的入口类。

PromptBuilder 类支持:
    - for_test_case: 测试用例生成（graph/linear）
    - for_test_data: 测试数据生成
    - 静态兼容方法: build_graph_prompt / build_multimodal_prompt / build_linear_prompt

可通过可选的 registry 参数从 PromptRegistry 读取 Prompt 内容，
DB 有记录则使用 DB 内容，否则使用现有硬编码逻辑。

extra_context 的渲染逻辑（task_type 分支）拆分至 _extra_context_renderer 模块。
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from app.services.prompt_builder.case_prompt import _build_graph_prompt
from app.services.prompt_builder.linear_prompt import _build_linear_prompt
from app.services.prompt_builder.data_prompt import _build_test_data_prompt
from app.services.prompt_builder._extra_context_renderer import (
    _append_extra_context_sections,
)

if TYPE_CHECKING:
    from app.services.prompt_registry import PromptRegistry


class PromptBuilder:
    """统一 Prompt 构建器 - 提供所有 Prompt 构建的链式入口。

    支持模式:
        - for_test_case: 测试用例生成（graph/linear）
        - for_test_data: 测试数据生成

    向后兼容静态方法:
        - build_graph_prompt: 流程图模式 Prompt
        - build_multimodal_prompt: 多模态 Prompt
        - build_linear_prompt: 线性模式 Prompt

    Args:
        registry: 可选的 PromptRegistry 实例，提供时优先从 DB 读取 Prompt 内容。
    """

    def __init__(self, registry: Optional["PromptRegistry"] = None) -> None:
        self._registry = registry

    def _resolve_prompt_content(self, key: str, fallback: str) -> str:
        """从 PromptRegistry 获取 Prompt 内容，DB 无记录时使用 fallback。

        Args:
            key: Prompt 唯一标识键。
            fallback: 硬编码 fallback 内容。

        Returns:
            Prompt 内容字符串。
        """
        if self._registry is not None:
            content = self._registry.get_prompt_content(key)
            if content:
                return content
        return fallback

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
        history_cases: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        db: Any = None,
        execution_feedback: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
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
            case_type: 用例类型约束。
            test_username: 测试账号（graph 模式）。
            test_password: 测试密码（graph 模式）。
            min_case_count: 期望最少用例数。
            history_cases: 历史参考用例列表，提供时注入 Prompt。
            project_id: 项目ID，用于加载领域 Few-shot 示例。
            db: 数据库会话，用于加载领域示例。
            execution_feedback: 历史执行失败归因文本。
            extra_context: 额外上下文字典（含 quality_feedback / task_type / task_context）。

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
                history_cases=history_cases,
                case_type=case_type,
                test_username=test_username,
                test_password=test_password,
                min_case_count=min_case_count,
            )
            # graph 模式同样支持 extra_context（质量反馈/任务类型）
            prompt = _append_extra_context_sections(prompt, extra_context)
            return {'prompt': prompt, 'weight_hint': 'graph'}

        prompt = _build_linear_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module, function=function,
            point=point, priority=priority,
            ui_specs=ui_specs,
            case_type=case_type,
            min_case_count=min_case_count,
            history_cases=history_cases,
            project_id=project_id,
            db=db,
            execution_feedback=execution_feedback,
        )
        prompt = _append_extra_context_sections(prompt, extra_context)
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
        history_cases: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        db: Any = None,
        execution_feedback: Optional[str] = None,
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
            extra_context: 额外上下文字典（含 quality_feedback 等键）。
            case_type: 用例类型约束。
            min_case_count: 最少用例数。
            history_cases: 历史参考用例列表。
            project_id: 项目ID，用于加载领域 Few-shot 示例。
            db: 数据库会话，用于加载领域示例。
            execution_feedback: 历史执行失败归因文本。

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
            min_case_count=min_case_count,
            history_cases=history_cases,
            project_id=project_id,
            db=db,
            execution_feedback=execution_feedback,
        )
        return _append_extra_context_sections(prompt, extra_context)
