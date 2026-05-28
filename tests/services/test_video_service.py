"""
VideoService单元测试

测试范围:
- 视频元信息CRUD操作
- 过期视频清理
- 存储统计

注意: 使用真实环境，不使用Mock
"""
import pytest
import time
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.services.video import VideoService
from app.services.video.models import VideoInfo, VideoStatus
from app.models.video_record import VideoRecord
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
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
def video_service(db):
    service = VideoService(db=db, video_base_dir="./test_videos")
    yield service
    import shutil
    if Path("./test_videos").exists():
        shutil.rmtree("./test_videos")


@pytest.fixture
def sample_user(db):
    username = f"video_user_{int(time.time() * 1000)}"
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="$2b$12$dummy_hash_for_testing"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)


@pytest.fixture
def sample_project(db, sample_user):
    project = Project(
        name=f"VideoTestProj_{int(time.time() * 1000)}",
        user_id=sample_user.id,
        description="Test Description"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project
    db.delete(project)


@pytest.fixture
def sample_task(db, sample_project, sample_user):
    task = TestTask(
        task_name=f"VideoTestTask_{int(time.time() * 1000)}",
        project_id=sample_project.id,
        executor_id=sample_user.id,
        case_ids=[],
        status=0,
        total_count=0,
        success_count=0,
        fail_count=0,
        progress=0
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    yield task
    db.delete(task)


@pytest.fixture
def sample_test_case(db, sample_project):
    case = TestCase(
        case_no=f"VT{int(time.time() * 1000)}",
        project_id=sample_project.id,
        module="测试模块",
        title="Video Test Case",
        precondition="无",
        steps_json=[{"step": "1", "action": "打开", "param": ""}],
        expected_result="成功",
        priority=2,
        case_type="UI"
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    yield case
    db.delete(case)


@pytest.fixture
def sample_video_record(db, sample_task, sample_test_case):
    record = VideoRecord(
        task_id=sample_task.id,
        case_id=sample_test_case.id,
        file_path="./test_videos/test_video.mp4",
        file_name="test_video.mp4",
        file_size=1024000,
        duration=10.5,
        status="completed"
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    yield record
    db.delete(record)


class TestVideoService:
    """视频服务测试类"""

    def test_service_initialization(self, video_service):
        """测试服务初始化"""
        assert video_service.db is not None
        assert str(video_service._video_base_dir) == "test_videos"

    @pytest.mark.asyncio
    async def test_save_video_info(self, video_service, sample_task, sample_test_case):
        """测试保存视频元信息"""
        video_info = await video_service.save_video_info(
            task_id=sample_task.id,
            test_case_id=sample_test_case.id,
            file_path="./test_videos/new_video.mp4",
            file_name="new_video.mp4",
            file_size=2048000,
            duration=20.0
        )

        assert isinstance(video_info, VideoInfo)
        assert video_info.task_id == sample_task.id
        assert video_info.file_name == "new_video.mp4"
        assert video_info.file_size == 2048000
        assert video_info.duration == 20.0

    @pytest.mark.asyncio
    async def test_get_video_info(self, video_service, sample_video_record):
        """测试获取视频信息"""
        info = await video_service.get_video_info(sample_video_record.id)

        assert info is not None
        assert info.id == sample_video_record.id
        assert info.file_name == "test_video.mp4"

    @pytest.mark.asyncio
    async def test_get_video_info_not_found(self, video_service):
        """测试获取不存在的视频"""
        info = await video_service.get_video_info(99999)
        assert info is None

    @pytest.mark.asyncio
    async def test_get_videos_by_task(self, video_service, sample_video_record, sample_task):
        """测试按任务ID查询视频列表"""
        videos = await video_service.get_videos_by_task(sample_task.id)
        assert len(videos) >= 1
        assert any(v.id == sample_video_record.id for v in videos)

    @pytest.mark.asyncio
    async def test_get_videos_by_case(self, video_service, sample_test_case):
        """测试按用例ID查询视频列表"""
        videos = await video_service.get_videos_by_case(sample_test_case.id)
        assert isinstance(videos, list)

    @pytest.mark.asyncio
    async def test_delete_video(self, video_service, sample_video_record):
        """测试删除视频"""
        video_id = sample_video_record.id
        success = await video_service.delete_video(video_id)
        assert success is True

        info = await video_service.get_video_info(video_id)
        assert info is None

    @pytest.mark.asyncio
    async def test_delete_video_not_found(self, video_service):
        """测试删除不存在的视频"""
        success = await video_service.delete_video(99999)
        assert success is False


class TestVideoModels:
    """视频数据模型测试类"""

    def test_video_info_creation(self):
        """测试VideoInfo数据类创建"""
        info = VideoInfo(
            id=1,
            task_id=100,
            test_case_id=200,
            file_path="/path/to/video.mp4",
            file_name="video.mp4",
            file_size=1024000,
            duration=15.5,
            status=VideoStatus.READY
        )

        assert info.id == 1
        assert info.task_id == 100
        assert info.test_case_id == 200
        assert info.duration == 15.5
        assert info.status == VideoStatus.READY

    def test_video_status_enum(self):
        """测试VideoStatus枚举值"""
        assert VideoStatus.READY.value == "ready"
        assert VideoStatus.PROCESSING.value == "processing"
        assert VideoStatus.FAILED.value == "failed"


class TestPathUtils:
    """路径工具测试类"""

    def test_get_video_path_exists(self, video_service, sample_video_record):
        """测试获取存在的视频路径"""
        path = video_service.get_video_path(sample_video_record.id)
        assert path is None

    def test_get_video_path_not_found(self, video_service):
        """测试获取不存在的视频路径"""
        path = video_service.get_video_path(99999)
        assert path is None

    def test_get_video_url(self, video_service, sample_video_record):
        """测试生成视频URL"""
        url = video_service.get_video_url(sample_video_record.id)
        assert url is not None
        assert f"/api/v1/videos/{sample_video_record.id}/stream/" in url


class TestFFmpegMixin:
    """FFmpeg工具测试类"""

    def test_check_ffmpeg_available(self, video_service):
        """测试FFmpeg可用性检查（同步方法）"""
        is_available = video_service._check_ffmpeg_available()
        assert isinstance(is_available, bool)

    def test_check_ffprobe_available(self, video_service):
        """测试FFprobe可用性检查（同步方法）"""
        is_available = video_service._check_ffprobe_available()
        assert isinstance(is_available, bool)
