"""S5 TestPointAlignment — 测试点对齐 Step

完整版对齐逻辑：
    1. 用户提供的测试点 (raw_signals.test_points)
    2. UI 原型控件 (raw_signals.ui_specs)
    3. AI 反推的业务能力 (inferred_business_summary)
    4. UI 提取的场景候选 (scenario_candidates)

输出 aligned_testpoints 产物，含对齐矩阵、冲突列表、置信度。
"""
import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class TestPointAlignment(PipelineStep):
    """测试点对齐 Step — 多源对齐。"""

    name: ClassVar[str] = "testpoint_alignment"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["raw_signals"]
    produces: ClassVar[List[str]] = ["aligned_testpoints"]

    def should_run(self, ctx: PipelineContext) -> bool:
        signals = ctx.get_artifact("raw_signals")
        if not signals:
            return False
        inferred = ctx.get_artifact("inferred_business_summary")
        return bool(signals.get("test_points") or (inferred is not None))

    def cache_key(self, ctx: PipelineContext) -> str:
        signals = ctx.get_artifact("raw_signals")
        if not signals:
            return ""
        tp_ids = sorted(p.get("id", 0) for p in signals.get("test_points", []))
        ui_count = len(signals.get("ui_specs", []))

        inferred = ctx.get_artifact("inferred_business_summary")
        inferred_hash = ""
        if inferred:
            try:
                caps = inferred.get("parsed", {}).get("inferred_capabilities", [])
                inferred_hash = hashlib.sha256(
                    json.dumps(caps, sort_keys=True, ensure_ascii=False, default=str).encode()
                ).hexdigest()[:16]
            except Exception:
                inferred_hash = "error"

        candidates = ctx.get_artifact("scenario_candidates")
        candidate_hash = ""
        if candidates:
            try:
                cands = candidates.get("candidates", [])
                candidate_hash = hashlib.sha256(
                    json.dumps(cands, sort_keys=True, ensure_ascii=False, default=str).encode()
                ).hexdigest()[:16]
            except Exception:
                candidate_hash = "error"

        raw = f"{self.name}:{self.version}:tp={tp_ids}:ui={ui_count}:inf={inferred_hash}:cand={candidate_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        signals = ctx.get_artifact("raw_signals")
        if not signals:
            return StepResult(success=False, error="缺少 raw_signals 产物")

        test_points = signals.get("test_points", [])
        ui_specs = signals.get("ui_specs", [])
        has_ui = signals.get("has_ui", False)

        inferred = ctx.get_artifact("inferred_business_summary")
        inferred_caps = _extract_inferred_capabilities(inferred)

        candidates = ctx.get_artifact("scenario_candidates")
        scenario_cands = _extract_scenario_candidates(candidates)

        aligned = []
        conflicts = []

        sources = {
            "ui": has_ui and len(ui_specs) > 0,
            "inferred": len(inferred_caps) > 0,
            "scenario": len(scenario_cands) > 0,
        }
        active_sources = [k for k, v in sources.items() if v]

        for tp in test_points:
            entry = {
                "test_point": tp,
                "ui_match": None,
                "capability_match": None,
                "scenario_match": None,
                "alignment_status": "aligned",
                "notes": "",
            }

            any_source_match = False

            if sources["ui"]:
                matched_screens = _find_matching_screens(tp, ui_specs)
                if matched_screens:
                    entry["ui_match"] = matched_screens[0]
                    any_source_match = True

            if sources["inferred"]:
                matched_cap = _find_matching_capability(tp, inferred_caps)
                if matched_cap:
                    entry["capability_match"] = matched_cap
                    any_source_match = True

            if sources["scenario"]:
                matched_scenario = _find_matching_scenario(tp, scenario_cands)
                if matched_scenario:
                    entry["scenario_match"] = matched_scenario
                    any_source_match = True

            if not any_source_match:
                if has_ui or sources["inferred"] or sources["scenario"]:
                    entry["alignment_status"] = "no_ui_match"
                    entry["notes"] = _build_no_match_note(tp, active_sources)
                    conflicts.append(entry)
                else:
                    entry["alignment_status"] = "no_sources"
                    entry["notes"] = "无可对齐的源（无 UI / 反推能力 / 场景候选）"

            aligned.append(entry)

        if not test_points and inferred_caps:
            aligned, conflicts = _align_from_inferred_only(inferred_caps)

        coverage = _compute_coverage(aligned, conflicts, inferred_caps)

        confidence = _compute_alignment_confidence(aligned, conflicts)
        should_pause = len(conflicts) > 0 and confidence < 0.7

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": signals.get("project_id"),
            "aligned_testpoints": aligned,
            "conflicts": conflicts,
            "total_testpoints": len(test_points) or len(inferred_caps),
            "aligned_count": len([a for a in aligned if a["alignment_status"] == "aligned"]),
            "conflict_count": len(conflicts),
            "has_ui": has_ui,
            "active_sources": active_sources,
            "sources": sources,
            "coverage": coverage,
        }

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="aligned_testpoints",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "conflict_count": len(conflicts),
                "active_sources": active_sources,
            },
            pause_for_confirmation=should_pause,
            confirmation_reason=f"发现 {len(conflicts)} 个测试点未对齐，请确认是否继续",
            confirmation_payload={"conflicts": conflicts[:10], "active_sources": active_sources},
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "aligned_testpoints" in payload and "sources" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        signals = ctx.get_artifact("raw_signals")
        test_points = signals.get("test_points", []) if signals else []
        aligned = [
            {
                "test_point": tp,
                "ui_match": None,
                "capability_match": None,
                "scenario_match": None,
                "alignment_status": "fallback",
                "notes": f"对齐降级: {error}",
            }
            for tp in test_points
        ]
        return StepResult(
            success=True,
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "aligned_testpoints": aligned,
                "conflicts": [],
                "total_testpoints": len(test_points),
                "aligned_count": 0,
                "conflict_count": 0,
                "has_ui": False,
                "active_sources": [],
                "sources": {"ui": False, "inferred": False, "scenario": False},
                "coverage": None,
            },
            artifact_kind="aligned_testpoints",
            artifact_confidence=0.3,
            degraded=True,
        )


# ==================== 纯函数 ====================


def _extract_inferred_capabilities(inferred: Optional[Any]) -> List[Dict[str, Any]]:
    if not inferred:
        return []
    parsed = inferred.get("parsed", {})
    caps = parsed.get("inferred_capabilities", [])
    if not isinstance(caps, list):
        caps = []
    if not caps:
        change_summary = parsed.get("change_summary", {})
        if isinstance(change_summary, dict):
            caps = (
                change_summary.get("new_capabilities", [])
                + change_summary.get("modified_capabilities", [])
            )
            if not isinstance(caps, list):
                caps = []
    return [c for c in caps if isinstance(c, dict)]


def _extract_scenario_candidates(candidates: Optional[Any]) -> List[Dict[str, Any]]:
    if not candidates:
        return []
    cands = candidates.get("candidates", [])
    if not isinstance(cands, list):
        return []
    return [c for c in cands if isinstance(c, dict)]


def _find_matching_screens(
    tp: Dict[str, Any], ui_specs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    tp_module = (tp.get("module") or "").lower().strip()
    tp_point = (tp.get("point") or "").lower().strip()
    tp_function = (tp.get("function") or "").lower().strip()

    matched = []
    seen_screen_ids = set()

    for spec in ui_specs:
        screen_name = (spec.get("screen_name") or "").lower()
        screen_id = spec.get("screen_id")

        if screen_id in seen_screen_ids:
            continue

        module_match = False
        if tp_module:
            module_words = tp_module.split()
            if len(module_words) > 1:
                module_match = all(w in screen_name for w in module_words)
            else:
                module_match = _is_significant_match(tp_module, screen_name)

        element_match = False
        ui_spec = spec.get("ui_spec", {})
        if isinstance(ui_spec, dict):
            elements = ui_spec.get("elements", [])
            search_text = tp_point or tp_function
            if search_text:
                for elem in elements:
                    elem_text = (elem.get("text") or "").lower()
                    if elem_text and _is_significant_match(search_text, elem_text):
                        element_match = True
                        break

        if module_match or element_match:
            matched.append({
                "screen_id": screen_id,
                "screen_name": spec.get("screen_name"),
            })
            seen_screen_ids.add(screen_id)

    return matched


def _find_matching_capability(
    tp: Dict[str, Any], caps: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    tp_point = (tp.get("point") or "").lower().strip()
    tp_module = (tp.get("module") or "").lower().strip()
    tp_function = (tp.get("function") or "").lower().strip()
    search_texts = [s for s in [tp_point, tp_module, tp_function] if s]

    best = None
    best_score = 0.0

    for cap in caps:
        cap_name = (cap.get("name") or "").lower()
        cap_key = (cap.get("key") or "").lower()
        cap_desc = (cap.get("description") or "").lower()

        score = 0.0
        max_possible = 0.0

        for search in search_texts:
            if search and _is_significant_match(search, cap_name):
                score += 1.0
            elif search and _is_significant_match(search, cap_key):
                score += 0.8
            elif search and search in cap_desc:
                score += 0.5
            max_possible += 1.0

        normalized = score / max(max_possible, 1)
        if normalized > best_score:
            best_score = normalized
            best = {
                "capability_name": cap.get("name"),
                "capability_key": cap.get("key"),
                "match_score": round(normalized, 2),
            }

    return best if best_score >= 0.3 else None


def _find_matching_scenario(
    tp: Dict[str, Any], cands: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    tp_point = (tp.get("point") or "").lower().strip()
    tp_function = (tp.get("function") or "").lower().strip()
    search_texts = [s for s in [tp_point, tp_function] if s]

    best = None
    best_score = 0.0

    for cand in cands:
        cand_title = (cand.get("title") or "").lower()
        cand_desc = (cand.get("description") or "").lower()

        score = 0.0
        max_possible = 0.0

        for search in search_texts:
            if search and _is_significant_match(search, cand_title):
                score += 1.0
            elif search and search in cand_desc:
                score += 0.5
            max_possible += 1.0

        normalized = score / max(max_possible, 1)
        if normalized > best_score:
            best_score = normalized
            best = {
                "scenario_title": cand.get("title"),
                "scenario_id": cand.get("id"),
                "match_score": round(normalized, 2),
            }

    return best if best_score >= 0.3 else None


def _build_no_match_note(tp: Dict[str, Any], active_sources: List[str]) -> str:
    tp_point = tp.get("point", "")
    source_labels = {
        "ui": "UI 控件",
        "inferred": "AI 能力",
        "scenario": "场景候选",
    }
    labels = [source_labels[s] for s in active_sources if s in source_labels]
    return f"测试点 '{tp_point}' 未在 {'/'.join(labels)} 中找到匹配"


def _align_from_inferred_only(
    inferred_caps: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    aligned = []
    conflicts = []

    for cap in inferred_caps:
        entry = {
            "test_point": {
                "module": cap.get("name", ""),
                "function": "",
                "point": cap.get("description", ""),
                "priority": 2,
                "source": "inferred",
            },
            "ui_match": None,
            "capability_match": {
                "capability_name": cap.get("name"),
                "capability_key": cap.get("key"),
                "match_score": 1.0,
            },
            "scenario_match": None,
            "alignment_status": "aligned",
            "notes": "由 AI 反推能力生成",
        }
        aligned.append(entry)

    return aligned, conflicts


def _compute_coverage(
    aligned: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    inferred_caps: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not inferred_caps:
        return None

    covered_caps = set()
    for entry in aligned:
        cap_match = entry.get("capability_match", {})
        if isinstance(cap_match, dict) and cap_match.get("capability_key"):
            covered_caps.add(cap_match["capability_key"])

    total_caps = len(inferred_caps)
    covered_count = len(covered_caps)
    rate = covered_count / max(total_caps, 1)

    return {
        "total_capabilities": total_caps,
        "covered_capabilities": covered_count,
        "uncovered_capabilities": total_caps - covered_count,
        "coverage_rate": round(rate, 2),
    }


def _is_significant_match(query: str, target: str) -> bool:
    if not query or not target:
        return False
    if len(query) < 2:
        return False
    if query == target:
        return True
    idx = target.find(query)
    if idx < 0:
        return False
    if len(query) >= 3:
        return True
    before_char = target[idx - 1] if idx > 0 else ""
    after_char = target[idx + len(query)] if idx + len(query) < len(target) else ""
    before_is_cjk = _is_cjk(before_char) if before_char else False
    after_is_cjk = _is_cjk(after_char) if after_char else False
    if before_is_cjk or after_is_cjk:
        return True
    before_ok = idx == 0 or not target[idx - 1].isalnum()
    after_ok = idx + len(query) >= len(target) or not target[idx + len(query)].isalnum()
    return before_ok and after_ok


def _is_cjk(char: str) -> bool:
    cp = ord(char)
    return (
        (0x4E00 <= cp <= 0x9FFF)
        or (0x3400 <= cp <= 0x4DBF)
        or (0x20000 <= cp <= 0x2A6DF)
        or (0x2A700 <= cp <= 0x2B73F)
        or (0x2B740 <= cp <= 0x2B81F)
    )


def _compute_alignment_confidence(
    aligned: List[Dict], conflicts: List[Dict]
) -> float:
    if not aligned:
        return 0.0
    aligned_count = len([a for a in aligned if a["alignment_status"] == "aligned"])
    return aligned_count / len(aligned)
