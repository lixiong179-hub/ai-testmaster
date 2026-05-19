"""
FlowTreeMixin 单元测试

覆盖范围：
- _build_flow_tree: 通用流程树构建
- _build_branch_tree: 分支流程树
- _build_exception_tree: 异常流程树
- _build_bypass_tree: 旁路流程树
- 边界场景：空数据、缺失节点、无效source/target
"""
import pytest
from app.services.case_generation.flow_tree_mixin import FlowTreeMixin


class MockEdge:
    """模拟FlowEdgeSchema对象"""
    def __init__(self, source, target, edge_type, condition=None):
        self.source = source
        self.target = target
        self.edge_type = edge_type
        self.condition = condition


class MockNode:
    """模拟FlowNodeSchema对象"""
    def __init__(self, screen_id, screen_order, screen_name, flow_type='main'):
        self.screen_id = screen_id
        self.screen_order = screen_order
        self.screen_name = screen_name
        self.flow_type = flow_type


class TestFlowTreeMixin:
    """测试FlowTreeMixin的流程树构建方法"""

    @pytest.fixture
    def mixin(self):
        return FlowTreeMixin()

    @pytest.fixture
    def main_nodes(self):
        return [
            MockNode(1, 1, '登录页'),
            MockNode(2, 2, '首页'),
            MockNode(3, 3, '详情页')
        ]

    @pytest.fixture
    def branch_edges(self):
        return [
            MockEdge('1', '4', 'branch', '点击注册'),
            MockEdge('2', '5', 'branch', '点击设置')
        ]

    @pytest.fixture
    def branch_nodes(self):
        return [
            MockNode(1, 1, '登录页', 'main'),
            MockNode(2, 2, '首页', 'main'),
            MockNode(4, 4, '注册页', 'branch'),
            MockNode(5, 5, '设置页', 'branch')
        ]

    def test_build_branch_tree_with_valid_data(self, mixin, branch_nodes, branch_edges):
        """测试正常分支流程树构建"""
        result = mixin._build_branch_tree(branch_edges, branch_nodes)

        assert len(result) == 2
        assert result[0]['source_step'] == 1
        assert result[0]['target_screen_id'] == 4
        assert result[0]['target_name'] == '注册页'
        assert result[0]['condition'] == '点击注册'
        assert result[1]['source_step'] == 2
        assert result[1]['target_name'] == '设置页'

    def test_build_exception_tree_with_valid_data(self, mixin, main_nodes):
        """测试正常异常流程树构建"""
        exception_edges = [
            MockEdge('1', '10', 'exception', '密码错误'),
            MockEdge('2', '11', 'exception', '网络超时')
        ]
        exception_nodes = main_nodes + [
            MockNode(10, 10, '错误提示页', 'exception'),
            MockNode(11, 11, '网络错误页', 'exception')
        ]

        result = mixin._build_exception_tree(exception_edges, exception_nodes)

        assert len(result) == 2
        assert result[0]['condition'] == '密码错误'
        assert result[0]['target_name'] == '错误提示页'
        assert result[1]['condition'] == '网络超时'

    def test_build_bypass_tree_with_valid_data(self, mixin, main_nodes):
        """测试正常旁路流程树构建"""
        bypass_edges = [
            MockEdge('1', '20', 'bypass', '自动弹出广告'),
        ]
        bypass_nodes = main_nodes + [
            MockNode(20, 20, '广告弹窗', 'bypass')
        ]

        result = mixin._build_bypass_tree(bypass_edges, bypass_nodes)

        assert len(result) == 1
        assert result[0]['condition'] == '自动弹出广告'
        assert result[0]['target_name'] == '广告弹窗'
        assert result[0]['source_step'] == 1

    def test_build_flow_tree_default_condition(self, mixin, main_nodes):
        """测试默认条件值"""
        bypass_edges = [MockEdge('1', '20', 'bypass')]
        bypass_nodes = main_nodes + [MockNode(20, 20, '弹窗', 'bypass')]

        result = mixin._build_flow_tree(bypass_edges, bypass_nodes, 'bypass', '自动弹出')

        assert len(result) == 1
        assert result[0]['condition'] == '自动弹出'

    def test_build_branch_tree_missing_target_node(self, mixin, branch_nodes):
        """测试目标节点不存在时的处理"""
        edges = [MockEdge('1', '999', 'branch', '条件')]

        result = mixin._build_branch_tree(edges, branch_nodes)

        assert len(result) == 0

    def test_build_branch_tree_missing_source_node(self, mixin, branch_nodes):
        """测试源节点不存在时的处理"""
        edges = [MockEdge('999', '4', 'branch', '条件')]

        result = mixin._build_branch_tree(edges, branch_nodes)

        assert len(result) == 0

    def test_build_branch_tree_invalid_source_type(self, mixin, branch_nodes):
        """测试无效source类型时的处理"""
        edges = [MockEdge('invalid', '4', 'branch', '条件')]

        result = mixin._build_branch_tree(edges, branch_nodes)

        assert len(result) == 0

    def test_build_branch_tree_invalid_target_type(self, mixin, branch_nodes):
        """测试无效target类型时的处理"""
        edges = [MockEdge('1', 'invalid', 'branch', '条件')]

        result = mixin._build_branch_tree(edges, branch_nodes)

        assert len(result) == 0

    def test_build_branch_tree_empty_edges(self, mixin, branch_nodes):
        """测试空边列表"""
        result = mixin._build_branch_tree([], branch_nodes)

        assert len(result) == 0

    def test_build_branch_tree_empty_nodes(self, mixin, branch_edges):
        """测试空节点列表"""
        result = mixin._build_branch_tree(branch_edges, [])

        assert len(result) == 0

    def test_build_branch_tree_none_condition(self, mixin, branch_nodes):
        """测试condition为None时使用默认值"""
        edges = [MockEdge('1', '4', 'branch', None)]

        result = mixin._build_branch_tree(edges, branch_nodes)

        assert len(result) == 1
        assert result[0]['condition'] == '未指定'

    def test_build_flow_tree_filters_by_edge_type(self, mixin, main_nodes):
        """测试通用方法按edge_type过滤"""
        mixed_edges = [
            MockEdge('1', '4', 'branch', '分支条件'),
            MockEdge('1', '5', 'exception', '异常条件'),
        ]
        mixed_nodes = main_nodes + [
            MockNode(4, 4, '分支页', 'branch'),
            MockNode(5, 5, '异常页', 'exception')
        ]

        branch_result = mixin._build_flow_tree(mixed_edges, mixed_nodes, 'branch', '默认')
        exception_result = mixin._build_flow_tree(mixed_edges, mixed_nodes, 'exception', '默认')

        assert len(branch_result) == 1
        assert branch_result[0]['condition'] == '分支条件'
        assert len(exception_result) == 1
        assert exception_result[0]['condition'] == '异常条件'

    def test_build_branch_tree_multiple_from_same_source(self, mixin, main_nodes):
        """测试同一源节点的多个分支"""
        edges = [
            MockEdge('1', '4', 'branch', '条件A'),
            MockEdge('1', '5', 'branch', '条件B'),
        ]
        nodes = main_nodes + [
            MockNode(4, 4, '分支A', 'branch'),
            MockNode(5, 5, '分支B', 'branch')
        ]

        result = mixin._build_branch_tree(edges, nodes)

        assert len(result) == 2
        assert result[0]['source_step'] == 1
        assert result[1]['source_step'] == 1
