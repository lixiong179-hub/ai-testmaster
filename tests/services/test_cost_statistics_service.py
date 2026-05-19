"""
CostStatisticsService 单元测试

测试范围:
- 用例成本统计
- 项目成本统计
- 成本报表生成
- 成本优化建议
- 成本趋势分析

要求: 使用真实MySQL数据库，不使用Mock，覆盖率>=95%
"""
import pytest
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.services.cost_statistics_service import (
    CostStatisticsService, CostStatistics, CostReport
)
from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.test_result import TestResult
from app.db.database import Base


# 使用真实MySQL数据库连接
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "mysql+pymysql://root:test1234@localhost:3306/ai_testmaster"
)

# 测试数据标识前缀（用于精确清理，不影响其他业务数据）
_TEST_PREFIX = "cost_stats_test_"


@pytest.fixture(scope="function")
def db_session():
    """
    创建数据库会话 - 使用事务隔离模式
    
    测试完成后自动回滚，不残留任何测试数据到真实数据库。
    这是安全的：不会影响任何已有业务数据。
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True
    )
    
    connection = engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()  # 回滚所有测试操作，不污染真实数据
        connection.close()
        engine.dispose()


@pytest.fixture
def test_project(db_session) -> Project:
    """创建测试项目"""
    project = Project(
        name=f"{_TEST_PREFIX}项目",
        description="用于测试成本统计功能",
        user_id=1
    )
    db_session.add(project)
    db_session.flush()
    return project