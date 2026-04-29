"""
Task 7 扩展单元测试 - 真实数据库交互

测试范围:
- VideoService完整CRUD操作
- VisibilityConfigService多级配置
- ExecutionReplayService会话管理
- 真实视频文件操作

注意: 使用真实MySQL数据库和真实文件系统，不使用Mock
"""
import pytest
import asyncio
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base

# 导入所有模型
from app.models import (
    User, Project, TestTask, TestCase, TestPoint,
    TestStep, TestData, TestResult, TestReport, ElementLocator,
    VideoRecord
)

from app.services.video_service import VideoService, VideoInfo
from app.services.visibility_config_service import (
    VisibilityConfigService, VisibilityConfig, VisibilityLevel
)
from app.services.execution_replay_service import (
    ExecutionReplayService, ReplayEvent, ExecutionTimeline
)


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def db_session():
    """创建测试数据库会话（真实MySQL数据库）"""
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # 清理所有测试数据
    session.query(VideoRecord).filter(VideoRecord.id >= 20000).delete()
    session.query(TestResult).filter(TestResult.id >= 20000).delete()
    session.query(TestCase).filter(TestCase.id >= 20000).delete()
    session.query(TestTask).filter(TestTask.id >= 20000).delete()
    session.query(Project).filter(Project.id >= 20000).delete()
    session.query(User).filter(User.id >= 20000).delete()
    session.commit()
    session.close()


@pytest.fixture(scope="module")
def test_user(db_session):
    """创建测试用户"""
    user = User(
        id=20000,
        username="task7_ext_user",
        email="task7_ext@example.com",
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
        id=20000,
        name="Task7扩展测试项目",
        description="用于Task7扩展测试的项目",
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
        id=20000,
        task_name="Task7扩展测试任务",
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
        id=20000,
        case_no="TASK7-EXT-001",
        project_id=test_project.id,
        module="扩展测试模块",
        title="扩展测试用例",
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
def test_result(db_session, test_task, test_case, test_project):
    """创建测试结果"""
    result = TestResult(
        id=20000,
        task_id=test_task.id,
        project_id=test_project.id,
        case_id=test_case.id,
        case_no=test_case.case_no,
        exec_status=1,  # 执行成功
        exec_time=datetime.now(),
        exec_log="测试执行成功",
        error_msg=None,
        screenshot_url=None
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    yield result


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


# ==================== VideoService 真实数据库测试 ====================

class TestVideoServiceRealDB:
    """VideoService真实数据库测试类"""
    
    @pytest.mark.asyncio
    async def test_save_video_info_real(self, db_session, video_service, test_task, test_case):
        """真实测试：保存视频信息到数据库"""
        # 创建视频信息
        video_info = VideoInfo(
            id=0,  # 数据库自增
            task_id=test_task.id,
            case_id=test_case.id,
            file_path=str(video_service._video_base_dir / "test_video.webm"),
            file_size=1024000,
            duration=60.0,
            resolution="1920x1080",
            fps=30
        )
        
        # 保存到数据库
        record = await video_service.save_video_info(db_session, video_info)
        
        # 验证
        assert record.id is not None
        assert record.task_id == test_task.id
        assert record.case_id == test_case.id
        assert record.file_size == 1024000
        assert record.status == "completed"
        
        # 清理
        db_session.delete(record)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_get_video_info_real(self, db_session, video_service, test_task, test_case):
        """真实测试：从数据库获取视频信息"""
        # 先创建记录
        video = VideoRecord(
            id=20001,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/test_get.webm",
            file_name="test_get.webm",
            file_size=2048000,
            duration=120.0,
            resolution="1280x720",
            fps=60,
            status="completed"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 获取视频信息
        video_info = await video_service.get_video_info(db_session, video.id)
        
        # 验证
        assert video_info is not None
        assert video_info.id == video.id
        assert video_info.task_id == test_task.id
        assert video_info.case_id == test_case.id
        assert video_info.file_size == 2048000
        assert video_info.duration == 120.0
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_get_video_info_not_found(self, db_session, video_service):
        """真实测试：获取不存在的视频"""
        video_info = await video_service.get_video_info(db_session, 99999)
        assert video_info is None
    
    @pytest.mark.asyncio
    async def test_get_videos_by_task_real(self, db_session, video_service, test_task, test_case):
        """真实测试：获取任务的所有视频"""
        # 创建多个视频记录
        for i in range(3):
            video = VideoRecord(
                id=20010 + i,
                task_id=test_task.id,
                case_id=test_case.id,
                file_path=f"/videos/task_video_{i}.webm",
                file_name=f"task_video_{i}.webm",
                file_size=1024 * (i + 1),
                duration=30.0 * (i + 1)
            )
            db_session.add(video)
        db_session.commit()
        
        # 获取任务视频
        videos = await video_service.get_videos_by_task(db_session, test_task.id)
        
        # 验证
        assert len(videos) == 3
        assert all(v.task_id == test_task.id for v in videos)
        
        # 清理
        for i in range(3):
            video = db_session.query(VideoRecord).filter(VideoRecord.id == 20010 + i).first()
            if video:
                db_session.delete(video)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_get_videos_by_case_real(self, db_session, video_service, test_task, test_case):
        """真实测试：获取用例的所有视频"""
        # 创建视频记录
        video = VideoRecord(
            id=20020,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/case_video.webm",
            file_name="case_video.webm",
            file_size=512000
        )
        db_session.add(video)
        db_session.commit()
        
        # 获取用例视频
        videos = await video_service.get_videos_by_case(db_session, test_case.id)
        
        # 验证
        assert len(videos) >= 1
        assert any(v.case_id == test_case.id for v in videos)
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_delete_video_real(self, db_session, video_service, test_task, test_case):
        """真实测试：删除视频"""
        # 创建视频文件
        video_file = video_service._video_base_dir / "delete_test.webm"
        video_file.write_bytes(b"test video content")
        
        # 创建数据库记录
        video = VideoRecord(
            id=20030,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path=str(video_file),
            file_name="delete_test.webm",
            file_size=video_file.stat().st_size
        )
        db_session.add(video)
        db_session.commit()
        
        # 删除视频
        result = await video_service.delete_video(db_session, video.id)
        
        # 验证
        assert result is True
        assert not video_file.exists()  # 文件已删除
        deleted_record = db_session.query(VideoRecord).filter(VideoRecord.id == 20030).first()
        assert deleted_record is None  # 记录已删除
    
    @pytest.mark.asyncio
    async def test_delete_video_not_found(self, db_session, video_service):
        """真实测试：删除不存在的视频"""
        result = await video_service.delete_video(db_session, 99999)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_storage_stats_real(self, video_service):
        """真实测试：获取存储统计"""
        # 创建测试视频文件
        for i in range(3):
            video_file = video_service._video_base_dir / f"stats_test_{i}.webm"
            video_file.write_bytes(b"x" * 1024)  # 1KB each
        
        # 获取统计
        stats = await video_service.get_storage_stats()
        
        # 验证
        assert stats["total_videos"] == 3
        assert stats["total_size_bytes"] == 3072
        assert stats["total_size_gb"] >= 0  # 可能为0因为文件太小
        assert "video_directory" in stats
        assert "retention_days" in stats


# ==================== VisibilityConfigService 多级配置测试 ====================

class TestVisibilityConfigLevels:
    """VisibilityConfigService多级配置测试类"""
    
    def test_set_and_get_global_config(self, visibility_service):
        """测试设置和获取全局配置"""
        # 创建新配置
        new_config = VisibilityConfig(
            headless=False,  # 可见模式
            record_video=True,
            video_resolution=(1280, 720),
            video_fps=60
        )
        
        # 设置全局配置
        visibility_service.set_global_config(new_config)
        
        # 获取并验证
        config = visibility_service.get_global_config()
        assert config.headless == False
        assert config.record_video == True
        assert config.video_resolution == (1280, 720)
        assert config.video_fps == 60
    
    def test_global_config_from_env(self, monkeypatch):
        """测试从环境变量加载全局配置"""
        # 设置环境变量
        monkeypatch.setenv("TEST_HEADLESS", "false")
        monkeypatch.setenv("TEST_RECORD_VIDEO", "true")
        monkeypatch.setenv("TEST_VIDEO_WIDTH", "1920")
        monkeypatch.setenv("TEST_VIDEO_HEIGHT", "1080")
        monkeypatch.setenv("TEST_VIDEO_FPS", "60")
        
        # 创建新服务实例（会读取环境变量）
        service = VisibilityConfigService()
        config = service.get_global_config()
        
        # 验证
        assert config.headless == False
        assert config.record_video == True
        assert config.video_resolution == (1920, 1080)
        assert config.video_fps == 60
    
    def test_config_speed_values(self, visibility_service):
        """测试配置速度值"""
        config = VisibilityConfig()
        
        # 测试速度配置
        config.execution_speed = "slow"
        assert config.execution_speed == "slow"
        
        config.execution_speed = "normal"
        assert config.execution_speed == "normal"
        
        config.execution_speed = "fast"
        assert config.execution_speed == "fast"
    
    def test_config_screenshot_options(self, visibility_service):
        """测试截图配置选项"""
        config = VisibilityConfig()
        
        # 默认配置
        assert config.take_screenshot == True
        assert config.screenshot_on_failure == True
        assert config.screenshot_on_success == False
        
        # 修改配置
        config.take_screenshot = False
        config.screenshot_on_failure = False
        config.screenshot_on_success = True
        
        assert config.take_screenshot == False
        assert config.screenshot_on_failure == False
        assert config.screenshot_on_success == True


# ==================== ExecutionReplayService 会话管理测试 ====================

class TestExecutionReplaySessions:
    """ExecutionReplayService会话管理测试类"""
    
    @pytest.fixture
    def event_loop(self):
        """创建新的事件循环"""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()
    
    @pytest.mark.asyncio
    async def test_create_replay_session(self, db_session, test_task, test_case, test_result):
        """测试创建回放会话 - 使用正确的API"""
        service = ExecutionReplayService()
        
        # 创建会话 - 使用execution_id作为第一个参数
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240101_120000"
        session_info = await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        
        # 验证
        assert session_info is not None
        assert session_info["execution_id"] == execution_id
        assert "total_duration" in session_info
        
        # 清理
        await service.close_replay_session(execution_id)
    
    @pytest.mark.asyncio
    async def test_get_replay_status(self, db_session, test_task, test_case, test_result):
        """测试获取回放状态"""
        service = ExecutionReplayService()
        
        # 创建会话
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240102_120000"
        await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        
        # 获取状态 - 使用await因为get_replay_status是async方法
        status = await service.get_replay_status(execution_id)
        
        # 验证
        assert status is not None
        assert "is_playing" in status
        assert status["is_playing"] == False
        
        # 清理
        await service.close_replay_session(execution_id)
    
    @pytest.mark.asyncio
    async def test_start_and_stop_replay(self, db_session, test_task, test_case, test_result):
        """测试开始和停止回放"""
        service = ExecutionReplayService()
        
        # 创建会话
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240103_120000"
        await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        
        # 开始回放
        result = await service.start_replay(execution_id)
        assert result is True
        
        # 验证状态
        status = await service.get_replay_status(execution_id)
        assert status["is_playing"] == True
        
        # 停止回放
        result = await service.stop_replay(execution_id)
        assert result is True
        
        # 验证状态
        status = await service.get_replay_status(execution_id)
        assert status["is_playing"] == False
        assert status["current_time"] == 0.0
        
        # 清理
        await service.close_replay_session(execution_id)
    
    @pytest.mark.asyncio
    async def test_pause_and_resume_replay(self, db_session, test_task, test_case, test_result):
        """测试暂停和恢复回放"""
        service = ExecutionReplayService()
        
        # 创建会话并开始回放
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240104_120000"
        await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        await service.start_replay(execution_id)
        
        # 暂停
        result = await service.pause_replay(execution_id)
        assert result is True
        
        status = await service.get_replay_status(execution_id)
        assert status["is_playing"] == False
        
        # 恢复
        result = await service.resume_replay(execution_id)
        assert result is True
        
        status = await service.get_replay_status(execution_id)
        assert status["is_playing"] == True
        
        # 清理
        await service.stop_replay(execution_id)
        await service.close_replay_session(execution_id)
    
    @pytest.mark.asyncio
    async def test_seek_to_timestamp(self, db_session, test_task, test_case, test_result):
        """测试跳转到指定时间戳"""
        service = ExecutionReplayService()
        
        # 创建会话
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240105_120000"
        await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        
        # 跳转到0.5秒（在范围内）
        result = await service.seek_to(execution_id, 0.5)
        assert result is True
        
        # 验证位置
        status = await service.get_replay_status(execution_id)
        assert status["current_time"] == 0.5
        
        # 清理
        await service.close_replay_session(execution_id)
    
    @pytest.mark.asyncio
    async def test_set_playback_speed(self, db_session, test_task, test_case, test_result):
        """测试设置播放速度 - 使用set_default_speed方法"""
        service = ExecutionReplayService()
        
        # 创建会话
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240106_120000"
        await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        
        # 设置默认速度
        service.set_default_speed(2.0)
        
        # 验证速度设置
        assert service._replay_speed == 2.0
        
        # 清理
        await service.close_replay_session(execution_id)
    
    @pytest.mark.asyncio
    async def test_close_session(self, db_session, test_task, test_case, test_result):
        """测试关闭会话"""
        service = ExecutionReplayService()
        
        # 创建会话
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240107_120000"
        await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        
        # 验证会话存在
        status = await service.get_replay_status(execution_id)
        assert status is not None
        
        # 关闭会话
        result = await service.close_replay_session(execution_id)
        assert result is True
        
        # 验证会话已关闭
        status = await service.get_replay_status(execution_id)
        assert status is None
    
    @pytest.mark.asyncio
    async def test_get_events_in_range(self, db_session, test_task, test_case, test_result):
        """测试获取时间范围内的事件"""
        service = ExecutionReplayService()
        
        # 创建会话
        execution_id = f"task_{test_task.id}_case_{test_case.id}_20240108_120000"
        await service.create_replay_session(
            db=db_session,
            execution_id=execution_id
        )
        
        # 获取时间范围内的事件
        events = await service.get_events_in_range(execution_id, 0.0, 10.0)
        assert isinstance(events, list)
        
        # 清理
        await service.close_replay_session(execution_id)


# ==================== 端到端集成测试 ====================

class TestEndToEndWorkflow:
    """端到端工作流测试类"""
    
    @pytest.mark.asyncio
    async def test_full_video_workflow(self, db_session, video_service, test_task, test_case):
        """完整视频工作流测试：创建->查询->删除"""
        # 1. 创建视频文件
        video_file = video_service._video_base_dir / "e2e_test.webm"
        video_file.write_bytes(b"x" * 10240)  # 10KB
        
        # 2. 保存视频信息
        video_info = VideoInfo(
            id=0,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path=str(video_file),
            file_size=video_file.stat().st_size,
            duration=30.0,
            resolution="1920x1080",
            fps=30
        )
        record = await video_service.save_video_info(db_session, video_info)
        assert record.id is not None
        
        # 3. 查询视频
        retrieved = await video_service.get_video_info(db_session, record.id)
        assert retrieved is not None
        assert retrieved.file_size == 10240
        
        # 4. 获取任务视频列表
        task_videos = await video_service.get_videos_by_task(db_session, test_task.id)
        assert any(v.id == record.id for v in task_videos)
        
        # 5. 删除视频
        result = await video_service.delete_video(db_session, record.id)
        assert result is True
        
        # 6. 验证删除
        deleted = await video_service.get_video_info(db_session, record.id)
        assert deleted is None
        assert not video_file.exists()
    
    @pytest.mark.asyncio
    async def test_visibility_config_workflow(self, visibility_service):
        """可见模式配置工作流测试"""
        # 1. 获取默认配置
        default_config = VisibilityConfigService.DEFAULT_GLOBAL_CONFIG
        assert default_config.headless == True
        
        # 2. 设置自定义配置
        custom_config = VisibilityConfig(
            headless=False,
            record_video=True,
            video_resolution=(2560, 1440),
            video_fps=60,
            execution_speed="slow"
        )
        visibility_service.set_global_config(custom_config)
        
        # 3. 验证配置已更新
        current_config = visibility_service.get_global_config()
        assert current_config.headless == False
        assert current_config.record_video == True
        assert current_config.video_resolution == (2560, 1440)
        assert current_config.execution_speed == "slow"
        
        # 4. 转换为字典
        config_dict = current_config.to_dict()
        assert config_dict["headless"] == False
        assert config_dict["record_video"] == True
    
    @pytest.mark.asyncio
    async def test_replay_session_workflow(self, db_session, test_task, test_case, test_result):
        """回放会话工作流测试"""
        service = ExecutionReplayService()
        execution_id = f"task_{test_task.id}_case_{test_case.id}_e2e_20240109_120000"
        
        try:
            # 1. 创建会话
            session_info = await service.create_replay_session(
                db=db_session,
                execution_id=execution_id
            )
            assert session_info is not None
            
            # 2. 开始回放
            result = await service.start_replay(execution_id)
            assert result is True
            
            # 3. 暂停
            result = await service.pause_replay(execution_id)
            assert result is True
            
            # 4. 跳转
            result = await service.seek_to(execution_id, 5.0)
            assert result is True
            
            # 5. 设置速度
            service.set_default_speed(1.5)
            
            # 6. 恢复回放
            result = await service.resume_replay(execution_id)
            assert result is True
            
            # 7. 停止回放
            result = await service.stop_replay(execution_id)
            assert result is True
            
            # 8. 获取最终状态
            status = await service.get_replay_status(execution_id)
            assert status is not None
            assert status["current_time"] == 0.0  # stop会重置时间
            
        finally:
            # 清理
            await service.close_replay_session(execution_id)
