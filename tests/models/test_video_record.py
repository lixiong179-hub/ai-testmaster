"""
VideoRecord模型单元测试

测试范围:
- VideoRecord模型创建和属�?
- 数据库CRUD操作
- 关联关系
- 方法功能

设计原则:
1. 使用共享 db fixture，自动事务隔离（commit 降级�?flush�?
2. 不硬编码 id，让数据库自动生�?
"""
import pytest
import time
from datetime import datetime
from sqlalchemy import select

from app.models import (
    User, Project, TestTask, TestCase, TestPoint,
    TestStep, TestData, TestResult, TestReport, ElementLocator,
    VideoRecord
)


@pytest.fixture(scope="function")
def video_test_user(db):
    """创建测试用户 - 不硬编码 id"""
    suffix = str(int(time.time() * 1000))[-6:]
    user = User(
        username=f"vrec_user_{suffix}",
        email=f"vrec_{suffix}@test.com",
        password_hash="test_hash",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user


@pytest.fixture(scope="function")
def video_test_project(db, video_test_user):
    """创建测试项目"""
    project = Project(
        name=f"视频测试项目_{video_test_user.id}",
        description="用于视频记录测试的项�?,
        user_id=video_test_user.id,
        status=1,
        project_type="web",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture(scope="function")
def video_test_task(db, video_test_project, video_test_user):
    """创建测试任务"""
    task = TestTask(
        task_name="视频测试任务",
        project_id=video_test_project.id,
        executor_id=video_test_user.id,
        case_ids=[],
        total_count=1,
        status=0,
        success_count=0,
        fail_count=0,
        progress=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    yield task


@pytest.fixture(scope="function")
def video_test_case(db, video_test_project):
    """创建测试用例"""
    case = TestCase(
        case_no="VIDEO-001",
        project_id=video_test_project.id,
        module="视频测试模块",
        title="视频测试用例",
        precondition="前置条件",
        steps_json=[],
        expected_result="预期结果",
        priority=2,
        case_type="UI",
        generate_status=0,
        review_status="pending",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    yield case


class TestVideoRecordModel:
    """VideoRecord模型测试�?""

    def test_video_record_creation(self, db, video_test_task, video_test_case):
        """测试VideoRecord创建"""
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            execution_id="task_1_case_1_20240101_120000",
            file_path="/videos/test_video.webm",
            file_name="test_video.webm",
            file_size=1024000,
            file_format="webm",
            duration=120.5,
            resolution="1920x1080",
            fps=30,
            bitrate=5000000,
            thumbnail_path="/thumbnails/test_video.jpg",
            status="completed",
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        assert video.id is not None
        assert video.task_id == video_test_task.id
        assert video.case_id == video_test_case.id
        assert video.execution_id == "task_1_case_1_20240101_120000"
        assert video.file_path == "/videos/test_video.webm"
        assert video.file_size == 1024000
        assert video.duration == 120.5
        assert video.resolution == "1920x1080"
        assert video.fps == 30
        assert video.status == "completed"
        assert video.created_at is not None

    def test_video_record_to_dict(self, db, video_test_task, video_test_case):
        """测试to_dict方法"""
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            file_path="/videos/test.webm",
            file_name="test.webm",
            file_size=2048000,
            duration=60.0,
            resolution="1280x720",
            fps=30,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        video_dict = video.to_dict()
        assert video_dict["id"] == video.id
        assert video_dict["task_id"] == video_test_task.id
        assert video_dict["case_id"] == video_test_case.id
        assert video_dict["file_path"] == "/videos/test.webm"
        assert video_dict["file_size"] == 2048000
        assert video_dict["duration"] == 60.0
        assert video_dict["resolution"] == "1280x720"
        assert "created_at" in video_dict

    def test_video_record_file_size_human(self, db, video_test_task, video_test_case):
        """测试file_size_human属�?""
        test_sizes = [
            (512, "512.00 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024 * 1024 * 1024, "1.00 GB"),
        ]

        for size, expected in test_sizes:
            video = VideoRecord(
                task_id=video_test_task.id,
                case_id=video_test_case.id,
                file_path="/videos/test.webm",
                file_name="test.webm",
                file_size=size,
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            assert video.file_size_human == expected, f"Size {size} should be {expected}"

    def test_video_record_status_values(self, db, video_test_task, video_test_case):
        """测试不同状态�?""
        statuses = ["recording", "completed", "failed"]
        for status in statuses:
            video = VideoRecord(
                task_id=video_test_task.id,
                case_id=video_test_case.id,
                file_path=f"/videos/test_{status}.webm",
                file_name=f"test_{status}.webm",
                file_size=1024,
                status=status,
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            assert video.status == status

    def test_video_record_update(self, db, video_test_task, video_test_case):
        """测试视频记录更新"""
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            file_path="/videos/original.webm",
            file_name="original.webm",
            file_size=1024,
            status="recording",
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        video.file_path = "/videos/updated.webm"
        video.file_name = "updated.webm"
        video.file_size = 2048
        video.duration = 30.0
        video.status = "completed"
        db.commit()
        db.refresh(video)

        assert video.file_path == "/videos/updated.webm"
        assert video.file_name == "updated.webm"
        assert video.file_size == 2048
        assert video.duration == 30.0
        assert video.status == "completed"

    def test_video_record_query_by_task(self, db, video_test_task, video_test_case):
        """测试按任务查�?""
        for i in range(3):
            video = VideoRecord(
                task_id=video_test_task.id,
                case_id=video_test_case.id,
                file_path=f"/videos/task_video_{i}.webm",
                file_name=f"task_video_{i}.webm",
                file_size=1024 * (i + 1),
            )
            db.add(video)
        db.commit()

        videos = db.query(VideoRecord).filter(
            VideoRecord.task_id == video_test_task.id
        ).all()
        assert len(videos) == 3

    def test_video_record_query_by_case(self, db, video_test_task, video_test_case):
        """测试按用例查�?""
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            file_path="/videos/case_video.webm",
            file_name="case_video.webm",
            file_size=1024,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        result = db.query(VideoRecord).filter(
            VideoRecord.case_id == video_test_case.id
        ).first()
        assert result is not None
        assert result.file_name == "case_video.webm"

    def test_video_record_query_by_execution_id(self, db, video_test_task, video_test_case):
        """测试按执行ID查询"""
        execution_id = "task_1_case_1_20240101_120000"
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            execution_id=execution_id,
            file_path="/videos/exec_video.webm",
            file_name="exec_video.webm",
            file_size=1024,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        result = db.query(VideoRecord).filter(
            VideoRecord.execution_id == execution_id
        ).first()
        assert result is not None
        assert result.execution_id == execution_id

    def test_video_record_delete(self, db, video_test_task, video_test_case):
        """测试视频记录删除"""
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            file_path="/videos/delete_test.webm",
            file_name="delete_test.webm",
            file_size=1024,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        video_id = video.id

        db.delete(video)
        db.commit()

        result = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
        assert result is None

    def test_video_record_error_message(self, db, video_test_task, video_test_case):
        """测试错误信息字段"""
        error_msg = "录制失败：浏览器崩溃"
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            file_path="/videos/error.webm",
            file_name="error.webm",
            file_size=0,
            status="failed",
            error_message=error_msg,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        assert video.error_message == error_msg
        assert video.status == "failed"

    def test_video_record_optional_fields(self, db, video_test_task, video_test_case):
        """测试可选字�?""
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            file_path="/videos/minimal.webm",
            file_name="minimal.webm",
            file_size=1024,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        assert video.execution_id is None
        assert video.duration is None
        assert video.bitrate is None
        assert video.thumbnail_path is None
        # __init__ 已修复：Python 实例化时 status 正确设为 "completed"
        assert video.status == "completed"

    def test_video_record_timestamps(self, db, video_test_task, video_test_case):
        """测试时间戳字�?""
        video = VideoRecord(
            task_id=video_test_task.id,
            case_id=video_test_case.id,
            file_path="/videos/timestamp.webm",
            file_name="timestamp.webm",
            file_size=1024,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        assert video.created_at is not None
        assert video.updated_at is not None
        assert isinstance(video.created_at, datetime)
        assert isinstance(video.updated_at, datetime)
