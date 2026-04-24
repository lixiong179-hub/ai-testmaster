"""任务执行Mixin - 处理用例遍历、执行模式分发与结果记录。

本模块实现任务执行的核心逻辑，包括遍历项目下所有测试用例、
根据用例类型选择执行模式、创建执行结果记录等。作为Mixin
被TaskService组合使用，实现执行逻辑与任务管理的职责分离。

核心类:
    - TaskExecutionMixin: 任务执行逻辑Mixin

设计模式:
    作为Mixin模块，通过多继承组合到TaskService中，提供:
    - _execute_task: 任务级执行流程编排
    - execute_case: 用例级执行与结果记录
    - _run_case_by_mode: 执行模式分发

依赖关系:
    - app.models.test_task: TestTask ORM模型
    - app.models.test_case: TestCase ORM模型
    - app.models.test_result: TestResult ORM模型
    - app.services.execution_mode_selector: 执行模式选择器
    - app.services.test_execution_engine: Web执行引擎

执行流程:
    TaskService.start_task -> _execute_task -> [循环] execute_case
    -> _run_case_by_mode -> TestExecutionEngineV2.execute_test_task
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from loguru import logger
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.services.execution_mode_selector import get_execution_mode_selector
from sqlalchemy.orm import Session


class TaskExecutionMixin:
    """任务执行逻辑Mixin，处理用例遍历和分模式执行。

    职责:
        - 编排任务级执行流程（状态管理、进度计算）
        - 逐条执行测试用例并记录结果
        - 根据用例类型分发到对应执行引擎

    设计意图:
        将执行逻辑从TaskService中抽离为独立Mixin，便于:
        1. 单独测试执行逻辑
        2. 不同任务类型复用执行流程
        3. 与推送逻辑(TaskPushMixin)解耦

    使用场景:
        被TaskService通过多继承组合，不单独实例化使用。
    """

    async def _execute_task(self, task: TestTask, db: Session) -> None:
        """遍历项目下所有用例执行，更新任务状态和进度。

        执行流程:
            1. 更新任务状态为running，记录开始时间
            2. 查询项目下所有测试用例
            3. 逐条执行用例，统计通过/失败数量
            4. 每条用例执行后推送进度更新
            5. 全部完成后更新任务统计信息
            6. 异常时标记任务为failed状态

        Args:
            task: TestTask ORM实例。
            db: 数据库会话。
        """
        try:
            # 初始化任务执行状态
            task.status = "running"
            task.start_time = datetime.now()
            db.commit()
            await self.push_execution_progress(task.id, "running", 0, "任务开始执行")

            # 查询项目下所有待执行用例
            cases = db.query(TestCase).filter(
                TestCase.project_id == task.project_id
            ).all()
            if not cases:
                # 无用例时直接标记完成
                task.status = "completed"
                task.end_time = datetime.now()
                db.commit()
                await self.push_execution_progress(task.id, "completed", 100, "无测试用例可执行")
                return

            total = len(cases)
            completed = 0
            passed = 0
            failed = 0

            # 逐条执行用例，统计结果并推送进度
            for case in cases:
                try:
                    result = await self.execute_case(task, case, db)
                    if result.get("status") == "passed":
                        passed += 1
                    else:
                        failed += 1
                    completed += 1
                    # 计算进度百分比并推送
                    progress = int(completed / total * 100)
                    await self.push_execution_progress(
                        task.id, "running", progress,
                        f"已完成 {completed}/{total}"
                    )
                except Exception as e:
                    # 单条用例异常不影响整体任务，记录后继续执行
                    failed += 1
                    completed += 1
                    logger.error(f"执行用例失败 {case.id}: {e}")
                    await self.push_execution_log(
                        task.id, case.id, "error",
                        f"执行异常: {str(e)}"
                    )

            # 更新任务最终统计信息
            task.status = "completed"
            task.end_time = datetime.now()
            task.passed_count = passed
            task.failed_count = failed
            task.total_count = total
            db.commit()
            await self.push_execution_progress(
                task.id, "completed", 100,
                f"任务完成: 通过{passed}, 失败{failed}"
            )
        except Exception as e:
            # 任务级异常，标记为failed
            logger.error(f"任务执行异常: {e}")
            task.status = "failed"
            task.end_time = datetime.now()
            task.error_message = str(e)
            db.commit()
            await self.push_execution_progress(task.id, "failed", 0, f"任务执行异常: {str(e)}")

    async def execute_case(
        self, task: TestTask, case: TestCase, db: Session
    ) -> Dict[str, Any]:
        """根据用例类型选择执行模式，创建TestResult记录。

        执行流程:
            1. 通过ExecutionModeSelector选择执行模式
            2. 创建TestResult记录（初始状态running）
            3. 推送用例执行开始日志
            4. 调用对应执行引擎执行用例
            5. 更新TestResult状态和执行耗时
            6. 推送用例执行完成日志

        Args:
            task: 所属任务。
            case: TestCase ORM实例。
            db: 数据库会话。

        Returns:
            包含status和result_id的字典。
        """
        try:
            # 根据用例类型选择执行模式（web/mobile/api）
            selector = get_execution_mode_selector()
            case_type = getattr(case, 'case_type', '') or ''
            mode = selector.select_mode(case_type)

            # 创建执行结果记录，初始状态为running
            result = TestResult(
                task_id=task.id,
                case_id=case.id,
                status="running",
                exec_time=datetime.now()
            )
            db.add(result)
            db.commit()
            db.refresh(result)

            await self.push_execution_log(
                task.id, case.id, "info",
                f"开始执行用例: {case.title}, 模式: {mode}"
            )

            # 分发到对应执行引擎
            execution_result = await self._run_case_by_mode(case, mode, db)

            # 更新执行结果
            result.status = execution_result.get("status", "failed")
            result.execution_time = execution_result.get("duration", 0)
            result.error_message = execution_result.get("error_message")
            db.commit()

            await self.push_execution_log(
                task.id, case.id, "info",
                f"用例执行完成: {result.status}"
            )
            return {"status": result.status, "result_id": result.id}
        except Exception as e:
            logger.error(f"执行用例异常 {case.id}: {e}")
            return {"status": "failed", "error": "执行失败"}

    async def _run_case_by_mode(
        self, case: TestCase, mode: str, db: Session
    ) -> Dict[str, Any]:
        """根据执行模式分发到对应执行器，web/mobile/api各有独立路径。

        当前支持的模式:
            - web: 使用TestExecutionEngineV2执行Web端测试
            - mobile: 移动端执行器（暂未配置）
            - api: API执行器（尚未实现）

        Args:
            case: TestCase ORM实例。
            mode: 执行模式字符串。
            db: 数据库会话。

        Returns:
            包含status、error_message的字典。
        """
        try:
            if mode == "web":
                # Web端执行，延迟导入避免循环依赖
                try:
                    from app.services.test_execution_engine import TestExecutionEngineV2
                    engine = TestExecutionEngineV2(db=db)
                    result = await engine.execute_test_case(
                        test_case=case,
                        project_id=case.project_id,
                        execution_mode="smart"
                    )
                    status = "passed" if result.status.value == "passed" else "failed"
                    return {"status": status, "duration": result.duration_ms}
                except Exception as e:
                    return {"status": "failed", "error_message": f"Web执行器加载失败: {e}"}
            elif mode == "mobile":
                # 移动端执行器尚未配置
                raise NotImplementedError("移动端执行器尚未实现")
            elif mode == "api":
                # API执行器尚未实现
                raise NotImplementedError("API执行器尚未实现")
            else:
                return {"status": "failed", "error_message": f"不支持的执行模式: {mode}"}
        except Exception as e:
            logger.error(f"执行模式分发异常: {e}")
            return {"status": "failed", "error_message": "执行失败"}
