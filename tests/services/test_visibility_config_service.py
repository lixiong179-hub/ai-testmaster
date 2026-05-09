"""
VisibilityConfigService单元测试

测试范围:
- 全局配置管理
- 任务级别配置
- 用例级别配置
- 配置合并
- 配置验证
- 环境变量加载

注意: 使用真实环境，不使用Mock
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.database import Base
from app.services.visibility_config_service import (
    VisibilityConfigService,
    VisibilityConfig,
    get_visibility_config_service
)
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


@pytest.fixture(scope="module")
def db_engine():
    """创建数据库引�?""
    engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
    return engine


@pytest.fixture(scope="function")
def db(db_engine):
    """创建数据库会�?""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def config_service():
    """创建配置服务实例"""
    service = VisibilityConfigService()
    yield service


@pytest.fixture(scope="function")
def test_project(db):
    """创建测试项目"""
    # 先清理可能存在的旧测试数据（防止唯一键冲突和孤儿数据�?
    existing_user = db.query(User).filter(User.username == "config_test_user").first()
    if existing_user:
        db.query(Project).filter(Project.user_id == existing_user.id).delete()
        db.delete(existing_user)
        db.commit()
    
    # 也清理同名项目（防止孤立项目�?
    db.query(Project).filter(Project.name == "配置测试项目").delete()
    db.commit()
    
    user = User(
        username="config_test_user",
        email="config_test@example.com",
        password_hash="test_hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    project = Project(name="配置测试项目", user_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project
    
    # 清理
    db.delete(project)
    db.delete(user)
    db.commit()


@pytest.fixture(scope="function")
def test_task(db, test_project):
    """创建测试任务"""
    # 获取用户
    user = db.query(User).filter(User.username == "config_test_user").first()
    
    task = TestTask(
        task_name="配置测试任务",
        project_id=test_project.id,
        executor_id=user.id,
        case_ids=[],
        total_count=1,
        status=0,
        success_count=0,
        fail_count=0,
        progress=0
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    yield task
    
    db.delete(task)
    db.commit()


@pytest.fixture(scope="function")
def test_case(db, test_project):
    """创建测试用例"""
    case = TestCase(
        case_no="CONFIG-001",
        project_id=test_project.id,
        module="配置测试模块",
        title="配置测试用例",
        precondition="前置条件",
        steps_json=[],
        expected_result="预期结果",
        priority=2,
        case_type="UI",
        generate_status=0,
        review_status="pending"
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    yield case
    
    db.delete(case)
    db.commit()


class TestVisibilityConfigService:
    """可见模式配置服务测试�?""
    
    def test_service_initialization(self, config_service):
        """测试服务初始�?""
        assert config_service is not None
        assert config_service._video_base_dir.exists()
        assert config_service._screenshot_base_dir.exists()
    
    def test_default_global_config(self, config_service):
        """测试默认全局配置"""
        config = VisibilityConfigService.DEFAULT_GLOBAL_CONFIG
        
        assert config.headless is True
        assert config.record_video is False
        assert config.video_resolution == (1920, 1080)
        assert config.video_fps == 30
        assert config.take_screenshot is True
        assert config.screenshot_on_failure is True
        assert config.screenshot_on_success is False
        assert config.execution_speed == "normal"
        assert config.action_delay_ms == 500
        assert config.highlight_elements is True
        assert config.show_ai_analysis is True
    
    def test_get_global_config_default(self, config_service):
        """测试获取全局配置（默认）"""
        config = config_service.get_global_config()
        
        assert isinstance(config, VisibilityConfig)
        assert config.headless is True
        assert config.record_video is False
    
    def test_set_global_config(self, config_service):
        """测试设置全局配置"""
        # 设置新配�?
        new_config = VisibilityConfig(
            headless=False,
            record_video=True,
            video_resolution=(1280, 720),
            video_fps=60
        )
        
        config_service.set_global_config(new_config)
        
        # 验证
        config = config_service.get_global_config()
        assert config.headless is False
        assert config.record_video is True
        assert config.video_resolution == (1280, 720)
        assert config.video_fps == 60
        
        # 恢复默认
        config_service.set_global_config(VisibilityConfigService.DEFAULT_GLOBAL_CONFIG)
    
    def test_load_config_from_env(self, config_service, monkeypatch):
        """测试从环境变量加载配�?""
        # 设置环境变量
        monkeypatch.setenv("TEST_HEADLESS", "false")
        monkeypatch.setenv("TEST_RECORD_VIDEO", "true")
        monkeypatch.setenv("TEST_VIDEO_WIDTH", "1280")
        monkeypatch.setenv("TEST_VIDEO_HEIGHT", "720")
        monkeypatch.setenv("TEST_VIDEO_FPS", "60")
        monkeypatch.setenv("TEST_EXECUTION_SPEED", "fast")
        
        # 加载配置
        config = config_service._load_config_from_env()
        
        # 验证
        assert config.headless is False
        assert config.record_video is True
        assert config.video_resolution == (1280, 720)
        assert config.video_fps == 60
        assert config.execution_speed == "fast"
    
    def test_get_task_config(self, config_service, test_task):
        """测试获取任务配置"""
        config = config_service.get_task_config(test_task)
        
        # 应该返回全局默认配置（任务没有自定义配置�?
        assert isinstance(config, VisibilityConfig)
        assert config.headless is True
    
    def test_get_case_config(self, config_service, test_case, test_task):
        """测试获取用例配置"""
        config = config_service.get_case_config(test_case, test_task)
        
        # 应该返回全局配置（用例没有自定义配置�?
        assert isinstance(config, VisibilityConfig)
    
    def test_get_case_config_without_task(self, config_service, test_case):
        """测试获取用例配置（无任务�?""
        config = config_service.get_case_config(test_case)
        
        # 应该返回全局配置
        assert isinstance(config, VisibilityConfig)
    
    def test_config_merge(self, config_service):
        """测试配置合并"""
        base_config = VisibilityConfig(
            headless=True,
            record_video=False,
            video_fps=30
        )
        
        override_config = VisibilityConfig(
            headless=False,  # 覆盖
            record_video=True  # 覆盖
            # video_fps 不覆盖，保持base的�?
        )
        
        merged = config_service._merge_configs(base_config, override_config)
        
        # 验证：override覆盖base
        assert merged.headless is False
        assert merged.record_video is True
        assert merged.video_fps == 30  # 保持base的�?
    
    def test_config_to_dict(self, config_service):
        """测试配置转字�?""
        config = VisibilityConfig(
            headless=False,
            record_video=True,
            video_resolution=(1280, 720)
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["headless"] is False
        assert config_dict["record_video"] is True
        assert config_dict["video_resolution"] == (1280, 720)
    
    def test_config_from_dict(self, config_service):
        """测试从字典创建配�?""
        config_dict = {
            "headless": False,
            "record_video": True,
            "video_resolution": [1920, 1080],
            "video_fps": 60,
            "execution_speed": "fast"
        }
        
        config = VisibilityConfig.from_dict(config_dict)
        
        assert config.headless is False
        assert config.record_video is True
        assert config.video_resolution == (1920, 1080)
        assert config.video_fps == 60
        assert config.execution_speed == "fast"
    
    def test_get_video_save_path(self, config_service):
        """测试获取视频保存路径"""
        path = config_service.get_video_save_path(task_id=1, case_id=1)
        
        assert "task_1" in str(path)
        assert "case_1" in str(path)
        assert path.suffix == ".webm"
    
    def test_get_screenshot_save_path(self, config_service):
        """测试获取截图保存路径"""
        path = config_service.get_screenshot_save_path(task_id=1, case_id=1, step_number=5)
        
        assert "task_1" in str(path)
        assert "case_1" in str(path)
        assert "step_5" in str(path)
        assert path.suffix == ".png"
    
    def test_speed_delay_map(self, config_service):
        """测试速度延迟映射"""
        assert config_service.SPEED_DELAY_MAP["slow"] == 1000
        assert config_service.SPEED_DELAY_MAP["normal"] == 500
        assert config_service.SPEED_DELAY_MAP["fast"] == 100


class TestVisibilityConfigServiceSingleton:
    """可见模式配置服务单例测试"""
    
    def test_get_visibility_config_service_singleton(self):
        """测试获取配置服务单例"""
        service1 = get_visibility_config_service()
        service2 = get_visibility_config_service()
        
        # 应该是同一个实�?
        assert service1 is service2
