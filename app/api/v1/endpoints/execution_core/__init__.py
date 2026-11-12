"""执行链路端点包。

路由处理函数已内联在本模块（原 `_execution.py` / `_analysis.py` 已合并），
权限校验与失败分析逻辑下沉至 `app.services.execution_core`。

公开符号（`_perform_failure_analysis` 等）通过本模块 re-export，保持 import 路径不变。
"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.execution_core.schemas import SpeedReplayRequest
from app.core.exception import create_response
from app.db.database import async_get_db, PrimarySessionLocal
from app.models.enums import ExecStatus
from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.test_result import TestResult
from app.models.test_task import TaskStatus, TestTask
from app.models.user import User
from app.services.execution_core.failure_analysis import (
    _auto_create_bug_for_self_test,
    _generate_bug_no,
    _perform_failure_analysis,
    _perform_failure_analysis_with_steps,
    _spawn_failure_analysis_agent,
)
from app.services.execution_core.helpers import (
    _filter_by_visibility,
    _get_hidden_fields_async,
    get_task_or_404,
    verify_project_permission,
    verify_project_permission_async,
)
from app.services.execution_replay.legacy_service import get_execution_replay_service
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.services.visual_validation import (
    is_visual_validation_enabled,
    spawn_visual_validation_agent,
)
from app.utils.db_time import utcnow

router = APIRouter()

# 任务状态码 → 响应用字符串（与前端 executionStatus.status 取值对齐）
_TASK_STATUS_TEXT = {
    TaskStatus.PENDING: "pending",
    TaskStatus.RUNNING: "running",
    TaskStatus.COMPLETED: "completed",
    TaskStatus.FAILED: "failed",
    TaskStatus.STOPPED: "stopped",
    TaskStatus.PAUSED: "paused",
}


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
        return create_response(data=[], msg="ADB环境不可用，请确认已安装ADB并配置环境变量")
    except FileNotFoundError as e:
        logger.warning(f"ADB命令未找到: {e}")
        return create_response(data=[], msg="未找到ADB命令，请确认已安装Android SDK并配置环境变量")
    except Exception as e:
        logger.error(f"获取设备列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取设备列表失败"
        )


@router.post("/{task_id}/start")
async def start_test_execution(
    task_id: int,
    config: dict | None = None,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task_result = await db.execute(
            select(TestTask).where(TestTask.id == task_id)
        )
        task = task_result.scalars().first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        project_result = await db.execute(
            select(Project).where(
                Project.id == task.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 0=等待执行、3=执行失败、5=已暂停 均允许（重新）开始执行
        if task.status not in [0, 3, 5]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务状态不允许开始执行 (当前状态: {task.status})"
            )

        task.status = 1
        task.start_time = utcnow()
        task.error_message = None
        await db.commit()

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

        # 性能优化：将 async service 调用放到独立线程，避免 sync_db.query() 阻塞事件循环
        from app.utils.async_sync_bridge import run_async_coro_in_thread
        exec_db = PrimarySessionLocal()
        try:
            executor = TestExecutionEngineV2(exec_db)
            try:
                await run_async_coro_in_thread(
                    executor.execute_test_task(
                        task_id=task_id,
                        global_headless=headless,
                        global_record_video=record_video,
                        target_env=target_env,
                        skip_init=skip_init,
                        execution_mode=execution_mode,
                        mobile_device_id=mobile_device_id,
                        use_mcp=use_mcp
                    )
                )
            except Exception as e:
                logger.error(f"任务执行异常: {e}")
                # 3=FAILED：异常中断必须记为失败（此前误用 2=COMPLETED，前端无法区分成功/失败）。
                # 用 Core UPDATE 原子收尾：条件命中 1=RUNNING 才改写，
                # 不覆盖引擎内部已写入的终态（如已停止），也避免 ORM 过期属性触发懒加载 IO。
                failed = await db.execute(
                    update(TestTask)
                    .where(TestTask.id == task_id, TestTask.status == 1)
                    .values(
                        status=3,
                        error_message=f"任务执行异常：{e}",
                        end_time=utcnow(),
                    )
                    .execution_options(synchronize_session=False)
                )
                if failed.rowcount:
                    await db.commit()
        finally:
            exec_db.close()

        # 本端点同步等待执行结束后才返回，因此读取真实终态（此前固定返回 running 会误导调用方）。
        # 用 Core 列表查询读取，避免访问 commit 后已过期的 ORM 实例属性而触发同步懒加载。
        final_row = (
            await db.execute(
                select(
                    TestTask.status,
                    TestTask.progress,
                    TestTask.success_count,
                    TestTask.fail_count,
                    TestTask.total_count,
                    TestTask.error_message,
                ).where(TestTask.id == task_id)
            )
        ).first()
        final_status = int(final_row.status) if final_row else TaskStatus.RUNNING

        return create_response(data={
            "task_id": task_id,
            "status": _TASK_STATUS_TEXT.get(final_status, "unknown"),
            "task_status": final_status,
            "progress": int(final_row.progress or 0) if final_row else 0,
            "success_count": int(final_row.success_count or 0) if final_row else 0,
            "fail_count": int(final_row.fail_count or 0) if final_row else 0,
            "total_count": int(final_row.total_count or 0) if final_row else 0,
            "error_message": final_row.error_message if final_row else None,
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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task_result = await db.execute(
            select(TestTask).where(TestTask.id == task_id)
        )
        task = task_result.scalars().first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        project_result = await db.execute(
            select(Project).where(
                Project.id == task.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")

        if task.status != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在执行中，无法暂停")

        # 5 = PAUSED（此前误用 3，与 FAILED 冲突，导致前端无法区分"失败"与"暂停"）
        task.status = 5
        await db.commit()

        return create_response(data={"task_id": task_id, "status": "paused"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"暂停执行失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="暂停执行失败")


@router.post("/{task_id}/resume")
async def resume_test_execution(
    task_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task_result = await db.execute(
            select(TestTask).where(TestTask.id == task_id)
        )
        task = task_result.scalars().first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        project_result = await db.execute(
            select(Project).where(
                Project.id == task.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")

        if task.status != 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在暂停状态，无法恢复")

        task.status = 1
        await db.commit()

        return create_response(data={"task_id": task_id, "status": "running"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复执行失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="恢复执行失败")


@router.post("/{task_id}/stop")
async def stop_test_execution(
    task_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        task_result = await db.execute(
            select(TestTask).where(TestTask.id == task_id)
        )
        task = task_result.scalars().first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        project_result = await db.execute(
            select(Project).where(
                Project.id == task.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")

        # 1=执行中、3=执行失败、5=已暂停 均允许停止
        if task.status not in [1, 3, 5]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在执行中，无法停止")

        task.status = 4
        task.end_time = utcnow()
        await db.commit()

        return create_response(data={"task_id": task_id, "status": "stopped"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止执行失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="停止执行失败")


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
    2. 纯计算委托 `services.execution_core.failure_analysis`
    3. 可见字段过滤复用 `_get_hidden_fields_async`
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

        # 7. R3-3：视觉校验（默认关；全局关闭时零查询、零会话）
        if await is_visual_validation_enabled(db, test_case.project_id):
            spawn_visual_validation_agent(
                project_id=test_case.project_id,
                created_by=current_user.id if current_user else None,
                screenshot_url=analysis.get("screenshot_url"),
                last_error=result.error_msg,
            )

        return create_response(data=analysis, msg="失败原因分析完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析失败原因异常: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="分析失败原因异常")


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


__all__ = [
    "router",
    "SpeedReplayRequest",
    "verify_project_permission",
    "verify_project_permission_async",
    "get_task_or_404",
    "_perform_failure_analysis",
    "_auto_create_bug_for_self_test",
    "_generate_bug_no",
]
