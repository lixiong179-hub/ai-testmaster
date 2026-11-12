from collections import Counter
from typing import Any
from loguru import logger

from app.models.test_case import TestCase


class _DependencyGraphMixin:

    _anchor_snapshots: dict[str, dict[str, Any]]
    _case_results: dict[int, Any]
    _failed_main_titles: set[str]
    _duplicate_dependency_titles: set[str]
    _title_to_case_id: dict[str, int]
    _title_to_case_no: dict[str, str]

    def _init_dependency_state(self) -> None:
        self._anchor_snapshots: dict[str, dict[str, Any]] = {}
        self._case_results: dict[int, Any] = {}
        self._failed_main_titles: set[str] = set()
        self._duplicate_dependency_titles: set[str] = set()
        self._title_to_case_id: dict[str, int] = {}
        self._title_to_case_no: dict[str, str] = {}

    def _build_dependency_graph(
        self, cases: list[TestCase]
    ) -> dict[int, set[int]]:
        title_counts = Counter(case.title for case in cases if case.title)
        title_to_ids: dict[str, list[int]] = {}
        case_no_to_id: dict[str, int] = {}
        for case in cases:
            if case.title:
                title_to_ids.setdefault(case.title, []).append(case.id)
            if getattr(case, 'case_no', None):
                case_no_to_id[case.case_no] = case.id

        self._duplicate_dependency_titles = {
            title for title, count in title_counts.items() if count > 1
        }
        self._title_to_case_id = {}
        self._title_to_case_no = {}
        title_to_id: dict[str, int] = {}
        for case in cases:
            if case.title:
                if case.title in self._duplicate_dependency_titles:
                    logger.warning(
                        f"duplicate test case title '{case.title}'; dependency by title is ambiguous"
                    )
                    continue
                title_to_id[case.title] = case.id
                self._title_to_case_id[case.title] = case.id
                self._title_to_case_no[case.title] = case.case_no or f"TC-{case.id:03d}"

        graph: dict[int, set[int]] = {case.id: set() for case in cases}
        for case in cases:
            depends_on_title = getattr(case, 'depends_on', None)
            if depends_on_title in self._duplicate_dependency_titles:
                logger.warning(
                    f"case {case.case_no} dependency '{depends_on_title}' is ambiguous; "
                    "falling back to navigation instead of title snapshot"
                )
                graph[case.id].update(
                    dep_id for dep_id in title_to_ids.get(depends_on_title, [])
                    if dep_id != case.id
                )
            elif depends_on_title and depends_on_title in title_to_id:
                dep_id = title_to_id[depends_on_title]
                graph[case.id].add(dep_id)
            elif depends_on_title and depends_on_title in case_no_to_id:
                graph[case.id].add(case_no_to_id[depends_on_title])
            elif depends_on_title:
                logger.warning(
                    f"case {case.case_no} dependency '{depends_on_title}' is not in current case list"
                )

        return graph

    def _topological_sort_cases(
        self, cases: list[TestCase], graph: dict[int, set[int]]
    ) -> list[TestCase]:
        case_map = {case.id: case for case in cases}
        in_degree: dict[int, int] = {cid: len(deps) for cid, deps in graph.items()}
        reverse_graph: dict[int, set[int]] = {cid: set() for cid in graph}
        for cid, deps in graph.items():
            for dep_id in deps:
                if dep_id in reverse_graph:
                    reverse_graph[dep_id].add(cid)

        queue = [cid for cid, deg in in_degree.items() if deg == 0]
        sorted_ids: list[int] = []

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

    def _snapshot_keys_for_case(
        self, case: TestCase, anchor_step: int
    ) -> list[str]:
        keys: list[str] = []
        case_id = getattr(case, 'id', None)
        if case_id is not None:
            keys.append(f"id:{case_id}:{anchor_step}")

        title = getattr(case, 'title', None)
        duplicate_titles = getattr(self, '_duplicate_dependency_titles', set())
        if title and title not in duplicate_titles:
            keys.append(f"title:{title}:{anchor_step}")

        case_no = getattr(case, 'case_no', None)
        if case_no:
            keys.append(f"case_no:{case_no}:{anchor_step}")
            keys.append(f"{case_no}_{anchor_step}")

        if title and title not in duplicate_titles:
            keys.append(f"{title}_{anchor_step}")

        return keys

    def _snapshot_keys_for_dependency(
        self, case: TestCase
    ) -> list[str]:
        depends_on = getattr(case, 'depends_on', None)
        anchor_step = getattr(case, 'anchor_step', None)
        if not depends_on or anchor_step is None:
            return []

        duplicate_titles = getattr(self, '_duplicate_dependency_titles', set())
        if depends_on in duplicate_titles:
            logger.warning(
                f"dependency '{depends_on}' is ambiguous; snapshot restore is disabled"
            )
            return []

        keys: list[str] = []
        case_id = getattr(self, '_title_to_case_id', {}).get(depends_on)
        if case_id is not None:
            keys.append(f"id:{case_id}:{anchor_step}")

        case_no = self._resolve_depends_on_case_no(depends_on)
        if case_no:
            keys.append(f"case_no:{case_no}:{anchor_step}")
            keys.append(f"{case_no}_{anchor_step}")

        keys.append(f"title:{depends_on}:{anchor_step}")
        keys.append(f"{depends_on}_{anchor_step}")
        return keys

    def _resolve_depends_on_case_no(self, depends_on_title: str) -> str | None:
        return getattr(self, '_title_to_case_no', {}).get(depends_on_title)
