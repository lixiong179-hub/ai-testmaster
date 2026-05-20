from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque
from loguru import logger

from app.models.test_case import TestCase
from app.services.test_execution_engine.models import (
    ExecutionStatus,
    TestExecutionResult,
)


class _OrchestrationMixin:

    async def _navigate_to_dependency_anchor(
        self, case: TestCase
    ) -> Tuple[bool, str]:
        has_api_setup = bool(getattr(case, 'setup_api_calls', None))
        is_mobile = getattr(self, '_mobile_device_id', None) is not None

        if has_api_setup:
            api_ok, api_desc = await self._execute_setup_api_calls(case)
            if api_ok:
                target_url = self._extract_target_url_from_case(case)
                if target_url and self.browser and getattr(self.browser, '_page', None):
                    try:
                        await self.browser._page.goto(target_url, wait_until="networkidle")
                    except Exception:
                        pass
                return True, api_desc

        if not is_mobile:
            success = await self._restore_anchor_snapshot(case)
            if success:
                return True, "Level1-快照恢复"

        success = await self._execute_fallback_navigation(case)
        if success:
            return True, "Level2-降级导航"

        if is_mobile:
            success = await self._restore_anchor_snapshot(case)
            if success:
                return True, "Level1-快照恢复"

        success = await self._try_direct_url_navigation(case)
        if success:
            return True, "Level3-直接URL"

        return False, "全部降级失败"

    def _extract_target_url_from_case(self, case: TestCase) -> Optional[str]:
        precondition = getattr(case, 'precondition', '') or ''
        url = self._extract_url_from_text(precondition)
        if url:
            return url

        steps_json = getattr(case, 'steps_json', None)
        if steps_json and isinstance(steps_json, list):
            for step in steps_json:
                if not isinstance(step, dict):
                    continue
                step_url = self._extract_url_from_text(
                    step.get('action', '') + ' ' + (step.get('input_value') or '')
                )
                if step_url:
                    return step_url

        return None

    def _mark_dependents_blocked(
        self,
        failed_case: TestCase,
        cases: List[TestCase],
        case_results: Dict[int, TestExecutionResult],
    ) -> List[int]:
        blocked_ids: Set[int] = set()
        failed_title = failed_case.title
        self._failed_main_titles.add(failed_title)

        title_to_dependents: Dict[str, List[TestCase]] = {}
        for case in cases:
            if case.id in case_results:
                continue
            dep = getattr(case, 'depends_on', None)
            if dep:
                title_to_dependents.setdefault(dep, []).append(case)

        queue = deque([failed_title])
        visited: Set[str] = set()
        while queue:
            current_title = queue.popleft()
            if current_title in visited:
                continue
            visited.add(current_title)
            self._failed_main_titles.add(current_title)

            for dep_case in title_to_dependents.get(current_title, []):
                if dep_case.id not in case_results and dep_case.id not in blocked_ids:
                    blocked_ids.add(dep_case.id)
                    queue.append(dep_case.title)

        if blocked_ids:
            logger.info(
                f"用例 '{failed_title}' 失败，"
                f"{len(blocked_ids)} 个下游用例标记为 BLOCKED（含链式依赖）"
            )

        return list(blocked_ids)

    def _should_skip_as_blocked(self, case: TestCase) -> bool:
        depends_on = getattr(case, 'depends_on', None)
        if depends_on and depends_on in self._failed_main_titles:
            return True
        return False

    async def _save_main_flow_snapshots(
        self, case: TestCase, step_results: List[Any]
    ) -> None:
        if not step_results:
            return

        anchor_index = getattr(self, '_anchor_step_index', None)
        if not anchor_index:
            return

        anchor_steps_needed: Set[int] = set()
        for (title, step_num), _ in anchor_index.items():
            if title == case.title:
                anchor_steps_needed.add(step_num)

        if not anchor_steps_needed:
            return

        for step_result in step_results:
            step_num = getattr(step_result, 'step_number', None)
            if step_num in anchor_steps_needed:
                if getattr(step_result, 'status', None) == ExecutionStatus.PASSED:
                    try:
                        await self._save_anchor_snapshot(case, step_num)
                    except Exception as e:
                        logger.warning(f"快照保存异常: case={case.case_no}, step={step_num}, error={e}")
