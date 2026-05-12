"""上下文构建Mixin - 聚合需求文档、UI原型和测试点数据。

本模块提供用例生成所需的完整上下文数据聚合逻辑，包括需求文档加载、
UI原型数据加载和测试点数据加载。作为ContextMixin被CoreMixin组合使用。

核心类:
    - ContextMixin: 上下文构建Mixin

设计模式:
    作为Mixin模块，通过多继承组合到CoreMixin中，提供:
    - get_context_for_generation: 构建完整上下文
    - _get_file_content: 获取文件内容（支持缓存和强制刷新）

依赖关系:
    - app.services.case_generation.context_loader: 需求与UI数据加载
    - app.services.case_generation.test_point_loader: 测试点加载与文件获取
    - app.services.case_generation.flow_tree_mixin: 流程树构建

上下文构建流程:
    1. 加载需求文档内容（指定文件ID或项目全部需求文件）
    2. 加载UI原型数据（指定屏幕ID或文件ID或项目全部UI数据）
    3. 加载测试点数据（指定ID或分页查询）
    4. 处理流程图排序数据
    5. 返回聚合后的上下文字典
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.models.project import ProjectFile
from app.services.case_generation.flow_tree_mixin import FlowTreeMixin
from app.services.case_generation.context_loader import load_requirement_content, load_ui_data
from app.services.case_generation.test_point_loader import (
    load_test_points, get_file_content_helper,
    DEFAULT_TEST_POINT_PAGE_SIZE,
)


def _sort_flow_nodes(nodes: List[Any]) -> List[Any]:
    """优先使用显式主干顺序，缺失时退回screen_order。"""
    return sorted(
        nodes,
        key=lambda node: (
            0 if node.flow_type == 'main' else 1,
            getattr(node, 'main_order', None) or getattr(node, 'screen_order', 0),
            getattr(node, 'screen_order', 0),
        )
    )


class ContextMixin(FlowTreeMixin):
    """上下文构建Mixin - 聚合需求文档、UI原型和测试点数据。

    通过继承FlowTreeMixin获得流程树构建能力:
        - _build_branch_tree: 构建分支流程树
        - _build_exception_tree: 构建异常流程树
        - _build_bypass_tree: 构建旁路流程树

    职责:
        - 构建用例生成所需的完整上下文
        - 加载需求文档内容（支持指定文件和全量加载）
        - 加载UI原型数据（屏幕描述和UI规格）
        - 加载测试点数据（支持指定ID和分页查询）
        - 文件内容提取与缓存

    设计意图:
        将上下文构建逻辑从生成流程中抽离，便于:
        1. 上下文数据可被多个生成步骤复用
        2. 独立测试上下文构建逻辑
        3. 支持增量刷新(force_refresh)

    使用场景:
        被CoreMixin通过多继承组合，
        在生成流程开始前调用get_context_for_generation构建上下文。
    """

    def __init__(self, db: Session) -> None:
        """初始化上下文Mixin。

        Args:
            db: 数据库会话，贯穿用例生成生命周期。
        """
        self.db = db

    async def get_context_for_generation(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE,
        flow_sort_data: Optional[Any] = None
    ) -> Dict[str, Any]:
        """构建用例生成所需的完整上下文数据。

        上下文聚合策略（按优先级）:
            需求文档:
                1. 指定requirement_file_ids -> 加载指定文件
                2. 未指定 -> 加载项目全部需求文件
            UI原型:
                1. 指定ui_screen_ids -> 加载指定屏幕（含UI规格）
                2. 指定ui_file_ids -> 加载指定文件及关联屏幕
                3. 均未指定 -> 加载项目全部已解析UI屏幕
            测试点:
                1. 指定test_point_ids -> 加载指定测试点
                2. 未指定 -> 分页查询项目测试点
            流程图排序:
                1. 指定flow_sort_data -> 构建流程结构上下文
                2. 未指定 -> 不添加流程结构

        Args:
            project_id: 项目ID。
            user_id: 用户ID。
            requirement_file_ids: 需求文件ID列表，可选。
            ui_file_ids: UI文件ID列表，可选。
            ui_screen_ids: UI屏幕ID列表，可选。
            test_point_ids: 测试点ID列表，可选。
            force_refresh: 是否强制刷新文件内容，默认False。
            test_point_page: 测试点分页页码，默认1。
            test_point_page_size: 测试点分页大小，默认100。

        Returns:
            上下文字典，包含:
                - requirement_content: 需求文档内容
                - ui_descriptions: UI描述列表
                - ui_specs: UI规格列表
                - test_points: 测试点列表
                - files_used: 使用的文件ID列表
                - warnings: 警告信息列表
                - cache_info: 缓存信息
                - pagination: 分页信息（仅分页查询时）
        """
        context = {
            "requirement_content": "", "ui_descriptions": [], "ui_specs": [],
            "test_points": [], "files_used": [], "warnings": [], "cache_info": {},
            "flow_structure": None, "ocr_texts": {}
        }

        requirement_content, req_files_used = await load_requirement_content(
            self.db, project_id, requirement_file_ids, force_refresh
        )
        context["requirement_content"] = requirement_content
        context["files_used"].extend(req_files_used)

        ui_descriptions, ui_specs, ui_files_used = await load_ui_data(
            self.db, project_id, ui_screen_ids, ui_file_ids
        )
        context["ui_descriptions"] = ui_descriptions
        context["ui_specs"] = ui_specs
        context["files_used"].extend(ui_files_used)

        test_points, pagination = load_test_points(
            self.db, project_id, test_point_ids, test_point_page, test_point_page_size
        )
        context["test_points"] = test_points
        if pagination:
            context["pagination"] = pagination

        if flow_sort_data:
            sorted_nodes = _sort_flow_nodes(flow_sort_data.nodes)
            main_flow_nodes = [n for n in sorted_nodes if n.flow_type == 'main']
            branch_flow_nodes = [n for n in sorted_nodes if n.flow_type == 'branch']
            exception_flow_nodes = [n for n in sorted_nodes if n.flow_type == 'exception']
            bypass_flow_nodes = [n for n in sorted_nodes if n.flow_type == 'bypass']

            context["flow_structure"] = {
                "main_flow": [n.model_dump() for n in main_flow_nodes],
                "branch_flows": self._build_branch_tree(flow_sort_data.edges, sorted_nodes),
                "exception_flows": self._build_exception_tree(flow_sort_data.edges, sorted_nodes),
                "bypass_flows": self._build_bypass_tree(flow_sort_data.edges, sorted_nodes)
            }

            # ISSUE-006/007 FIX: 使用 ui_spec_elements 替代 ocr_text，并增加数据完整性校验
            context["ui_spec_elements_map"] = {
                n.screen_id: n.ui_spec_elements for n in sorted_nodes if n.ui_spec_elements
            }
            existing_screen_ids = {d.get("screen_id") for d in context["ui_descriptions"]}
            missing_screen_ids = []
            for node in sorted_nodes:
                if node.screen_id not in existing_screen_ids:
                    context["ui_descriptions"].append({
                        "screen_id": node.screen_id,
                        "screen_name": node.screen_name,
                        "screen_order": node.screen_order,
                        "flow_type": node.flow_type,
                        "summary": node.summary or "",
                        "ui_spec_elements": node.ui_spec_elements or []
                    })
                # 数据完整性校验：检查关键字段
                if not node.screen_name:
                    missing_screen_ids.append(node.screen_id)

            if missing_screen_ids:
                context["warnings"].append(
                    f"以下节点缺少 screen_name: {missing_screen_ids}"
                )

            missing_edge_conditions = [
                edge.label for edge in flow_sort_data.edges
                if edge.edge_type != 'normal' and not (edge.condition or '').strip()
            ]
            if missing_edge_conditions:
                context["warnings"].append(
                    f"以下连线缺少条件说明: {missing_edge_conditions}"
                )

            logger.info(
                f"流程图模式：接收到 {len(sorted_nodes)} 个节点"
                f"（主干:{len(main_flow_nodes)} 分支:{len(branch_flow_nodes)}"
                f" 异常:{len(exception_flow_nodes)} 旁路:{len(bypass_flow_nodes)}），"
                f"{len(flow_sort_data.edges)} 条连线"
            )
            logger.debug(f"流程图数据结构: {context['flow_structure']}")

        return context

    async def _get_file_content(self, file: ProjectFile, force_refresh: bool = False) -> Optional[str]:
        """获取文件内容，支持缓存和强制刷新。"""
        return await get_file_content_helper(self.db, file, force_refresh)
