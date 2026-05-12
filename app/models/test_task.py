"""
测试任务模型模块

本模块定义了测试任务（TestTask）模型及其状态常量，测试任务是执行测试用例的
调度单元，记录任务执行进度、成功/失败计数等统计信息。

核心类概览：
    - TaskStatus : 任务状态常量类，定义状态码和中文标签
    - TestTask   : 测试任务模型，管理用例执行调度和进度

表关系：
    Project → TestTask（一对多，级联删除）
    User → TestTask（一对多，用户执行的测试任务）
    TestTask → TestResult（一对多，级联删除）
    TestTask → VideoRecord（一对多，级联删除）

依赖关系：
    - app.db.database.Base : SQLAlchemy 声明性基类

注意：
    本模块使用 datetime.now 而非 utcnow 作为时间默认值，
    与其他模型模块保持一致需评估是否迁移为UTC时间。
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class TaskStatus:
    """
    任务状态常量类

    定义测试任务的5种状态码及对应的中文标签，
    供业务层统一引用，避免硬编码状态值。

    Attributes:
        PENDING   : 等待执行（状态码 0）
        RUNNING   : 执行中（状态码 1）
        COMPLETED : 执行完成（状态码 2）
        FAILED    : 执行失败（状态码 3）
        STOPPED   : 已停止（状态码 4）
        LABELS    : 状态码到中文标签的映射字典
    """
    PENDING = 0       # 等待执行
    RUNNING = 1       # 执行中
    COMPLETED = 2     # 执行完成
    FAILED = 3        # 执行失败
    STOPPED = 4       # 已停止
    
    LABELS = {
        0: "等待执行",
        1: "执行中",
        2: "执行完成",
        3: "执行失败",
        4: "已停止"
    }


class TestTask(Base):
    """
    测试任务表

    测试任务是执行测试用例的调度单元，包含待执行用例列表、执行进度和统计信息。
    任务创建后进入 PENDING 状态，由执行引擎调度运行。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → User（执行人）
        - 一对多 → TestResult（测试结果，级联删除）
        - 一对多 → VideoRecord（视频录制，级联删除）

    使用场景：
        - 创建测试任务，选择待执行用例
        - 执行引擎调度任务运行
        - 查看任务执行进度和结果统计
        - 任务执行过程中支持停止操作
    """
    __tablename__ = "test_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                            # 任务主键ID
    task_name = Column(String(255), nullable=False, comment="任务名称")                                # 任务名称，如"登录模块回归测试"
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")  # 所属项目，级联删除
    case_ids = Column(JSON, nullable=False, comment="待执行用例ID列表")                                # JSON数组，存储待执行的用例ID列表
    executor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="执行用户ID")  # 任务执行人
    status = Column(Integer, nullable=False, default=0, index=True, comment="状态：0等待执行/1执行中/2执行完成/3执行失败/4已停止")  # 任务状态，默认0等待执行
    start_time = Column(DateTime, nullable=True, index=True, comment="开始执行时间")                    # 任务开始执行的时间
    end_time = Column(DateTime, nullable=True, index=True, comment="结束执行时间")                      # 任务结束执行的时间
    success_count = Column(Integer, nullable=False, default=0, comment="成功用例数")                    # 执行通过的用例计数
    fail_count = Column(Integer, nullable=False, default=0, comment="失败用例数")                       # 执行失败的用例计数
    total_count = Column(Integer, nullable=False, default=0, comment="总用例数")                        # 待执行用例总数
    progress = Column(Integer, nullable=False, default=0, comment="执行进度（0-100）")                  # 执行进度百分比，0-100
    create_time = Column(DateTime, default=datetime.now, index=True, comment="创建时间")                # 任务创建时间
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True, comment="更新时间")  # 任务更新时间
    
    # 关系
    project = relationship("Project", back_populates="test_tasks")                                    # 所属项目
    executor = relationship("User", back_populates="test_tasks")                                      # 任务执行人
    test_results = relationship("TestResult", back_populates="test_task", cascade="all, delete-orphan")  # 测试结果，级联删除
    video_records = relationship("VideoRecord", back_populates="task", cascade="all, delete-orphan")  # 视频录制，级联删除
