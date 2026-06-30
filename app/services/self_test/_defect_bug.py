"""Defect severity assessment and automatic Bug creation."""
import json
from typing import Any, Dict, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.project import Project


# P0 触发关键词：安全断言失败 / 系统崩溃
_P0_SECURITY_ASSERTIONS = frozenset({"no_sensitive_data", "no_xss"})
_P0_CRASH_KEYWORDS = frozenset({
    "页面白屏", "500错误", "internal server error",
    "白屏", "blank page", "crash",
})

# P1 触发关键词：核心功能不可用 / 5xx / 数据不一致 / 权限绕过 / 内存泄漏
_P1_ELEMENT_FAILURES = frozenset({
    "元素未找到", "定位失败", "no such element",
    "element not found", "stale element",
})
_P1_NETWORK_5XX = frozenset({"5xx", "500", "502", "503", "504"})
_P1_DATA_KEYWORDS = frozenset({"数据不一致", "权限绕过", "permission bypass"})
_P1_MEMORY_LEAK = frozenset({"memory_leak_suspect"})

# P2 触发关键词：加载超时 / 渲染问题 / 非核心功能异常
_P2_LOADING_ASSERTIONS = frozenset({"loading_hidden", "loading_visible"})
_P2_RENDERING_ASSERTIONS = frozenset({"text_not_empty"})

# P3 触发关键词：控制台错误 / UI 瑕疵
_P3_CONSOLE_ASSERTIONS = frozenset({"no_console_errors"})

# ux_category 映射表
_UX_CATEGORY_MAP: Dict[str, Optional[str]] = {
    "no_sensitive_data": "security",
    "no_xss": "security",
    "loading_hidden": "loading_experience",
    "loading_visible": "loading_experience",
    "no_console_errors": "error_feedback",
    "no_network_errors": "response_performance",
    "response_time_lt": "response_performance",
    "text_not_empty": "empty_state",
    "memory_leak_suspect": "response_performance",
}


def _assess_defect_severity(
    failure_type: str,
    defect_evidence: Optional[Dict[str, Any]] = None,
    error_message: str = "",
) -> Tuple[int, Optional[str]]:
    """根据断言类型和缺陷证据自动评估缺陷严重度和 UX 分类。

    评估规则:
        - P0 (severity=1): 安全断言失败、系统崩溃（白屏/500）
        - P1 (severity=2): 核心功能不可用、5xx 网络错误、数据不一致、
          权限绕过、内存泄漏嫌疑
        - P2 (severity=3): 加载超时、渲染问题、非核心功能异常、体验性问题
        - P3 (severity=4): 控制台错误、UI 瑕疵、非关键体验优化

    Args:
        failure_type: 断言类型或缺陷来源标识（如 no_sensitive_data、
            loading_hidden、element_not_found 等）。
        defect_evidence: 浏览器缺陷证据字典，可能包含
            console_errors / network_failures / memory_leak_suspect /
            uncaught_exceptions 等键。
        error_message: 步骤执行错误信息，用于关键词匹配。

    Returns:
        (severity, ux_category) 二元组。
        severity 取值 1-4（1=致命，4=轻微）。
        ux_category 为合法枚举值或 None（功能 Bug）。
    """
    failure_lower = failure_type.lower()
    evidence = defect_evidence or {}
    msg_lower = error_message.lower()

    # --- P0: 安全断言失败 ---
    if failure_lower in _P0_SECURITY_ASSERTIONS:
        return (1, _UX_CATEGORY_MAP.get(failure_lower))

    # --- P0: 系统崩溃（白屏 / 500） ---
    if any(kw in msg_lower for kw in _P0_CRASH_KEYWORDS):
        return (1, None)

    # --- P1: 内存泄漏嫌疑 ---
    if failure_lower in _P1_MEMORY_LEAK or bool(evidence.get("memory_leak_suspect")):
        return (2, "response_performance")

    # --- P1: 5xx 网络错误 ---
    network_failures = evidence.get("network_failures", [])
    if network_failures:
        for failure in network_failures:
            status_code = str(failure.get("status", ""))
            if any(code in status_code for code in _P1_NETWORK_5XX):
                return (2, "response_performance")

    # --- P1: no_network_errors 断言失败 ---
    if failure_lower == "no_network_errors":
        return (2, "response_performance")

    # --- P1: 数据不一致 / 权限绕过 ---
    if any(kw in msg_lower for kw in _P1_DATA_KEYWORDS):
        return (2, None)

    # --- P1: 核心功能不可用（元素未找到导致流程中断） ---
    if failure_lower in ("element_not_found", "locator_failure") or any(
        kw in msg_lower for kw in _P1_ELEMENT_FAILURES
    ):
        return (2, None)

    # --- P2: 加载超时 ---
    if failure_lower in _P2_LOADING_ASSERTIONS:
        return (3, _UX_CATEGORY_MAP.get(failure_lower))

    # --- P2: response_time_lt 断言失败 ---
    if failure_lower == "response_time_lt":
        return (3, "response_performance")

    # --- P2: 渲染问题（text_not_empty 失败） ---
    if failure_lower in _P2_RENDERING_ASSERTIONS:
        return (3, _UX_CATEGORY_MAP.get(failure_lower))

    # --- P2: 非核心功能异常 / 体验性问题 ---
    if failure_lower in ("not_visible", "visible", "text_contains",
                         "text_equals", "text_matches"):
        return (3, "visual_consistency")

    # --- P3: 控制台错误 ---
    if failure_lower in _P3_CONSOLE_ASSERTIONS:
        return (4, "error_feedback")

    # --- P3: UI 瑕疵 / 非关键体验优化 ---
    if failure_lower in ("url_contains", "url_equals"):
        return (4, None)

    # --- 默认 P2 ---
    return (3, None)


def _generate_bug_no(db: Session, project_id: int) -> str:
    """生成 Bug 编号，格式: BUG-{project_id}-{YYYYMMDD}-{序号:04d}。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        全局唯一的 Bug 编号字符串。
    """
    from app.models.bug import Bug
    from app.utils.db_time import utcnow

    prefix = f"BUG-{project_id}-{utcnow().strftime('%Y%m%d')}-"
    count = db.query(Bug).filter(Bug.project_id == project_id, Bug.bug_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def _auto_create_defect_bug(
    db: Session,
    project: Project,
    failure_type: str,
    error_message: str,
    defect_evidence: Optional[Dict[str, Any]] = None,
    test_case_id: Optional[int] = None,
    test_result_id: Optional[int] = None,
    step_description: str = "",
) -> Optional["Bug"]:
    """根据缺陷严重度自动创建 Bug 记录。

    调用 _assess_defect_severity 评估严重度和 UX 分类后创建 Bug。
    P0/P1 缺陷标记为需立即通知，P2/P3 缺陷仅记录不立即通知。

    Args:
        db: 数据库会话。
        project: 关联的项目实例（必须为自测项目）。
        failure_type: 断言类型或缺陷来源标识。
        error_message: 步骤执行错误信息。
        defect_evidence: 浏览器缺陷证据字典。
        test_case_id: 关联测试用例 ID。
        test_result_id: 关联执行结果 ID。
        step_description: 步骤描述，用于 Bug 标题和描述。

    Returns:
        创建的 Bug 实例；评估失败或项目非自测时返回 None。
    """
    if not getattr(project, "is_self_test", False):
        return None

    from app.models.bug import Bug, VALID_UX_CATEGORIES

    severity, ux_category = _assess_defect_severity(
        failure_type=failure_type,
        defect_evidence=defect_evidence,
        error_message=error_message,
    )

    # 应用层校验 ux_category 合法性
    if ux_category is not None and ux_category not in VALID_UX_CATEGORIES:
        logger.warning(f"ux_category '{ux_category}' 不在合法枚举中，置为 None")
        ux_category = None

    # 优先级映射：severity 1→priority 1, 2→1, 3→2, 4→3
    priority_map = {1: 1, 2: 1, 3: 2, 4: 3}
    priority = priority_map.get(severity, 2)

    # 构建 Bug 标题
    title_prefix = f"[P{severity}]" if severity <= 2 else f"[P{severity}]"
    title = f"{title_prefix} 自测发现缺陷: {step_description or failure_type}"
    if len(title) > 255:
        title = title[:252] + "..."

    # 构建 Bug 描述（包含复现步骤 + 缺陷证据）
    evidence_str = ""
    if defect_evidence:
        try:
            evidence_str = json.dumps(defect_evidence, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            evidence_str = str(defect_evidence)

    description_parts = [
        f"缺陷来源: {failure_type}",
        f"严重程度: P{severity} (severity={severity})",
        f"UX分类: {ux_category or '功能Bug'}",
        f"错误信息: {error_message}",
    ]
    if evidence_str:
        description_parts.append(f"缺陷证据: {evidence_str}")
    description = "\n".join(description_parts)

    bug = Bug(
        bug_no=_generate_bug_no(db, project.id),
        project_id=project.id,
        title=title,
        description=description,
        severity=severity,
        priority=priority,
        status="open",
        source="self_test",
        ux_category=ux_category,
        reporter_id=project.user_id,
        test_case_id=test_case_id,
        test_result_id=test_result_id,
        reproduction_steps=f"步骤: {step_description}\n错误信息: {error_message}",
        actual_behavior=error_message,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)

    logger.info(
        f"自测缺陷自动创建Bug: bug_no={bug.bug_no}, severity=P{severity}, "
        f"ux_category={ux_category}, failure_type={failure_type}"
    )

    return bug


async def _notify_critical_defect_bug(bug: "Bug", project: Project) -> None:
    """P0/P1 缺陷立即通过 WebSocket 推送通知给管理员。

    复用 app.core.websocket.manager 的 broadcast 方法，
    以项目 ID 为频道标识推送紧急缺陷通知。

    Args:
        bug: 已创建的 Bug 实例。
        project: 关联的项目实例。
    """
    from app.core.websocket import manager as ws_manager

    try:
        message = {
            "type": "critical_defect_notification",
            "project_id": project.id,
            "project_name": project.name,
            "bug_no": bug.bug_no,
            "title": bug.title,
            "severity": bug.severity,
            "ux_category": bug.ux_category,
            "source": bug.source,
            "create_time": bug.create_time.isoformat() if bug.create_time else None,
        }
        await ws_manager.broadcast(str(project.id), message)
        logger.info(f"P0/P1缺陷通知已推送: bug_no={bug.bug_no}")
    except Exception as exc:
        logger.warning(f"P0/P1缺陷WebSocket通知失败: {exc}")
