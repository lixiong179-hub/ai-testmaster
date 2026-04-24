from typing import List, Dict, Any
from datetime import datetime
import time
import asyncio
import os
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.crud.test_task import (
    update_test_task_status,
    update_test_task_progress
)
from app.crud.test_result import (
    create_test_result,
    update_test_result
)
from app.models.test_case import TestCase
from app.core.config import settings
from app.utils.websocket import manager
from loguru import logger


class TaskCoreMixin:
    """核心任务管理Mixin - 任务创建、启动、停止、状态查询。"""

    def __init__(self):
        self.running_tasks = {}  # 存储正在运行的任务

    def start_task(self, task_id: int, project_id: int, case_ids: List[int]):
        """
        开始执行任务

        Args:
            task_id: 任务ID
            project_id: 项目ID
            case_ids: 用例ID列表
        """
        logger.info(f"开始执行任务: {task_id}, 项目: {project_id}, 用例数: {len(case_ids)}")

        # 标记任务为运行中
        self.running_tasks[task_id] = {
            "status": "running",
            "project_id": project_id,
            "case_ids": case_ids,
            "current_case": 0,
            "success_count": 0,
            "fail_count": 0
        }
        # 启动异步任务
        import asyncio
        asyncio.create_task(self._execute_task(task_id, project_id, case_ids))

    def stop_task(self, task_id: int) -> None:
        """
        停止执行任务

        Args:
            task_id: 任务ID
        """
        logger.info(f"停止执行任务: {task_id}")

        if task_id in self.running_tasks:
            self.running_tasks[task_id]["status"] = "stopped"

    async def _execute_task(self, task_id: int, project_id: int, case_ids: List[int]):
        """
        执行测试任务（批量执行用例）

        Args:
            task_id: 任务ID
            project_id: 项目ID
            case_ids: 用例ID列表
        """
        from app.db.database import SessionLocal
        from app.services.precondition_service import PreconditionService

        db = SessionLocal()
        total_cases = len(case_ids)
        success_count = 0
        fail_count = 0

        # 任务级别共享前置条件服务，实现浏览器会话复用和智能登录检测
        precondition_service = PreconditionService()
        try:
            await precondition_service.initialize()
        except Exception as e:
            logger.warning(f"前置条件服务初始化失败: {e}")

        try:
            for i, case_id in enumerate(case_ids):
                # 检查任务是否被停止
                if task_id not in self.running_tasks or self.running_tasks[task_id]["status"] == "stopped":
                    logger.info(f"任务已停止: {task_id}")
                    update_test_task_status(db, task_id, project_id, 4)  # 4: 已停止
                    break

                # 更新当前执行的用例
                self.running_tasks[task_id]["current_case"] = i + 1

                # 计算进度
                progress = int((i + 1) / total_cases * 100)

                # 执行用例
                case_result = await self.execute_case(db, task_id, project_id, case_id, precondition_service)

                # 更新成功/失败计数（跳过 status 为 0 的用例）
                if case_result["status"] == 1:  # 1: 执行成功
                    success_count += 1
                elif case_result["status"] in [2, 3]:  # 2: 执行失败, 3: 阻塞
                    fail_count += 1

                # 更新任务进度
                update_test_task_progress(
                    db=db,
                    task_id=task_id,
                    project_id=project_id,
                    progress=progress,
                    success_count=success_count,
                    fail_count=fail_count
                )

                # 推送执行进度（添加异常处理）
                try:
                    await self.push_execution_progress(
                        task_id=task_id,
                        progress=progress,
                        success_count=success_count,
                        fail_count=fail_count,
                        current_case=i + 1,
                        total_cases=total_cases
                    )
                except Exception as e:
                    logger.error(f"推送进度失败: {e}")

                # 推送执行日志（添加异常处理）
                try:
                    await self.push_execution_log(
                        task_id=task_id,
                        case_id=case_id,
                        case_no=case_result["case_no"],
                        status=case_result["status"],
                        log=case_result["log"]
                    )
                except Exception as e:
                    logger.error(f"推送日志失败: {e}")

                # 模拟执行延迟
                await asyncio.sleep(1)

            # 任务执行完成
            if task_id in self.running_tasks and self.running_tasks[task_id]["status"] == "running":
                # 根据执行结果更新任务状态
                if fail_count == 0:
                    status = 2  # 2: 执行完成
                else:
                    status = 3  # 3: 执行失败

                update_test_task_status(db, task_id, project_id, status)

                # 推送任务完成消息
                await self.push_execution_log(
                    task_id=task_id,
                    case_id=0,
                    case_no="",
                    status=status,
                    log=f"任务执行完成，成功: {success_count}, 失败: {fail_count}"
                )

        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            update_test_task_status(db, task_id, project_id, 3)  # 3: 执行失败

            # 推送错误消息
            await self.push_execution_log(
                task_id=task_id,
                case_id=0,
                case_no="",
                status=3,
                log=f"任务执行失败: {str(e)}"
            )
        finally:
            # 清理前置条件服务（关闭浏览器等资源）
            try:
                await precondition_service.cleanup()
                logger.info("前置条件服务已清理")
            except Exception as e:
                logger.warning(f"前置条件服务清理失败: {e}")

            # 从运行任务列表中移除
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

            # 关闭数据库连接（防止连接泄漏）
            db.close()


TestTaskCoreMixin = TaskCoreMixin
