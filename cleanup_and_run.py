"""
清理数据库并运行真实项目测试
"""
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.database import Base
from app.models.project import Project
from app.models.user import User
from app.models.test_case import TestCase, TestStep, TestCaseExecution

# 清理数据库
print("清理测试数据...")
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # 删除测试数据
    db.query(TestCaseExecution).filter(TestCaseExecution.id >= 99990).delete()
    db.query(TestStep).filter(TestStep.id >= 99990).delete()
    db.query(TestCase).filter(TestCase.id >= 99990).delete()
    db.query(Project).filter(Project.id >= 99990).delete()
    db.query(User).filter(User.id >= 99990).delete()
    db.commit()
    print("✓ 数据库清理完成")
except Exception as e:
    print(f"清理时出错: {e}")
    db.rollback()
finally:
    db.close()

# 运行测试
print("\n运行真实项目测试...\n")
from test_real_project_execution import test_real_project_login
result = asyncio.run(test_real_project_login())

print("\n" + "="*80)
print("测试完成！")
print("="*80)
