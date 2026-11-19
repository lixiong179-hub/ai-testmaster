import json
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.services.test_execution_engine.models import ExecutionError


@dataclass
class _CaseCounts:
    """任务内用例执行计数。"""

    passed: int = 0
    failed: int = 0
    blocked: int = 0


def _parse_web_env_configs(raw: Any) -> dict[str, Any]:
    """解析项目 web_env_configs（dict / JSON 串 / 双层编码串），失败返回空 dict。"""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, str):
        try:
            inner = json.loads(parsed)
        except (json.JSONDecodeError, ValueError, TypeError):
            return {}
        if isinstance(inner, dict):
            return inner
    return {}


_EVIDENCE_KEYS = ("console_errors", "network_failures", "uncaught_exceptions", "memory_leak_suspect")


def _collect_step_evidence(steps: Any) -> dict[str, list] | None:
    """合并各步骤的 defect_evidence；无任何证据返回 None。"""
    merged: dict[str, list] = {key: [] for key in _EVIDENCE_KEYS}
    has_evidence = False
    for step in steps:
        evidence = getattr(step, "defect_evidence", None)
        if not evidence or not isinstance(evidence, dict):
            continue
        has_evidence = True
        for key in _EVIDENCE_KEYS:
            items = evidence.get(key)
            if isinstance(items, list):
                merged[key].extend(items)
    return merged if has_evidence else None


def _dedupe_evidence(merged: dict[str, list]) -> dict[str, list]:
    """按内容去重（dict 转有序 tuple 作标识）。"""
    deduped: dict[str, list] = {}
    for key, items in merged.items():
        seen = set()
        unique = []
        for item in items:
            ident = tuple(sorted(item.items())) if isinstance(item, dict) else str(item)
            if ident not in seen:
                seen.add(ident)
                unique.append(item)
        deduped[key] = unique
    return deduped


def _resolve_target_env_config(raw_configs: Any, target_env: str) -> dict[str, Any]:
    """取目标环境配置；目标不存在时回退第一个可用环境并告警。"""
    resolved = _parse_web_env_configs(raw_configs)
    if not resolved:
        return {}
    env_config = resolved.get(target_env, {})
    if env_config:
        return env_config
    available_envs = list(resolved.keys())
    if not available_envs:
        return {}
    fallback_env = available_envs[0]
    logger.warning(f"目标环境 '{target_env}' 不存在，回退到 '{fallback_env}'")
    return resolved.get(fallback_env, {})


class _HelpersMixin:
    def _resolve_execution_order(self, cases: list[TestCase]) -> list[TestCase]:
        has_dependency = any(getattr(c, "depends_on", None) for c in cases)
        if not has_dependency:
            return cases

        graph = self._build_dependency_graph(cases)
        sorted_cases = self._topological_sort_cases(cases, graph)

        main_count = sum(1 for c in sorted_cases if not getattr(c, "depends_on", None))
        dep_count = len(sorted_cases) - main_count
        logger.info(
            f"依赖解析完成: 主干用例 {main_count} 条, "
            f"依赖用例 {dep_count} 条, "
            f"快照锚点 {len(self._collect_anchor_steps(sorted_cases))} 个"
        )
        return sorted_cases

    def _collect_anchor_steps(self, cases: list[TestCase]) -> list[int]:
        steps = []
        for case in cases:
            anchor = getattr(case, "anchor_step", None)
            if anchor is not None:
                steps.append(anchor)
        return steps

    def _build_anchor_step_index(self, cases: list[TestCase]) -> dict[tuple, bool]:
        index: dict[tuple, bool] = {}
        for case in cases:
            depends_on = getattr(case, "depends_on", None)
            anchor = getattr(case, "anchor_step", None)
            if depends_on and anchor is not None:
                index[(depends_on, anchor)] = True
        return index

    def _get_task_summary(self, task_id: int) -> dict[str, Any]:
        from app.models.test_task import TestTask
        from app.models.test_result import TestResult

        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ExecutionError(f"测试任务不存在: {task_id}")

        results = self.db.query(TestResult).filter(TestResult.task_id == task_id).all()

        total = len(results)
        passed = len([r for r in results if r.exec_status == ExecStatus.PASSED])
        failed = len([r for r in results if r.exec_status == ExecStatus.FAILED])
        blocked = len([r for r in results if r.exec_status == ExecStatus.BLOCKED])

        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "task_id": task.id,
            "task_name": task.task_name,
            "status": str(task.status),
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "blocked_cases": blocked,
            "pass_rate": f"{pass_rate:.2f}%",
            "start_time": task.start_time.strftime("%Y-%m-%d %H:%M:%S") if task.start_time else None,
            "end_time": task.end_time.strftime("%Y-%m-%d %H:%M:%S") if task.end_time else None,
        }

    def get_task_execution_summary(self, task_id: int) -> dict[str, Any]:
        return self._get_task_summary(task_id)
