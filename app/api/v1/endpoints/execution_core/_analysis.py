import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.database import async_get_db
from app.models.user import User
from app.models.test_case import TestCase, TestStep
from app.models.test_result import TestResult
from app.models.enums import LocatorStatus, ExecStatus
from app.api.v1.endpoints.auth import get_current_user
from app.services.execution_replay.legacy_service import get_execution_replay_service
from app.core.exception import create_response
from app.utils.db_time import utcnow
from app.api.v1.endpoints.execution_core._helpers import (
    _filter_by_visibility,
    _get_hidden_fields_async,
    SpeedReplayRequest,
)

router = APIRouter()


def _spawn_failure_analysis_agent(
    *,
    project_id: int,
    created_by: Optional[int],
    last_error: Optional[str],
    screenshot_url: Optional[str],
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


@router.get("/replay/{execution_id}")
async def get_replay_session(
    execution_id: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = get_execution_replay_service()
        session = await service.get_session(execution_id)
        if session:
            return create_response(data=session)
        return create_response(code=404, message="回放会话不存在")
    except Exception as e:
        logger.error(f"获取回放会话失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取回放会话失败")


@router.post("/replay/{execution_id}/speed")
async def set_replay_speed(
    execution_id: str,
    data: SpeedReplayRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        speed = data.speed
        service = get_execution_replay_service()
        await service.set_speed(execution_id, speed)
        return create_response(message=f"速度已设置为 {speed}x")
    except Exception as e:
        logger.error(f"设置速度失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="设置速度失败")


@router.post("/results/{result_id}/analyze-failure")
async def analyze_failure(
    result_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """失败原因分析。

    原实现通过 db.run_sync(_analyze) 桥接 sync 查询。现拆分为:
    1. inline async 查询 TestResult / TestCase / TestStep
    2. asyncio.to_thread 包装 VisibilityConfigService.get_project_config (sync 服务)
    3. _perform_failure_analysis 改为接收预查询的 steps 列表，主体保持纯计算
    """
    try:
        # 1. async 查询 TestResult
        result = (
            await db.execute(
                select(TestResult).where(TestResult.id == result_id)
            )
        ).scalar_one_or_none()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行结果不存在")

        if result.exec_status != ExecStatus.FAILED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有执行失败的结果才能进行失败分析")

        # 2. async 查询 TestCase
        test_case = (
            await db.execute(
                select(TestCase).where(
                    TestCase.id == result.case_id,
                    TestCase.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if not test_case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联的测试用例不存在")

        # 3. async 查询 TestStep (原 _perform_failure_analysis 内部 sync 查询)
        steps = list(
            (
                await db.execute(
                    select(TestStep)
                    .where(TestStep.test_case_id == test_case.id)
                    .order_by(TestStep.step_number)
                )
            ).scalars().all()
        )

        # 4. 纯计算失败原因分析
        analysis = _perform_failure_analysis_with_steps(result, test_case, steps)

        # 5. async 查询项目可见模式配置（替代原 PrimarySessionLocal + asyncio.to_thread
        #    桥接 sync VisibilityConfigService，避免测试嵌套事务中 MissingGreenlet）
        hidden_fields = await _get_hidden_fields_async(db, test_case.project_id)

        analysis = _filter_by_visibility(analysis, hidden_fields)

        # 6. R1-1：脱敏后 fire-and-forget 触发 Agent 失败分析（不阻塞本端点响应）
        _spawn_failure_analysis_agent(
            project_id=test_case.project_id,
            created_by=current_user.id,
            last_error=result.error_msg,
            screenshot_url=analysis.get("screenshot_url"),
        )

        return create_response(data=analysis, msg="失败原因分析完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败原因异常: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="分析失败原因异常")


def _perform_failure_analysis(result: TestResult, test_case: TestCase, db: Session) -> dict:
    """失败原因分析（sync 版本，向后兼容入口）。

    内部查询 TestStep 后委托给 _perform_failure_analysis_with_steps。
    保留供测试与 sync 调用方使用；async 端点请直接调用 _with_steps 版本。
    """
    steps = db.query(TestStep).filter(
        TestStep.test_case_id == test_case.id
    ).order_by(TestStep.step_number).all()
    return _perform_failure_analysis_with_steps(result, test_case, steps)


def _perform_failure_analysis_with_steps(result: TestResult, test_case: TestCase, steps: list) -> dict:
    """纯计算失败原因分析。

    Args:
        result: 执行结果对象。
        test_case: 关联测试用例对象。
        steps: 已预查询的 TestStep 列表（按 step_number 排序）。
            原实现内部使用 db.query(TestStep)，迁移 async 后改为参数传入。
    """
    case_issue_indicators = []
    bug_issue_indicators = []

    error_msg = result.error_msg or ""
    exec_log = result.exec_log or ""
    ai_analysis = result.ai_analysis or ""

    locator_error_keywords = [
        "元素未找到", "定位失败", "css selector", "no such element",
        "element not found", "stale element", "element is not clickable",
        "element not interactable", "等待超时", "waiting for element",
        "无法定位", "找不到元素", "定位信息"
    ]
    case_issue_keywords = [
        "步骤描述错误", "预期结果错误", "操作类型错误",
        "前置条件不完整", "用例问题", "需要修改用例",
        "test case error", "incorrect step"
    ]
    bug_issue_keywords = [
        "功能缺陷", "产品问题", "实际结果与预期不符",
        "页面显示异常", "数据不一致", "功能异常",
        "product bug", "功能未按预期工作"
    ]

    combined_text = f"{error_msg} {exec_log}".lower()
    ai_lower = ai_analysis.lower() if ai_analysis else ""

    for keyword in locator_error_keywords:
        if keyword.lower() in combined_text:
            case_issue_indicators.append(f"执行日志中包含定位相关错误: '{keyword}'")
            break
    for keyword in case_issue_keywords:
        if keyword.lower() in combined_text or keyword.lower() in ai_lower:
            case_issue_indicators.append(f"分析文本中包含用例问题关键词: '{keyword}'")
            break
    for keyword in bug_issue_keywords:
        if keyword.lower() in combined_text or keyword.lower() in ai_lower:
            bug_issue_indicators.append(f"分析文本中包含Bug问题关键词: '{keyword}'")
            break

    for step in steps:
        if step.locator_status == LocatorStatus.FAILED.value:
            case_issue_indicators.append(f"步骤{step.step_number}定位状态为失败")
        elif step.has_locator == 0 and step.action_type in [
            "click", "input", "navigate", "hover", "select", "scroll"
        ]:
            case_issue_indicators.append(f"步骤{step.step_number}需要元素定位但缺少定位信息")

    if ai_analysis:
        ai_lower = ai_analysis.lower()
        if any(kw in ai_lower for kw in ["修改用例", "调整步骤", "更新定位", "修改预期"]):
            case_issue_indicators.append("AI分析建议修改用例内容")
        if any(kw in ai_lower for kw in ["bug", "缺陷", "产品问题", "功能异常"]):
            bug_issue_indicators.append("AI分析提示可能是产品Bug")

    case_issue_score = len(case_issue_indicators)
    bug_issue_score = len(bug_issue_indicators)

    if case_issue_score > bug_issue_score:
        suggested_type = "case_issue"
        confidence = min(0.95, 0.5 + case_issue_score * 0.15)
        reason = "分析表明失败原因更可能与测试用例本身有关（步骤描述、定位信息等）"
    elif bug_issue_score > case_issue_score:
        suggested_type = "product_bug"
        confidence = min(0.95, 0.5 + bug_issue_score * 0.15)
        reason = "分析表明失败原因更可能与产品功能缺陷有关，执行步骤本身没有问题"
    elif case_issue_score > 0 and bug_issue_score > 0:
        suggested_type = "needs_review"
        confidence = 0.4
        reason = "用例问题和Bug问题的指标同时存在，需要人工进一步判断"
    else:
        suggested_type = "needs_review"
        confidence = 0.3
        reason = "无法自动判断失败类型，建议人工分析执行日志和截图"

    return {
        "result_id": result.id, "case_id": test_case.id,
        "case_title": test_case.title, "suggested_type": suggested_type,
        "confidence": round(confidence, 2), "reason": reason,
        "case_issue_indicators": case_issue_indicators,
        "bug_issue_indicators": bug_issue_indicators,
        "error_msg": error_msg, "ai_analysis": ai_analysis,
        "screenshot_url": result.screenshot_url,
        "analysis_time": utcnow().isoformat()
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


@router.post("/quick-verify")
async def create_quick_verify_task(
    case_id: int = Body(..., embed=True),
    step_indices: list[int] = Body(default=[], embed=True),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        test_case_result = await db.execute(
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            )
        )
        test_case = test_case_result.scalars().first()
        if not test_case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")

        if not step_indices:
            steps_result = await db.execute(
                select(TestStep).where(
                    TestStep.test_case_id == case_id
                ).order_by(TestStep.step_number)
            )
            steps = steps_result.scalars().all()
            step_indices = [s.step_number for s in steps]

        task_data = {
            "name": f"快速验证 - {test_case.title}",
            "case_id": case_id, "case_ids": [case_id],
            "task_type": "quick_verify", "step_indices": step_indices,
            "created_by": current_user.username if current_user else "system",
            "description": f"用例纠正后快速验证，用例ID: {case_id}，验证步骤: {step_indices}"
        }

        if test_case.correction_status:
            test_case.correction_status = "verifying"
            await db.commit()

        logger.info(f"创建快速验证任务: 用例ID={case_id}, 步骤={step_indices}, 操作人={current_user.username if current_user else 'system'}")
        return create_response(data=task_data, message="快速验证任务已创建")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"创建快速验证任务失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建快速验证任务失败")
