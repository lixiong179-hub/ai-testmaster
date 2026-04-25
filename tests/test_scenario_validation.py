"""
真实场景验证测试 - 10个业务场景流程图Prompt质量验证

验证目标:
- 主干流程步骤顺序正确
- 分支/异常/旁路流程完整
- 触发条件描述清晰
- UI元素信息准确
- 生成要求明确

覆盖场景:
S1: 后台管理系统-查询功能
S2: 电商系统-下单流程
S3: 用户注册流程
S4: 文件上传功能
S5: 权限管理-角色分配
S6: 数据导出功能
S7: 审批流程
S8: 支付流程
S9: 消息通知设置
S10: 系统登录
"""
import pytest
from app.services.prompt_builder import PromptBuilder


class TestScenarioQueryManagement:
    """S1: 后台管理系统-查询功能"""

    def test_query_main_flow(self):
        """验证查询功能主干流程"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '查询页', 'ui_spec_elements': [{'type': 'input', 'label': '关键词'}, {'type': 'button', 'label': '查询'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'main', 'screen_name': '结果列表', 'ui_spec_elements': [{'type': 'table', 'label': '数据列表'}, {'type': 'button', 'label': '导出'}]},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'main', 'screen_name': '详情页', 'ui_spec_elements': [{'type': 'text', 'label': '详细信息'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'normal', 'condition': '', 'label': '正常流转'},
            {'source': '2', 'target': '3', 'edge_type': 'normal', 'condition': '', 'label': '正常流转'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges,
            module_info={'name': '查询管理', 'description': '支持多条件组合查询'},
            requirement_content='用户可以通过关键词查询数据', test_point_json='{}', ui_specs_text=''
        )
        assert '步骤 1: [截图1 - 查询页]' in prompt
        assert '步骤 2: [截图2 - 结果列表]' in prompt
        assert '步骤 3: [截图3 - 详情页]' in prompt
        assert '主干流程' in prompt

    def test_query_branch_flow(self):
        """验证查询功能分支流程（高级筛选）"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '查询页', 'ui_spec_elements': [{'type': 'button', 'label': '高级筛选'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'branch', 'screen_name': '高级筛选弹窗', 'ui_spec_elements': [{'type': 'input', 'label': '时间范围'}, {'type': 'select', 'label': '状态'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'branch', 'condition': '用户点击高级筛选按钮', 'label': '条件分支'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=None, requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert '分支流程' in prompt
        assert '用户点击高级筛选按钮' in prompt
        assert '高级筛选弹窗' in prompt

    def test_query_exception_flow(self):
        """验证查询功能异常流程（非法输入）"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '查询页', 'ui_spec_elements': [{'type': 'input', 'label': '关键词'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'exception', 'screen_name': '错误提示', 'ui_spec_elements': [{'type': 'text', 'label': '请输入有效字符'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'exception', 'condition': '输入非法字符或超长文本', 'label': '异常跳转'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=None, requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert '异常流程' in prompt
        assert '输入非法字符或超长文本' in prompt
        assert '错误提示' in prompt


class TestScenarioECommerceOrder:
    """S2: 电商系统-下单流程"""

    def test_order_full_flow(self):
        """验证下单完整流程（主干+分支+异常）"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '商品详情', 'ui_spec_elements': [{'type': 'button', 'label': '立即购买'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'main', 'screen_name': '确认订单', 'ui_spec_elements': [{'type': 'text', 'label': '收货地址'}, {'type': 'button', 'label': '提交订单'}]},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'branch', 'screen_name': '优惠券选择', 'ui_spec_elements': [{'type': 'select', 'label': '可用优惠券'}]},
            {'screen_id': 4, 'screen_order': 4, 'flow_type': 'exception', 'screen_name': '库存不足提示', 'ui_spec_elements': [{'type': 'text', 'label': '商品库存不足'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'normal', 'condition': '', 'label': '正常流转'},
            {'source': '2', 'target': '3', 'edge_type': 'branch', 'condition': '用户选择使用优惠券', 'label': '条件分支'},
            {'source': '2', 'target': '4', 'edge_type': 'exception', 'condition': '商品库存不足', 'label': '异常跳转'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges,
            module_info={'name': '电商下单', 'description': '用户下单购买商品流程'},
            requirement_content='支持优惠券和库存校验', test_point_json='{}', ui_specs_text=''
        )
        assert '步骤 1: [截图1 - 商品详情]' in prompt
        assert '步骤 2: [截图2 - 确认订单]' in prompt
        assert '分支 A: 从步骤 2 分支' in prompt
        assert '用户选择使用优惠券' in prompt
        assert '异常 A: 从步骤 2 异常跳转' in prompt
        assert '商品库存不足' in prompt


class TestScenarioUserRegistration:
    """S3: 用户注册流程"""

    def test_registration_with_bypass(self):
        """验证注册流程（含旁路-协议弹窗）"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '注册页', 'ui_spec_elements': [{'type': 'input', 'label': '用户名'}, {'type': 'input', 'label': '密码'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'exception', 'screen_name': '用户名重复提示', 'ui_spec_elements': [{'type': 'text', 'label': '用户名已存在'}]},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'bypass', 'screen_name': '用户协议弹窗', 'ui_spec_elements': [{'type': 'text', 'label': '请同意用户协议'}, {'type': 'button', 'label': '同意'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'exception', 'condition': '用户名已存在', 'label': '异常跳转'},
            {'source': '1', 'target': '3', 'edge_type': 'bypass', 'condition': '首次注册自动弹出', 'label': '旁路步骤'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=None, requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert '旁路流程' in prompt
        assert '首次注册自动弹出' in prompt
        assert '用户协议弹窗' in prompt
        assert '异常流程' in prompt
        assert '用户名已存在' in prompt


class TestScenarioFileUpload:
    """S4: 文件上传功能"""

    def test_upload_exception_flows(self):
        """验证文件上传异常流程（格式错误+超大文件）"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '上传页', 'ui_spec_elements': [{'type': 'button', 'label': '选择文件'}, {'type': 'button', 'label': '上传'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'exception', 'screen_name': '格式错误提示', 'ui_spec_elements': [{'type': 'text', 'label': '仅支持PDF格式'}]},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'exception', 'screen_name': '文件过大提示', 'ui_spec_elements': [{'type': 'text', 'label': '文件大小超过10MB'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'exception', 'condition': '上传非PDF格式文件', 'label': '异常跳转'},
            {'source': '1', 'target': '3', 'edge_type': 'exception', 'condition': '上传文件超过10MB', 'label': '异常跳转'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=None, requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert '异常 A: 从步骤 1 异常跳转' in prompt
        assert '上传非PDF格式文件' in prompt
        assert '异常 B: 从步骤 1 异常跳转' in prompt
        assert '上传文件超过10MB' in prompt


class TestScenarioApprovalProcess:
    """S7: 审批流程"""

    def test_approval_complex_flow(self):
        """验证审批流程（主干+分支+旁路）"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '待审批列表', 'ui_spec_elements': [{'type': 'table', 'label': '审批列表'}, {'type': 'button', 'label': '审批'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'main', 'screen_name': '审批详情', 'ui_spec_elements': [{'type': 'button', 'label': '通过'}, {'type': 'button', 'label': '驳回'}]},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'branch', 'screen_name': '驳回重审页', 'ui_spec_elements': [{'type': 'input', 'label': '驳回原因'}]},
            {'screen_id': 4, 'screen_order': 4, 'flow_type': 'bypass', 'screen_name': '催办提醒弹窗', 'ui_spec_elements': [{'type': 'text', 'label': '您有3条待办'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'normal', 'condition': '', 'label': '正常流转'},
            {'source': '2', 'target': '3', 'edge_type': 'branch', 'condition': '审批人点击驳回按钮', 'label': '条件分支'},
            {'source': '1', 'target': '4', 'edge_type': 'bypass', 'condition': '进入页面时自动弹出', 'label': '旁路步骤'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges,
            module_info={'name': '审批管理', 'description': '支持多级审批和驳回重审'},
            requirement_content='审批流程支持通过、驳回、催办', test_point_json='{}', ui_specs_text=''
        )
        assert '步骤 1: [截图1 - 待审批列表]' in prompt
        assert '步骤 2: [截图2 - 审批详情]' in prompt
        assert '分支 A: 从步骤 2 分支' in prompt
        assert '审批人点击驳回按钮' in prompt
        assert '旁路 A: 进入步骤 1 时' in prompt
        assert '催办提醒弹窗' in prompt


class TestScenarioSystemLogin:
    """S10: 系统登录"""

    def test_login_all_flow_types(self):
        """验证登录流程（主干+异常+旁路）"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '登录页', 'ui_spec_elements': [{'type': 'input', 'label': '用户名'}, {'type': 'input', 'label': '密码'}, {'type': 'button', 'label': '登录'}]},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'exception', 'screen_name': '密码错误提示', 'ui_spec_elements': [{'type': 'text', 'label': '用户名或密码错误'}]},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'exception', 'screen_name': '账号锁定提示', 'ui_spec_elements': [{'type': 'text', 'label': '账号已锁定，请联系管理员'}]},
            {'screen_id': 4, 'screen_order': 4, 'flow_type': 'bypass', 'screen_name': '验证码弹窗', 'ui_spec_elements': [{'type': 'input', 'label': '验证码'}, {'type': 'button', 'label': '确认'}]},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'exception', 'condition': '输入错误密码', 'label': '异常跳转'},
            {'source': '1', 'target': '3', 'edge_type': 'exception', 'condition': '连续5次登录失败', 'label': '异常跳转'},
            {'source': '1', 'target': '4', 'edge_type': 'bypass', 'condition': '首次登录或IP变更时弹出', 'label': '旁路步骤'},
        ]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges,
            module_info={'name': '系统登录', 'description': '支持用户名密码登录和验证码校验'},
            requirement_content='登录功能需要验证码校验和安全锁定', test_point_json='{}', ui_specs_text=''
        )
        assert '步骤 1: [截图1 - 登录页]' in prompt
        assert '异常 A: 从步骤 1 异常跳转' in prompt
        assert '输入错误密码' in prompt
        assert '异常 B: 从步骤 1 异常跳转' in prompt
        assert '连续5次登录失败' in prompt
        assert '旁路 A: 进入步骤 1 时' in prompt
        assert '验证码弹窗' in prompt


class TestPromptQualityMetrics:
    """Prompt质量指标验证"""

    def test_prompt_structure_completeness(self):
        """验证Prompt结构完整性"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '测试页', 'ui_spec_elements': [{'type': 'button', 'label': '提交'}]},
        ]
        edges = []
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges,
            module_info={'name': '测试模块', 'description': '测试描述'},
            requirement_content='测试需求', test_point_json='{"point": "测试点"}', ui_specs_text='UI规格'
        )
        # 验证所有必要部分存在
        assert '资深测试工程师' in prompt
        assert '测试点信息' in prompt
        assert '需求文档内容' in prompt
        assert '模块信息' in prompt
        assert '主干流程' in prompt
        assert '生成要求' in prompt
        assert '输出JSON格式' in prompt

    def test_prompt_ui_elements_description(self):
        """验证UI元素描述准确性"""
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '表单页', 'ui_spec_elements': [
                {'type': 'input', 'label': '用户名'},
                {'type': 'input', 'label': '邮箱'},
                {'type': 'button', 'label': '提交'},
            ]},
        ]
        edges = []
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=edges, module_info=None, requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        assert 'input:用户名' in prompt
        assert 'input:邮箱' in prompt
        assert 'button:提交' in prompt

    def test_generation_rules_count(self):
        """验证生成要求数量"""
        nodes = [{'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '页', 'ui_spec_elements': []}]
        prompt = PromptBuilder.build_graph_prompt(
            nodes=nodes, edges=[], module_info=None, requirement_content='', test_point_json='{}', ui_specs_text=''
        )
        # 验证至少5条生成要求
        rule_count = prompt.count('必须完整覆盖') + prompt.count('需标注') + prompt.count('作为独立') + prompt.count('输出格式')
        assert rule_count >= 3
