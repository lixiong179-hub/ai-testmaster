from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from datetime import datetime
from app.utils.db_time import utcnow

from app.db.database import get_db
from app.models.user import User
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.test_case import TestCase, TestStep
from app.models.enums import LocatorStatus
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.services.video_service import VideoService, get_video_service
from app.services.execution_replay_service import (
    ExecutionReplayService,
    get_execution_replay_service
)
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


@router.get("/{task_id}/screenshot/{case_id}/{step_number}/{type}")
async def get_step_screenshot(
    task_id: int,
    case_id: int,
    step_number: int,
    type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from fastapi.responses import FileResponse

        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        from app.api.v1.endpoints.execution_core import verify_project_permission
        verify_project_permission(db, task.project_id, current_user.id)

        screenshot_dir = f"./screenshots/{task_id}/{case_id}"
        screenshot_path = f"{screenshot_dir}/{step_number}_{type}.png"

        import os
        if os.path.exists(screenshot_path):
            return FileResponse(screenshot_path)

        return create_response(code=404, message="截图不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取截图失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取截图失败: {str(e)}"
        )


@router.get("/{task_id}/case/{case_id}/video")
async def get_execution_video(
    task_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from fastapi.responses import FileResponse

        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        from app.api.v1.endpoints.execution_core import verify_project_permission
        verify_project_permission(db, task.project_id, current_user.id)

        service = get_video_service()
        videos = await service.get_videos_by_task(db, task_id)

        for video in videos:
            if video.case_id == case_id and video.file_path:
                import os
                if os.path.exists(video.file_path):
                    return FileResponse(
                        video.file_path,
                        media_type="video/mp4",
                        filename=f"task_{task_id}_case_{case_id}.mp4"
                    )

        return create_response(code=404, message="视频不存在或未启用录制")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取视频失败: {str(e)}"
        )


@router.get("/{task_id}/case/{case_id}/video/info")
async def get_video_info(
    task_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        from app.api.v1.endpoints.execution_core import verify_project_permission
        verify_project_permission(db, task.project_id, current_user.id)

        service = get_video_service()
        videos = await service.get_videos_by_case(db, case_id)

        if videos:
            video = videos[0]
            return create_response(data=video.to_dict())

        return create_response(code=404, message="视频不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取视频信息失败: {str(e)}"
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回放会话失败: {str(e)}"
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"开始回放失败: {str(e)}"
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"暂停回放失败: {str(e)}"
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复回放失败: {str(e)}"
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止回放失败: {str(e)}"
        )


@router.post("/replay/{execution_id}/seek")
async def seek_replay(
    execution_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        timestamp = data.get("timestamp", 0)
        service = get_execution_replay_service()
        await service.seek_to(execution_id, timestamp)
        return create_response(message=f"已跳转到 {timestamp}s")

    except Exception as e:
        logger.error(f"跳转失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"跳转失败: {str(e)}"
        )


@router.post("/replay/{execution_id}/speed")
async def set_replay_speed(
    execution_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        speed = data.get("speed", 1.0)
        service = get_execution_replay_service()
        await service.set_speed(execution_id, speed)
        return create_response(message=f"速度已设置为 {speed}x")

    except Exception as e:
        logger.error(f"设置速度失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置速度失败: {str(e)}"
        )


@router.post("/results/{result_id}/analyze-failure")
async def analyze_failure(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = db.query(TestResult).filter(TestResult.id == result_id).first()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="执行结果不存在"
            )

        if result.exec_status != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只有执行失败的结果才能进行失败分析"
            )

        test_case = db.query(TestCase).filter(TestCase.id == result.case_id).first()
        if not test_case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="关联的测试用例不存在"
            )

        analysis = _perform_failure_analysis(result, test_case, db)

        return create_response(data=analysis, message="失败原因分析完成")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败原因异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分析失败原因异常: {str(e)}"
        )


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
            case_issue_indicators.append(
                f"步骤{step.step_number}定位状态为失败"
            )
        elif step.has_locator == 0 and step.action_type in [
            "click", "input", "navigate", "hover", "select", "scroll"
        ]:
            case_issue_indicators.append(
                f"步骤{step.step_number}需要元素定位但缺少定位信息"
            )

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试用例不存在"
            )

        if not step_indices:
            steps = db.query(TestStep).filter(
                TestStep.test_case_id == case_id
            ).order_by(TestStep.step_number).all()
            step_indices = [s.step_number for s in steps]

        task_data = {
            "name": f"快速验证 - {test_case.title}",
            "case_id": case_id,
            "case_ids": [case_id],
            "task_type": "quick_verify",
            "step_indices": step_indices,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建快速验证任务失败: {str(e)}"
        )
