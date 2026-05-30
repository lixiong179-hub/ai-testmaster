"""流程感知历史用例评审 - 覆盖推断与未覆盖检测。

提供:
    - _match_flow_nodes: 公共流程节点匹配（消除重复逻辑）
    - _infer_history_case_flow_coverage: 推断历史用例覆盖的流程节点
    - _find_uncovered_flow_nodes: 查找未被历史用例覆盖的流程节点
    - _append_flow_aware_history_cases: 追加流程感知的历史用例评审部分
"""
from typing import List, Dict, Any, Optional

from loguru import logger

from app.services.prompt_builder.helpers import _safe_int


_CHILD_TYPE_CONFIG = [
    ('branch', '分支'),
    ('exception', '异常'),
    ('bypass', '旁路'),
]


def _match_flow_nodes(
    combined_text: str,
    main_nodes: List[Dict[str, Any]],
    branch_by_source: Dict[int, List[Dict[str, Any]]],
    exception_by_source: Dict[int, List[Dict[str, Any]]],
    bypass_by_source: Dict[int, List[Dict[str, Any]]],
    node_map: Dict[Any, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """匹配文本与流程节点，返回匹配结果列表。

    将 combined_text 与流程结构中的主干/分支/异常/旁路节点进行关键词匹配，
    返回结构化的匹配结果，供覆盖标注和未覆盖检测共用。

    Args:
        combined_text: 待匹配的文本（历史用例标题+摘要+模块）。
        main_nodes: 主干流程节点列表（已排序）。
        branch_by_source: 按源节点分组的分支连线。
        exception_by_source: 按源节点分组的异常连线。
        bypass_by_source: 按源节点分组的旁路连线。
        node_map: 节点映射字典（screen_id -> node）。

    Returns:
        匹配结果列表，每项包含:
            - node_type: 'main'/'branch'/'exception'/'bypass'
            - step_index: 主干步骤序号（1-based）
            - child_index: 子节点索引（0-based，main 类型为 -1）
            - label: 可读标签
    """
    child_sources = {
        'branch': branch_by_source,
        'exception': exception_by_source,
        'bypass': bypass_by_source,
    }
    matched: List[Dict[str, Any]] = []

    for i, node in enumerate(main_nodes, 1):
        screen_name = (node.get('screen_name') or '').lower()
        if screen_name and (screen_name in combined_text or any(
            kw in combined_text for kw in screen_name.split() if len(kw) >= 2
        )):
            matched.append({
                'node_type': 'main',
                'step_index': i,
                'child_index': -1,
                'label': f"步骤{i}[{node.get('screen_name', '')}]",
            })

        screen_id = node.get('screen_id')
        for child_type, suffix in _CHILD_TYPE_CONFIG:
            for cidx, edge in enumerate(child_sources[child_type].get(screen_id, [])):
                tid = _safe_int(edge.get('target'))
                if tid is None:
                    continue
                target_node = node_map.get(tid, {})
                target_name = (target_node.get('screen_name') or '').lower()
                condition = (edge.get('condition') or '').lower()
                keywords = f"{target_name} {condition}"
                if any(kw in combined_text for kw in keywords.split() if len(kw) >= 2):
                    matched.append({
                        'node_type': child_type,
                        'step_index': i,
                        'child_index': cidx,
                        'label': (
                            f"步骤{i}-{suffix}{chr(ord('A') + cidx)}"
                            f"[{target_node.get('screen_name', '')}]"
                        ),
                    })

    return matched


def _infer_history_case_flow_coverage(
    case: Dict[str, Any],
    main_nodes: List[Dict[str, Any]],
    branch_by_source: Dict[int, List[Dict[str, Any]]],
    exception_by_source: Dict[int, List[Dict[str, Any]]],
    bypass_by_source: Dict[int, List[Dict[str, Any]]],
    node_map: Dict[Any, Dict[str, Any]],
) -> str:
    """推断历史用例覆盖的流程节点，生成流程归属标注。

    通过关键词匹配将历史用例的标题/摘要/模块与流程节点名称进行关联，
    返回流程归属标注字符串，供 Prompt 中标注历史用例的覆盖范围。

    Args:
        case: 历史用例字典，包含 title/summary/module 等字段。
        main_nodes: 主干流程节点列表（已排序）。
        branch_by_source: 按源节点分组的分支连线。
        exception_by_source: 按源节点分组的异常连线。
        bypass_by_source: 按源节点分组的旁路连线。
        node_map: 节点映射字典（screen_id -> node）。

    Returns:
        流程归属标注字符串，如 "→ 覆盖: 步骤1[登录页], 步骤1-异常A[密码错误]"。
        无法匹配时返回 "→ 覆盖: 未匹配流程节点"。
    """
    title = (case.get('title') or '').lower()
    summary = (case.get('summary') or case.get('expected_result') or '').lower()
    module = (case.get('module') or '').lower()
    combined_text = f"{title} {summary} {module}"

    matched = _match_flow_nodes(
        combined_text, main_nodes,
        branch_by_source, exception_by_source, bypass_by_source, node_map,
    )

    if not matched:
        return "→ 覆盖: 未匹配流程节点"
    labels = [m['label'] for m in matched]
    return f"→ 覆盖: {', '.join(labels)}"


def _find_uncovered_flow_nodes(
    history_cases: List[Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    branch_by_source: Dict[int, List[Dict[str, Any]]],
    exception_by_source: Dict[int, List[Dict[str, Any]]],
    bypass_by_source: Dict[int, List[Dict[str, Any]]],
    node_map: Dict[Any, Dict[str, Any]],
) -> List[str]:
    """查找未被任何历史用例覆盖的流程节点。

    Args:
        history_cases: 历史用例列表。
        main_nodes: 主干流程节点列表。
        branch_by_source: 按源节点分组的分支连线。
        exception_by_source: 按源节点分组的异常连线。
        bypass_by_source: 按源节点分组的旁路连线。
        node_map: 节点映射字典。

    Returns:
        未覆盖的流程节点标签列表。
    """
    covered_keys: set[str] = set()
    for case in history_cases:
        title = (case.get('title') or '').lower()
        summary = (case.get('summary') or case.get('expected_result') or '').lower()
        module = (case.get('module') or '').lower()
        combined_text = f"{title} {summary} {module}"

        matched = _match_flow_nodes(
            combined_text, main_nodes,
            branch_by_source, exception_by_source, bypass_by_source, node_map,
        )
        for m in matched:
            key = f"{m['node_type']}_{m['step_index']}_{m['child_index']}"
            covered_keys.add(key)

    uncovered: List[str] = []
    child_sources = {
        'branch': branch_by_source,
        'exception': exception_by_source,
    }
    for i, node in enumerate(main_nodes, 1):
        if f"main_{i}_-1" not in covered_keys:
            uncovered.append(f"步骤{i}[{node.get('screen_name', '')}] — 主干流程未覆盖")

        screen_id = node.get('screen_id')
        for child_type, suffix in [('branch', '分支'), ('exception', '异常')]:
            for cidx, edge in enumerate(child_sources[child_type].get(screen_id, [])):
                key = f"{child_type}_{i}_{cidx}"
                if key not in covered_keys:
                    tid = _safe_int(edge.get('target'))
                    target_node = node_map.get(tid, {}) if tid is not None else {}
                    uncovered.append(
                        f"步骤{i}-{suffix}{chr(ord('A') + cidx)}"
                        f"[{target_node.get('screen_name', '')}]"
                        f" — {suffix}流程未覆盖"
                    )

        for cidx, edge in enumerate(bypass_by_source.get(screen_id, [])):
            key = f"bypass_{i}_{cidx}"
            if key not in covered_keys:
                tid = _safe_int(edge.get('target'))
                target_node = node_map.get(tid, {}) if tid is not None else {}
                uncovered.append(
                    f"步骤{i}[{node.get('screen_name', '')}]"
                    f" — 旁路[{target_node.get('screen_name', '弹窗')}]未在主干用例中补充关闭操作"
                )

    return uncovered


def _append_flow_aware_history_cases(
    parts: List[str],
    history_cases: List[Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    branch_by_source: Dict[int, List[Dict[str, Any]]],
    exception_by_source: Dict[int, List[Dict[str, Any]]],
    bypass_by_source: Dict[int, List[Dict[str, Any]]],
    node_map: Dict[Any, Dict[str, Any]],
) -> None:
    """追加历史用例覆盖摘要/避重部分到 parts 列表。

    以避重视角列出已有用例的覆盖摘要，仅供避免重复生成参考：
    1. 每条历史用例标注其覆盖的流程节点
    2. 评审规则按流程步骤逐一检查覆盖
    3. 查漏补缺以流程结构为骨架

    Args:
        parts: Prompt 片段列表。
        history_cases: 历史用例列表。
        main_nodes: 主干流程节点列表。
        branch_by_source: 按源节点分组的分支连线。
        exception_by_source: 按源节点分组的异常连线。
        bypass_by_source: 按源节点分组的旁路连线。
        node_map: 节点映射字典。
    """
    parts.append("## 项目已有测试用例（覆盖摘要，仅供避重参考）\n")
    parts.append(
        "以下为项目已有的测试用例摘要，仅供避免重复生成使用："
    )
    parts.append("")
    parts.append("参考原则：")
    parts.append(
        "- 已覆盖：流程场景已被旧用例覆盖 → 无需重复生成"
    )
    parts.append(
        "- 避重：新场景未被任何旧用例覆盖 → 仅生成新场景用例"
    )
    parts.append(
        "- 不要改写或废弃已有用例，已有用例的维护由保鲜建议流程单独处理"
    )
    parts.append("")

    for i, case in enumerate(history_cases, 1):
        desc = case.get("summary", "") or case.get("expected_result", "") or "无摘要"
        coverage = _infer_history_case_flow_coverage(
            case, main_nodes,
            branch_by_source, exception_by_source, bypass_by_source, node_map,
        )
        parts.append(
            f"  {i}. [{case.get('module', '')}] {case.get('title', '')} "
            f"(ID:{case.get('id', '')}) — {desc}"
        )
        parts.append(f"     {coverage}")

    uncovered = _find_uncovered_flow_nodes(
        history_cases, main_nodes,
        branch_by_source, exception_by_source, bypass_by_source, node_map,
    )
    if uncovered:
        parts.append("")
        parts.append("⚠️ 以下流程节点未被任何历史用例覆盖（必须生成新用例）：")
        for label in uncovered:
            parts.append(f"  - {label}")

    parts.append("")
