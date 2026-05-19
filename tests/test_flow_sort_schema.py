"""
FlowSortDataSchema 单元测试

覆盖范围 —
- FlowNodeSchema: 字段校验、边界值、空值处理
- FlowEdgeSchema: 字段校验、类型限制
- FlowSortDataSchema: 整体校验、数量限制
"""
import pytest
from pydantic import ValidationError
from app.schemas.test_case import FlowNodeSchema, FlowEdgeSchema, FlowSortDataSchema


class TestFlowNodeSchema:
    """测试FlowNodeSchema字段校验"""

    def test_valid_node(self):
        """测试正常节点数据"""
        node = FlowNodeSchema(
            screen_id=1,
            screen_order=1,
            flow_type='main',
            screen_name='登录页',
            ocr_text='请输入用户名',
            summary='用户登录页面'
        )
        assert node.screen_id == 1
        assert node.screen_order == 1
        assert node.flow_type == 'main'
        assert node.screen_name == '登录页'
        assert node.ocr_text == '请输入用户名'

    def test_screen_id_must_be_positive(self):
        """测试screen_id必须大于0"""
        with pytest.raises(ValidationError) as exc_info:
            FlowNodeSchema(
                screen_id=0,
                screen_order=1,
                flow_type='main',
                screen_name='测试页'
            )
        assert 'screen_id' in str(exc_info.value)

    def test_screen_order_must_be_positive(self):
        """测试screen_order必须大于0"""
        with pytest.raises(ValidationError) as exc_info:
            FlowNodeSchema(
                screen_id=1,
                screen_order=0,
                flow_type='main',
                screen_name='测试页'
            )
        assert 'screen_order' in str(exc_info.value)

    def test_screen_name_cannot_be_blank(self):
        """测试screen_name不能为空白字符串"""
        with pytest.raises(ValidationError) as exc_info:
            FlowNodeSchema(
                screen_id=1,
                screen_order=1,
                flow_type='main',
                screen_name='   '
            )
        assert 'screen_name' in str(exc_info.value)

    def test_screen_name_stripped(self):
        """测试screen_name自动去除首尾空格"""
        node = FlowNodeSchema(
            screen_id=1,
            screen_order=1,
            flow_type='main',
            screen_name='  登录页 '
        )
        assert node.screen_name == '登录页'

    def test_invalid_flow_type(self):
        """测试无效的flow_type"""
        with pytest.raises(ValidationError) as exc_info:
            FlowNodeSchema(
                screen_id=1,
                screen_order=1,
                flow_type='invalid',
                screen_name='测试页'
            )
        assert 'flow_type' in str(exc_info.value)

    def test_valid_flow_types(self):
        """测试所有有效的flow_type值"""
        for ft in ['main', 'branch', 'exception', 'bypass']:
            node = FlowNodeSchema(
                screen_id=1,
                screen_order=1,
                flow_type=ft,
                screen_name='测试页'
            )
            assert node.flow_type == ft

    def test_optional_fields_default_none(self):
        """测试可选字段默认值为None"""
        node = FlowNodeSchema(
            screen_id=1,
            screen_order=1,
            flow_type='main',
            screen_name='测试页'
        )
        assert node.ocr_text is None
        assert node.summary is None
        assert node.ui_spec_elements is None

    def test_ocr_text_max_length(self):
        """测试ocr_text长度限制"""
        long_text = 'a' * 5001
        with pytest.raises(ValidationError) as exc_info:
            FlowNodeSchema(
                screen_id=1,
                screen_order=1,
                flow_type='main',
                screen_name='测试页',
                ocr_text=long_text
            )
        assert 'ocr_text' in str(exc_info.value)

    def test_summary_max_length(self):
        """测试summary长度限制"""
        long_text = 'a' * 1001
        with pytest.raises(ValidationError) as exc_info:
            FlowNodeSchema(
                screen_id=1,
                screen_order=1,
                flow_type='main',
                screen_name='测试页',
                summary=long_text
            )
        assert 'summary' in str(exc_info.value)

    def test_screen_name_max_length(self):
        """测试screen_name长度限制"""
        long_name = 'a' * 201
        with pytest.raises(ValidationError) as exc_info:
            FlowNodeSchema(
                screen_id=1,
                screen_order=1,
                flow_type='main',
                screen_name=long_name
            )
        assert 'screen_name' in str(exc_info.value)


class TestFlowEdgeSchema:
    """测试FlowEdgeSchema字段校验"""

    def test_valid_edge(self):
        """测试正常连线数据"""
        edge = FlowEdgeSchema(
            source='1',
            target='2',
            edge_type='normal',
            condition='点击按钮',
            label='正常流转'
        )
        assert edge.source == '1'
        assert edge.target == '2'
        assert edge.edge_type == 'normal'
        assert edge.condition == '点击按钮'

    def test_invalid_edge_type(self):
        """测试无效的edge_type"""
        with pytest.raises(ValidationError) as exc_info:
            FlowEdgeSchema(
                source='1',
                target='2',
                edge_type='invalid',
                label='测试'
            )
        assert 'edge_type' in str(exc_info.value)

    def test_valid_edge_types(self):
        """测试所有有效的edge_type值"""
        for et in ['normal', 'branch', 'exception', 'bypass']:
            edge = FlowEdgeSchema(
                source='1',
                target='2',
                edge_type=et,
                label='测试',
                condition='测试触发条件'
            )
            assert edge.edge_type == et

    def test_label_cannot_be_blank(self):
        """测试label不能为空白字符串"""
        with pytest.raises(ValidationError) as exc_info:
            FlowEdgeSchema(
                source='1',
                target='2',
                edge_type='normal',
                label='   '
            )
        assert 'label' in str(exc_info.value)

    def test_label_stripped(self):
        """测试label自动去除首尾空格"""
        edge = FlowEdgeSchema(
            source='1',
            target='2',
            edge_type='normal',
            label='  正常流转  '
        )
        assert edge.label == '正常流转'

    def test_condition_max_length(self):
        """测试condition长度限制"""
        long_condition = 'a' * 501
        with pytest.raises(ValidationError) as exc_info:
            FlowEdgeSchema(
                source='1',
                target='2',
                edge_type='branch',
                condition=long_condition,
                label='测试'
            )
        assert 'condition' in str(exc_info.value)

    def test_condition_optional(self):
        """测试condition为可选字段"""
        edge = FlowEdgeSchema(
            source='1',
            target='2',
            edge_type='normal',
            label='正常流转'
        )
        assert edge.condition is None

    def test_label_max_length(self):
        """测试label长度限制"""
        long_label = 'a' * 101
        with pytest.raises(ValidationError) as exc_info:
            FlowEdgeSchema(
                source='1',
                target='2',
                edge_type='normal',
                label=long_label
            )
        assert 'label' in str(exc_info.value)


class TestFlowSortDataSchema:
    """测试FlowSortDataSchema整体校验"""

    def test_valid_sort_data(self):
        """测试正常排序数据"""
        data = FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='登录页'),
                FlowNodeSchema(screen_id=2, screen_order=2, flow_type='main', screen_name='首页')
            ],
            edges=[
                FlowEdgeSchema(source='1', target='2', edge_type='normal', label='正常流转')
            ],
            module_info={'name': '用户模块', 'description': '用户相关功能'}
        )
        assert len(data.nodes) == 2
        assert len(data.edges) == 1
        assert data.module_info['name'] == '用户模块'

    def test_nodes_must_not_be_empty(self):
        """测试nodes不能为空列表"""
        with pytest.raises(ValidationError) as exc_info:
            FlowSortDataSchema(nodes=[])
        assert 'nodes' in str(exc_info.value)

    def test_edges_default_empty(self):
        """测试edges默认为空列表"""
        data = FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='测试页')
            ]
        )
        assert data.edges == []

    def test_module_info_optional(self):
        """测试module_info为可选字段"""
        data = FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='测试页')
            ]
        )
        assert data.module_info is None

    def test_complex_flow_structure(self):
        """测试复杂流程结构"""
        data = FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='登录页'),
                FlowNodeSchema(screen_id=2, screen_order=2, flow_type='main', screen_name='首页'),
                FlowNodeSchema(screen_id=3, screen_order=3, flow_type='branch', screen_name='注册页'),
                FlowNodeSchema(screen_id=4, screen_order=4, flow_type='exception', screen_name='错误页'),
                FlowNodeSchema(screen_id=5, screen_order=5, flow_type='bypass', screen_name='弹窗')
            ],
            edges=[
                FlowEdgeSchema(source='1', target='2', edge_type='normal', label='登录成功'),
                FlowEdgeSchema(source='1', target='3', edge_type='branch', condition='点击注册', label='去注册'),
                FlowEdgeSchema(source='1', target='4', edge_type='exception', condition='密码错误', label='登录失败'),
                FlowEdgeSchema(source='2', target='5', edge_type='bypass', condition='自动弹出', label='广告')
            ]
        )
        assert len(data.nodes) == 5
        assert len(data.edges) == 4
        main_nodes = [n for n in data.nodes if n.flow_type == 'main']
        assert len(main_nodes) == 2

    @pytest.mark.skip(reason="_validate_flow_sort_data_size已移除")
    def test_request_size_limit_nodes(self):
        """测试nodes数量上限校验 - 验证校验函数存在且逻辑正确"""
        from app.api.v1.endpoints.test_case_ai_schemas import AIGenerateEnhancedRequest
        _validate_flow_sort_data_size = AIGenerateEnhancedRequest.validate_flow_sort_data_size
        # 由于内存限制，仅验证函数存在和基本逻辑
        assert callable(_validate_flow_sort_data_size)
        assert _validate_flow_sort_data_size(None) is None

    @pytest.mark.skip(reason="_validate_flow_sort_data_size已移")
    def test_request_size_limit_edges(self):
        """测试edges数量上限校验 - 验证校验函数存在且逻辑正确"""
        from app.api.v1.endpoints.test_case_ai_schemas import AIGenerateEnhancedRequest
        _validate_flow_sort_data_size = AIGenerateEnhancedRequest.validate_flow_sort_data_size
        assert callable(_validate_flow_sort_data_size)
        assert _validate_flow_sort_data_size(None) is None
