"""S10 DecisionDispatch -- 裁决分发 Step

在 Reconciliation (S9) 之后、CaseGeneration (S11) 之前，
将 merged_verdicts 转化为结构化的 generation_tasks 列表。

核心流程：
    1. 读取 merged_verdicts + aligned_testpoints + history_fingerprints + scenario_candidates
    2. 遍历每个 verdict，按 action 分类生成任务：
       - KEEP           → 跳过，仅计数
       - NEEDS_MODIFY   → modify 任务
       - LOCATOR_BROKEN → locator_fix 任务
       - LOCATOR_AND_MODIFY → modify 任务 + need_locator_fix=True
       - DEPRECATE      → deprecation_suggestions
       - ADD_NEW        → create 任务
       - CONFLICT       → skip 任务
       - PENDING_REVIEW → skip 任务
    3. 聚合 stats，输出 generation_tasks 产物

纯计算逻辑，零 AI 调用，confidence = 1.0。
"""
import hashlib
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


# ── 动作常量（与 reconciliation.py 中 MergedAction 保持同步） ──

_KEEP = "keep"
_NEEDS_MODIFY = "needs_modify"
_LOCATOR_BROKEN = "locator_broken"
_LOCATOR_AND_MODIFY = "locator_and_modify"
_DEPRECATE = "deprecate"
_ADD_NEW = "add_new"
_CONFLICT = "conflict"
_PENDING_REVIEW = "pending_review"


class DecisionDispatch(PipelineStep):
    """裁决分发 Step -- 将合并裁决转化为结构化生成任务列表。"""

    name: ClassVar[str] = "decision_dispatch"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = [
        "merged_verdicts",
        "aligned_testpoints",
        "history_fingerprints",
        "scenario_candidates",
    ]
    produces: ClassVar[List[str]] = ["generation_tasks"]

    def should_run(self, ctx: PipelineContext) -> bool:
        merged = ctx.get_artifact("merged_verdicts")
        if merged is None:
            return False
        verdicts = merged.get("verdicts", [])
        total = merged.get("total_count", 0)
        return len(verdicts) > 0 and total > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        merged = ctx.get_artifact("merged_verdicts")
        if merged is None:
            return hashlib.sha256(f"{self.name}:{self.version}:empty".encode()).hexdigest()
        verdicts = merged.get("verdicts", [])
        case_ids = sorted(
            v.get("case_id") or 0 for v in verdicts if isinstance(v, dict)
        )
        actions = sorted(
            v.get("action", "") for v in verdicts if isinstance(v, dict)
        )
        raw = f"{self.name}:{self.version}:ids={case_ids}:acts={actions}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        merged = ctx.get_artifact("merged_verdicts")
        aligned = ctx.get_artifact("aligned_testpoints")
        fingerprints = ctx.get_artifact("history_fingerprints")
        candidates = ctx.get_artifact("scenario_candidates")

        if merged is None:
            return StepResult(
                success=False,
                error="缺少 merged_verdicts 产物",
            )

        verdicts = merged.get("verdicts", [])
        fps = fingerprints.get("fingerprints", []) if fingerprints else []
        cands = candidates.get("candidates", []) if candidates else []
        aligned_tps = aligned.get("aligned_testpoints", []) if aligned else []

        # 构建 fingerprint 按 case_id 的索引，用于快速查找 original_case
        fp_by_case_id: Dict[int, Dict[str, Any]] = {}
        for fp in fps:
            cid = fp.get("case_id")
            if cid is not None:
                fp_by_case_id[cid] = fp

        generation_tasks: List[Dict[str, Any]] = []
        deprecation_suggestions: List[Dict[str, Any]] = []
        budget_exhausted = False
        stats = {
            "keep_count": 0,
            "modify_count": 0,
            "create_count": 0,
            "locator_fix_count": 0,
            "deprecate_count": 0,
            "skip_count": 0,
            "conflict_count": 0,
        }

        for verdict in verdicts:
            if not isinstance(verdict, dict):
                continue

            # 预算耗尽暂停：已生成的任务仍然输出，但标记暂停等待用户确认
            if not ctx.check_budget():
                logger.warning(
                    "DecisionDispatch 预算耗尽，已生成 {} 条任务后暂停",
                    len(generation_tasks),
                )
                budget_exhausted = True
                break

            action = verdict.get("action", "")
            case_id = verdict.get("case_id")
            candidate_index = verdict.get("candidate_index")
            reason = verdict.get("reason", "")

            if action == _KEEP:
                stats["keep_count"] += 1
                continue

            elif action == _DEPRECATE:
                deprecation = _build_deprecation_suggestion(
                    case_id=case_id,
                    reason=reason,
                    fp_by_case_id=fp_by_case_id,
                )
                deprecation_suggestions.append(deprecation)
                stats["deprecate_count"] += 1
                continue

            elif action == _NEEDS_MODIFY:
                task = _build_modify_task(
                    case_id=case_id,
                    reason=reason,
                    fp_by_case_id=fp_by_case_id,
                    need_locator_fix=False,
                )
                generation_tasks.append(task)
                stats["modify_count"] += 1

            elif action == _LOCATOR_BROKEN:
                task = _build_locator_fix_task(
                    case_id=case_id,
                    reason=reason,
                    fp_by_case_id=fp_by_case_id,
                )
                generation_tasks.append(task)
                stats["locator_fix_count"] += 1

            elif action == _LOCATOR_AND_MODIFY:
                task = _build_modify_task(
                    case_id=case_id,
                    reason=reason,
                    fp_by_case_id=fp_by_case_id,
                    need_locator_fix=True,
                )
                generation_tasks.append(task)
                stats["modify_count"] += 1

            elif action == _ADD_NEW:
                task = _build_create_task(
                    candidate_index=candidate_index,
                    cands=cands,
                    reason=reason,
                )
                generation_tasks.append(task)
                stats["create_count"] += 1

            elif action == _CONFLICT:
                task = _build_skip_task(
                    case_id=case_id,
                    skip_reason=f"冲突: {reason}" if reason else "合并冲突，需人工决策",
                    fp_by_case_id=fp_by_case_id,
                )
                generation_tasks.append(task)
                stats["skip_count"] += 1
                stats["conflict_count"] += 1

            elif action == _PENDING_REVIEW:
                task = _build_skip_task(
                    case_id=case_id,
                    skip_reason="pending_review deferred",
                    fp_by_case_id=fp_by_case_id,
                )
                generation_tasks.append(task)
                stats["skip_count"] += 1

            else:
                logger.warning("未知裁决动作 action={}, case_id={}，跳过", action, case_id)
                stats["skip_count"] += 1

        project_id = merged.get("project_id", 0)

        payload = {
            "project_id": project_id,
            "generation_tasks": generation_tasks,
            "deprecation_suggestions": deprecation_suggestions,
            "stats": stats,
            "total_tasks": len(generation_tasks),
            "total_deprecations": len(deprecation_suggestions),
        }

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="generation_tasks",
            artifact_confidence=1.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "total_tasks": len(generation_tasks),
                "total_deprecations": len(deprecation_suggestions),
                "stats": stats,
                "budget_exhausted": budget_exhausted,
            },
            pause_for_confirmation=budget_exhausted,
            confirmation_reason=(
                f"Token 预算耗尽，已生成 {len(generation_tasks)} 条任务，"
                "剩余裁决未处理，等待用户确认"
            ) if budget_exhausted else None,
            confirmation_payload=payload if budget_exhausted else None,
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        tasks = payload.get("generation_tasks")
        if not isinstance(tasks, list):
            return False
        if tasks and not all(_validate_task_field(t) for t in tasks):
            return False
        stats = payload.get("stats")
        if not isinstance(stats, dict):
            return False
        required_stats = [
            "keep_count", "modify_count", "create_count",
            "locator_fix_count", "deprecate_count", "skip_count", "conflict_count",
        ]
        return all(k in stats for k in required_stats)

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        merged = ctx.get_artifact("merged_verdicts")
        if merged is not None:
            logger.warning(
                "DecisionDispatch 执行异常但 merged_verdicts 可用, 返回空任务列表: {}",
                error,
            )
            return StepResult(
                success=True,
                artifact_payload={
                    "project_id": merged.get("project_id", 0),
                    "generation_tasks": [],
                    "deprecation_suggestions": [],
                    "stats": {
                        "keep_count": 0, "modify_count": 0, "create_count": 0,
                        "locator_fix_count": 0, "deprecate_count": 0,
                        "skip_count": 0, "conflict_count": 0,
                    },
                    "total_tasks": 0,
                    "total_deprecations": 0,
                },
                artifact_kind="generation_tasks",
                artifact_confidence=0.0,
                artifact_provenance={
                    "step": self.name,
                    "version": self.version,
                    "degraded": True,
                    "error": str(error),
                },
                degraded=True,
            )

        # merged_verdicts 缺失时，基于 aligned_testpoints 生成默认 create 任务
        aligned = ctx.get_artifact("aligned_testpoints")
        if aligned is None:
            return StepResult(
                success=False,
                error=f"DecisionDispatch 降级失败: 缺少 aligned_testpoints ({error})",
                artifact_payload={
                    "project_id": 0,
                    "generation_tasks": [],
                    "deprecation_suggestions": [],
                    "stats": {
                        "keep_count": 0, "modify_count": 0, "create_count": 0,
                        "locator_fix_count": 0, "deprecate_count": 0,
                        "skip_count": 0, "conflict_count": 0,
                    },
                    "total_tasks": 0,
                    "total_deprecations": 0,
                },
                artifact_kind="generation_tasks",
                artifact_confidence=0.0,
                degraded=True,
            )

        aligned_tps = aligned.get("aligned_testpoints", [])
        fallback_tasks: List[Dict[str, Any]] = []
        for idx, entry in enumerate(aligned_tps):
            tp = entry.get("test_point", {}) if isinstance(entry, dict) else {}
            task = {
                "task_type": "create",
                "task_id": f"create_fallback_{idx}",
                "case_id": None,
                "candidate_description": tp.get("point", ""),
                "candidate_module": tp.get("module", ""),
                "candidate_priority": tp.get("priority", 3),
                "candidate_reason": "fallback: 由 aligned_testpoints 自动生成",
                "change_type": "added",
            }
            fallback_tasks.append(task)

        fallback_count = len(fallback_tasks)

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": aligned.get("project_id", 0),
                "generation_tasks": fallback_tasks,
                "deprecation_suggestions": [],
                "stats": {
                    "keep_count": 0, "modify_count": 0, "create_count": fallback_count,
                    "locator_fix_count": 0, "deprecate_count": 0,
                    "skip_count": 0, "conflict_count": 0,
                },
                "total_tasks": fallback_count,
                "total_deprecations": 0,
            },
            artifact_kind="generation_tasks",
            artifact_confidence=0.3,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
                "fallback_source": "aligned_testpoints",
            },
            degraded=True,
        )


# ── 纯函数：任务构建 ──


def _resolve_original_case(
    case_id: Optional[int],
    fp_by_case_id: Dict[int, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """从 fingerprint 中查找原始用例信息，并尝试从 DB 补全 steps_json 等字段。

    优先使用 fingerprint 中的基本信息，DB 查询作为补充。

    Args:
        case_id: 用例 ID。
        fp_by_case_id: case_id → fingerprint 索引。

    Returns:
        包含 title/module/steps_json/precondition/expected_result 的字典，
        或 None（未找到时）。
    """
    if case_id is None:
        return None

    fp = fp_by_case_id.get(case_id)
    if fp is None:
        return None

    original: Dict[str, Any] = {
        "title": fp.get("title", ""),
        "module": fp.get("module", ""),
        "steps_json": None,
        "precondition": "",
        "expected_result": "",
    }

    # 尝试从 DB 获取更完整的用例数据（steps_json / precondition / expected_result）
    try:
        from app.db.core import SessionLocal
        from app.models.test_case import TestCase as _TestCase

        db = SessionLocal()
        try:
            db_case = db.query(_TestCase).filter(_TestCase.id == case_id).first()
            if db_case is not None:
                original["steps_json"] = _safe_json(db_case.steps_json)
                original["precondition"] = db_case.precondition or ""
                original["expected_result"] = db_case.expected_result or ""
        finally:
            db.close()
    except Exception as e:
        logger.debug("从 DB 补全原始用例信息失败 case_id={}: {}", case_id, e)

    return original


def _safe_json(value: Any) -> Any:
    """安全转换 JSON 字段为 Python 对象。"""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        import json as _json
        try:
            return _json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _build_modify_task(
    case_id: Optional[int],
    reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
    need_locator_fix: bool,
) -> Dict[str, Any]:
    """构建 modify 类型的生成任务。

    Args:
        case_id: 原用例 ID。
        reason: 裁决理由，作为 modification_hint。
        fp_by_case_id: case_id → fingerprint 索引。
        need_locator_fix: 是否需要同时修复定位器。

    Returns:
        modify 任务字典。
    """
    task_id = f"modify_{case_id}" if case_id is not None else "modify_unknown"
    task: Dict[str, Any] = {
        "task_type": "modify",
        "task_id": task_id,
        "case_id": case_id,
        "original_case": _resolve_original_case(case_id, fp_by_case_id),
        "change_type": "modified",
        "modification_hint": reason or "需修改",
    }
    if need_locator_fix:
        task["need_locator_fix"] = True
    return task


def _build_locator_fix_task(
    case_id: Optional[int],
    reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """构建 locator_fix 类型的生成任务。

    Args:
        case_id: 原用例 ID。
        reason: 裁决理由。
        fp_by_case_id: case_id → fingerprint 索引。

    Returns:
        locator_fix 任务字典。
    """
    task_id = f"locator_{case_id}" if case_id is not None else "locator_unknown"
    return {
        "task_type": "locator_fix",
        "task_id": task_id,
        "case_id": case_id,
        "original_case": _resolve_original_case(case_id, fp_by_case_id),
        "change_type": "locator_fix",
        "locator_hint": reason or "元素定位变更",
    }


def _build_create_task(
    candidate_index: Optional[int],
    cands: List[Dict[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    """构建 create 类型的生成任务。

    从 scenario_candidates 中按 candidate_index 获取候选描述。

    Args:
        candidate_index: 候选索引。
        cands: scenario_candidates 的 candidates 列表。
        reason: 裁决理由。

    Returns:
        create 任务字典。
    """
    if candidate_index is not None and 0 <= candidate_index < len(cands):
        cand = cands[candidate_index]
    else:
        cand = {}

    task_id = f"create_{candidate_index}" if candidate_index is not None else "create_unknown"
    return {
        "task_type": "create",
        "task_id": task_id,
        "candidate_index": candidate_index,
        "candidate_description": cand.get("description", ""),
        "candidate_module": cand.get("module", ""),
        "candidate_priority": cand.get("priority", 3),
        "candidate_reason": cand.get("reason", reason or "新增场景"),
        "change_type": "added",
    }


def _build_skip_task(
    case_id: Optional[int],
    skip_reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """构建 skip 类型的任务（冲突或待审核）。

    Args:
        case_id: 原用例 ID（可选）。
        skip_reason: 跳过原因。
        fp_by_case_id: case_id → fingerprint 索引。

    Returns:
        skip 任务字典。
    """
    task_id = f"skip_{case_id}" if case_id is not None else "skip_unknown"
    task: Dict[str, Any] = {
        "task_type": "skip",
        "task_id": task_id,
        "case_id": case_id,
        "skip_reason": skip_reason,
    }
    if case_id is not None:
        original = _resolve_original_case(case_id, fp_by_case_id)
        if original:
            task["original_case"] = original
    return task


def _build_deprecation_suggestion(
    case_id: Optional[int],
    reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """构建废弃建议条目。

    Args:
        case_id: 用例 ID。
        reason: 裁决理由（作为废弃原因）。
        fp_by_case_id: case_id → fingerprint 索引。

    Returns:
        废弃建议字典。
    """
    title = ""
    if case_id is not None:
        fp = fp_by_case_id.get(case_id)
        if fp is not None:
            title = fp.get("title", "")
    return {
        "case_id": case_id,
        "title": title,
        "deprecate_reason": reason or "建议废弃",
    }


def _validate_task_field(task: Dict[str, Any]) -> bool:
    """校验单条任务是否包含必需的 task_type 字段。"""
    return isinstance(task, dict) and "task_type" in task
