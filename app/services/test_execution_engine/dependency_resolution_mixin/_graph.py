import json
from collections import deque
from typing import Any, Dict, List, Optional, Set
from loguru import logger

from app.models.test_case import TestCase


class _DependencyGraphMixin:

    _anchor_snapshots: Dict[str, Dict[str, Any]]
    _case_results: Dict[int, Any]
    _failed_main_titles: Set[str]
    _title_to_case_no: Dict[str, str]

    def _init_dependency_state(self) -> None:
        self._anchor_snapshots: Dict[str, Dict[str, Any]] = {}
        self._case_results: Dict[int, Any] = {}
        self._failed_main_titles: Set[str] = set()
        self._title_to_case_no: Dict[str, str] = {}

    def _build_dependency_graph(
        self, cases: List[TestCase]
    ) -> Dict[int, Set[int]]:
        title_to_id: Dict[str, int] = {}
        self._title_to_case_no = {}
        for case in cases:
            if case.title:
                if case.title in title_to_id:
                    logger.warning(f"用例标题重复: '{case.title}'，依赖解析可能不准确")
                title_to_id[case.title] = case.id
                self._title_to_case_no[case.title] = case.case_no or f"TC-{case.id:03d}"

        graph: Dict[int, Set[int]] = {case.id: set() for case in cases}
        for case in cases:
            depends_on_title = getattr(case, 'depends_on', None)
            if depends_on_title and depends_on_title in title_to_id:
                dep_id = title_to_id[depends_on_title]
                graph[case.id].add(dep_id)
            elif depends_on_title:
                logger.warning(f"用例 {case.case_no} 的依赖 '{depends_on_title}' 不在当前用例列表中")

        return graph

    def _topological_sort_cases(
        self, cases: List[TestCase], graph: Dict[int, Set[int]]
    ) -> List[TestCase]:
        case_map = {case.id: case for case in cases}
        in_degree: Dict[int, int] = {cid: len(deps) for cid, deps in graph.items()}
        reverse_graph: Dict[int, Set[int]] = {cid: set() for cid in graph}
        for cid, deps in graph.items():
            for dep_id in deps:
                if dep_id in reverse_graph:
                    reverse_graph[dep_id].add(cid)

        queue = deque(cid for cid, deg in in_degree.items() if deg == 0)
        sorted_ids: List[int] = []

        while queue:
            cid = queue.popleft()
            sorted_ids.append(cid)
            for dependent in reverse_graph.get(cid, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(sorted_ids) < len(cases):
            remaining = sorted(cid for cid in graph if cid not in sorted_ids)
            logger.warning(
                f"检测到循环依赖，{len(remaining)} 个用例将追加到执行队列末尾: {remaining}"
            )
            sorted_ids.extend(remaining)

        return [case_map[cid] for cid in sorted_ids if cid in case_map]

    def _resolve_depends_on_case_no(self, depends_on_title: str) -> str:
        """将 depends_on 标题解析为 case_no，用于快照 key 查找。

        Args:
            depends_on_title: 依赖用例的标题。

        Returns:
            对应的 case_no，未找到时回退到标题本身。
        """
        return self._title_to_case_no.get(depends_on_title, depends_on_title)
