from typing import Optional
"""
测试执行核心端点模块

本模块定义测试执行的核心API端点，包括启动执行、停止执行和状态查询。

路由前缀: /execution（由父模块execution.py注册）
标签: 测试执行

端点概览:
    - POST /{test_case_id}/run     - 启动测试用例执行
    - POST /{execution_id}/stop    - 停止执行
    - GET  /{execution_id}/status  - 查询执行状态

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 执行支持同步和异步两种模式
    - 执行结果包含步骤级别的通过/失败状态
    - 停止执行会中断正在运行的测试进程
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.test_task import TestTask
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.core.exception import create_response
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
        logger.error(f"获取设备列表失败: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"详细堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取设备列表失败: {type(e).__name__}: {str(e)}"
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
            detail=f"开始执行失败: {str(e)}"
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"暂停执行失败: {str(e)}")


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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"恢复执行失败: {str(e)}")


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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"停止执行失败: {str(e)}")
