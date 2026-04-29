"""
更新洪恩管理系统项目配置
账号和密码都是admin123
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.project import Project


def update_hongen_project():
    """更新洪恩项目配置"""
    print("=" * 70)
    print("更新洪恩管理系统项目配置")
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
        
        print(f"找到项目: {project.name} (ID: {project.id})")
        print(f"\n更新前:")
        print(f"  - 用户名: {project.test_object_username}")
        print(f"  - 密码: {project.test_object_password}")
        
        # 更新用户名和密码
        project.test_object_username = "admin123"
        project.test_object_password = "admin123"
        
        db.commit()
        
        print(f"\n更新后:")
        print(f"  - 用户名: {project.test_object_username}")
        print(f"  - 密码: {project.test_object_password}")
        print(f"\n✅ 项目配置更新成功！")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    update_hongen_project()
