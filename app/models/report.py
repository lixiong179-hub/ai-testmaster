"""
测试报告模型模块

本模块定义了测试报告（TestReport）模型，记录测试任务的执行汇总结果，
包括通过/失败/跳过用例数、执行时间和详细报告内容。

核心类概览：
    - TestReport : 测试报告模型，记录任务执行汇总

表关系：
    Project → TestReport（一对多，级联删除）
    TestTask → TestReport（一对多，SET NULL，任务删除后报告保留）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.utils.db_time import utcnow
from app.db.database import Base


class TestReport(Base):
    """
    测试报告模型

    记录测试任务的执行汇总结果，包括用例统计、执行时间、
    AI生成的摘要和详细报告内容。报告与任务关联但独立存储，
    任务删除后报告仍可保留用于历史追溯。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → TestTask（关联任务，SET NULL）

    使用场景：
        - 测试任务执行完成后自动生成报告
        - 按项目查看历史测试报告
        - 报告中查看用例通过率和失败详情
    """
    __tablename__ = "test_reports"

    id = Column(Integer, primary_key=True, index=True)                                                # 报告主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID，多项目隔离核心")  # 项目ID，级联删除
    test_task_id = Column(Integer, ForeignKey("test_tasks.id", ondelete="SET NULL"), nullable=True)   # 任务ID，SET NULL保留报告
    name = Column(String(255), nullable=False)                                                        # 报告名称
    description = Column(Text, nullable=True)                                                         # 报告描述
    status = Column(String(20), default="completed")  # pending, running, completed, failed           # 报告状态：pending=生成中，running=执行中，completed=已完成，failed=生成失败
    total_cases = Column(Integer, default=0)                                                          # 总用例数
    passed_cases = Column(Integer, default=0)                                                         # 通过用例数
    failed_cases = Column(Integer, default=0)                                                         # 失败用例数
    skipped_cases = Column(Integer, default=0)                                                        # 跳过用例数
    start_time = Column(DateTime, nullable=True)                                                      # 报告起始时间
    end_time = Column(DateTime, nullable=True)                                                        # 报告结束时间
    execution_time = Column(Integer, nullable=True)  # 执行时间（秒）                                  # 执行总耗时，单位秒
    summary = Column(Text, nullable=True)                                                             # AI生成的报告摘要
    content = Column(JSON, nullable=True)  # 详细结果                                                 # 详细报告内容，JSON格式存储结构化数据
    create_time = Column(DateTime, default=utcnow)                                                    # 创建时间，UTC时区
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow)                                   # 更新时间

    # 关联关系 - 通过project_id隔离
    project = relationship("Project", back_populates="test_reports")                                  # 所属项目
