"""
VideoRecord模型单元测试

测试范围:
- VideoRecord模型创建和属性
- 数据库CRUD操作
- 关联关系
- 方法功能

注意: 使用真实MySQL数据库，不使用Mock
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base

# 导入所有模型以确保SQLAlchemy关系正确
from app.models import (
    User, Project, TestTask, TestCase, TestPoint,
    TestStep, TestData, TestResult, TestReport, ElementLocator,
    VideoRecord
)


@pytest.fixture(scope="function")
def db_session():
    """创建测试数据库会话（真实MySQL数据库）"""
    engine = create_engine(settings.DATABASE_URL)
    # 创建所有表
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # 清理所有测试数据
    session.rollback()
    session.query(VideoRecord).filter(VideoRecord.id >= 10000).delete()
    session.query(TestCase).filter(TestCase.id >= 10000).delete()
    session.query(TestTask).filter(TestTask.id >= 10000).delete()
    session.query(Project).filter(Project.id >= 10000).delete()
    session.query(User).filter(User.id >= 10000).delete()
    session.commit()
    session.close()


@pytest.fixture(scope="function")
def test_project(db_session):
    """创建测试项目"""
    # 先创建测试用户
    user = User(
        id=10000,
        username="video_test_user",
        email="video_test@example.com",
        password_hash="test_hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    project = Project(
        id=10000,
        name="视频测试项目",
        description="用于视频记录测试的项目",
        user_id=user.id
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    yield project


@pytest.fixture(scope="function")
def test_task(db_session, test_project):
    """创建测试任务"""
    # 获取测试用户
    user = db_session.query(User).filter(User.id == 10000).first()
    
    task = TestTask(
        id=10000,
        task_name="视频测试任务",
        project_id=test_project.id,
        executor_id=user.id,
        case_ids=[],
        total_count=1,
        status=0,
        success_count=0,
        fail_count=0,
        progress=0
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    yield task


@pytest.fixture(scope="function")
def test_case(db_session, test_project):
    """创建测试用例"""
    case = TestCase(
        id=10000,
        case_no="VIDEO-001",
        project_id=test_project.id,
        module="视频测试模块",
        title="视频测试用例",
        precondition="前置条件",
        steps_json=[],
        expected_result="预期结果",
        priority=2,
        case_type="UI",
        generate_status=0,
        review_status="pending"
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    yield case


class TestVideoRecordModel:
    """VideoRecord模型测试类"""
    
    def test_video_record_creation(self, db_session, test_task, test_case):
        """测试VideoRecord创建"""
        # 创建视频记录
        video = VideoRecord(
            id=10000,
            task_id=test_task.id,
            case_id=test_case.id,
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
            status="completed"
        )
        
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 验证
        assert video.id is not None
        assert video.task_id == test_task.id
        assert video.case_id == test_case.id
        assert video.execution_id == "task_1_case_1_20240101_120000"
        assert video.file_path == "/videos/test_video.webm"
        assert video.file_size == 1024000
        assert video.duration == 120.5
        assert video.resolution == "1920x1080"
        assert video.fps == 30
        assert video.status == "completed"
        assert video.created_at is not None
        
        # 清理
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
            file_size=2048000,
            duration=60.0,
            resolution="1280x720",
            fps=30
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 转换为字典
        video_dict = video.to_dict()
        
        # 验证
        assert video_dict["id"] == video.id
        assert video_dict["task_id"] == test_task.id
        assert video_dict["case_id"] == test_case.id
        assert video_dict["file_path"] == "/videos/test.webm"
        assert video_dict["file_size"] == 2048000
        assert video_dict["duration"] == 60.0
        assert video_dict["resolution"] == "1280x720"
        assert "created_at" in video_dict
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_file_size_human(self, db_session, test_task, test_case):
        """测试file_size_human属性"""
        # 测试不同大小的文件
        test_sizes = [
            (512, "512.00 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024 * 1024 * 1024, "1.00 GB"),
        ]
        
        for idx, (size, expected) in enumerate(test_sizes):
            video = VideoRecord(
                id=10002 + idx,
                task_id=test_task.id,
                case_id=test_case.id,
                file_path="/videos/test.webm",
                file_name="test.webm",
                file_size=size
            )
            db_session.add(video)
            db_session.commit()
            db_session.refresh(video)
            
            assert video.file_size_human == expected, f"Size {size} should be {expected}"
            
            db_session.delete(video)
            db_session.commit()
    
    def test_video_record_status_values(self, db_session, test_task, test_case):
        """测试不同状态值"""
        statuses = ["recording", "completed", "failed"]
        
        for idx, status in enumerate(statuses):
            video = VideoRecord(
                id=10010 + idx,
                task_id=test_task.id,
                case_id=test_case.id,
                file_path=f"/videos/test_{status}.webm",
                file_name=f"test_{status}.webm",
                file_size=1024,
                status=status
            )
            db_session.add(video)
            db_session.commit()
            db_session.refresh(video)
            
            assert video.status == status
            
            db_session.delete(video)
            db_session.commit()
    
    def test_video_record_update(self, db_session, test_task, test_case):
        """测试视频记录更新"""
        video = VideoRecord(
            id=10020,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/original.webm",
            file_name="original.webm",
            file_size=1024,
            status="recording"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 更新字段
        video.file_path = "/videos/updated.webm"
        video.file_name = "updated.webm"
        video.file_size = 2048
        video.duration = 30.0
        video.status = "completed"
        
        db_session.commit()
        db_session.refresh(video)
        
        # 验证更新
        assert video.file_path == "/videos/updated.webm"
        assert video.file_name == "updated.webm"
        assert video.file_size == 2048
        assert video.duration == 30.0
        assert video.status == "completed"
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_query_by_task(self, db_session, test_task, test_case):
        """测试按任务查询"""
        # 创建多个视频记录
        for i in range(3):
            video = VideoRecord(
                id=10030 + i,
                task_id=test_task.id,
                case_id=test_case.id,
                file_path=f"/videos/task_video_{i}.webm",
                file_name=f"task_video_{i}.webm",
                file_size=1024 * (i + 1)
            )
            db_session.add(video)
        db_session.commit()
        
        # 查询
        videos = db_session.query(VideoRecord).filter(
            VideoRecord.task_id == test_task.id
        ).all()
        
        assert len(videos) == 3
        
        # 清理
        for video in videos:
            db_session.delete(video)
        db_session.commit()
    
    def test_video_record_query_by_case(self, db_session, test_task, test_case):
        """测试按用例查询"""
        # 创建视频记录
        video = VideoRecord(
            id=10040,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/case_video.webm",
            file_name="case_video.webm",
            file_size=1024
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 查询
        result = db_session.query(VideoRecord).filter(
            VideoRecord.case_id == test_case.id
        ).first()
        
        assert result is not None
        assert result.file_name == "case_video.webm"
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_query_by_execution_id(self, db_session, test_task, test_case):
        """测试按执行ID查询"""
        execution_id = "task_1_case_1_20240101_120000"
        
        video = VideoRecord(
            id=10050,
            task_id=test_task.id,
            case_id=test_case.id,
            execution_id=execution_id,
            file_path="/videos/exec_video.webm",
            file_name="exec_video.webm",
            file_size=1024
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 查询
        result = db_session.query(VideoRecord).filter(
            VideoRecord.execution_id == execution_id
        ).first()
        
        assert result is not None
        assert result.execution_id == execution_id
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_delete(self, db_session, test_task, test_case):
        """测试视频记录删除"""
        video = VideoRecord(
            id=10060,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/delete_test.webm",
            file_name="delete_test.webm",
            file_size=1024
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        video_id = video.id
        
        # 删除
        db_session.delete(video)
        db_session.commit()
        
        # 验证删除
        result = db_session.query(VideoRecord).filter(VideoRecord.id == video_id).first()
        assert result is None
    
    def test_video_record_error_message(self, db_session, test_task, test_case):
        """测试错误信息字段"""
        error_msg = "录制失败：浏览器崩溃"
        
        video = VideoRecord(
            id=10070,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/error.webm",
            file_name="error.webm",
            file_size=0,
            status="failed",
            error_message=error_msg
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        assert video.error_message == error_msg
        assert video.status == "failed"
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_optional_fields(self, db_session, test_task, test_case):
        """测试可选字段"""
        # 只设置必填字段
        video = VideoRecord(
            id=10080,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/minimal.webm",
            file_name="minimal.webm",
            file_size=1024
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 验证可选字段有默认值
        assert video.execution_id is None
        assert video.duration is None
        assert video.bitrate is None
        assert video.thumbnail_path is None
        assert video.status == "completed"  # 默认值
        
        # 清理
        db_session.delete(video)
        db_session.commit()
    
    def test_video_record_timestamps(self, db_session, test_task, test_case):
        """测试时间戳字段"""
        video = VideoRecord(
            id=10090,
            task_id=test_task.id,
            case_id=test_case.id,
            file_path="/videos/timestamp.webm",
            file_name="timestamp.webm",
            file_size=1024
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        
        # 验证时间戳
        assert video.created_at is not None
        assert video.updated_at is not None
        assert isinstance(video.created_at, datetime)
        assert isinstance(video.updated_at, datetime)
        
        # 清理
        db_session.delete(video)
        db_session.commit()
