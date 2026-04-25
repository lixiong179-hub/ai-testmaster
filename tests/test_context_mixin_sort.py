"""
_sort_flow_nodes 单元测试

覆盖范围：
- 有 main_order 时按 main_order 排序
- 无 main_order 时回退到 screen_order
- main 节点在前，branch 在后
- main_order 优先于 screen_order
"""
from typing import Optional
import pytest
from app.services.case_generation.context_mixin import _sort_flow_nodes


class MockNode:
    """模拟FlowNodeSchema对象，支持main_order属性"""

    def __init__(
        self,
        screen_id: int,
        screen_order: int,
        screen_name: str,
        flow_type: str = 'main',
        main_order: Optional[int] = None
    ):
        self.screen_id = screen_id
        self.screen_order = screen_order
        self.screen_name = screen_name
        self.flow_type = flow_type
        self.main_order = main_order


class TestSortFlowNodes:
    """测试_sort_flow_nodes排序逻辑"""

    def test_sort_with_main_order(self) -> None:
        """测试有main_order时按main_order排序"""
        nodes = [
            MockNode(1, 3, '第三步', 'main', main_order=3),
            MockNode(2, 1, '第一步', 'main', main_order=1),
            MockNode(3, 2, '第二步', 'main', main_order=2),
        ]

        result = _sort_flow_nodes(nodes)

        assert result[0].screen_name == '第一步'
        assert result[1].screen_name == '第二步'
        assert result[2].screen_name == '第三步'

    def test_sort_without_main_order_fallback(self) -> None:
        """测试无main_order时回退到screen_order排序"""
        nodes = [
            MockNode(1, 3, '第三步', 'main', main_order=None),
            MockNode(2, 1, '第一步', 'main', main_order=None),
            MockNode(3, 2, '第二步', 'main', main_order=None),
        ]

        result = _sort_flow_nodes(nodes)

        assert result[0].screen_name == '第一步'
        assert result[1].screen_name == '第二步'
        assert result[2].screen_name == '第三步'

    def test_sort_mixed_main_and_branch(self) -> None:
        """测试main节点在前，branch节点在后"""
        nodes = [
            MockNode(4, 4, '分支页', 'branch'),
            MockNode(1, 1, '登录页', 'main'),
            MockNode(5, 5, '异常页', 'exception'),
            MockNode(2, 2, '首页', 'main'),
        ]

        result = _sort_flow_nodes(nodes)

        flow_types = [n.flow_type for n in result]
        main_indices = [i for i, ft in enumerate(flow_types) if ft == 'main']
        non_main_indices = [i for i, ft in enumerate(flow_types) if ft != 'main']
        # 所有main节点的索引必须小于所有非main节点的索引
        assert all(i < j for i in main_indices for j in non_main_indices)

    def test_sort_main_order_priority_over_screen_order(self) -> None:
        """测试main_order优先于screen_order"""
        nodes = [
            MockNode(1, 1, 'screen_order=1', 'main', main_order=2),
            MockNode(2, 2, 'screen_order=2', 'main', main_order=1),
        ]

        result = _sort_flow_nodes(nodes)

        # main_order=1 应排在 main_order=2 前面，尽管 screen_order 相反
        assert result[0].screen_name == 'screen_order=2'
        assert result[1].screen_name == 'screen_order=1'
