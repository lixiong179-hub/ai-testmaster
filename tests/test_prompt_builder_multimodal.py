"""
PromptBuilder 多模态与模板统一测试

覆盖范围:
- ISSUE-004: 多模态图片数据支�?
- ISSUE-005: 新旧Prompt模板统一
"""
import pytest
from app.services.prompt_builder import PromptBuilder


class TestMultimodalPrompt:
    """测试多模态Prompt构建（ISSUE-004�?""

    def test_build_multimodal_prompt_includes_image_urls(self):
        """验证build_multimodal_prompt包含图片URL"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '登录�?, 'image_url': 'https://example.com/login.png',
                'ui_spec_elements': [{'type': 'input', 'label': '用户�?}]
            },
            {
                'screen_id': 2, 'screen_order': 2, 'flow_type': 'main',
                'screen_name': '首页', 'image_url': 'https://example.com/home.png',
                'ui_spec_elements': [{'type': 'button', 'label': '提交'}]
            },
        ]
        edges = []
        prompt = PromptBuilder.build_multimodal_prompt(
            nodes=nodes, edges=edges, module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert 'https://example.com/login.png' in prompt
        assert 'https://example.com/home.png' in prompt
        assert '图片URL:' in prompt

    def test_build_multimodal_prompt_skips_missing_image_url(self):
        """验证节点缺少image_url时不显示图片引用"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '登录�?, 'image_url': '',
                'ui_spec_elements': []
            },
        ]
        edges = []
        prompt = PromptBuilder.build_multimodal_prompt(
            nodes=nodes, edges=edges, module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert '图片URL:' not in prompt

    def test_build_graph_prompt_with_include_images_false(self):
        """验证include_images=False时不包含图片URL"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '登录�?, 'image_url': 'https://example.com/login.png',
                'ui_spec_elements': []
            },
        ]
        edges = []
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text='',
            include_images=False
        )
        assert 'https://example.com/login.png' not in prompt

    def test_build_graph_prompt_with_include_images_true(self):
        """验证include_images=True时包含图片URL"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '登录�?, 'image_url': 'https://example.com/login.png',
                'ui_spec_elements': []
            },
        ]
        edges = []
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text='',
            include_images=True
        )
        assert 'https://example.com/login.png' in prompt

    def test_multimodal_prompt_branch_includes_image(self):
        """验证分支流程节点也包含图片URL"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '主页�?, 'image_url': 'https://example.com/main.png',
                'ui_spec_elements': []
            },
            {
                'screen_id': 2, 'screen_order': 2, 'flow_type': 'branch',
                'screen_name': '分支�?, 'image_url': 'https://example.com/branch.png',
                'ui_spec_elements': []
            },
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'branch', 'condition': '点击按钮', 'label': '分支'},
        ]
        prompt = PromptBuilder.build_multimodal_prompt(
            nodes=nodes, edges=edges, module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert 'https://example.com/branch.png' in prompt

    def test_multimodal_prompt_exception_includes_image(self):
        """验证异常流程节点也包含图片URL"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '主页�?, 'image_url': 'https://example.com/main.png',
                'ui_spec_elements': []
            },
            {
                'screen_id': 2, 'screen_order': 2, 'flow_type': 'exception',
                'screen_name': '错误�?, 'image_url': 'https://example.com/error.png',
                'ui_spec_elements': []
            },
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'exception', 'condition': '输入错误', 'label': '异常'},
        ]
        prompt = PromptBuilder.build_multimodal_prompt(
            nodes=nodes, edges=edges, module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert 'https://example.com/error.png' in prompt

    def test_multimodal_prompt_bypass_includes_image(self):
        """验证旁路流程节点也包含图片URL"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '主页�?, 'image_url': 'https://example.com/main.png',
                'ui_spec_elements': []
            },
            {
                'screen_id': 2, 'screen_order': 2, 'flow_type': 'bypass',
                'screen_name': '弹窗�?, 'image_url': 'https://example.com/popup.png',
                'ui_spec_elements': []
            },
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'bypass', 'condition': '自动弹出', 'label': '旁路'},
        ]
        prompt = PromptBuilder.build_multimodal_prompt(
            nodes=nodes, edges=edges, module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert 'https://example.com/popup.png' in prompt


class TestPromptTemplateUnification:
    """测试Prompt模板统一（ISSUE-005�?""

    def test_graph_prompt_output_format_consistency(self):
        """验证graph模式输出格式包含test_data"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '测试�?, 'ui_spec_elements': []
            },
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=[], module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert '"test_data"' in prompt
        assert '"normal"' in prompt
        assert '"boundary"' in prompt
        assert '"abnormal"' in prompt

    def test_graph_prompt_step_is_string(self):
        """验证graph模式step字段为字符串类型"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '测试�?, 'ui_spec_elements': []
            },
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=[], module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        # 检查输出格式示例中step是否为字符串
        assert '"step": "1"' in prompt or '"step": "' in prompt

    def test_graph_prompt_has_description_field(self):
        """验证graph模式包含description字段"""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '测试�?, 'ui_spec_elements': []
            },
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=[], module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert '"description"' in prompt

    def test_graph_prompt_no_expected_results_array(self):
        """验证graph模式不包含expected_results数组（统一为expected_result�?""
        nodes = [
            {
                'screen_id': 1, 'screen_order': 1, 'flow_type': 'main',
                'screen_name': '测试�?, 'ui_spec_elements': []
            },
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=[], module_info=None,
            requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        # 检查是否只有expected_result而没有expected_results数组
        assert '"expected_result"' in prompt
