"""失败原因分析与自测缺陷创建（从 endpoints/execution_core/_analysis.py 下沉）。

纯计算 + 后台 Agent 编排，保持原函数名以兼容既有调用点与测试 patch 目标。
"""

import asyncio

from loguru import logger
from sqlalchemy.orm import Session

from app.models.enums import LocatorStatus
from app.models.test_case import TestCase, TestStep
from app.models.test_result import TestResult
from app.utils.db_time import utcnow


def _spawn_failure_analysis_agent(
    *,
    project_id: int,
    created_by: int | None,
    last_error: str | None,
    screenshot_url: str | None,
) -> None:
    """R1-1：fire-and-forget 触发 AgentOrchestrator 的失败分析管线。

    设计约束（见 agents.py 既有注释）：`AgentRuntime.run` 会阻塞，不得在主请求
    路径中 await。因此：

    - 用 `asyncio.create_task` 在后台执行，端点立即返回既有响应；
    - 使用**独立会话** `AsyncPrimarySessionLocal`（请求结束后请求会话即失效，
      复用会导致会话已关闭错误）；
    - 任何异常仅 `logger.warning`，并把会话置为 failed，**不影响主流程响应**。

    Args:
        project_id: 项目 ID。
        created_by: 触发用户 ID。
        last_error: 失败的错误信息（注入 ExecutionStateArtifact）。
        screenshot_url: 失败截图 URL（注入 ExecutionStateArtifact）。
    """

    async def _run() -> None:
        try:
            from app.db.database import AsyncPrimarySessionLocal
            from app.services.agent.artifacts import ExecutionStateArtifact
            from app.services.agent.orchestrator import AgentOrchestrator
            from app.services.agent.runtime import AgentRuntime

            async with AsyncPrimarySessionLocal() as db:
                orchestrator = AgentOrchestrator(runtime=AgentRuntime(db=db))
                await orchestrator.execute_pipeline(
                    pipeline=["failure_analysis"],
                    project_id=project_id,
                    initial_artifacts=[
                        ExecutionStateArtifact(
                            last_error=last_error,
                            screenshot_url=screenshot_url,
                        )
                    ],
                    created_by=created_by,
                )
                await db.commit()
        except Exception as e:
            # 异常隔离：仅告警，不冒泡到 HTTP 响应
            logger.warning(f"触发失败分析 Agent 失败（不影响主流程）: {e}")

    asyncio.create_task(_run())


_LOCATOR_ERROR_KEYWORDS = (
    "元素未找到",
    "定位失败",
    "css selector",
    "no such element",
    "element not found",
    "stale element",
    "element is not clickable",
    "element not interactable",
    "等待超时",
    "waiting for element",
    "无法定位",
    "找不到元素",
    "定位信息",
)
_CASE_ISSUE_KEYWORDS = (
    "步骤描述错误",
    "预期结果错误",
    "操作类型错误",
    "前置条件不完整",
    "用例问题",
    "需要修改用例",
    "test case error",
    "incorrect step",
)
_BUG_ISSUE_KEYWORDS = (
    "功能缺陷",
    "产品问题",
    "实际结果与预期不符",
    "页面显示异常",
    "数据不一致",
    "功能异常",
    "product bug",
    "功能未按预期工作",
)
_AI_CASE_HINTS = ("修改用例", "调整步骤", "更新定位", "修改预期")
_AI_BUG_HINTS = ("bug", "缺陷", "产品问题", "功能异常")
_INTERACTIVE_ACTION_TYPES = frozenset({"click", "input", "navigate", "hover", "select", "scroll"})


def _match_keyword_indicator(text: str, keywords: tuple[str, ...], label: str, extra_text: str = "") -> list[str]:
    """命中首个关键词即返回单条指标（避免同类关键词刷分）。"""
    for keyword in keywords:
        normalized = keyword.lower()
        if normalized in text or (extra_text and normalized in extra_text):
            return [f"{label}: '{keyword}'"]
    return []


def _collect_step_indicators(steps: list) -> list[str]:
    indicators = []
    for step in steps:
        if step.locator_status == LocatorStatus.FAILED.value:
            indicators.append(f"步骤{step.step_number}定位状态为失败")
        elif step.has_locator == 0 and step.action_type in _INTERACTIVE_ACTION_TYPES:
            indicators.append(f"步骤{step.step_number}需要元素定位但缺少定位信息")
    return indicators


def _collect_ai_indicators(ai_lower: str) -> tuple[list[str], list[str]]:
    """AI 分析文本中的用例疑点 / Bug 疑点。"""
    if not ai_lower:
        return [], []
    case_indicators = []
    bug_indicators = []
    if any(keyword in ai_lower for keyword in _AI_CASE_HINTS):
        case_indicators.append("AI分析建议修改用例内容")
    if any(keyword in ai_lower for keyword in _AI_BUG_HINTS):
        bug_indicators.append("AI分析提示可能是产品Bug")
    return case_indicators, bug_indicators


def _classify_failure(case_score: int, bug_score: int) -> tuple[str, float, str]:
    """按双方指标数量判定失败归属。"""
    if case_score > bug_score:
        return (
            "case_issue",
            min(0.95, 0.5 + case_score * 0.15),
            "分析表明失败原因更可能与测试用例本身有关（步骤描述、定位信息等）",
        )
    if bug_score > case_score:
        return (
            "product_bug",
            min(0.95, 0.5 + bug_score * 0.15),
            "分析表明失败原因更可能与产品功能缺陷有关，执行步骤本身没有问题",
        )
    if case_score > 0:
        return "needs_review", 0.4, "用例问题和Bug问题的指标同时存在，需要人工进一步判断"
    return "needs_review", 0.3, "无法自动判断失败类型，建议人工分析执行日志和截图"


def _perform_failure_analysis(result: TestResult, test_case: TestCase, db: Session) -> dict:
    """失败原因分析（sync 版本，向后兼容入口）。

    内部查询 TestStep 后委托给 _perform_failure_analysis_with_steps。
    保留供测试与 sync 调用方使用；async 端点请直接调用 _with_steps 版本。
    """
    steps = db.query(TestStep).filter(TestStep.test_case_id == test_case.id).order_by(TestStep.step_number).all()
    return _perform_failure_analysis_with_steps(result, test_case, steps)


def _perform_failure_analysis_with_steps(result: TestResult, test_case: TestCase, steps: list) -> dict:
    """纯计算失败原因分析。

    Args:
        result: 执行结果对象。
        test_case: 关联测试用例对象。
        steps: 已预查询的 TestStep 列表（按 step_number 排序）。
            原实现内部使用 db.query(TestStep)，迁移 async 后改为参数传入。
    """
    error_msg = result.error_msg or ""
    exec_log = result.exec_log or ""
    ai_analysis = result.ai_analysis or ""

    combined_text = f"{error_msg} {exec_log}".lower()
    ai_lower = ai_analysis.lower()

    case_issue_indicators = _match_keyword_indicator(
        combined_text, _LOCATOR_ERROR_KEYWORDS, "执行日志中包含定位相关错误"
    )
    case_issue_indicators += _match_keyword_indicator(
        combined_text, _CASE_ISSUE_KEYWORDS, "分析文本中包含用例问题关键词", ai_lower
    )
    bug_issue_indicators = _match_keyword_indicator(
        combined_text, _BUG_ISSUE_KEYWORDS, "分析文本中包含Bug问题关键词", ai_lower
    )

    case_issue_indicators += _collect_step_indicators(steps)

    ai_case_indicators, ai_bug_indicators = _collect_ai_indicators(ai_lower)
    case_issue_indicators += ai_case_indicators
    bug_issue_indicators += ai_bug_indicators

    suggested_type, confidence, reason = _classify_failure(len(case_issue_indicators), len(bug_issue_indicators))

    return {
        "result_id": result.id,
        "case_id": test_case.id,
        "case_title": test_case.title,
        "suggested_type": suggested_type,
        "confidence": round(confidence, 2),
        "reason": reason,
        "case_issue_indicators": case_issue_indicators,
        "bug_issue_indicators": bug_issue_indicators,
        "error_msg": error_msg,
        "ai_analysis": ai_analysis,
        "screenshot_url": result.screenshot_url,
        "analysis_time": utcnow().isoformat(),
    }


def _generate_bug_no(db: Session, project_id: int) -> str:
    from app.models.bug import Bug

    prefix = f"BUG-{project_id}-{utcnow().strftime('%Y%m%d')}-"
    count = db.query(Bug).filter(Bug.project_id == project_id, Bug.bug_no.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def _auto_create_bug_for_self_test(
    db: Session,
    project,
    result: TestResult,
    test_case: TestCase,
    analysis: dict,
):
    if not getattr(project, "is_self_test", False):
        return None
    if analysis.get("suggested_type") != "product_bug":
        return None

    from app.models.bug import Bug

    confidence = float(analysis.get("confidence") or 0)
    bug = Bug(
        bug_no=_generate_bug_no(db, project.id),
        project_id=project.id,
        title=f"自测发现缺陷: {test_case.title}",
        description=(
            "AI分析结果\n"
            f"建议类型: {analysis.get('suggested_type')}\n"
            f"置信度: {confidence}\n"
            f"原因: {analysis.get('reason')}\n"
            f"错误信息: {result.error_msg or ''}\n"
            f"AI分析: {result.ai_analysis or ''}"
        ),
        severity=2 if confidence >= 0.7 else 3,
        priority=1 if confidence >= 0.7 else 2,
        status="open",
        source="self_test",
        reporter_id=project.user_id,
        test_case_id=test_case.id,
        test_result_id=result.id,
        reproduction_steps=f"执行日志: {result.exec_log or ''}\n错误信息: {result.error_msg or ''}",
        expected_behavior=test_case.expected_result,
        actual_behavior=result.error_msg or result.ai_analysis,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug
