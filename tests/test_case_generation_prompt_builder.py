"""
PromptBuilder 单元测试

覆盖范围：
- build_graph_prompt: 主干/分支/异常/旁路流程的 Prompt 生成
- build_linear_prompt: 线性模式的 Prompt 生成
- 边界场景：空节点、空连线、缺失字段、异常数据
"""
import pytest
from app.services.prompt_builder import PromptBuilder


class TestBuildGraphPrompt:
    """测试 build_graph_prompt 方法"""

    def test_build_graph_prompt_main_flow_only(self):
        """测试仅主干流程的 Prompt 生成"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [
                    {'type': 'input', 'label': '用户名'},
                    {'type': 'input', 'label': '密码'},
                    {'type': 'button', 'label': '登录'}
                ],
                'summary': '用户登录页面'
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'main',
                'screen_name': '首页',
                'ui_spec_elements': [
                    {'type': 'text', 'label': '欢迎'},
                    {'type': 'button', 'label': '退出'}
                ],
                'summary': '系统首页'
            }
        ]
        edges = []
        module_info = {'name': '用户模块', 'description': '用户登录相关'}
        requirement_content = '用户需要能够登录系统'
        test_point_json = '{"module": "用户", "function": "登录", "point": "登录验证", "priority": 1}'
        ui_specs_text = ''

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info=module_info,
            requirement_content=requirement_content,
            test_point_json=test_point_json,
            ui_specs_text=ui_specs_text
        )

        assert '主干流程' in result
        assert '步骤 1: [截图1 - 登录页]' in result
        assert '步骤 2: [截图2 - 首页]' in result
        assert 'input:用户名' in result
        assert 'button:登录' in result
        assert '用户模块' in result
        assert '用户登录相关' in result
        assert '用户需要能够登录系统' in result

    def test_build_graph_prompt_with_branch_flow(self):
        """测试包含分支流程的 Prompt 生成"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [{'type': 'button', 'label': '登录'}],
                'summary': ''
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'main',
                'screen_name': '首页',
                'ui_spec_elements': [{'type': 'text', 'label': '欢迎'}],
                'summary': ''
            },
            {
                'screen_id': 3,
                'screen_order': 3,
                'flow_type': 'branch',
                'screen_name': '忘记密码页',
                'ui_spec_elements': [{'type': 'input', 'label': '邮箱'}],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': '1',
                'target': '2',
                'edge_type': 'normal',
                'condition': '',
                'label': ''
            },
            {
                'source': '1',
                'target': '3',
                'edge_type': 'branch',
                'condition': '点击忘记密码',
                'label': '忘记密码'
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '主干流程' in result
        assert '分支流程' in result
        assert '分支 A: 从步骤 1 分支' in result
        assert '触发条件「点击忘记密码」' in result
        assert 'input:邮箱' in result

    def test_build_graph_prompt_with_exception_flow(self):
        """测试包含异常流程的 Prompt 生成"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [{'type': 'button', 'label': '登录'}],
                'summary': ''
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'exception',
                'screen_name': '错误提示页',
                'ui_spec_elements': [{'type': 'text', 'label': '密码错误'}],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': '1',
                'target': '2',
                'edge_type': 'exception',
                'condition': '密码错误',
                'label': '异常'
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '异常流程' in result
        assert '异常 A: 从步骤 1 异常跳转' in result
        assert '异常场景「密码错误」' in result
        assert 'text:密码错误' in result

    def test_build_graph_prompt_with_bypass_flow(self):
        """测试包含旁路流程的 Prompt 生成"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '首页',
                'ui_spec_elements': [{'type': 'text', 'label': '欢迎'}],
                'summary': ''
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'bypass',
                'screen_name': '弹窗广告',
                'ui_spec_elements': [{'type': 'button', 'label': '关闭'}],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': '1',
                'target': '2',
                'edge_type': 'bypass',
                'condition': '自动弹出',
                'label': '广告'
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '旁路流程' in result
        assert '旁路 A: 进入步骤 1 时自动弹出' in result
        assert 'button:关闭' in result

    def test_build_graph_prompt_empty_elements(self):
        """测试节点无 UI 元素时的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '空白页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=[],
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '步骤 1: [截图1 - 空白页]' in result
        assert '元素: ' in result

    def test_build_graph_prompt_missing_fields(self):
        """测试节点缺失字段时的容错处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '测试页'
                # 缺少 ui_spec_elements 和 summary
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=[],
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '步骤 1: [截图1 - 测试页]' in result

    def test_build_graph_prompt_invalid_edge_source_target(self):
        """测试无效连线 source/target 的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '页面1',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': 'invalid',
                'target': '999',
                'edge_type': 'branch',
                'condition': '测试',
                'label': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        # 无效连线的 target (999) 不在 nodes 中，所以不会生成分支流程
        # 但 edge_type 是 branch，所以会进入 branch_edges 分支
        # 由于 _safe_int('999') 返回 999，但 node_map 中没有 999，所以会 continue 跳过
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_graph_prompt_with_ui_specs_text(self):
        """测试包含 UI 规格文本的 Prompt 生成"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        ui_specs_text = '屏幕 1: {"elements": [{"type": "input", "label": "用户名"}]}'

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=[],
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=ui_specs_text
        )

        assert 'UI原型图解析结果' in result
        assert ui_specs_text in result

    def test_build_graph_prompt_without_requirement(self):
        """测试无需求文档时的 Prompt 生成"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=[],
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '[无需求文档内容]' in result

    def test_build_graph_prompt_multiple_branches(self):
        """测试多个分支流程的 Prompt 生成"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'branch',
                'screen_name': '注册页',
                'ui_spec_elements': [],
                'summary': ''
            },
            {
                'screen_id': 3,
                'screen_order': 3,
                'flow_type': 'branch',
                'screen_name': '忘记密码页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': '1',
                'target': '2',
                'edge_type': 'branch',
                'condition': '点击注册',
                'label': ''
            },
            {
                'source': '1',
                'target': '3',
                'edge_type': 'branch',
                'condition': '点击忘记密码',
                'label': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '分支 A: 从步骤 1 分支' in result
        assert '分支 B: 从步骤 1 分支' in result

    def test_build_graph_prompt_no_module_info(self):
        """测试 module_info 为 None 时的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=[],
            module_info=None,  # 测试 None 值
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        assert '模块信息' not in result  # 确保不会添加模块信息部分

    def test_build_graph_prompt_with_ui_specs_text_present(self):
        """测试 ui_specs_text 存在时的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        ui_specs_text = 'UI原型图规格内容'

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=[],
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=ui_specs_text  # 测试非空值
        )

        assert 'UI原型图解析结果' in result
        assert ui_specs_text in result

    def test_build_graph_prompt_find_main_step_not_found(self):
        """测试 _find_main_step 函数在未找到节点时的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': '1',
                'target': '999',  # 不存在的节点ID
                'edge_type': 'branch',
                'condition': '测试条件',
                'label': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        # 验证即使目标节点不存在，也不会导致错误
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_graph_prompt_without_test_point(self):
        """测试无测试点信息时的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=[],
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='',  # 空字符串
            ui_specs_text=''
        )

        # 验证不会添加测试点信息部分
        assert '## 测试点信息' not in result

    def test_build_graph_prompt_invalid_edge_types(self):
        """测试无效 edge source/target 类型的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'exception',
                'screen_name': '错误页',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': None,  # 测试 None 值
                'target': 2,
                'edge_type': 'exception',
                'condition': '测试',
                'label': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        # 验证无效边被跳过
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_graph_prompt_invalid_bypass_edge(self):
        """测试旁路流程中无效边的处理"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'bypass',
                'screen_name': '弹窗',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': 'invalid',  # 无效 source
                'target': 2,
                'edge_type': 'bypass',
                'condition': '自动弹出',
                'label': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        # 验证无效旁路边被跳过
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_graph_prompt_find_main_step_not_found_in_bypass(self):
        """测试旁路流程中 _find_main_step 未找到节点时返回 '?'"""
        nodes = [
            {
                'screen_id': 1,
                'screen_order': 1,
                'flow_type': 'main',
                'screen_name': '登录页',
                'ui_spec_elements': [],
                'summary': ''
            },
            {
                'screen_id': 2,
                'screen_order': 2,
                'flow_type': 'bypass',
                'screen_name': '弹窗',
                'ui_spec_elements': [],
                'summary': ''
            }
        ]
        edges = [
            {
                'source': '999',  # 不存在的节点ID
                'target': 2,
                'edge_type': 'bypass',
                'condition': '自动弹出',
                'label': ''
            }
        ]

        result = PromptBuilder.build_graph_prompt(
            nodes=nodes,
            edges=edges,
            module_info={'name': '', 'description': ''},
            requirement_content='',
            test_point_json='{}',
            ui_specs_text=''
        )

        # 验证即使 source 节点不在主干流程中，也能正常处理
        assert isinstance(result, str)
        assert len(result) > 0


class TestBuildLinearPrompt:
    """测试 build_linear_prompt 方法"""

    def test_build_linear_prompt_basic(self):
        """测试基本线性模式 Prompt 生成"""
        ui_specs = [
            {
                'screen_id': 1,
                'screen_name': '登录页',
                'ui_spec': {
                    'elements': [
                        {'type': 'input', 'label': '用户名'},
                        {'type': 'button', 'label': '登录'}
                    ]
                },
                'summary': '用户登录页面'
            }
        ]

        result = PromptBuilder.build_linear_prompt(
            requirement_content='用户需要能够登录系统',
            ui_description='登录页面',
            module='用户模块',
            function='登录',
            point='用户登录功能',
            priority=2,
            ui_specs=ui_specs
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert '用户模块' in result
        assert '登录' in result

    def test_build_linear_prompt_empty_ui_specs(self):
        """测试空 UI 规格列表的处理"""
        result = PromptBuilder.build_linear_prompt(
            requirement_content='需求内容',
            ui_description='',
            module='测试模块',
            function='测试功能',
            point='测试点',
            priority=1,
            ui_specs=[]
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert '测试模块' in result

    def test_build_linear_prompt_missing_requirement(self):
        """测试无需求文档时的处理"""
        result = PromptBuilder.build_linear_prompt(
            requirement_content='',
            ui_description='页面描述',
            module='模块',
            function='功能',
            point='测试点',
            priority=2,
            ui_specs=None
        )

        assert isinstance(result, str)
        assert len(result) > 0
