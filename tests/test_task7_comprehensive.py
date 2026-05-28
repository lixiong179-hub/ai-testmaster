"""
Task 7 综合单元测试

测试范围:
- VideoRecord模型
- VideoService
- VisibilityConfigService  
- ExecutionReplayService

注意: 使用真实MySQL数据库，不使用Mock
覆盖率目标: >= 95%
"""
import pytest
import asyncio
import os
import tempfile
import shutil
from app.utils.db_time import utcnow
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base

# 导入所有模型
from app.models import (
    User, Project, TestTask, TestCase, TestPoint,
    TestStep, TestData, TestResult, TestReport, ElementLocator,
    VideoRecord
)

from app.services.video import VideoService
from app.services.video.models import VideoInfo
from app.services.visibility_config_service import (
    VisibilityConfigService, VisibilityConfig, VisibilityLevel
)
from app.services.execution_replay.legacy_service import (
    ExecutionReplayService, ReplayEvent, ExecutionTimeline
)


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def db_session():
    """创建测试数据库会话（真实MySQL数据库）"""
    engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
        
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def test_user(db_session):
    """创建测试用户"""
    user = User(
        id=10000,
        username="task7_test_user",
        email="task7_test@example.com",
        password_hash="test_hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user


@pytest.fixture(scope="module")
def test_project(db_session, test_user):
    """创建测试项目"""
    project = Project(
        id=10000,
        name="Task7测试项目",
        description="用于Task7测试的项目",
        user_id=test_user.id
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    yield project


@pytest.fixture(scope="module")
def test_task(db_session, test_project, test_user):
    """创建测试任务"""
    task = TestTask(
        id=10000,
        task_name="Task7测试任务",
        project_id=test_project.id,
        executor_id=test_user.id,
        case_ids=[],
        total_count=1
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    yield task


@pytest.fixture(scope="module")
def test_case(db_session, test_project):
    """创建测试用例"""
    case = TestCase(
        id=10000,
        case_no="TASK7-001",
        project_id=test_project.id,
        module="Task7测试模块",
        title="Task7测试用例",
        precondition="前置条件",
        steps_json=[],
        expected_result="预期结果",
        priority=2,
        case_type="UI"
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    yield case


@pytest.fixture(scope="module")
def video_service():
    """创建视频服务实例"""
    test_dir = tempfile.mkdtemp()
    service = VideoService(video_base_dir=test_dir)
    yield service
    # 清理测试目录
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def visibility_service():
    """创建可见模式配置服务"""
    service = VisibilityConfigService()
    yield service


@pytest.fixture(scope="function")
def replay_service():
    """创建执行回放服务 - 使用function scope避免事件循环问题"""
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    service = ExecutionReplayService()
    yield service
    
    # 清理
    try:
        loop.run_until_complete(service.close_all_sessions())
    except:
        pass
    finally:
        loop.close()


# ==================== VideoRecord模型测试 ====================

class TestVideoRecordModel:
    """VideoRecord模型测试类"""
    
    def test_video_record_creation(self, db_session, test_task, test_case):
        """测试VideoRecord创建"""
        video = VideoRecord(
            id=10000,
            task_id=test_task.id,
            case_id=test_case.id,
            execution_id="exec_001",
            file_path="/videos/test.webm",
            file_name="test.webm",
            file_size=1024000,
            file_format="webm",
            duration=120.5,
            resolution="1920x1080",
            fps=30,
            status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        assert video.id == 10000
        assert video.task_id == test_task.id
        assert video.case_id == test_case.id
        assert video.status == "completed"
        
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_to_dict(self, db_session, test_task, test_case):
        """测试to_dict方法"""
        video = VideoRecord(
            id=10001,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/test.webm",
            file_name="test.webm",
            file_size=2048000
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        video_dict = video.to_dict()
        assert video_dict["id"] == 10001
        assert video_dict["file_size"] == 2048000
        assert "created_at" in video_dict
        
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_file_size_human(self, db_session, test_task, test_case):
        """测试file_size_human属性"""
        test_cases = [
            (512, "512.00 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
        ]
        
        for idx, (size, expected) in enumerate(test_cases):
            video = VideoRecord(
                id=10010 + idx,
                task_id=test_task.id,
                case_id=test_case.id,
                file_path="/videos/test.webm",
                file_name="test.webm",
                file_size=size
            )
            db_session.add(video)
            db_session.commit()
            
            assert video.file_size_human == expected
            
            db_session.delete(video)
            db_session.commit()


# ==================== VideoService测试 ====================

class TestVideoService:
    """视频服务测试类"""
    
    def test_service_initialization(self, video_service):
        """测试服务初始化"""
        assert video_service is not None
        assert video_service._video_base_dir.exists()
    
    def test_get_video_path(self, video_service):
        """测试获取视频路径"""
        path = video_service.get_video_path(task_id=1, case_id=1)
        assert "task_1_case_1" in str(path)
        assert path.suffix == ".webm"
    
    def test_get_video_url(self, video_service):
        """测试获取视频URL - 使用相对于video_base_dir的路径"""
        # 创建一个测试视频文件
        test_video = video_service._video_base_dir / "test_video.webm"
        test_video.touch()
        
        url = video_service.get_video_url(str(test_video))
        assert "/videos/" in url
        assert "test_video.webm" in url
    
    def test_video_info_creation(self):
        """测试VideoInfo创建 - 使用正确的参数"""
        info = VideoInfo(
            id=1,
            task_id=1,
            case_id=1,
            file_path="/videos/test.webm",
            file_size=1024,
            duration=60.0
        )
        assert info.file_path == "/videos/test.webm"
        assert info.duration == 60.0
        assert info.file_size == 1024
    
    def test_video_info_to_dict(self):
        """测试VideoInfo转字典"""
        info = VideoInfo(
            id=1,
            task_id=1,
            case_id=1,
            file_path="/videos/test.webm",
            file_size=1024,
            duration=60.0
        )
        info_dict = info.to_dict()
        assert info_dict["id"] == 1
        assert info_dict["file_size"] == 1024
        assert "file_size_human" in info_dict
    
    def test_check_ffmpeg_available(self, video_service):
        """测试ffmpeg可用性检查 - 异步方法"""
        # 使用asyncio.run运行异步方法
        result = video_service._check_ffmpeg_available()
        assert isinstance(result, bool)


# ==================== VisibilityConfigService测试 ====================

class TestVisibilityConfigService:
    """可见模式配置服务测试类"""
    
    def test_service_initialization(self, visibility_service):
        """测试服务初始化"""
        assert visibility_service is not None
        # 使用类常量而不是实例属性
        assert VisibilityConfigService.DEFAULT_GLOBAL_CONFIG is not None
    
    def test_default_config_values(self):
        """测试默认配置值 - 使用VisibilityConfig对象"""
        config = VisibilityConfigService.DEFAULT_GLOBAL_CONFIG
        assert config.headless == True  # 默认无头模式
        assert config.record_video == False
        assert config.video_resolution == (1920, 1080)
        assert config.video_fps == 30
    
    def test_get_global_config(self, visibility_service):
        """测试获取全局配置 - 返回VisibilityConfig对象"""
        config = visibility_service.get_global_config()
        # 返回的是VisibilityConfig对象，不是字典
        assert hasattr(config, "headless")
        assert hasattr(config, "record_video")
        assert hasattr(config, "video_resolution")
        # 可以转换为字典
        config_dict = config.to_dict()
        assert "headless" in config_dict
        assert "record_video" in config_dict
    
    def test_visibility_config_to_dict(self):
        """测试VisibilityConfig转字典"""
        config = VisibilityConfig(
            headless=False,
            record_video=True,
            video_resolution=(1280, 720),
            video_fps=60
        )
        config_dict = config.to_dict()
        assert config_dict["headless"] == False
        assert config_dict["record_video"] == True
        assert config_dict["video_resolution"] == (1280, 720)
        assert config_dict["video_fps"] == 60
    
    def test_visibility_config_from_dict(self):
        """测试从字典创建VisibilityConfig"""
        data = {
            "headless": False,
            "record_video": True,
            "video_resolution": [1280, 720],
            "video_fps": 60
        }
        config = VisibilityConfig.from_dict(data)
        assert config.headless == False
        assert config.record_video == True
        assert config.video_resolution == (1280, 720)
        assert config.video_fps == 60
    
    def test_visibility_level_enum(self):
        """测试VisibilityLevel枚举"""
        assert VisibilityLevel.GLOBAL == "global"
        assert VisibilityLevel.TASK == "task"
        assert VisibilityLevel.CASE == "case"


# ==================== ExecutionReplayService测试 ====================

class TestExecutionReplayService:
    """执行回放服务测试类"""
    
    def test_replay_event_creation(self):
        """测试回放事件创建"""
        event = ReplayEvent(
            timestamp=0.0,
            event_type="click",
            data={"element": "button"}
        )
        assert event.timestamp == 0.0
        assert event.event_type == "click"
    
    def test_replay_event_to_dict(self):
        """测试ReplayEvent转字典"""
        event = ReplayEvent(
            timestamp=1.5,
            event_type="input",
            data={"value": "test"}
        )
        event_dict = event.to_dict()
        assert event_dict["timestamp"] == 1.5
        assert event_dict["event_type"] == "input"
    
    def test_execution_timeline_creation(self):
        """测试执行时间线创建"""
        timeline = ExecutionTimeline(
            execution_id="test_exec_001",
            start_time=utcnow(),
            total_duration=100.0,
            events=[]
        )
        assert timeline.execution_id == "test_exec_001"
        assert timeline.total_duration == 100.0
        assert timeline.events == []
    
    def test_execution_timeline_to_dict(self):
        """测试ExecutionTimeline转字典"""
        timeline = ExecutionTimeline(
            execution_id="test_exec_001",
            start_time=utcnow(),
            total_duration=100.0,
            events=[ReplayEvent(0.0, "start", {})]
        )
        timeline_dict = timeline.to_dict()
        assert timeline_dict["execution_id"] == "test_exec_001"
        assert timeline_dict["total_duration"] == 100.0
        assert len(timeline_dict["events"]) == 1


# ==================== 集成测试 ====================

class TestTask7Integration:
    """Task 7集成测试类"""
    
    def test_video_record_workflow(self, db_session, test_task, test_case):
        """测试视频记录完整工作流"""
        # 1. 创建视频记录
        video = VideoRecord(
            id=10050,
            task_id=test_task.id,
            case_id=test_case.id,
            execution_id="workflow_test",
            file_path="/videos/workflow.webm",
            file_name="workflow.webm",
            file_size=1024000,
            duration=60.0,
            status="completed"
        )
        db_session.add(video)
        db_session.commit()
        
        # 2. 查询验证
        result = db_session.query(VideoRecord).filter(
            VideoRecord.execution_id == "workflow_test"
        ).first()
        assert result is not None
        assert result.file_size == 1024000
        
        # 3. 更新状态
        result.status = "archived"
        db_session.commit()
        
        # 4. 删除
        db_session.delete(result)
        db_session.commit()
        
        # 5. 验证删除
        deleted = db_session.query(VideoRecord).filter(
            VideoRecord.id == 10050
        ).first()
        assert deleted is None
    
    def test_services_integration(self, video_service, visibility_service):
        """测试服务间集成"""
        # 验证所有服务可以共存
        assert video_service is not None
        assert visibility_service is not None
        
        # 验证各服务配置
        config = visibility_service.get_global_config()
        assert config.headless == True  # 默认无头模式
        
        # 验证VideoService配置
        assert video_service._video_base_dir.exists()
