"""
PromptBuilder 单元测试

覆盖范围：
- build_graph_prompt: 空数据、仅主干、全类型混合、无效source、超长分支
- build_linear_prompt: 正常调用、参数传递
- _safe_int: 安全转换
- _find_main_step: 步骤查找
"""
import pytest
from app.services.prompt_builder import PromptBuilder, _safe_int, _find_main_step


class TestSafeInt:
    """测试_safe_int辅助函数"""

    def test_valid_int(self):
        assert _safe_int(123) == 123

    def test_valid_string(self):
        assert _safe_int("456") == 456

    def test_invalid_string(self):
        assert _safe_int("abc") is None

    def test_none_value(self):
        assert _safe_int(None) is None

    def test_empty_string(self):
        assert _safe_int("") is None

    def test_float_string(self):
        assert _safe_int("3.14") is None


class TestFindMainStep:
    """测试_find_main_step辅助函数"""

    @pytest.fixture
    def main_nodes(self):
        return [
            {"screen_id": 1, "screen_order": 1, "screen_name": "登录页"},
            {"screen_id": 2, "screen_order": 2, "screen_name": "首页"},
            {"screen_id": 3, "screen_order": 3, "screen_name": "详情页"}
        ]

    def test_find_existing_step(self, main_nodes):
        assert _find_main_step(main_nodes, 1) == "1"
        assert _find_main_step(main_nodes, 2) == "2"
        assert _find_main_step(main_nodes, 3) == "3"

    def test_find_non_existing_step(self, main_nodes):
        assert _find_main_step(main_nodes, 999) == "?"

    def test_empty_nodes(self):
        assert _find_main_step([], 1) == "?"


class TestBuildGraphPrompt:
    """测试build_graph_prompt方法"""

    @pytest.fixture
    def basic_nodes(self):
        return [
            {"screen_id": 1, "screen_order": 1, "screen_name": "登录页", "flow_type": "main", "ocr_text": "请输入账号", "ui_spec_elements": [{"type": "input", "label": "用户名"}]},
            {"screen_id": 2, "screen_order": 2, "screen_name": "首页", "flow_type": "main", "ocr_text": "欢迎回来", "ui_spec_elements": [{"type": "button", "label": "搜索"}]}
        ]

    @pytest.fixture
    def basic_edges(self):
        return [
            {"source": "1", "target": "2", "edge_type": "normal", "condition": None, "label": "登录成功"}
        ]

    def test_prompt_contains_role_definition(self, basic_nodes, basic_edges):
        prompt = PromptBuilder.build_graph_prompt(basic_nodes, basic_edges)
        assert "资深测试工程师" in prompt

    def test_prompt_contains_main_flow(self, basic_nodes, basic_edges):
        prompt = PromptBuilder.build_graph_prompt(basic_nodes, basic_edges)
        assert "主干流程" in prompt
        assert "登录页" in prompt
        assert "首页" in prompt

    def test_prompt_contains_ui_elements(self, basic_nodes, basic_edges):
        prompt = PromptBuilder.build_graph_prompt(basic_nodes, basic_edges)
        assert "input:用户名" in prompt
        assert "button:搜索" in prompt

    def test_prompt_contains_requirement(self, basic_nodes, basic_edges):
        prompt = PromptBuilder.build_graph_prompt(
            basic_nodes, basic_edges, requirement_content="用户需要登录系统"
        )
        assert "用户需要登录系统" in prompt

    def test_prompt_contains_test_point(self, basic_nodes, basic_edges):
        prompt = PromptBuilder.build_graph_prompt(
            basic_nodes, basic_edges, test_point_json='{"module": "登录", "point": "验证登录功能"}'
        )
        assert "验证登录功能" in prompt

    def test_prompt_contains_module_info(self, basic_nodes, basic_edges):
        prompt = PromptBuilder.build_graph_prompt(
            basic_nodes, basic_edges, module_info={"name": "用户系统", "description": "用户管理模块"}
        )
        assert "用户系统" in prompt

    def test_prompt_with_branch_flow(self, basic_nodes):
        nodes = basic_nodes + [
            {"screen_id": 3, "screen_order": 3, "screen_name": "注册页", "flow_type": "branch", "ocr_text": "填写注册信息", "ui_spec_elements": [{"type": "input", "label": "手机号"}]}
        ]
        edges = [
            {"source": "1", "target": "2", "edge_type": "normal", "condition": None, "label": "正常"},
            {"source": "1", "target": "3", "edge_type": "branch", "condition": "点击注册", "label": "去注册"}
        ]
        prompt = PromptBuilder.build_graph_prompt(nodes, edges)
        assert "分支流程" in prompt
        assert "点击注册" in prompt
        assert "注册页" in prompt

    def test_prompt_with_exception_flow(self, basic_nodes):
        nodes = basic_nodes + [
            {"screen_id": 4, "screen_order": 4, "screen_name": "错误页", "flow_type": "exception", "ocr_text": "密码错误", "ui_spec_elements": []}
        ]
        edges = [
            {"source": "1", "target": "2", "edge_type": "normal", "condition": None, "label": "正常"},
            {"source": "1", "target": "4", "edge_type": "exception", "condition": "密码错误", "label": "异常"}
        ]
        prompt = PromptBuilder.build_graph_prompt(nodes, edges)
        assert "异常流程" in prompt
        assert "密码错误" in prompt
        assert "错误页" in prompt

    def test_prompt_with_bypass_flow(self, basic_nodes):
        nodes = basic_nodes + [
            {"screen_id": 5, "screen_order": 5, "screen_name": "广告弹窗", "flow_type": "bypass", "ocr_text": "限时优惠", "ui_spec_elements": [{"type": "button", "label": "关闭"}]}
        ]
        edges = [
            {"source": "1", "target": "2", "edge_type": "normal", "condition": None, "label": "正常"},
            {"source": "2", "target": "5", "edge_type": "bypass", "condition": "自动弹出广告", "label": "广告"}
        ]
        prompt = PromptBuilder.build_graph_prompt(nodes, edges)
        assert "旁路流程" in prompt
        assert "自动弹出广告" in prompt
        assert "广告弹窗" in prompt

    def test_prompt_with_invalid_source_target(self, basic_nodes):
        edges = [
            {"source": "invalid", "target": "2", "edge_type": "branch", "condition": "条件", "label": "分支"}
        ]
        prompt = PromptBuilder.build_graph_prompt(basic_nodes, edges)
        assert "主干流程" in prompt

    def test_prompt_with_empty_data(self):
        prompt = PromptBuilder.build_graph_prompt([], [])
        assert "资深测试工程师" in prompt
        assert "主干流程" in prompt

    def test_prompt_contains_generation_rules(self, basic_nodes, basic_edges):
        prompt = PromptBuilder.build_graph_prompt(basic_nodes, basic_edges)
        assert "生成要求" in prompt
        assert "步骤不可颠倒" in prompt
        assert "JSON格式" in prompt

    def test_prompt_branch_index_overflow(self, basic_nodes):
        nodes = basic_nodes
        edges = [
            {"source": "1", "target": "2", "edge_type": "branch", "condition": f"条件{i}", "label": f"分支{i}"}
            for i in range(30)
        ]
        prompt = PromptBuilder.build_graph_prompt(nodes, edges)
        assert "分支流程" in prompt


class TestBuildLinearPrompt:
    """测试build_linear_prompt方法"""

    def test_calls_ai_prompt_mixin(self):
        prompt = PromptBuilder.build_linear_prompt(
            requirement_content="测试需求",
            ui_description="UI描述",
            module="测试模块",
            function="测试功能",
            point="测试点",
            priority=2
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_passes_ui_specs(self):
        ui_specs = [{"screen_name": "测试页", "ui_spec": {"elements": []}}]
        prompt = PromptBuilder.build_linear_prompt(
            requirement_content="",
            ui_description="",
            module="",
            function="",
            point="",
            priority=2,
            ui_specs=ui_specs
        )
        assert isinstance(prompt, str)
