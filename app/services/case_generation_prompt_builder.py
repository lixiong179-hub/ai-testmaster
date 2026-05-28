"""Backward-compatible prompt builder wrapper."""

from typing import Any, Dict, List, Optional

from app.services.prompt_builder import PromptBuilder as UnifiedPromptBuilder


class PromptBuilder:
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
        test_username: str = "testuser",
        test_password: str = "TestPass123",
        case_type: Optional[str] = None,
    ) -> str:
        return UnifiedPromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info=module_info,
            requirement_content=requirement_content,
            test_point_json=test_point_json,
            ui_specs_text=ui_specs_text,
            include_images=include_images,
            history_cases=history_cases,
            case_type=case_type,
            test_username=test_username,
            test_password=test_password,
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
    ) -> str:
        return UnifiedPromptBuilder.build_multimodal_prompt(
            nodes=nodes,
            edges=edges,
            module_info=module_info,
            requirement_content=requirement_content,
            test_point_json=test_point_json,
            ui_specs_text=ui_specs_text,
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
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        return UnifiedPromptBuilder.build_linear_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module,
            function=function,
            point=point,
            priority=priority,
            ui_specs=ui_specs,
            extra_context=extra_context,
        )


__all__ = ["PromptBuilder"]
