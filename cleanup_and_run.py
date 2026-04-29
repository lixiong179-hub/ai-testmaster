"""
清理数据库并运行真实项目测试
注意：仅清理以 "自动化测试项目_" 或 "测试项目_" 为前缀的测试数据，
避免误删用户正常创建的项目。
"""
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.project import Project

# 清理数据库（仅清理测试前缀的项目）
print("清理测试数据...")
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

TEST_PROJECT_PREFIXES = ("自动化测试项目_", "测试项目_")

try:
    # 仅删除名称以测试前缀开头的项目，级联删除关联数据
    test_projects = db.query(Project).filter(
        Project.name.startswith(TEST_PROJECT_PREFIXES[0]) |
        Project.name.startswith(TEST_PROJECT_PREFIXES[1])
    ).all()
    for p in test_projects:
        print(f"  删除测试项目: {p.name} (id={p.id})")
        db.delete(p)
    if test_projects:
        db.commit()
        print(f"✓ 已清理 {len(test_projects)} 个测试项目")
    else:
        print("✓ 无需清理")
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
