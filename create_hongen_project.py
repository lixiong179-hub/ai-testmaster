"""
创建洪恩管理系统测试项目
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.project import Project


def create_hongen_project():
    """创建洪恩管理系统测试项目"""
    print("=" * 70)
    print("创建洪恩管理系统测试项目")
    print("=" * 70)
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 检查是否已存在洪恩项目
        existing = db.query(Project).filter(
            Project.name == "洪恩管理系统"
        ).first()
        
        if existing:
            print(f"✅ 洪恩项目已存在 (ID: {existing.id})")
            print(f"  - URL: {existing.test_object_url}")
            return existing.id
        
        # 创建新项目
        project = Project(
            name="洪恩管理系统",
            description="洪恩管理系统自动化测试项目",
            user_id=1,
            status=1,
            test_object_type="web",
            test_object_url="https://admin-jxw-panda-test.ihumand.com",
            test_object_username="admin",
            test_object_password="admin123"
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        print(f"✅ 洪恩项目创建成功！")
        print(f"  - 项目ID: {project.id}")
        print(f"  - 项目名称: {project.name}")
        print(f"  - 测试对象URL: {project.test_object_url}")
        print(f"  - 用户名: {project.test_object_username}")
        print(f"  - 密码: {'已配置' if project.test_object_password else '未配置'}")
        
        return project.id
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()


if __name__ == "__main__":
    create_hongen_project()
