import json
from typing import Any, Dict, List, Set
from loguru import logger

from app.models.test_case import TestCase


class _DependencyGraphMixin:

    _anchor_snapshots: Dict[str, Dict[str, Any]]
    _case_results: Dict[int, Any]
    _failed_main_titles: Set[str]

    def _init_dependency_state(self) -> None:
        self._anchor_snapshots: Dict[str, Dict[str, Any]] = {}
        self._case_results: Dict[int, Any] = {}
        self._failed_main_titles: Set[str] = set()

    def _build_dependency_graph(
        self, cases: List[TestCase]
    ) -> Dict[int, Set[int]]:
        title_to_id: Dict[str, int] = {}
        for case in cases:
            if case.title:
                title_to_id[case.title] = case.id

        graph: Dict[int, Set[int]] = {case.id: set() for case in cases}
        for case in cases:
            depends_on_title = getattr(case, 'depends_on', None)
            if depends_on_title and depends_on_title in title_to_id:
                dep_id = title_to_id[depends_on_title]
                graph[case.id].add(dep_id)

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

        queue = [cid for cid, deg in in_degree.items() if deg == 0]
        sorted_ids: List[int] = []

        while queue:
            cid = queue.pop(0)
            sorted_ids.append(cid)
            for dependent in reverse_graph.get(cid, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(sorted_ids) < len(cases):
            remaining = [cid for cid in graph if cid not in sorted_ids]
            logger.warning(
                f"检测到循环依赖，{len(remaining)} 个用例将追加到执行队列末尾: {remaining}"
            )
            sorted_ids.extend(remaining)

        return [case_map[cid] for cid in sorted_ids if cid in case_map]
