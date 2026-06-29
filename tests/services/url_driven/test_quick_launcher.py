"""QuickLauncher 单元测试。

使用真实测试库（tests/conftest.py 的 db fixture），Mock 外部依赖：
- FakeProjectBuilder/FakeSiteExplorer/FakeCaseGenerator/FakePushService：
  建项/探索/生成/推送的替身，可控抛异常；真实 TaskAssembler + FakeExecutor 装配任务。
验证编排顺序、4 阶段推送、各步降级策略、响应字段与通道格式。
"""
import asyncio
from typing import Any, Dict, List, Optional

import pytest

from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_task import TaskStatus
from app.schemas.quick_test import QuickTestLaunchResponse
from app.services.url_driven.auto_case_generator import AutoCaseGenerator
from app.services.url_driven.quick_launcher import QuickLauncher
from app.services.url_driven.site_explorer import SiteMap
from app.services.url_driven.task_assembler import TaskAssembler


class FakeProjectBuilder:
    """AutoProjectBuilder 替身，创建真实 Project 入库供后续装配使用。"""

    def __init__(self, raise_exc: Optional[Exception] = None) -> None:
        self._raise = raise_exc
        self.calls: List[Dict[str, Any]] = []

    def build(self, url: str, description, user_id: int, session) -> Project:
        self.calls.append({"url": url, "description": description, "user_id": user_id})
        if self._raise is not None:
            raise self._raise
        proj = Project(
            name="quick_test_proj", user_id=user_id, project_type="web",
            source="url_quick_test",
        )
        session.add(proj)
        session.flush()
        return proj


class FakeSiteExplorer:
    """SiteExplorer 替身，async explore 可控返回/抛异常。"""

    def __init__(self, site_map: Optional[SiteMap] = None, raise_exc: Optional[Exception] = None) -> None:
        self._site_map = site_map
        self._raise = raise_exc
        self.calls: List[Dict[str, Any]] = []

    async def explore(self, url: str, credentials: Optional[Dict[str, str]] = None) -> SiteMap:
        self.calls.append({"url": url, "credentials": credentials})
        if self._raise is not None:
            raise self._raise
        return self._site_map or SiteMap(
            entry_url=url, pages=[], max_depth_reached=0,
            explored_count=0, skipped_count=0, cache_key="",
        )


class FakeCaseGenerator:
    """AutoCaseGenerator 替身，返回预建 TestCase 列表，可控抛异常。"""

    def __init__(self, cases: Optional[List[TestCase]] = None, raise_exc: Optional[Exception] = None) -> None:
        self._cases = cases or []
        self._raise = raise_exc
        self.calls: List[Dict[str, Any]] = []

    def generate(self, site_map, project_id: int, description, user_id: int, session) -> List[TestCase]:
        self.calls.append({"project_id": project_id, "description": description})
        if self._raise is not None:
            raise self._raise
        return self._cases


class FakePushService:
    """PushService 替身，async push 记录调用，可控抛异常。"""

    def __init__(self, raise_exc: Optional[Exception] = None) -> None:
        self._raise = raise_exc
        self.calls: List[Dict[str, Any]] = []

    async def push(self, channel: str, data: Dict[str, Any]) -> bool:
        self.calls.append({"channel": channel, "data": data})
        if self._raise is not None:
            raise self._raise
        return True


class FakeExecutor:
    """TestExecutionEngineV2 替身，记录 execute_test_task 调用。"""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def execute_test_task(self, task_id: int, execution_mode: str = "smart", **kwargs: Any) -> Dict[str, Any]:
        self.calls.append({"task_id": task_id, "execution_mode": execution_mode})
        return {"task_id": task_id}


class FailingAssembler:
    """TaskAssembler 替身，create_skeleton_task 委托真实实现，assemble 抛异常。"""

    def __init__(self, real: TaskAssembler) -> None:
        self._real = real

    def create_skeleton_task(self, project_id: int, user_id: int, session):
        return self._real.create_skeleton_task(project_id, user_id, session)

    async def assemble(self, project_id: int, case_ids, user_id: int, session, task_id=None):
        raise RuntimeError("assemble boom")


def make_case(db, project: Project, case_no: str) -> TestCase:
    """构造并持久化 TestCase，供 FakeCaseGenerator 返回。"""
    case = TestCase(
        case_no=case_no, project_id=project.id, module="默认", title=f"用例{case_no}",
        precondition="无", steps_json=[], expected_result="成功",
        priority=2, case_type="UI",
    )
    db.add(case)
    db.flush()
    return case


def build_launcher(
    db, testUser, *, project_raise=None, explorer_raise=None, explorer_map=None,
    generator_raise=None, generator_cases=None, push_raise=None, assembler_fail=False,
):
    """组装 QuickLauncher，注入各 Fake 依赖，返回 (launcher, fakes_dict)。"""
    project_builder = FakeProjectBuilder(raise_exc=project_raise)
    explorer = FakeSiteExplorer(site_map=explorer_map, raise_exc=explorer_raise)
    case_generator = FakeCaseGenerator(cases=generator_cases, raise_exc=generator_raise)
    push_service = FakePushService(raise_exc=push_raise)
    executor = FakeExecutor()
    real_assembler = TaskAssembler(executor_factory=lambda session: executor)
    assembler = FailingAssembler(real_assembler) if assembler_fail else real_assembler
    launcher = QuickLauncher(
        project_builder=project_builder,
        explorer_factory=lambda: explorer,
        case_generator_factory=lambda: case_generator,
        assembler=assembler,
        push_service=push_service,
    )
    fakes = {
        "project_builder": project_builder, "explorer": explorer,
        "case_generator": case_generator, "push_service": push_service,
        "executor": executor, "assembler": assembler,
    }
    return launcher, fakes


class TestLaunchSuccess:
    """完整编排成功：响应字段、预估时长、4 阶段推送顺序、通道格式。"""

    @pytest.mark.asyncio
    async def test_full_orchestration_returns_response(self, db, testUser):
        class _Gen:
            def generate(self, site_map, project_id, description, user_id, session):
                case = TestCase(
                    case_no="TC-Q-1", project_id=project_id, module="默认", title="用例",
                    precondition="无", steps_json=[], expected_result="成功",
                    priority=2, case_type="UI",
                )
                session.add(case)
                session.flush()
                return [case]

        launcher, fakes = build_launcher(
            db, testUser, explorer_map=SiteMap(
                entry_url="https://shop.example.com", pages=[], max_depth_reached=0,
                explored_count=0, skipped_count=0, cache_key="",
            ),
        )
        launcher._case_generator_factory = lambda: _Gen()
        resp = await launcher.launch(
            "https://shop.example.com", "重点测登录", None, testUser.id, db
        )
        assert isinstance(resp, QuickTestLaunchResponse)
        assert resp.task_id > 0
        assert resp.project_id > 0
        assert resp.estimated_duration_sec == 1 * 30
        assert resp.websocket_channel == f"quick_test:{resp.task_id}"
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_estimated_duration_zero_when_no_cases(self, db, testUser):
        launcher, _ = build_launcher(db, testUser, generator_cases=[])
        resp = await launcher.launch(
            "https://shop.example.com", None, None, testUser.id, db
        )
        assert resp.estimated_duration_sec == 0
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_4_stages_pushed_in_order(self, db, testUser):
        launcher, fakes = build_launcher(db, testUser, generator_cases=[])
        resp = await launcher.launch(
            "https://shop.example.com", None, None, testUser.id, db
        )
        push = fakes["push_service"]
        # 提取阶段去重相邻（每阶段 running+done 两次推送）
        stages = []
        for call in push.calls:
            stage = call["data"]["stage"]
            if not stages or stages[-1] != stage:
                stages.append(stage)
        assert stages == ["site_exploring", "case_generating", "task_assembling", "completed"]
        channels = {c["channel"] for c in push.calls}
        assert channels == {resp.websocket_channel}
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_completed_message_contains_task_and_project(self, db, testUser):
        launcher, fakes = build_launcher(db, testUser, generator_cases=[])
        resp = await launcher.launch(
            "https://shop.example.com", None, None, testUser.id, db
        )
        push = fakes["push_service"]
        completed = [c for c in push.calls if c["data"]["stage"] == "completed"]
        assert len(completed) == 1
        data = completed[0]["data"]
        assert data["status"] == "done"
        assert data["progress"] == 100
        assert data["detail"]["task_id"] == resp.task_id
        assert data["detail"]["project_id"] == resp.project_id
        await asyncio.sleep(0.05)


class TestExploreFailure:
    """站点探索失败降级为空 SiteMap，仍返回 task_id。"""

    @pytest.mark.asyncio
    async def test_explore_failure_degrades_to_empty(self, db, testUser):
        launcher, fakes = build_launcher(
            db, testUser, explorer_raise=RuntimeError("browser timeout"),
            generator_cases=[],
        )
        resp = await launcher.launch(
            "https://shop.example.com", None, None, testUser.id, db
        )
        assert resp.task_id > 0
        assert resp.estimated_duration_sec == 0
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_explore_failure_pushes_failed_status(self, db, testUser):
        launcher, fakes = build_launcher(
            db, testUser, explorer_raise=RuntimeError("browser timeout"),
            generator_cases=[],
        )
        await launcher.launch("https://shop.example.com", None, None, testUser.id, db)
        push = fakes["push_service"]
        failed = [c for c in push.calls if c["data"]["stage"] == "site_exploring" and c["data"]["status"] == "failed"]
        assert len(failed) == 1
        assert failed[0]["data"]["detail"]["degraded"] is True
        await asyncio.sleep(0.05)


class TestCaseGenerationFailure:
    """用例生成失败降级为空用例，仍创建任务。"""

    @pytest.mark.asyncio
    async def test_generation_failure_degrades_to_empty(self, db, testUser):
        launcher, fakes = build_launcher(
            db, testUser, generator_raise=RuntimeError("ai timeout"),
        )
        resp = await launcher.launch(
            "https://shop.example.com", None, None, testUser.id, db
        )
        assert resp.task_id > 0
        assert resp.estimated_duration_sec == 0
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_generation_failure_pushes_failed_status(self, db, testUser):
        launcher, fakes = build_launcher(
            db, testUser, generator_raise=RuntimeError("ai timeout"),
        )
        await launcher.launch("https://shop.example.com", None, None, testUser.id, db)
        push = fakes["push_service"]
        failed = [c for c in push.calls if c["data"]["stage"] == "case_generating" and c["data"]["status"] == "failed"]
        assert len(failed) == 1
        assert failed[0]["data"]["detail"]["degraded"] is True
        await asyncio.sleep(0.05)


class TestAssembleFailure:
    """任务装配失败仍返回已预创建 task_id。"""

    @pytest.mark.asyncio
    async def test_assemble_failure_still_returns_task_id(self, db, testUser):
        launcher, fakes = build_launcher(db, testUser, assembler_fail=True)
        resp = await launcher.launch(
            "https://shop.example.com", None, None, testUser.id, db
        )
        assert resp.task_id > 0
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_assemble_failure_pushes_failed_status(self, db, testUser):
        launcher, fakes = build_launcher(db, testUser, assembler_fail=True)
        await launcher.launch("https://shop.example.com", None, None, testUser.id, db)
        push = fakes["push_service"]
        failed = [c for c in push.calls if c["data"]["stage"] == "task_assembling" and c["data"]["status"] == "failed"]
        assert len(failed) == 1
        assert "error" in failed[0]["data"]["detail"]
        await asyncio.sleep(0.05)


class TestBuildFailure:
    """建项失败抛出，编排终止。"""

    @pytest.mark.asyncio
    async def test_build_failure_raises(self, db, testUser):
        launcher, fakes = build_launcher(
            db, testUser, project_raise=RuntimeError("build failed"),
        )
        with pytest.raises(RuntimeError, match="build failed"):
            await launcher.launch("https://shop.example.com", None, None, testUser.id, db)
        # 建项失败前无推送
        assert fakes["push_service"].calls == []


class TestPushFailure:
    """推送失败不阻断编排，仍返回响应。"""

    @pytest.mark.asyncio
    async def test_push_failure_doesnt_block(self, db, testUser):
        launcher, fakes = build_launcher(
            db, testUser, push_raise=ConnectionError("ws refused"), generator_cases=[],
        )
        resp = await launcher.launch("https://shop.example.com", None, None, testUser.id, db)
        assert resp.task_id > 0
        await asyncio.sleep(0.05)


class TestDefaultCaseGeneratorFactory:
    """默认用例生成器工厂：不注入时返回 AutoCaseGenerator（构造无 I/O 副作用）。"""

    def test_default_case_generator_factory_returns_generator(self):
        # 注入其余依赖避免触发 get_push_service 等真实连接
        launcher = QuickLauncher(
            project_builder=FakeProjectBuilder(),
            explorer_factory=lambda: FakeSiteExplorer(),
            push_service=FakePushService(),
        )
        generator = launcher._case_generator_factory()
        assert isinstance(generator, AutoCaseGenerator)
