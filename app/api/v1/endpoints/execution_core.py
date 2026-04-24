from typing import Optional
"""
测试执行核心端点模块

本模块定义测试执行的核心API端点，包括启动执行、停止执行、状态查询、回放会话和失败分析。

路由前缀: /execution（由父模块execution.py注册）
标签: 测试执行

端点概览:
    - GET  /devices                          - 获取ADB设备列表
    - POST /{task_id}/start                  - 启动测试执行
    - POST /{task_id}/pause                  - 暂停执行
    - POST /{task_id}/resume                 - 恢复执行
    - POST /{task_id}/stop                   - 停止执行
    - GET  /replay/{execution_id}            - 获取回放会话
    - POST /replay/{execution_id}/speed      - 设置回放速度
    - POST /results/{result_id}/analyze-failure - 失败原因分析
    - POST /quick-verify                     - 创建快速验证任务

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 执行支持同步和异步两种模式
    - 执行结果包含步骤级别的通过/失败状态
    - 停止执行会中断正在运行的测试进程
    - 回放控制（开始/暂停/恢复/停止/跳转）由execution_visualization模块提供
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.test_task import TestTask
from app.models.test_case import TestCase, TestStep
from app.models.test_result import TestResult
from app.models.project import Project
from app.models.enums import LocatorStatus
from app.api.v1.endpoints.auth import get_current_user
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.services.execution_replay_service import get_execution_replay_service
from app.core.exception import create_response
from app.utils.db_time import utcnow
from loguru import logger

router = APIRouter()


def verify_project_permission(db: Session, project_id: int, user_id: int) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return project


def get_task_or_404(db: Session, task_id: int, project_id: int) -> TestTask:
    task = db.query(TestTask).filter(
        TestTask.id == task_id,
        TestTask.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    return task


@router.get("/devices")
async def list_connected_devices(
    current_user: User = Depends(get_current_user)
):
    try:
        from app.utils.adb_controller import AdbController, AdbError
        logger.info("开始获取ADB设备列表...")
        adb = AdbController()
        logger.info("AdbController实例已创建")
        devices = await adb.list_devices()
        logger.info(f"获取到{len(devices)}个设备: {[d.udid for d in devices]}")
        return create_response(data=[
            {
                "udid": d.udid,
                "state": d.state,
                "model": d.model,
                "android_version": d.android_version,
                "screen_size": list(d.screen_size) if d.screen_size else None
            }
            for d in devices
        ])
    except AdbError as e:
        logger.warning(f"ADB不可用: {e}")
        return create_response(data=[], message="ADB环境不可用，请确认已安装ADB并配置环境变量")
    except FileNotFoundError as e:
        logger.warning(f"ADB命令未找到: {e}")
        return create_response(data=[], message="未找到ADB命令，请确认已安装Android SDK并配置环境变量")
    except Exception as e:
        logger.error(f"获取设备列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取设备列表失败"
        )


@router.post("/{task_id}/start")
async def start_test_execution(
    task_id: int,
    config: Optional[dict] = None,
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

        verify_project_permission(db, task.project_id, current_user.id)

        if task.status not in [0, 3]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务状态不允许开始执行 (当前状态: {task.status})"
            )

        task.status = 1
        task.start_time = datetime.now()
        db.commit()

        executor = TestExecutionEngineV2(db)

        headless = True
        record_video = False
        target_env = "test"
        skip_init = False
        use_mcp = None
        ALLOWED_ENVS = {"test", "staging", "prod"}
        execution_mode = "smart"
        mobile_device_id = None
        if config:
            headless = config.get("headless", True)
            record_video = config.get("recordVideo", False)
            raw_target_env = config.get("targetEnv", "test")
            if raw_target_env and raw_target_env not in ALLOWED_ENVS:
                logger.warning(f"非法目标环境值 '{raw_target_env}'，已回退到默认值 'test'")
                target_env = "test"
            else:
                target_env = raw_target_env or "test"
            skip_init = config.get("skipInit", False)
            execution_mode = config.get("executionMode", "smart") if config else "smart"
            mobile_device_id = config.get("mobileDeviceId") if config else None
            if execution_mode not in ("preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"):
                logger.warning(f"非法执行模式 '{execution_mode}'，回退到默认值 'smart'")
                execution_mode = "smart"
            use_mcp = config.get("use_mcp", None)

        logger.info(f"执行配置: headless={headless}, recordVideo={record_video}, targetEnv={target_env}, skipInit={skip_init}, useMcp={use_mcp}")

        try:
            await executor.execute_test_task(
                task_id=task_id,
                global_headless=headless,
                global_record_video=record_video,
                target_env=target_env,
                skip_init=skip_init,
                execution_mode=execution_mode,
                mobile_device_id=mobile_device_id,
                use_mcp=use_mcp
            )
        except Exception as e:
            logger.error(f"任务执行异常: {e}")
            task.status = 2
            task.end_time = datetime.now()
            db.commit()

        return create_response(data={
            "task_id": task_id,
            "status": "running",
            "config": config or {}
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"开始执行失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="开始执行失败"
        )


@router.post("/{task_id}/pause")
async def pause_test_execution(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        verify_project_permission(db, task.project_id, current_user.id)

        if task.status != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在执行中，无法暂停")

        task.status = 3
        db.commit()

        return create_response(data={"task_id": task_id, "status": "paused"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"暂停执行失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="暂停执行失败")


@router.post("/{task_id}/resume")
async def resume_test_execution(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        verify_project_permission(db, task.project_id, current_user.id)

        if task.status != 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在暂停状态，无法恢复")

        task.status = 1
        db.commit()

        return create_response(data={"task_id": task_id, "status": "running"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复执行失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="恢复执行失败")


@router.post("/{task_id}/stop")
async def stop_test_execution(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        verify_project_permission(db, task.project_id, current_user.id)

        if task.status not in [1, 3]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在执行中，无法停止")

        task.status = 4
        task.end_time = datetime.now()
        db.commit()

        return create_response(data={"task_id": task_id, "status": "stopped"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止执行失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="停止执行失败")


# ============================================================================
# 回放会话与失败分析API（从execution_replay模块迁入）
# ============================================================================

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
    """执行失败原因分析，返回分析结果字典"""
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
