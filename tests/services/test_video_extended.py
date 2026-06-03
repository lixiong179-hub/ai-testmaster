import os
import time
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.services.video.models import VideoInfo, VideoStatus, VideoRecordStatus
from app.services.video.ffmpeg_mixin import FFmpegMixin
from app.services.video.cleanup_mixin import CleanupMixin
from app.services.video.crud_mixin import CRUDMixin
from app.services.video.path_utils_mixin import PathUtilsMixin
from app.models.video_record import VideoRecord
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


def _create_parent_records(db):
    ts = int(time.time() * 1000)
    user = User(
        username=f"vid_ext_{ts}",
        email=f"vid_ext_{ts}@test.com",
        password_hash="$2b$12$dummy_hash_for_testing",
    )
    db.add(user)
    db.flush()
    project = Project(
        name=f"vid_ext_proj_{ts}",
        user_id=user.id,
        description="test",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    task = TestTask(
        task_name=f"vid_ext_task_{ts}",
        project_id=project.id,
        executor_id=user.id,
        case_ids=[],
        status=0,
        total_count=0,
        success_count=0,
        fail_count=0,
        progress=0,
    )
    db.add(task)
    db.flush()
    case = TestCase(
        case_no=f"VE{ts}",
        project_id=project.id,
        module="测试模块",
        title="Video Ext Test Case",
        precondition="无",
        steps_json=[{"step": "1", "action": "打开", "param": ""}],
        expected_result="成功",
        priority=2,
        case_type="UI",
    )
    db.add(case)
    db.flush()
    return task.id, case.id


class TestVideoStatus:
    def test_values(self):
        assert VideoStatus.PROCESSING == "processing"
        assert VideoStatus.READY == "ready"
        assert VideoStatus.FAILED == "failed"
        assert VideoStatus.EXPIRED == "expired"


class TestVideoRecordStatus:
    def test_values(self):
        assert VideoRecordStatus.PENDING == "pending"
        assert VideoRecordStatus.RECORDING == "recording"
        assert VideoRecordStatus.COMPLETED == "completed"
        assert VideoRecordStatus.FAILED == "failed"


class TestVideoInfoModel:
    def test_to_dict(self):
        info = VideoInfo(
            id=1,
            task_id=100,
            test_case_id=200,
            file_path="/tmp/test.webm",
            file_name="test.webm",
            file_size=1024,
            duration=10.5,
            status=VideoStatus.READY,
            created_at=datetime(2026, 1, 1),
        )
        d = info.to_dict()
        assert d["id"] == 1
        assert d["task_id"] == 100
        assert d["status"] == "ready"
        assert d["created_at"] == "2026-01-01T00:00:00"

    def test_to_dict_none_dates(self):
        info = VideoInfo(id=1)
        d = info.to_dict()
        assert d["created_at"] is None
        assert d["expires_at"] is None

    def test_defaults(self):
        info = VideoInfo(id=1)
        assert info.task_id is None
        assert info.status == VideoStatus.PROCESSING
        assert info.file_size == 0


class TestFFmpegMixin:
    def test_is_valid_video_path_empty(self):
        assert FFmpegMixin._is_valid_video_path("") is False

    def test_is_valid_video_path_nonexistent(self):
        assert FFmpegMixin._is_valid_video_path("/nonexistent/file.mp4") is False

    def test_is_valid_video_path_invalid_extension(self):
        with patch("os.path.exists", return_value=True):
            assert FFmpegMixin._is_valid_video_path("/tmp/file.txt") is False

    def test_is_valid_video_path_valid(self):
        with patch("os.path.exists", return_value=True):
            assert FFmpegMixin._is_valid_video_path("/tmp/file.mp4") is True

    def test_is_valid_video_path_webm(self):
        with patch("os.path.exists", return_value=True):
            assert FFmpegMixin._is_valid_video_path("/tmp/file.webm") is True

    def test_check_ffmpeg_available_not_installed(self):
        mixin = FFmpegMixin()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert mixin._check_ffmpeg_available() is False

    def test_check_ffprobe_available_not_installed(self):
        mixin = FFmpegMixin()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert mixin._check_ffprobe_available() is False

    @pytest.mark.asyncio
    async def test_extract_video_thumbnail_no_ffmpeg(self):
        mixin = FFmpegMixin()
        with patch.object(mixin, "_check_ffmpeg_available", return_value=False):
            result = await mixin.extract_video_thumbnail("/tmp/test.mp4")
            assert result is None

    @pytest.mark.asyncio
    async def test_extract_video_thumbnail_invalid_path(self):
        mixin = FFmpegMixin()
        with patch.object(mixin, "_check_ffmpeg_available", return_value=True), \
             patch.object(mixin, "_is_valid_video_path", return_value=False):
            result = await mixin.extract_video_thumbnail("/tmp/invalid.txt")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_video_duration_no_ffprobe(self):
        mixin = FFmpegMixin()
        with patch.object(mixin, "_check_ffprobe_available", return_value=False):
            result = await mixin.get_video_duration("/tmp/test.mp4")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_video_duration_invalid_path(self):
        mixin = FFmpegMixin()
        with patch.object(mixin, "_check_ffprobe_available", return_value=True), \
             patch.object(mixin, "_is_valid_video_path", return_value=False):
            result = await mixin.get_video_duration("/tmp/invalid.txt")
            assert result is None


class TestCleanupMixin:
    @pytest.mark.asyncio
    async def test_cleanup_expired_videos_no_expired(self, db):
        mixin = CleanupMixin()
        mixin.db = db
        mixin._retention_days = 30
        mixin._video_base_dir = "/tmp/test_videos"
        # 清理数据库中残留的过期 VideoRecord，避免数据隔离问题
        db.query(VideoRecord).filter(
            VideoRecord.created_at < datetime.utcnow() - timedelta(days=30)
        ).delete(synchronize_session=False)
        db.flush()
        result = await mixin.cleanup_expired_videos()
        assert result["deleted_count"] == 0
        assert result["freed_mb"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_videos_with_days(self, db):
        mixin = CleanupMixin()
        mixin.db = db
        mixin._retention_days = 30
        mixin._video_base_dir = "/tmp/test_videos"
        result = await mixin.cleanup_expired_videos(days=60)
        assert result["retention_days"] == 60

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, db):
        mixin = CleanupMixin()
        mixin.db = db
        mixin._video_base_dir = "/tmp/test_videos"
        result = await mixin.get_storage_stats()
        assert "total_count" in result
        assert "total_size_mb" in result

    def test_set_retention_policy_valid(self):
        mixin = CleanupMixin()
        mixin._retention_days = 30
        mixin.set_retention_policy(60)
        assert mixin._retention_days == 60

    def test_set_retention_policy_invalid(self):
        mixin = CleanupMixin()
        mixin._retention_days = 30
        mixin.set_retention_policy(0)
        assert mixin._retention_days == 30

    def test_set_retention_policy_negative(self):
        mixin = CleanupMixin()
        mixin._retention_days = 30
        mixin.set_retention_policy(-1)
        assert mixin._retention_days == 30


class TestPathUtilsMixin:
    def test_get_video_path_not_found(self, db):
        mixin = PathUtilsMixin()
        mixin.db = db
        result = mixin.get_video_path(99999)
        assert result is None

    def test_get_video_url_not_found(self, db):
        mixin = PathUtilsMixin()
        mixin.db = db
        result = mixin.get_video_url(99999)
        assert result is None

    def test_ensure_directory(self, tmp_path):
        mixin = PathUtilsMixin()
        new_dir = str(tmp_path / "new_subdir")
        mixin._ensure_directory(new_dir)
        assert Path(new_dir).exists()


class TestCRUDMixin:
    @pytest.mark.asyncio
    async def test_get_video_info_not_found(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        result = await mixin.get_video_info(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_video_not_found(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        result = await mixin.delete_video(99999)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_videos_by_task_empty(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        result = await mixin.get_videos_by_task(99999)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_videos_by_case_empty(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        result = await mixin.get_videos_by_case(99999)
        assert result == []

    @pytest.mark.asyncio
    async def test_save_and_get_video_info(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        task_id, case_id = _create_parent_records(db)
        video_info = await mixin.save_video_info(
            task_id=task_id,
            test_case_id=case_id,
            file_path="/tmp/test_video.webm",
            file_name="test_video.webm",
            file_size=2048,
            duration=15.0,
        )
        assert video_info.id is not None
        assert video_info.task_id == task_id
        assert video_info.file_name == "test_video.webm"

        fetched = await mixin.get_video_info(video_info.id)
        assert fetched is not None
        assert fetched.file_name == "test_video.webm"

    @pytest.mark.asyncio
    async def test_save_video_with_none_ids(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        task_id, case_id = _create_parent_records(db)
        video_info = await mixin.save_video_info(
            task_id=task_id,
            test_case_id=case_id,
            file_path="/tmp/test.webm",
            file_name="test.webm",
            file_size=1024,
        )
        assert video_info.task_id == task_id
        assert video_info.test_case_id == case_id

    @pytest.mark.asyncio
    async def test_delete_video_success(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        task_id, case_id = _create_parent_records(db)
        video_info = await mixin.save_video_info(
            task_id=task_id,
            test_case_id=case_id,
            file_path="/tmp/delete_test.webm",
            file_name="delete_test.webm",
            file_size=1024,
        )
        result = await mixin.delete_video(video_info.id)
        assert result is True
        fetched = await mixin.get_video_info(video_info.id)
        assert fetched is None

    def test_to_video_info_completed(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        task_id, case_id = _create_parent_records(db)
        record = VideoRecord(
            task_id=task_id,
            case_id=case_id,
            file_path="/tmp/test.webm",
            file_name="test.webm",
            file_size=1024,
            status="completed",
        )
        db.add(record)
        db.flush()
        info = mixin._to_video_info(record)
        assert info.status == VideoStatus.READY

    def test_to_video_info_recording(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        task_id, case_id = _create_parent_records(db)
        record = VideoRecord(
            task_id=task_id,
            case_id=case_id,
            file_path="/tmp/test.webm",
            file_name="test.webm",
            file_size=1024,
            status="recording",
        )
        db.add(record)
        db.flush()
        info = mixin._to_video_info(record)
        assert info.status == VideoStatus.PROCESSING

    def test_to_video_info_failed(self, db):
        mixin = CRUDMixin()
        mixin.db = db
        task_id, case_id = _create_parent_records(db)
        record = VideoRecord(
            task_id=task_id,
            case_id=case_id,
            file_path="/tmp/test.webm",
            file_name="test.webm",
            file_size=1024,
            status="failed",
        )
        db.add(record)
        db.flush()
        info = mixin._to_video_info(record)
        assert info.status == VideoStatus.FAILED
