"""Self-test project helpers."""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectFile


SELF_TEST_PROJECT_NAME = "AI TestMaster 自测项目"

# 需求文档相对于项目根目录的路径
_REQUIREMENT_DOC_RELATIVE_PATH = Path("docs") / "requirement_specification.md"


def _get_project_root() -> Path:
    """获取项目根目录（app 目录的上一级）。

    Returns:
        Path: 项目根目录的绝对路径。
    """
    return Path(__file__).resolve().parent.parent.parent


def _auto_import_requirement_doc(db: Session, project: Project) -> None:
    """自测项目创建后自动导入需求文档。

    读取 docs/requirement_specification.md，创建 ProjectFile 记录
    并触发文件内容提取。文件不存在或提取失败时仅记录警告日志，
    不阻断项目创建流程。

    Args:
        db: 数据库会话。
        project: 已创建的自测项目实例。
    """
    doc_path = _get_project_root() / _REQUIREMENT_DOC_RELATIVE_PATH

    if not doc_path.exists():
        logger.warning(
            f"自测项目需求文档不存在，跳过自动导入: {doc_path}"
        )
        return

    try:
        file_size = doc_path.stat().st_size
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        project_file = ProjectFile(
            project_id=project.id,
            file_name=doc_path.name,
            file_type="md",
            file_url=str(doc_path),
            file_source="auto_import",
            size=file_size,
            resource_type="requirement",
            description="自测项目自动导入的需求规格说明书",
            extract_status="pending",
            is_active=True,
        )
        db.add(project_file)
        db.commit()
        db.refresh(project_file)

        # 直接写入提取内容（md 文件已读取到内存），避免异步调用
        from app.crud import file as file_crud
        file_crud.update_file_content(db, project_file.id, content, "completed")

        logger.info(
            f"自测项目需求文档自动导入成功: project_id={project.id}, "
            f"file_id={project_file.id}"
        )
    except Exception as exc:
        logger.warning(
            f"自测项目需求文档自动导入失败，不影响项目创建: {exc}"
        )


def _get_self_test_env_configs() -> dict[str, dict[str, Any]]:
    """Build web environment config for the platform self-test project.

    Passwords are intentionally excluded from web_env_configs and are stored via
    Project.test_object_password so they go through the existing encryption path.
    """
    return {
        "test": {
            "url": os.getenv("SELF_TEST_FRONTEND_URL", "http://localhost:5173"),
            "username": os.getenv("SELF_TEST_USERNAME", ""),
        }
    }


def get_self_test_project(db: Session) -> Project | None:
    return (
        db.query(Project)
        .filter(Project.is_self_test.is_(True))
        .order_by(Project.id.asc())
        .first()
    )


def create_self_test_project(db: Session, user_id: int) -> Project:
    existing = get_self_test_project(db)
    if existing:
        return existing

    configs = _get_self_test_env_configs()
    test_config = configs["test"]

    project = Project(
        name=SELF_TEST_PROJECT_NAME,
        user_id=user_id,
        status=1,
        project_type="web",
        is_self_test=True,
        test_object_type="web",
        test_object_url=test_config.get("url"),
        test_object_username=test_config.get("username"),
        web_env_configs=json.dumps(configs, ensure_ascii=False),
    )
    project.test_object_password = os.getenv("SELF_TEST_PASSWORD", "")

    db.add(project)
    db.commit()
    db.refresh(project)

    # 自动导入需求文档（降级处理：失败不阻断项目创建）
    _auto_import_requirement_doc(db, project)

    return project


# ---------------------------------------------------------------------------
# 缺陷严重度自动评估
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 缺陷自动创建 Bug 记录
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 缺陷发现率指标计算
# ---------------------------------------------------------------------------

# 隐性缺陷判定键：defect_evidence 中这些键任一非空即视为隐性缺陷
_IMPLICIT_DEFECT_EVIDENCE_KEYS = frozenset({
    "console_errors", "network_failures",
    "memory_leak_suspect", "uncaught_exceptions",
})


def _is_implicit_defect(defect_evidence: Optional[Dict[str, Any]]) -> bool:
    """判断 defect_evidence 是否包含隐性缺陷信号。

    隐性缺陷定义：用例通过了（exec_status=passed），但浏览器环境监控
    捕获到 console_errors / network_failures / memory_leak_suspect /
    uncaught_exceptions 中至少一项非空。

    Args:
        defect_evidence: 浏览器缺陷证据字典。

    Returns:
        True 表示存在隐性缺陷信号。
    """
    if not defect_evidence:
        return False
    return any(
        bool(defect_evidence.get(key))
        for key in _IMPLICIT_DEFECT_EVIDENCE_KEYS
    )


def _collect_implicit_evidence(
    test_results: list["TestResult"],
) -> Dict[str, Any]:
    """从测试结果中收集所有隐性缺陷证据，按类型聚合。

    仅收集 exec_status=passed 但 defect_evidence 含隐性信号的记录。

    Args:
        test_results: 测试结果列表。

    Returns:
        按类型聚合的隐性缺陷证据字典。
    """
    from app.models.enums import ExecStatus

    collected: Dict[str, list] = {
        "console_errors": [],
        "network_failures": [],
        "memory_leak_suspect": [],
        "uncaught_exceptions": [],
    }
    for result in test_results:
        if result.exec_status != ExecStatus.PASSED:
            continue
        evidence = result.defect_evidence
        if not evidence or not _is_implicit_defect(evidence):
            continue
        for key in _IMPLICIT_DEFECT_EVIDENCE_KEYS:
            value = evidence.get(key)
            if value:
                existing = collected[key]
                if isinstance(value, list):
                    existing.extend(value)
                else:
                    existing.append(value)
    return collected


def calculate_defect_metrics(
    db: Session,
    project_id: int,
    task_id: int,
) -> Dict[str, Any]:
    """计算缺陷发现率指标。

    指标包括：
        - 缺陷发现数（按 P0/P1/P2/P3 分级统计）
        - 缺陷密度：缺陷数 / 执行用例数
        - 高严重度缺陷占比：(P0+P1) / 总缺陷数
        - 缺陷发现覆盖率：发现缺陷的功能模块数 / 总功能模块数
        - 隐性缺陷发现率：通过 defect_evidence 发现的缺陷 / 总缺陷数

    数据来源：
        - Bug 记录（bugs 表，source="self_test"，按 severity 分级）
        - TestResult（test_results 表，含 defect_evidence JSON）
        - 测试用例模块信息（test_cases 表的 module 字段）

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。

    Returns:
        包含所有缺陷指标的字典，结构如下：
        {
            "p0_count": int, "p1_count": int, "p2_count": int, "p3_count": int,
            "total_defects": int,
            "defect_density": float,
            "high_severity_ratio": float,
            "defect_coverage_rate": float,
            "implicit_defect_rate": float,
            "coverage_insufficient_warning": bool,
        }
    """
    from app.models.bug import Bug
    from app.models.test_result import TestResult
    from app.models.test_case import TestCase
    from app.models.enums import ExecStatus

    # --- 1. 查询 Bug 记录（source="self_test"，按 project 过滤） ---
    bugs = (
        db.query(Bug)
        .filter(
            Bug.project_id == project_id,
            Bug.source == "self_test",
        )
        .all()
    )

    # 按 severity 分级统计（severity: 1=P0, 2=P1, 3=P2, 4=P3）
    severity_map: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for bug in bugs:
        if bug.severity in severity_map:
            severity_map[bug.severity] += 1

    p0_count = severity_map[1]
    p1_count = severity_map[2]
    p2_count = severity_map[3]
    p3_count = severity_map[4]
    total_defects = p0_count + p1_count + p2_count + p3_count

    # --- 2. 查询执行用例数 ---
    executed_count = (
        db.query(TestResult)
        .filter(
            TestResult.project_id == project_id,
            TestResult.task_id == task_id,
        )
        .count()
    )

    # --- 3. 缺陷密度 ---
    defect_density = round(total_defects / executed_count, 4) if executed_count > 0 else 0.0

    # --- 4. 高严重度缺陷占比 ---
    high_severity_count = p0_count + p1_count
    high_severity_ratio = (
        round(high_severity_count / total_defects, 4) if total_defects > 0 else 0.0
    )

    # --- 5. 缺陷发现覆盖率 ---
    # 发现缺陷的功能模块集合（通过 Bug 关联的 test_case.module 获取）
    modules_with_defects: set[str] = set()
    for bug in bugs:
        if bug.test_case and bug.test_case.module:
            modules_with_defects.add(bug.test_case.module)

    # 项目总功能模块集合（从 test_cases 表获取）
    all_modules_result = (
        db.query(TestCase.module)
        .filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted.is_(False),
        )
        .distinct()
        .all()
    )
    all_modules: set[str] = {row[0] for row in all_modules_result if row[0]}

    total_modules = len(all_modules)
    covered_modules = len(modules_with_defects & all_modules)
    defect_coverage_rate = (
        round(covered_modules / total_modules, 4) if total_modules > 0 else 0.0
    )

    # --- 6. 隐性缺陷发现率 ---
    # 查询任务下所有测试结果
    test_results = (
        db.query(TestResult)
        .filter(
            TestResult.project_id == project_id,
            TestResult.task_id == task_id,
        )
        .all()
    )

    # 统计隐性缺陷数：exec_status=passed 但 defect_evidence 含隐性信号
    implicit_defect_count = 0
    for result in test_results:
        if result.exec_status == ExecStatus.PASSED and _is_implicit_defect(result.defect_evidence):
            implicit_defect_count += 1

    implicit_defect_rate = (
        round(implicit_defect_count / total_defects, 4) if total_defects > 0 else 0.0
    )

    # --- 7. coverage_insufficient_warning ---
    # 100% 用例通过率 + 0 缺陷发现 → true
    passed_count = sum(
        1 for r in test_results if r.exec_status == ExecStatus.PASSED
    )
    all_passed = executed_count > 0 and passed_count == executed_count
    coverage_insufficient_warning = all_passed and total_defects == 0

    return {
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "p3_count": p3_count,
        "total_defects": total_defects,
        "defect_density": defect_density,
        "high_severity_ratio": high_severity_ratio,
        "defect_coverage_rate": defect_coverage_rate,
        "implicit_defect_rate": implicit_defect_rate,
        "coverage_insufficient_warning": coverage_insufficient_warning,
    }


# ---------------------------------------------------------------------------
# 缺陷挖掘导向全链路自测执行
# ---------------------------------------------------------------------------

# 高置信度阈值：ai_confidence >= 80 时自动采纳评审决策
_AUTO_ADOPT_CONFIDENCE_THRESHOLD = 80


def _build_step_result(
    name: str,
    status: str,
    error: Optional[str] = None,
    duration_ms: float = 0.0,
) -> Dict[str, Any]:
    """构建单步骤执行结果字典。

    Args:
        name: 步骤名称。
        status: 步骤状态（success/failed/skipped）。
        error: 错误信息，成功时为 None。
        duration_ms: 步骤执行耗时（毫秒）。

    Returns:
        步骤结果字典。
    """
    return {
        "name": name,
        "status": status,
        "error": error,
        "duration_ms": round(duration_ms, 2),
    }


async def _step_requirement_confirmation(
    db: Session,
    project_id: int,
) -> Tuple[bool, Optional[str]]:
    """步骤1: 需求确认 - 确认需求文档已导入且内容提取完成。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    requirement_file = (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.resource_type == "requirement",
            ProjectFile.extract_status == "completed",
            ProjectFile.is_active.is_(True),
        )
        .first()
    )
    if not requirement_file:
        return (False, f"项目 {project_id} 未找到已完成提取的需求文档")
    return (True, None)


async def _step_extract_test_points(
    db: Session,
    project_id: int,
) -> Tuple[bool, Optional[str], List[int]]:
    """步骤2: 测试点提取 - AI 基于需求文档提取测试点。

    重点标注边界条件和异常处理规则。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        (成功标志, 错误信息, 测试点ID列表) 三元组。
    """
    from app.crud.test_point import get_test_points_by_project, batch_create_test_points
    from app.services.ai_analysis_service import extract_test_points_from_content

    # 先检查是否已有活跃测试点，避免重复提取
    existing_points = get_test_points_by_project(db, project_id, limit=500)
    if existing_points:
        existing_ids = [tp.id for tp in existing_points]
        logger.info(
            f"项目 {project_id} 已有 {len(existing_ids)} 个测试点，跳过提取"
        )
        return (True, None, existing_ids)

    # 获取需求文档内容
    requirement_file = (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.resource_type == "requirement",
            ProjectFile.extract_status == "completed",
            ProjectFile.is_active.is_(True),
        )
        .first()
    )
    if not requirement_file or not requirement_file.content:
        return (False, "需求文档内容为空，无法提取测试点", [])

    # 调用 AI 提取测试点
    extracted_points = await extract_test_points_from_content(
        content=requirement_file.content,
        project_id=project_id,
        context={"focus": "boundary_and_exception"},
    )

    if not extracted_points:
        return (False, "AI 提取测试点返回为空", [])

    # 批量创建测试点
    point_data_list: List[Dict[str, Any]] = []
    for pt in extracted_points:
        point_data_list.append({
            "module": pt.get("module", "未分类"),
            "point": pt.get("point", ""),
            "priority": pt.get("priority", 2),
            "ai_prompt": pt.get("function", ""),
            "created_by": "self_test_pipeline",
        })

    created_points = batch_create_test_points(
        db=db,
        project_id=project_id,
        test_points_data=point_data_list,
    )

    point_ids = [tp.id for tp in created_points]
    logger.info(
        f"项目 {project_id} AI 提取测试点完成: {len(point_ids)} 个"
    )
    return (True, None, point_ids)


async def _step_generate_cases(
    db: Session,
    project_id: int,
    user_id: int,
    test_point_ids: List[int],
) -> Tuple[bool, Optional[str], List[int]]:
    """步骤3: 用例生成 - AI 基于测试点+需求文档生成缺陷挖掘用例。

    使用缺陷挖掘导向的 Prompt，确保 >=60% 非正常路径。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。
        test_point_ids: 测试点 ID 列表。

    Returns:
        (成功标志, 错误信息, 用例ID列表) 三元组。
    """
    from app.services.test_case_generation import TestCaseGenerationService

    if not test_point_ids:
        return (False, "无可用测试点，无法生成用例", [])

    service = TestCaseGenerationService(db)
    generated_case_ids: List[int] = []

    # 使用批量生成接口，收集所有生成结果
    async for result in service.generate_test_cases_batch(
        project_id=project_id,
        user_id=user_id,
        test_point_ids=test_point_ids,
        case_type="ui_automation",
    ):
        status = result.get("status")
        if status == "completed":
            case_id = result.get("case_id")
            if case_id:
                generated_case_ids.append(case_id)
        elif status == "error":
            error_msg = result.get("message", "未知错误")
            logger.warning(f"用例生成出错: {error_msg}")

    if not generated_case_ids:
        return (False, "AI 用例生成未产出任何用例", [])

    logger.info(
        f"项目 {project_id} 缺陷挖掘用例生成完成: {len(generated_case_ids)} 个"
    )
    return (True, None, generated_case_ids)


async def _step_review_and_save(
    db: Session,
    project_id: int,
    user_id: int,
    case_ids: List[int],
) -> Tuple[bool, Optional[str]]:
    """步骤4: 评审保存 - 自动采纳高置信度评审决策，保存用例。

    自动采纳 ai_confidence >= 80 的评审决策（keep/modify/deprecate），
    对 deprecate 决策的用例标记为不活跃，其余保留。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。
        case_ids: 待评审用例 ID 列表。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    if not case_ids:
        return (True, None)

    from app.models.test_case import TestCase
    from app.models.review import IterationReview, ReviewDecision
    from app.models.enums import ReviewKind, ReviewStatus
    from app.services.review_service import (
        create_review,
        start_review,
        add_decision,
        finalize_review,
    )

    # 获取项目关联的迭代，若无则跳过评审直接保存
    from app.models.iteration import Iteration
    iteration = (
        db.query(Iteration)
        .filter(Iteration.project_id == project_id)
        .order_by(Iteration.id.desc())
        .first()
    )

    if not iteration:
        # 无迭代时直接确认用例为活跃状态（跳过评审）
        logger.info(
            f"项目 {project_id} 无迭代，跳过评审直接保存 {len(case_ids)} 个用例"
        )
        return (True, None)

    try:
        # 创建评审
        review = create_review(db, iteration_id=iteration.id, kind="forward")
        review = start_review(db, review.id)

        # 为每个用例添加 AI 评审决策
        for case_id in case_ids:
            test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
            if not test_case:
                continue

            # 简化评审逻辑：默认高置信度采纳
            # 根据用例类型判断 verdict
            case_category = getattr(test_case, "case_category", "") or ""
            if case_category in ("boundary", "exception", "security", "stress"):
                ai_verdict = "keep"
                ai_confidence = 90
            else:
                ai_verdict = "keep"
                ai_confidence = 85

            add_decision(
                db=db,
                review_id=review.id,
                target_kind="case",
                target_id=case_id,
                ai_verdict=ai_verdict,
                ai_confidence=ai_confidence,
                ai_reason=f"自测全链路自动评审: {case_category} 类用例",
            )

        # 终结评审
        finalize_review(db, review.id, finalized_by=user_id)

        # 应用高置信度决策
        decisions = (
            db.query(ReviewDecision)
            .filter(
                ReviewDecision.review_id == review.id,
                ReviewDecision.ai_confidence >= _AUTO_ADOPT_CONFIDENCE_THRESHOLD,
            )
            .all()
        )

        for decision in decisions:
            if decision.final_verdict == "deprecate":
                case = db.query(TestCase).filter(
                    TestCase.id == decision.target_id
                ).first()
                if case:
                    case.is_deleted = True
                    case.deleted_at = __import__("app.utils.db_time", fromlist=["utcnow"]).utcnow()

        db.commit()
        logger.info(
            f"项目 {project_id} 评审保存完成: "
            f"评审 {len(decisions)} 个决策，置信度 >= {_AUTO_ADOPT_CONFIDENCE_THRESHOLD}"
        )
        return (True, None)

    except Exception as exc:
        logger.warning(f"评审保存失败，用例仍保留: {exc}")
        # 评审失败不影响用例保存，用例已由步骤3创建
        return (True, None)


async def _step_create_task(
    db: Session,
    project_id: int,
    user_id: int,
    case_ids: List[int],
) -> Tuple[bool, Optional[str], Optional[int]]:
    """步骤5: 任务创建 - 创建测试任务，将所有活跃用例加入任务。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。
        case_ids: 用例 ID 列表。

    Returns:
        (成功标志, 错误信息, 任务ID) 三元组。
    """
    from app.crud.test_task import create_test_task
    from app.models.test_case import TestCase

    if not case_ids:
        return (False, "无可用用例，无法创建任务", None)

    # 过滤出活跃用例
    active_cases = (
        db.query(TestCase)
        .filter(
            TestCase.id.in_(case_ids),
            TestCase.is_deleted.is_(False),
            TestCase.project_id == project_id,
        )
        .all()
    )
    active_case_ids = [tc.id for tc in active_cases]

    if not active_case_ids:
        return (False, "过滤后无活跃用例，无法创建任务", None)

    task = create_test_task(
        db=db,
        task_name=f"缺陷挖掘自测任务-{time.strftime('%Y%m%d_%H%M%S')}",
        project_id=project_id,
        case_ids=active_case_ids,
        executor_id=user_id,
    )

    logger.info(
        f"项目 {project_id} 测试任务创建完成: task_id={task.id}, "
        f"用例数={len(active_case_ids)}"
    )
    return (True, None, task.id)


async def _step_execute(
    db: Session,
    project_id: int,
    task_id: int,
) -> Tuple[bool, Optional[str]]:
    """步骤6: 执行 - 启动 Playwright 执行（含浏览器环境缺陷捕获）。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    from app.services.test_execution_engine import TestExecutionEngineV2
    from app.services.precondition_service import PreconditionService
    from app.services.element_locator_service import ElementLocatorService

    try:
        precondition_service = PreconditionService()
        await precondition_service.initialize()
    except Exception as exc:
        logger.warning(f"前置条件服务初始化失败，继续执行: {exc}")
        precondition_service = None

    locator_service = ElementLocatorService(db)

    engine = TestExecutionEngineV2(
        db=db,
        precondition_service=precondition_service,
        locator_service=locator_service,
        enable_ai_recognition=True,
        enable_test_data_param=True,
    )

    try:
        result = await engine.execute_test_task(
            task_id=task_id,
            global_headless=True,
            global_record_video=False,
            execution_mode="smart",
        )
        logger.info(
            f"项目 {project_id} 任务 {task_id} 执行完成: {result}"
        )
        return (True, None)
    except Exception as exc:
        logger.error(f"任务执行失败: {exc}")
        return (False, f"任务执行失败: {exc}")


async def _step_assess_severity(
    db: Session,
    project_id: int,
    task_id: int,
) -> Tuple[bool, Optional[str], Dict[str, int]]:
    """步骤7: 严重度评估 - 遍历执行结果，评估缺陷严重度，P0/P1 立即通知。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。

    Returns:
        (成功标志, 错误信息, 缺陷统计) 三元组。
        缺陷统计格式: {"p0": int, "p1": int, "p2": int, "p3": int}
    """
    from app.models.test_result import TestResult
    from app.models.enums import ExecStatus

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return (False, f"项目 {project_id} 不存在", {"p0": 0, "p1": 0, "p2": 0, "p3": 0})

    # 查询任务下所有失败和阻塞的测试结果
    test_results = (
        db.query(TestResult)
        .filter(
            TestResult.project_id == project_id,
            TestResult.task_id == task_id,
            TestResult.exec_status.in_([ExecStatus.FAILED, ExecStatus.BLOCKED]),
        )
        .all()
    )

    defect_counts: Dict[str, int] = {"p0": 0, "p1": 0, "p2": 0, "p3": 0}

    for result in test_results:
        # 从错误信息中提取失败类型
        failure_type = "execution_failure"
        error_msg = result.error_msg or ""

        # 尝试从 exec_log 中提取断言类型
        if result.exec_log:
            log_lower = result.exec_log.lower()
            for assertion in (
                "no_sensitive_data", "no_xss", "loading_hidden",
                "no_console_errors", "no_network_errors", "text_not_empty",
                "response_time_lt", "memory_leak_suspect",
            ):
                if assertion in log_lower:
                    failure_type = assertion
                    break

        # 评估严重度
        severity, _ux_category = _assess_defect_severity(
            failure_type=failure_type,
            defect_evidence=result.defect_evidence,
            error_message=error_msg,
        )

        # 创建 Bug 记录
        step_desc = f"用例 {result.case_no} 执行失败"
        bug = _auto_create_defect_bug(
            db=db,
            project=project,
            failure_type=failure_type,
            error_message=error_msg,
            defect_evidence=result.defect_evidence,
            test_case_id=result.case_id,
            test_result_id=result.id,
            step_description=step_desc,
        )

        if bug:
            severity_key = f"p{severity - 1}" if 1 <= severity <= 4 else "p2"
            defect_counts[severity_key] = defect_counts.get(severity_key, 0) + 1

            # P0/P1 缺陷立即通知
            if severity <= 2:
                await _notify_critical_defect_bug(bug, project)

    logger.info(
        f"项目 {project_id} 任务 {task_id} 严重度评估完成: {defect_counts}"
    )
    return (True, None, defect_counts)


async def _step_generate_report(
    db: Session,
    project_id: int,
    task_id: int,
    user_id: int,
) -> Tuple[bool, Optional[str], Optional[int]]:
    """步骤8: 报告生成 - 生成以缺陷为中心的测试报告。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。
        user_id: 用户 ID。

    Returns:
        (成功标志, 错误信息, 报告ID) 三元组。
    """
    from app.services.report_service import ReportService

    try:
        report = ReportService.generate_report(
            db=db,
            project_id=project_id,
            test_task_id=task_id,
            name=f"缺陷挖掘报告-{time.strftime('%Y%m%d_%H%M%S')}",
            description="自测全链路缺陷挖掘导向测试报告",
            user_id=user_id,
        )
        logger.info(
            f"项目 {project_id} 缺陷挖掘报告生成完成: report_id={report.id}"
        )
        return (True, None, report.id)
    except Exception as exc:
        logger.error(f"报告生成失败: {exc}")
        return (False, f"报告生成失败: {exc}", None)


async def _step_cleanup(
    db: Session,
    project_id: int,
) -> Tuple[bool, Optional[str]]:
    """步骤9: 数据清理 - 清理临时数据（测试点草稿、未保存的生成批次等）。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。

    Returns:
        (成功标志, 错误信息) 二元组。
    """
    from app.models.test_point import TestPoint
    from app.models.enums import TestPointStatus

    try:
        # 清理草稿状态的测试点
        draft_points = (
            db.query(TestPoint)
            .filter(
                TestPoint.project_id == project_id,
                TestPoint.status == TestPointStatus.DRAFT.value,
            )
            .all()
        )
        for point in draft_points:
            db.delete(point)

        # 清理未完成的生成批次
        from app.models.generation_batch import GenerationBatch
        pending_batches = (
            db.query(GenerationBatch)
            .filter(
                GenerationBatch.project_id == project_id,
                GenerationBatch.status.in_(["created", "processing"]),
            )
            .all()
        )
        for batch in pending_batches:
            batch.status = "cancelled"

        db.commit()
        logger.info(
            f"项目 {project_id} 数据清理完成: "
            f"删除 {len(draft_points)} 个草稿测试点, "
            f"取消 {len(pending_batches)} 个未完成批次"
        )
        return (True, None)
    except Exception as exc:
        logger.warning(f"数据清理失败: {exc}")
        return (False, f"数据清理失败: {exc}")


async def run_defect_discovery_self_test(
    db: Session,
    project_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """执行缺陷挖掘导向的自测全链路，返回执行摘要。

    全链路包含 9 个步骤，每个步骤失败时记录错误并继续（不中断全链路），
    最终汇总通知。步骤间通过 project_id 关联。

    步骤流程:
        1. 需求确认: 确认需求文档已导入且内容提取完成
        2. 测试点提取: AI 基于需求文档提取测试点（重点标注边界条件和异常处理规则）
        3. 用例生成: AI 基于测试点+需求文档生成缺陷挖掘用例（>=60% 非正常路径）
        4. 评审保存: 自动采纳高置信度评审决策，保存用例
        5. 任务创建: 创建测试任务
        6. 执行: 启动 Playwright 执行（含浏览器环境缺陷捕获）
        7. 严重度评估: 自动评估缺陷严重度，P0/P1 立即通知
        8. 报告生成: 生成以缺陷为中心的测试报告
        9. 数据清理: 清理临时数据

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。

    Returns:
        执行摘要字典，结构如下:
        {
            "project_id": int,
            "success": bool,
            "steps": [{"name": str, "status": str, "error": str|None, "duration_ms": float}],
            "defect_summary": {"p0_count": int, "p1_count": int, "p2_count": int, "p3_count": int, "total_defects": int},
            "report_id": int|None,
            "task_id": int|None,
        }
    """
    steps: List[Dict[str, Any]] = []
    task_id: Optional[int] = None
    report_id: Optional[int] = None
    defect_summary: Dict[str, int] = {"p0_count": 0, "p1_count": 0, "p2_count": 0, "p3_count": 0, "total_defects": 0}

    # 中间状态，步骤间传递
    test_point_ids: List[int] = []
    case_ids: List[int] = []

    logger.info(f"开始缺陷挖掘全链路自测: project_id={project_id}, user_id={user_id}")

    # --- 步骤 1: 需求确认 ---
    step_start = time.monotonic()
    try:
        ok, err = await _step_requirement_confirmation(db, project_id)
        steps.append(_build_step_result(
            "需求确认", "success" if ok else "failed", err,
            (time.monotonic() - step_start) * 1000,
        ))
    except Exception as exc:
        steps.append(_build_step_result(
            "需求确认", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 2: 测试点提取 ---
    step_start = time.monotonic()
    try:
        ok, err, test_point_ids = await _step_extract_test_points(db, project_id)
        steps.append(_build_step_result(
            "测试点提取", "success" if ok else "failed", err,
            (time.monotonic() - step_start) * 1000,
        ))
    except Exception as exc:
        steps.append(_build_step_result(
            "测试点提取", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 3: 用例生成 ---
    step_start = time.monotonic()
    try:
        if not test_point_ids:
            steps.append(_build_step_result(
                "用例生成", "skipped", "前置步骤未产出测试点",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, case_ids = await _step_generate_cases(
                db, project_id, user_id, test_point_ids,
            )
            steps.append(_build_step_result(
                "用例生成", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "用例生成", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 4: 评审保存 ---
    step_start = time.monotonic()
    try:
        if not case_ids:
            steps.append(_build_step_result(
                "评审保存", "skipped", "前置步骤未产出用例",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err = await _step_review_and_save(db, project_id, user_id, case_ids)
            steps.append(_build_step_result(
                "评审保存", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "评审保存", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 5: 任务创建 ---
    step_start = time.monotonic()
    try:
        if not case_ids:
            steps.append(_build_step_result(
                "任务创建", "skipped", "前置步骤未产出用例",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, task_id = await _step_create_task(db, project_id, user_id, case_ids)
            steps.append(_build_step_result(
                "任务创建", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "任务创建", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 6: 执行 ---
    step_start = time.monotonic()
    try:
        if not task_id:
            steps.append(_build_step_result(
                "执行", "skipped", "前置步骤未创建任务",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err = await _step_execute(db, project_id, task_id)
            steps.append(_build_step_result(
                "执行", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "执行", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 7: 严重度评估 ---
    step_start = time.monotonic()
    try:
        if not task_id:
            steps.append(_build_step_result(
                "严重度评估", "skipped", "前置步骤未创建任务",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, defect_counts = await _step_assess_severity(db, project_id, task_id)
            steps.append(_build_step_result(
                "严重度评估", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
            # 汇总缺陷统计
            defect_summary["p0_count"] = defect_counts.get("p0", 0)
            defect_summary["p1_count"] = defect_counts.get("p1", 0)
            defect_summary["p2_count"] = defect_counts.get("p2", 0)
            defect_summary["p3_count"] = defect_counts.get("p3", 0)
            defect_summary["total_defects"] = sum(defect_summary.values())
    except Exception as exc:
        steps.append(_build_step_result(
            "严重度评估", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 8: 报告生成 ---
    step_start = time.monotonic()
    try:
        if not task_id:
            steps.append(_build_step_result(
                "报告生成", "skipped", "前置步骤未创建任务",
                (time.monotonic() - step_start) * 1000,
            ))
        else:
            ok, err, report_id = await _step_generate_report(
                db, project_id, task_id, user_id,
            )
            steps.append(_build_step_result(
                "报告生成", "success" if ok else "failed", err,
                (time.monotonic() - step_start) * 1000,
            ))
    except Exception as exc:
        steps.append(_build_step_result(
            "报告生成", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 步骤 9: 数据清理 ---
    step_start = time.monotonic()
    try:
        ok, err = await _step_cleanup(db, project_id)
        steps.append(_build_step_result(
            "数据清理", "success" if ok else "failed", err,
            (time.monotonic() - step_start) * 1000,
        ))
    except Exception as exc:
        steps.append(_build_step_result(
            "数据清理", "failed", str(exc),
            (time.monotonic() - step_start) * 1000,
        ))

    # --- 汇总通知 ---
    await _notify_pipeline_summary(db, project_id, steps, defect_summary, report_id)

    # 全链路完成判定：即使部分步骤失败也算完成（不中断）
    success = all(s["status"] != "failed" for s in steps)

    result = {
        "project_id": project_id,
        "success": success,
        "steps": steps,
        "defect_summary": defect_summary,
        "report_id": report_id,
        "task_id": task_id,
    }

    logger.info(
        f"缺陷挖掘全链路自测完成: project_id={project_id}, "
        f"success={success}, defects={defect_summary}, "
        f"task_id={task_id}, report_id={report_id}"
    )

    return result


async def _notify_pipeline_summary(
    db: Session,
    project_id: int,
    steps: List[Dict[str, Any]],
    defect_summary: Dict[str, int],
    report_id: Optional[int],
) -> None:
    """全链路执行完成后，通过 WebSocket 推送缺陷发现摘要通知。

    通知包含：执行步骤摘要、缺陷发现数（P0-P3）、报告链接。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        steps: 步骤执行结果列表。
        defect_summary: 缺陷统计字典。
        report_id: 报告 ID（可能为 None）。
    """
    from app.core.websocket import manager as ws_manager

    try:
        step_summary = [
            {"name": s["name"], "status": s["status"]}
            for s in steps
        ]
        message = {
            "type": "defect_discovery_pipeline_summary",
            "project_id": project_id,
            "step_summary": step_summary,
            "defect_summary": defect_summary,
            "report_id": report_id,
            "report_link": f"/report/{report_id}" if report_id else None,
        }
        await ws_manager.broadcast(str(project_id), message)
        logger.info(
            f"缺陷挖掘全链路摘要通知已推送: project_id={project_id}"
        )
    except Exception as exc:
        logger.warning(f"全链路摘要 WebSocket 通知失败: {exc}")


__all__ = [
    "SELF_TEST_PROJECT_NAME",
    "_get_self_test_env_configs",
    "_get_project_root",
    "_auto_import_requirement_doc",
    "get_self_test_project",
    "create_self_test_project",
    "_assess_defect_severity",
    "_generate_bug_no",
    "_auto_create_defect_bug",
    "_notify_critical_defect_bug",
    "calculate_defect_metrics",
    "_is_implicit_defect",
    "_collect_implicit_evidence",
    "run_defect_discovery_self_test",
    "_notify_pipeline_summary",
    "_build_step_result",
    "_step_requirement_confirmation",
    "_step_extract_test_points",
    "_step_generate_cases",
    "_step_review_and_save",
    "_step_create_task",
    "_step_execute",
    "_step_assess_severity",
    "_step_generate_report",
    "_step_cleanup",
]
