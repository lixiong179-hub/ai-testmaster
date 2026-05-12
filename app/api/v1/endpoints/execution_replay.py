"""
测试执行回放端点模块

本模块定义测试执行回放的API端点，支持步骤级别的执行回放和视频回放。

路由前缀: /execution（由父模块execution.py注册）
标签: 测试执行

端点概览:
    - GET  /{execution_id}/steps          - 获取执行步骤列表
    - POST /{execution_id}/replay         - 重新执行指定步骤
    - GET  /{execution_id}/screenshots    - 获取执行截图列表

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 步骤回放支持单步和连续回放
    - 截图按步骤序号关联
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.utils.db_time import utcnow
from app.db.database import get_db
from app.models.user import User
from app.models.test_result import TestResult
from app.models.test_case import TestCase, TestStep
from app.models.enums import LocatorStatus
from app.api.v1.endpoints.auth import get_current_user
from app.services.execution_replay_service import get_execution_replay_service
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


class SeekReplayRequest(BaseModel):
    """回放跳转请求模型"""
    timestamp: float = Field(0, description="跳转时间点（秒）")


class SpeedReplayRequest(BaseModel):
    """回放速度设置请求模型"""
    speed: float = Field(1.0, description="播放速度倍率")


@router.get("/replay/{execution_id}")
async def get_replay_session(
    execution_id: str,
    db: Session = Depends(get_db),
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


@router.post("/replay/{execution_id}/start")
async def start_replay(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = get_execution_replay_service()
        await service.start_replay(execution_id)
        return create_response(message="回放已开始")
    except Exception as e:
        logger.error(f"开始回放失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="开始回放失败")


@router.post("/replay/{execution_id}/pause")
async def pause_replay(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = get_execution_replay_service()
        await service.pause_replay(execution_id)
        return create_response(message="回放已暂停")
    except Exception as e:
        logger.error(f"暂停回放失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="暂停回放失败")


@router.post("/replay/{execution_id}/resume")
async def resume_replay(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = get_execution_replay_service()
        await service.resume_replay(execution_id)
        return create_response(message="回放已恢复")
    except Exception as e:
        logger.error(f"恢复回放失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="恢复回放失败")


@router.post("/replay/{execution_id}/stop")
async def stop_replay(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = get_execution_replay_service()
        await service.stop_replay(execution_id)
        return create_response(message="回放已停止")
    except Exception as e:
        logger.error(f"停止回放失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="停止回放失败")


@router.post("/replay/{execution_id}/seek")
async def seek_replay(
    execution_id: str,
    data: SeekReplayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        timestamp = data.timestamp
        service = get_execution_replay_service()
        await service.seek_to(execution_id, timestamp)
        return create_response(message=f"已跳转到 {timestamp}s")
    except Exception as e:
        logger.error(f"跳转失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="跳转失败")


@router.post("/replay/{execution_id}/speed")
async def set_replay_speed(
    execution_id: str,
    data: SpeedReplayRequest,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = db.query(TestResult).filter(TestResult.id == result_id).first()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行结果不存在")

        if result.exec_status != 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有执行失败的结果才能进行失败分析")

        test_case = db.query(TestCase).filter(TestCase.id == result.case_id).first()
        if not test_case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联的测试用例不存在")

        analysis = _perform_failure_analysis(result, test_case, db)
        return create_response(data=analysis, message="失败原因分析完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败原因异常: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="分析失败原因异常")


def _perform_failure_analysis(result: TestResult, test_case: TestCase, db: Session) -> dict:
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

    steps = db.query(TestStep).filter(
        TestStep.test_case_id == test_case.id
    ).order_by(TestStep.step_number).all()

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


@router.post("/quick-verify")
async def create_quick_verify_task(
    case_id: int = Body(..., embed=True),
    step_indices: list[int] = Body(default=[], embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
        if not test_case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")

        if not step_indices:
            steps = db.query(TestStep).filter(
                TestStep.test_case_id == case_id
            ).order_by(TestStep.step_number).all()
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
            db.commit()

        logger.info(f"创建快速验证任务: 用例ID={case_id}, 步骤={step_indices}, 操作人={current_user.username if current_user else 'system'}")
        return create_response(data=task_data, message="快速验证任务已创建")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建快速验证任务失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建快速验证任务失败")
