"""
ExecutionReplayService单元测试

测试范围:
- 回放事件和时间轴创建
- 回放会话管理
- 回放控制功能

注意: 使用真实环境，不使用Mock
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.services.execution_replay import ExecutionReplayService
from app.services.execution_replay.models import (
    ReplayEvent, ExecutionTimeline, ReplayEventType
)
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def replay_service(db):
    service = ExecutionReplayService(db=db)
    yield service
    session = service.db


@pytest.fixture
def sample_project(db):
    user = User(username="test_user", email="test@example.com")
    user.set_password("password123")
    db.add(user)
    db.commit()
    db.refresh(user)

    project = Project(name="TestProject", description="Test Description")
    db.add(project)
    db.commit()
    db.refresh(project)

    yield project

    db.delete(project)
    db.delete(user)
    db.commit()


@pytest.fixture
def sample_test_case(db, sample_project):
    case = TestCase(
        title="Test Case",
        case_type="web",
        project_id=sample_project.id
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    yield case

    db.delete(case)


@pytest.fixture
def sample_task(db, sample_project):
    task = TestTask(
        name="Test Task",
        project_id=sample_project.id,
        status="pending"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    yield task

    db.delete(task)


class TestReplayEvent:
    """回放事件测试类"""

    def test_replay_event_creation(self):
        """测试回放事件创建"""
        event = ReplayEvent(
            timestamp=5.0,
            event_type=ReplayEventType.CLICK,
            action="点击按钮",
            step_number=1
        )

        assert event.timestamp == 5.0
        assert event.event_type == ReplayEventType.CLICK
        assert event.step_number == 1

    def test_replay_event_to_dict(self):
        """测试回放事件转字典"""
        event = ReplayEvent(
            timestamp=10.0,
            event_type=ReplayEventType.SCREENSHOT,
            action="截图",
            step_number=2
        )

        event_dict = event.to_dict()

        assert event_dict["timestamp"] == 10.0
        assert event_dict["event_type"] == "screenshot"
        assert event_dict["step_number"] == 2

    def test_replay_event_default_fields(self):
        """测试回放事件默认字段"""
        event = ReplayEvent(
            timestamp=0.0,
            event_type=ReplayEventType.NAVIGATE,
            action="开始导航",
            step_number=0
        )

        assert event.screenshot_path is None
        assert event.element_info is None
        assert event.error_message is None
        assert event.duration_ms == 0

    def test_replay_event_with_optional_fields(self):
        """测试带可选字段的回放事件"""
        event = ReplayEvent(
            timestamp=15.0,
            event_type=ReplayEventType.ERROR,
            action="执行失败",
            step_number=3,
            screenshot_path="/screenshots/step3.png",
            error_message="元素未找到"
        )

        assert event.screenshot_path == "/screenshots/step3.png"
        assert event.error_message == "元素未找到"


class TestExecutionTimeline:
    """执行时间轴测试类"""

    def test_execution_timeline_creation(self):
        """测试执行时间轴创建"""
        now = datetime.now()
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=1,
            start_time=now,
            total_duration_ms=60000
        )

        assert timeline.execution_id == 1
        assert timeline.test_case_id == 1
        assert timeline.total_duration_ms == 60000
        assert len(timeline.events) == 0
        assert timeline.end_time is None

    def test_execution_timeline_with_events(self):
        """测试带事件的执行时间轴"""
        now = datetime.now()
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=1,
            start_time=now,
            total_duration_ms=30000,
            events=[
                ReplayEvent(timestamp=0.0, event_type=ReplayEventType.NAVIGATE, action="开始", step_number=0),
                ReplayEvent(timestamp=10.0, event_type=ReplayEventType.CLICK, action="点击", step_number=1)
            ]
        )

        assert timeline.total_duration_ms == 30000
        assert len(timeline.events) == 2

    def test_execution_timeline_to_dict(self):
        """测试执行时间轴转字典"""
        now = datetime.now()
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=1,
            start_time=now,
            end_time=now,
            total_duration_ms=30000,
            events=[
                ReplayEvent(timestamp=0.0, event_type=ReplayEventType.NAVIGATE, action="开始", step_number=0),
                ReplayEvent(timestamp=10.0, event_type=ReplayEventType.CLICK, action="点击", step_number=1)
            ]
        )

        timeline_dict = timeline.to_dict()

        assert timeline_dict["execution_id"] == 1
        assert timeline_dict["test_case_id"] == 1
        assert timeline_dict["total_duration_ms"] == 30000
        assert len(timeline_dict["events"]) == 2
        assert timeline_dict["start_time"] is not None
        assert timeline_dict["end_time"] is not None

    def test_execution_timeline_empty_events(self):
        """测试空事件的执行时间轴"""
        timeline = ExecutionTimeline(
            execution_id=1,
            test_case_id=1,
            start_time=datetime.now()
        )

        assert timeline.events == []
        assert timeline.total_duration_ms == 0


class TestReplayDataTypes:
    """回放数据类型测试类"""

    def test_replay_event_various_types(self):
        """测试不同类型的枚举事件"""
        event_types = [
            ReplayEventType.NAVIGATE,
            ReplayEventType.CLICK,
            ReplayEventType.INPUT,
            ReplayEventType.VERIFY,
            ReplayEventType.WAIT,
            ReplayEventType.SCROLL
        ]

        for idx, event_type in enumerate(event_types):
            event = ReplayEvent(
                timestamp=float(idx * 5),
                event_type=event_type,
                action=f"执行动作{idx}",
                step_number=idx
            )

            assert event.event_type == event_type
            assert event.timestamp == idx * 5
