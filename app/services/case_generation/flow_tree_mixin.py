"""流程树构建Mixin - 分支/异常/旁路流程树构建逻辑。

本模块提供流程图排序数据中的分支、异常和旁路流程树构建逻辑。
作为FlowTreeMixin被ContextMixin组合使用。

核心类:
    - FlowTreeMixin: 流程树构建Mixin

设计模式:
    作为Mixin模块，通过多继承组合到ContextMixin中，提供:
    - _build_branch_tree: 构建分支流程树
    - _build_exception_tree: 构建异常流程树
    - _build_bypass_tree: 构建旁路流程树
    - _build_flow_tree: 通用流程树构建（内部方法）
"""

from typing import List, Dict, Any
from loguru import logger


class FlowTreeMixin:
    """流程树构建Mixin，提供分支/异常/旁路流程树构建方法。"""

    def _build_flow_tree(
        self,
        edges: List[Any],
        nodes: List[Any],
        edge_type: str,
        default_condition: str
    ) -> List[Dict[str, Any]]:
        """通用流程树构建方法。

        Args:
            edges: 连线列表，source/target为screen_id的字符串形式
            nodes: 节点列表，包含screen_id和screen_order等信息
            edge_type: 要过滤的连线类型（branch/exception/bypass）
            default_condition: 默认条件描述

        Returns:
            流程树列表，每个元素包含source_step/target_screen_id/target_name/condition
        """
        filtered_edges = [e for e in edges if e.edge_type == edge_type]
        node_map = {node.screen_id: node for node in nodes}
        main_nodes = [n for n in nodes if getattr(n, 'flow_type', 'main') == 'main']
        step_map = {node.screen_id: idx + 1 for idx, node in enumerate(main_nodes)}
        result = []
        for edge in filtered_edges:
            try:
                source_screen_id = int(edge.source)
                target_screen_id = int(edge.target)
            except (ValueError, TypeError):
                logger.warning(
                    f"连线source/target格式错误: source={edge.source}, target={edge.target}"
                )
                continue
            source_node = node_map.get(source_screen_id)
            target_node = node_map.get(target_screen_id)
            if source_node and target_node:
                result.append({
                    'source_step': step_map.get(source_screen_id, source_node.screen_order),
                    'source_screen_id': source_screen_id,
                    'target_screen_id': target_screen_id,
                    'target_name': target_node.screen_name,
                    'condition': edge.condition or default_condition
                })
            else:
                missing = []
                if not source_node:
                    missing.append(f'source={source_screen_id}')
                if not target_node:
                    missing.append(f'target={target_screen_id}')
                logger.warning(f"{edge_type}连线节点不存在: {', '.join(missing)}")
        return result

    def _build_branch_tree(self, edges: List[Any], nodes: List[Any]) -> List[Dict[str, Any]]:
        """构建分支流程树

        Args:
            edges: 连线列表，source/target为screen_id的字符串形式
            nodes: 节点列表，包含screen_id和screen_order等信息

        Returns:
            分支流程列表，每个元素包含source_step/target_screen_id/target_name/condition
        """
        return self._build_flow_tree(edges, nodes, 'branch', '未指定')

    def _build_exception_tree(self, edges: List[Any], nodes: List[Any]) -> List[Dict[str, Any]]:
        """构建异常流程树

        Args:
            edges: 连线列表，source/target为screen_id的字符串形式
            nodes: 节点列表

        Returns:
            异常流程列表，结构同_build_branch_tree
        """
        return self._build_flow_tree(edges, nodes, 'exception', '未指定')

    def _build_bypass_tree(self, edges: List[Any], nodes: List[Any]) -> List[Dict[str, Any]]:
        """构建旁路流程树

        Args:
            edges: 连线列表，source/target为screen_id的字符串形式
            nodes: 节点列表

        Returns:
            旁路流程列表，结构同_build_branch_tree
        """
        return self._build_flow_tree(edges, nodes, 'bypass', '自动弹出')
