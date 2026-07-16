from datetime import datetime
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.test_result import create_test_result_async
from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.core.websocket import manager
from loguru import logger


class TaskExecutionMixin:
    """任务执行相关Mixin - 执行用例、日志推送、进度推送。"""

    async def execute_case(
        self,
        db: AsyncSession,
        task_id: int,
        project_id: int,
        case_id: int,
        precondition_service=None,
    ) -> Dict[str, Any]:
        """
        执行单个测试用例（使用V2执行引擎）

        Args:
            db: 异步数据库会话（用于用例查询与结果保存）。
            task_id: 任务ID
            project_id: 项目ID
            case_id: 用例ID
            precondition_service: 前置条件服务（任务级别共享，实现浏览器会话复用）

        Returns:
            执行结果
        """
        from app.services.test_execution_engine_v2 import TestExecutionEngineV2, ExecutionStatus

        logger.info(f"执行用例: {case_id}, 任务: {task_id}")

        # 获取用例信息
        test_case = (
            await db.execute(
                select(TestCase).where(
                    TestCase.id == case_id,
                    TestCase.project_id == project_id,
                    TestCase.is_deleted.is_(False),
                )
            )
        ).scalars().first()

        if not test_case:
            logger.error(f"用例不存在: {case_id}")
            return {
                "status": 2,  # 2: 执行失败
                "case_no": "",
                "log": f"用例不存在: {case_id}"
            }

        # 初始化执行结果
        exec_status = ExecStatus.NOT_EXECUTED
        exec_log = f"开始执行用例: {test_case.case_no}"
        error_msg = None
        screenshot_url = None

        test_category = test_case.test_category or ""
        if test_category == "manual" or not test_category:
            logger.info(f"[跳过手工测试用例] 用例ID={test_case.id}, 用例编号={test_case.case_no}, 用例标题={test_case.title}")
            exec_status = ExecStatus.NOT_EXECUTED
            exec_log += "\n手工测试，跳过执行"
            _ = await create_test_result_async(
                db=db,
                task_id=task_id,
                project_id=project_id,
                case_id=case_id,
                case_no=test_case.case_no,
                exec_status=exec_status,
                exec_log=exec_log,
                error_msg="手工测试，跳过执行",
                screenshot_url=screenshot_url
            )
            return {
                "status": 0,
                "case_no": test_case.case_no,
                "log": exec_log
            }

        if test_category == "api_automation":
            logger.info(f"[跳过接口测试用例] 用例ID={test_case.id}, 用例编号={test_case.case_no}, 用例标题={test_case.title}（当前仅支持UI自动化）")
            exec_status = ExecStatus.NOT_EXECUTED
            exec_log += "\n接口测试，跳过执行（当前仅支持UI自动化）"
            _ = await create_test_result_async(
                db=db,
                task_id=task_id,
                project_id=project_id,
                case_id=case_id,
                case_no=test_case.case_no,
                exec_status=exec_status,
                exec_log=exec_log,
                error_msg="接口测试，跳过执行（当前仅支持UI自动化）",
                screenshot_url=screenshot_url
            )
            return {
                "status": 0,
                "case_no": test_case.case_no,
                "log": exec_log
            }

        logger.info(f"[执行UI自动化用例] 用例ID={test_case.id}, 用例编号={test_case.case_no}, 用例标题={test_case.title}")

        # TestExecutionEngineV2 内部使用 sync Session，通过独立 sync 会话 +
        # run_async_coro_in_thread 在独立线程运行避免阻塞事件循环
        from app.db.database import PrimarySessionLocal
        from app.utils.async_sync_bridge import run_async_coro_in_thread

        effective_precondition_service = precondition_service
        cleanup_precondition = False
        try:
            # 使用V2执行引擎执行测试用例
            # 优先使用任务级别共享的 precondition_service，实现浏览器会话复用
            if effective_precondition_service is None:
                # 兜底：独立执行时创建临时前置条件服务
                from app.services.precondition_service import PreconditionService
                effective_precondition_service = PreconditionService()
                await effective_precondition_service.initialize()
                cleanup_precondition = True

            sync_db = PrimarySessionLocal()
            try:
                executor = TestExecutionEngineV2(
                    db=sync_db,
                    precondition_service=effective_precondition_service,
                    enable_ai_recognition=True,
                    enable_test_data_param=True
                )

                # 执行用例（skip_precondition=False，内部智能检测登录状态避免重复登录）
                # 引擎内部使用 sync db，通过 run_async_coro_in_thread 在独立线程运行
                result = await run_async_coro_in_thread(
                    executor.execute_test_case(
                        test_case=test_case,
                        project_id=project_id,
                        skip_precondition=False
                    )
                )

                # 更新执行状态
                if result.status == ExecutionStatus.PASSED:
                    exec_status = ExecStatus.PASSED
                    exec_log += "\n执行结果: 成功"
                elif result.status == ExecutionStatus.FAILED:
                    exec_status = ExecStatus.FAILED
                    exec_log += "\n执行结果: 失败"
                    error_msg = result.error_message or "用例执行失败"
                else:
                    exec_status = ExecStatus.FAILED
                    exec_log += "\n执行结果: 失败"
                    error_msg = result.error_message or "用例执行异常"

                # 添加执行详情
                exec_log += f"\n执行时间: {result.duration_ms}ms"
                if result.actual_result:
                    exec_log += f"\n执行详情: {result.actual_result}"

                # 统计步骤结果
                passed_steps = sum(1 for sr in result.step_results if sr.status == ExecutionStatus.PASSED)
                failed_steps = sum(1 for sr in result.step_results if sr.status == ExecutionStatus.FAILED)
                exec_log += f"\n步骤统计: 通过{passed_steps}步, 失败{failed_steps}步"

            finally:
                sync_db.close()

        except Exception as e:
            logger.error(f"用例执行异常: {e}")
            exec_status = ExecStatus.FAILED
            exec_log += "\n执行结果: 异常"
            error_msg = str(e)
        finally:
            # 独立执行时（非任务级别共享），清理临时前置条件服务
            if cleanup_precondition and effective_precondition_service is not None:
                try:
                    await effective_precondition_service.cleanup()
                except Exception:
                    logger.debug("清理前置条件服务失败", exc_info=True)

        # 保存执行结果（函数内部已写入数据库，返回值无需使用）
        _ = await create_test_result_async(
            db=db,
            task_id=task_id,
            project_id=project_id,
            case_id=case_id,
            case_no=test_case.case_no,
            exec_status=exec_status,
            exec_log=exec_log,
            error_msg=error_msg,
            screenshot_url=screenshot_url
        )

        return {
            "status": exec_status,
            "case_no": test_case.case_no,
            "log": exec_log
        }

    async def push_execution_log(self, task_id: int, case_id: int, case_no: str, status: int, log: str):
        """
        推送执行日志

        Args:
            task_id: 任务ID
            case_id: 用例ID
            case_no: 用例编号
            status: 执行状态
            log: 执行日志
        """
        # 记录日志
        logger.info(f"任务 {task_id} 用例 {case_no} 状态 {status}: {log}")

        # 通过WebSocket连接管理器推送消息
        message = {
            "type": "log",
            "task_id": task_id,
            "case_id": case_id,
            "case_no": case_no,
            "status": status,
            "log": log,
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast(message, task_id)

    async def push_execution_progress(self, task_id: int, progress: int, success_count: int, fail_count: int, current_case: int, total_cases: int) -> None:
        """
        推送执行进度

        Args:
            task_id: 任务ID
            progress: 执行进度
            success_count: 成功用例数
            fail_count: 失败用例数
            current_case: 当前执行的用例
            total_cases: 总用例数
        """
        # 记录日志
        logger.info(f"任务 {task_id} 进度: {progress}%, 成功: {success_count}, 失败: {fail_count}, {current_case}/{total_cases}")

        # 通过WebSocket连接管理器推送消息
        message = {
            "type": "progress",
            "task_id": task_id,
            "progress": progress,
            "success_count": success_count,
            "fail_count": fail_count,
            "current_case": current_case,
            "total_cases": total_cases,
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast(message, task_id)
