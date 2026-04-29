import pytest
from app.models.video_record import VideoRecord
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="vr_test_user",
        email="vr_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(VideoRecord).filter(VideoRecord.task_id.in_(
        db.query(TestTask.id).filter(TestTask.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestTask).filter(TestTask.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="视频测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_task(db, test_project, test_user):
    task = TestTask(
        task_name="视频测试任务",
        project_id=test_project.id,
        executor_id=test_user.id,
        case_ids=[]
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    yield task


@pytest.fixture
def test_case(db, test_project):
    tc = TestCase(
        case_no="TC-VR-001",
        project_id=test_project.id,
        module="模块",
        title="视频测试用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI"
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    yield tc


class TestVideoRecordModel:
    def test_create_video_record(self, db, test_task, test_case):
        vr = VideoRecord(
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/test.webm",
            file_name="test.webm",
            file_size=1024000
        )
        db.add(vr)
        db.commit()
        db.refresh(vr)
        assert vr.id is not None
        assert vr.task_id == test_task.id
        assert vr.case_id == test_case.id
        assert vr.file_path == "/videos/test.webm"
        assert vr.file_name == "test.webm"
        assert vr.file_size == 1024000
        assert vr.created_at is not None
        db.delete(vr)
        db.commit()

    def test_video_record_default_values(self, db, test_task, test_case):
        vr = VideoRecord(
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/min.webm",
            file_name="min.webm",
            file_size=0
        )
        db.add(vr)
        db.commit()
        db.refresh(vr)
        assert vr.execution_id is None
        assert vr.file_format == "webm"
        assert vr.duration is None
        assert vr.resolution == "1920x1080"
        assert vr.fps == 30
        assert vr.bitrate is None
        assert vr.thumbnail_path is None
        assert vr.status == "completed"
        assert vr.error_message is None
        db.delete(vr)
        db.commit()

    def test_video_record_status_values(self, db, test_task, test_case):
        for status in ["recording", "completed", "failed"]:
            vr = VideoRecord(
                task_id=test_task.id,
                case_id=test_case.id,
                file_path=f"/videos/{status}.webm",
                file_name=f"{status}.webm",
                file_size=1024,
                status=status
            )
            db.add(vr)
            db.commit()
            db.refresh(vr)
            assert vr.status == status
            db.delete(vr)
            db.commit()

    def test_video_record_file_size_human(self, db, test_task, test_case):
        sizes = [
            (512, "512.00 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024 * 1024 * 1024, "1.00 GB"),
        ]
        for size, expected in sizes:
            vr = VideoRecord(
                task_id=test_task.id,
                case_id=test_case.id,
                file_path="/videos/size.webm",
                file_name="size.webm",
                file_size=size
            )
            db.add(vr)
            db.commit()
            db.refresh(vr)
            assert vr.file_size_human == expected
            db.delete(vr)
            db.commit()

    def test_video_record_to_dict(self, db, test_task, test_case):
        vr = VideoRecord(
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/dict.webm",
            file_name="dict.webm",
            file_size=2048,
            duration=60.0
        )
        db.add(vr)
        db.commit()
        db.refresh(vr)
        d = vr.to_dict()
        assert d["task_id"] == test_task.id
        assert d["case_id"] == test_case.id
        assert d["file_path"] == "/videos/dict.webm"
        assert d["file_size"] == 2048
        assert d["duration"] == 60.0
        assert "created_at" in d
        db.delete(vr)
        db.commit()

    def test_video_record_with_error(self, db, test_task, test_case):
        vr = VideoRecord(
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/err.webm",
            file_name="err.webm",
            file_size=0,
            status="failed",
            error_message="录制失败：浏览器崩溃"
        )
        db.add(vr)
        db.commit()
        db.refresh(vr)
        assert vr.status == "failed"
        assert vr.error_message == "录制失败：浏览器崩溃"
        db.delete(vr)
        db.commit()

    def test_video_record_repr(self, db, test_task, test_case):
        vr = VideoRecord(
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/repr.webm",
            file_name="repr.webm",
            file_size=1024
        )
        db.add(vr)
        db.commit()
        db.refresh(vr)
        repr_str = repr(vr)
        assert "VideoRecord" in repr_str
        db.delete(vr)
        db.commit()

    def test_video_record_relationships(self):
        assert hasattr(VideoRecord, 'task')
        assert hasattr(VideoRecord, 'case')
