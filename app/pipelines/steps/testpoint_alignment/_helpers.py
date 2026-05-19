from typing import Any, Dict, List, Optional


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
) -> tuple:
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
