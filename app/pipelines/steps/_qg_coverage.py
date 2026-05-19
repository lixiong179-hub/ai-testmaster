from typing import Any, Dict, List, Optional


def _build_tp_from_task(task: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not task:
        return None
    task_type = task.get("task_type", "")
    if task_type == "modify" or task_type == "locator_fix":
        original = task.get("original_case", {})
        return {
            "id": task.get("task_id"),
            "module": original.get("module", task.get("module", "")),
            "function": task.get("modification_hint", ""),
            "point": original.get("title", ""),
            "priority": task.get("candidate_priority", original.get("priority", 3)),
        }
    if task_type == "create":
        return {
            "id": task.get("task_id"),
            "module": task.get("candidate_module", task.get("module", "")),
            "function": task.get("candidate_description", ""),
            "point": task.get("candidate_description", ""),
            "priority": task.get("candidate_priority", 3),
        }
    return None


_TYPE_KEYWORDS_LOCAL: Dict[str, List[str]] = {
    "positive": ["正向", "正常", "主流程", "happy", "成功提交", "完整流程", "正确输入", "常规"],
    "boundary": ["边界", "上限", "下限", "最大", "最小", "临界", "超长", "超限", "空值", "极值",
                 "最多", "最少", "最长", "最短", "极限", "范围", "阈值"],
    "negative": ["异常", "错误", "失败", "缺失", "拒绝", "无权限", "断网", "超时", "容错", "拦截",
                 "非法", "无效", "不存在", "未授权", "冲突", "重复", "exception"],
}


def _classify_case_type_local(case: Dict[str, Any]) -> str:
    cat = (case.get("case_category") or case.get("case_type") or "").lower()
    for type_name in ("boundary", "negative", "positive"):
        kw_map = {
            "boundary": ["boundary", "边界"],
            "negative": ["negative", "exception", "异常", "abnormal"],
            "positive": ["positive", "正向", "normal", "happy"],
        }
        if any(k in cat for k in kw_map[type_name]):
            return type_name
    title = (case.get("title") or "").lower()
    for type_name, keywords in _TYPE_KEYWORDS_LOCAL.items():
        if any(kw in title for kw in keywords):
            return type_name

    steps = case.get("steps", [])
    if isinstance(steps, list):
        steps_text = ""
        for step in steps:
            if isinstance(step, dict):
                steps_text += (step.get("action", "") + " " + step.get("expected_result", "")).lower()
        if steps_text:
            for type_name, keywords in _TYPE_KEYWORDS_LOCAL.items():
                if any(kw in steps_text for kw in keywords):
                    return type_name

    return "positive"


def _compute_module_coverage(
    generated_cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    module_coverage: Dict[str, Any] = {}
    for entry in generated_cases:
        if entry.get("status") != "success":
            continue
        for case_data in entry.get("case_data", []):
            case_module = case_data.get("module", "未分类")
            case_type = _classify_case_type_local(case_data)
            final_score = case_data.get("prior_quality_score", 0)

            if case_module not in module_coverage:
                module_coverage[case_module] = {
                    "case_count": 0,
                    "type_distribution": {"positive": 0, "boundary": 0, "negative": 0},
                    "total_score": 0.0,
                }

            mc = module_coverage[case_module]
            mc["case_count"] += 1
            mc["type_distribution"][case_type] = mc["type_distribution"].get(case_type, 0) + 1
            mc["total_score"] += final_score

    for module_name, mc in module_coverage.items():
        mc["average_score"] = round(mc["total_score"] / mc["case_count"], 1) if mc["case_count"] > 0 else 0.0
        del mc["total_score"]

    return module_coverage


def _compute_ui_element_coverage(
    signals: Dict[str, Any],
    cases_artifact: Dict[str, Any],
) -> Dict[str, Any]:
    total_ui_elements = 0
    covered_ui_elements = 0

    if signals:
        ui_specs = signals.get("ui_specs", [])
        for spec in ui_specs:
            regions = spec.get("ui_spec", {}).get("regions", {})
            if isinstance(regions, dict):
                total_ui_elements += len(regions)

    if cases_artifact:
        covered_element_names: set = set()
        for gc_entry in cases_artifact.get("generated_cases", []):
            if gc_entry.get("status") != "success":
                continue
            for case in gc_entry.get("case_data", []):
                for step in case.get("steps", []):
                    target = step.get("target_element", "")
                    if target:
                        covered_element_names.add(target.lower())
        covered_ui_elements = len(covered_element_names)

    return {
        "total": total_ui_elements,
        "covered": covered_ui_elements,
        "coverage_rate": round(covered_ui_elements / total_ui_elements, 2) if total_ui_elements > 0 else 0.0,
    }
