"""TaskAssembler 单元测试。

使用真实测试库（tests/conftest.py 的 db fixture，事务隔离 + 自动回滚），
不 Mock 数据库，验证任务名推导、占位任务创建、创建/更新双模式装配、
TestResult 批量生成、执行引擎异步启动、启动失败不阻断、DB 异常回滚。

清理：依赖 db fixture 事务级回滚自动清理。执行引擎用 FakeExecutor 替身，
asyncio.create_task 后台任务用 await asyncio.sleep(0.05) 排空。
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from app.models.enums import ExecStatus
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TaskStatus, TestTask
from app.services.url_driven.task_assembler import (
    EXECUTION_MODE_SMART,
    _TASK_NAME_TS_FORMAT,
    TaskAssembler,
)


class FakeExecutor:
    """TestExecutionEngineV2 替身，记录 execute_test_task 调用，可控抛异常。"""

    def __init__(self, raise_exc: Optional[Exception] = None) -> None:
        self._raise = raise_exc
        self.calls: List[Dict[str, Any]] = []

    async def execute_test_task(
        self, task_id: int, execution_mode: str = "smart", **kwargs: Any
    ) -> Dict[str, Any]:
        self.calls.append({"task_id": task_id, "execution_mode": execution_mode})
        if self._raise is not None:
            raise self._raise
        return {"task_id": task_id}


def make_project(db, testUser, name: str = "assembler_proj") -> Project:
    """构造并持久化 Project，依赖 db 事务回滚自动清理。"""
    proj = Project(
        name=name, user_id=testUser.id, project_type="web", source="url_quick_test"
    )
    db.add(proj)
    db.flush()
    return proj


def make_case(db, project: Project, case_no: str, title: str = "用例") -> TestCase:
    """构造并持久化 TestCase，字段对齐 model 必填约束。"""
    case = TestCase(
        case_no=case_no, project_id=project.id, module="默认", title=title,
        precondition="无", steps_json=[], expected_result="成功",
        priority=2, case_type="UI",
    )
    db.add(case)
    db.flush()
    return case


@pytest.fixture
def assembler_with_executor():
    """返回 (TaskAssembler, FakeExecutor)，工厂注入 FakeExecutor 供断言。"""
    executor = FakeExecutor()
    asm = TaskAssembler(executor_factory=lambda session: executor)
    return asm, executor


class TestDeriveTaskName:
    """任务名推导：{项目名}_快速测试_{YYYYMMDDHHmmss}。"""

    def test_task_name_format(self, db, testUser):
        proj = make_project(db, testUser, name="demo_site")
        name = TaskAssembler.derive_task_name(proj)
        prefix = "demo_site_快速测试_"
        assert name.startswith(prefix)
        ts = name[len(prefix):]
        assert len(ts) == 14
        # 验证时间戳可解析为合法日期，杜绝格式错误
        datetime.strptime(ts, _TASK_NAME_TS_FORMAT)


class TestCreateSkeletonTask:
    """占位任务创建：status=PENDING/case_ids 空/total_count=0。"""

    def test_creates_placeholder_task(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        task = asm.create_skeleton_task(proj.id, testUser.id, db)
        assert task.id is not None
        assert task.project_id == proj.id
        assert task.executor_id == testUser.id
        assert task.case_ids == []
        assert task.total_count == 0
        assert task.status == TaskStatus.PENDING
        # 不创建 TestResult
        assert db.query(TestResult).filter(TestResult.task_id == task.id).count() == 0

    def test_project_not_found_raises(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        with pytest.raises(ValueError, match="项目不存在"):
            asm.create_skeleton_task(99999, testUser.id, db)

    def test_db_exception_rolls_back(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        with patch.object(db, "commit", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError, match="db down"):
                asm.create_skeleton_task(proj.id, testUser.id, db)
        # 任务未持久化
        assert db.query(TestTask).filter(TestTask.project_id == proj.id).count() == 0


class TestAssembleCreate:
    """task_id=None 模式：创建新任务 + TestResult + 启动执行。"""

    @pytest.mark.asyncio
    async def test_creates_task_with_correct_fields(self, db, testUser, assembler_with_executor):
        asm, executor = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-A-1")
        case2 = make_case(db, proj, "TC-A-2")
        task = await asm.assemble(proj.id, [case1.id, case2.id], testUser.id, db)
        await asyncio.sleep(0.05)  # 排空 asyncio.create_task 启动的后台执行
        assert task.id is not None
        assert task.project_id == proj.id
        assert set(task.case_ids) == {case1.id, case2.id}
        assert task.total_count == 2
        assert task.executor_id == testUser.id
        assert task.task_name.startswith("assembler_proj_快速测试_")
        # _start_task 置 RUNNING
        assert task.status == TaskStatus.RUNNING
        assert task.start_time is not None
        assert len(executor.calls) == 1

    @pytest.mark.asyncio
    async def test_creates_test_results_with_not_executed(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-B-1")
        task = await asm.assemble(proj.id, [case1.id], testUser.id, db)
        results = db.query(TestResult).filter(TestResult.task_id == task.id).all()
        assert len(results) == 1
        assert results[0].case_id == case1.id
        assert results[0].case_no == case1.case_no
        assert results[0].exec_status == int(ExecStatus.NOT_EXECUTED)
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_starts_execution_with_smart_mode(self, db, testUser, assembler_with_executor):
        asm, executor = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-C-1")
        task = await asm.assemble(proj.id, [case1.id], testUser.id, db)
        await asyncio.sleep(0.05)  # 排空后台执行任务
        assert len(executor.calls) == 1
        call = executor.calls[0]
        assert call["task_id"] == task.id
        assert call["execution_mode"] == EXECUTION_MODE_SMART

    @pytest.mark.asyncio
    async def test_empty_case_ids_still_creates_and_starts(self, db, testUser, assembler_with_executor):
        asm, executor = assembler_with_executor
        proj = make_project(db, testUser)
        task = await asm.assemble(proj.id, [], testUser.id, db)
        await asyncio.sleep(0.05)  # 排空后台执行任务
        assert task.total_count == 0
        assert task.case_ids == []
        assert db.query(TestResult).filter(TestResult.task_id == task.id).count() == 0
        assert len(executor.calls) == 1

    @pytest.mark.asyncio
    async def test_unmatched_case_id_skipped_in_results(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-D-1")
        task = await asm.assemble(proj.id, [case1.id, 99999], testUser.id, db)
        # 仅 case1 创建 TestResult
        results = db.query(TestResult).filter(TestResult.task_id == task.id).all()
        assert len(results) == 1
        assert results[0].case_id == case1.id
        # case_ids 保留原始入参（含未匹配项）
        assert task.total_count == 2
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_project_not_found_raises(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        with pytest.raises(ValueError, match="项目不存在"):
            await asm.assemble(99999, [], testUser.id, db)


class TestAssembleUpdate:
    """task_id=已有 模式：更新占位任务 case_ids + TestResult + 启动。"""

    @pytest.mark.asyncio
    async def test_updates_skeleton_task(self, db, testUser, assembler_with_executor):
        asm, executor = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-E-1")
        skeleton = asm.create_skeleton_task(proj.id, testUser.id, db)
        assert skeleton.case_ids == []
        assert skeleton.total_count == 0
        task = await asm.assemble(
            proj.id, [case1.id], testUser.id, db, task_id=skeleton.id
        )
        await asyncio.sleep(0.05)  # 排空后台执行任务
        assert task.id == skeleton.id
        assert task.case_ids == [case1.id]
        assert task.total_count == 1
        assert task.status == TaskStatus.RUNNING
        results = db.query(TestResult).filter(TestResult.task_id == task.id).all()
        assert len(results) == 1
        assert len(executor.calls) == 1

    @pytest.mark.asyncio
    async def test_task_not_found_raises(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        with pytest.raises(ValueError, match="待更新的任务不存在"):
            await asm.assemble(proj.id, [], testUser.id, db, task_id=99999)


class TestStartFailure:
    """启动失败不阻断：执行引擎异常/启动 commit 失败均不抛出。"""

    @pytest.mark.asyncio
    async def test_executor_exception_doesnt_block(self, db, testUser):
        executor = FakeExecutor(raise_exc=RuntimeError("engine boom"))
        asm = TaskAssembler(executor_factory=lambda session: executor)
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-F-1")
        task = await asm.assemble(proj.id, [case1.id], testUser.id, db)
        # 启动时已置 RUNNING，后台执行异常被 _run_executor_safely 捕获
        assert task.status == TaskStatus.RUNNING
        await asyncio.sleep(0.05)
        assert len(executor.calls) == 1

    @pytest.mark.asyncio
    async def test_start_commit_failure_returns_without_executor(self, db, testUser):
        executor = FakeExecutor()
        asm = TaskAssembler(executor_factory=lambda session: executor)
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-SC-1")
        original_commit = db.commit
        call_count = {"n": 0}

        def flaky_commit(*args: Any, **kwargs: Any) -> Any:
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise RuntimeError("start commit down")
            return original_commit(*args, **kwargs)

        with patch.object(db, "commit", side_effect=flaky_commit):
            task = await asm.assemble(proj.id, [case1.id], testUser.id, db)
        # assemble 未抛异常（启动失败仅记录不阻断）
        assert task is not None
        # commit 失败后 _start_task return，执行器未调用
        assert executor.calls == []
        await asyncio.sleep(0.05)


class TestCreateDbException:
    """创建模式 DB 异常：flush/commit 失败均回滚抛出。"""

    @pytest.mark.asyncio
    async def test_create_flush_failure_raises(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        # 关闭 autoflush 使异常落在显式 flush 的 try 块；flush 仅首次抛异常，
        # rollback 重建 savepoint 时的 flush 需放行以覆盖 logger.error+raise 分支
        db.autoflush = False
        flush_counter = {"n": 0}

        def flaky_flush(*args: Any, **kwargs: Any) -> None:
            flush_counter["n"] += 1
            if flush_counter["n"] == 1:
                raise RuntimeError("flush down")

        try:
            with patch.object(db, "flush", side_effect=flaky_flush):
                with pytest.raises(RuntimeError, match="flush down"):
                    await asm.assemble(proj.id, [], testUser.id, db)
        finally:
            db.autoflush = True
        assert db.query(TestTask).filter(TestTask.project_id == proj.id).count() == 0

    @pytest.mark.asyncio
    async def test_create_commit_failure_raises(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-H-1")
        with patch.object(db, "commit", side_effect=RuntimeError("commit down")):
            with pytest.raises(RuntimeError, match="commit down"):
                await asm.assemble(proj.id, [case1.id], testUser.id, db)
        assert db.query(TestTask).filter(TestTask.project_id == proj.id).count() == 0


class TestUpdateDbException:
    """更新模式 DB 异常：flush/commit 失败均回滚抛出。"""

    @pytest.mark.asyncio
    async def test_update_flush_failure_raises(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-I-1")
        skeleton = asm.create_skeleton_task(proj.id, testUser.id, db)
        # 关闭 autoflush 使异常落在显式 flush 的 try 块；flush 仅首次抛异常，
        # rollback 重建 savepoint 时的 flush 需放行以覆盖 logger.error+raise 分支
        db.autoflush = False
        flush_counter = {"n": 0}

        def flaky_flush(*args: Any, **kwargs: Any) -> None:
            flush_counter["n"] += 1
            if flush_counter["n"] == 1:
                raise RuntimeError("update flush down")

        try:
            with patch.object(db, "flush", side_effect=flaky_flush):
                with pytest.raises(RuntimeError, match="update flush down"):
                    await asm.assemble(proj.id, [case1.id], testUser.id, db, task_id=skeleton.id)
        finally:
            db.autoflush = True

    @pytest.mark.asyncio
    async def test_update_commit_failure_raises(self, db, testUser, assembler_with_executor):
        asm, _ = assembler_with_executor
        proj = make_project(db, testUser)
        case1 = make_case(db, proj, "TC-J-1")
        skeleton = asm.create_skeleton_task(proj.id, testUser.id, db)
        with patch.object(db, "commit", side_effect=RuntimeError("update commit down")):
            with pytest.raises(RuntimeError, match="update commit down"):
                await asm.assemble(proj.id, [case1.id], testUser.id, db, task_id=skeleton.id)


class TestDefaultExecutorFactory:
    """默认执行引擎工厂：不注入时返回 TestExecutionEngineV2（构造无 I/O 副作用）。"""

    def test_default_executor_factory_returns_instance(self, db, testUser):
        asm = TaskAssembler()
        executor = asm._executor_factory(db)
        from app.services.test_execution_engine_v2 import TestExecutionEngineV2
        assert isinstance(executor, TestExecutionEngineV2)
        assert executor.db is db
