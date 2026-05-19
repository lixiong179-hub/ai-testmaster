import pytest
from app.services.prompt_builder import PromptBuilder


class TestBuildGraphPrompt:
    def test_minimal(self):
        result = PromptBuilder.build_graph_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "开始"}],
            edges=[{"id": "e1", "source": "n1", "target": "n2"}],
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_module_info(self):
        result = PromptBuilder.build_graph_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "S"}],
            edges=[],
            module_info={"name": "登录模块", "description": "用户登录"},
        )
        assert "登录模块" in result

    def test_with_requirement(self):
        result = PromptBuilder.build_graph_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "S"}],
            edges=[],
            requirement_content="需求文档内容",
        )
        assert "需求文档内容" in result

    def test_with_test_point(self):
        result = PromptBuilder.build_graph_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "S"}],
            edges=[],
            test_point_json='[{"point": "验证登录"}]',
        )
        assert "验证登录" in result

    def test_with_ui_specs(self):
        result = PromptBuilder.build_graph_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "S"}],
            edges=[],
            ui_specs_text="UI规格文本",
        )
        assert "UI规格文本" in result

    def test_with_case_type(self):
        result = PromptBuilder.build_graph_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "S"}],
            edges=[],
            case_type="functional",
        )
        assert isinstance(result, str)

    def test_empty_nodes(self):
        result = PromptBuilder.build_graph_prompt(nodes=[], edges=[])
        assert isinstance(result, str)


class TestBuildMultimodalPrompt:
    def test_includes_images(self):
        result = PromptBuilder.build_multimodal_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "S", "image_url": "http://img.png"}],
            edges=[],
        )
        assert isinstance(result, str)

    def test_delegates_to_graph_prompt(self):
        result = PromptBuilder.build_multimodal_prompt(
            nodes=[{"id": "n1", "type": "start", "label": "S"}],
            edges=[],
            requirement_content="需求",
        )
        assert "需求" in result


class TestBuildLinearPrompt:
    def test_normal(self):
        result = PromptBuilder.build_linear_prompt(
            requirement_content="需求内容",
            ui_description="UI描述",
            module="登录模块",
            function="登录功能",
            point="验证登录",
            priority=1,
        )
        assert isinstance(result, str)
        assert "登录模块" in result
        assert "验证登录" in result

    def test_with_ui_specs(self):
        result = PromptBuilder.build_linear_prompt(
            requirement_content="需求",
            ui_description="UI",
            module="M",
            function="F",
            point="P",
            priority=2,
            ui_specs=[{"screen_id": 1, "title": "首页"}],
        )
        assert isinstance(result, str)

    def test_no_extra_context(self):
        result = PromptBuilder.build_linear_prompt(
            requirement_content="需求",
            ui_description="UI",
            module="M",
            function="F",
            point="P",
            priority=2,
        )
        assert isinstance(result, str)
