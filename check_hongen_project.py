"""
检查洪恩管理系统项目配置
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.project import Project


def check_hongen_project():
    """检查洪恩项目配置"""
    print("=" * 70)
    print("检查洪恩管理系统项目配置")
    print("=" * 70)
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 查找洪恩项目
        project = db.query(Project).filter(
            Project.name == "洪恩管理系统"
        ).first()
        
        if not project:
            print("❌ 未找到洪恩项目")
            return
        
        print(f"✅ 找到项目: {project.name}")
        print(f"\n项目配置:")
        print(f"  - 项目ID: {project.id}")
        print(f"  - 项目名称: {project.name}")
        print(f"  - 项目描述: {project.description}")
        print(f"  - 测试对象类型: {project.test_object_type}")
        print(f"  - 测试对象URL: {project.test_object_url}")
        print(f"  - 用户名: {project.test_object_username}")
        print(f"  - 密码: {project.test_object_password}")
        print(f"  - 状态: {project.status}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    check_hongen_project()
