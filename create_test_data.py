"""
创建测试数据
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.database import Base
from app.models.project import Project
from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase, TestStep


def create_test_data():
    """创建测试数据"""
    print("=" * 60)
    print("创建测试数据")
    print("=" * 60)
    
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 检查是否已有项目
        existing_project = db.query(Project).first()
        if existing_project:
            print(f"项目已存在: {existing_project.name}")
            project = existing_project
        else:
            # 创建项目
            project = Project(
                name="测试项目",
                description="用于测试的项目",
                user_id=1,
                test_object_type="web",
                test_object_url="https://example.com",
                status=1
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            print(f"✅ 创建项目: {project.name} (ID: {project.id})")
        
        # 检查是否已有测试用例
        existing_case = db.query(TestCase).filter(TestCase.project_id == project.id).first()
        if existing_case:
            print(f"测试用例已存在: {existing_case.case_no}")
        else:
            # 创建测试用例
            test_case = TestCase(
                project_id=project.id,
                case_no="TC001",
                module="登录模块",
                title="登录功能测试",
                precondition="用户已注册",
                expected_result="登录成功",
                priority=1,
                case_type="UI",
                generate_status=1,
                steps_json=[]
            )
            db.add(test_case)
            db.commit()
            db.refresh(test_case)
            print(f"✅ 创建测试用例: {test_case.case_no}")
            
            # 创建测试步骤
            steps_data = [
                {
                    "step_number": 1,
                    "action": "打开登录页面",
                    "expected_result": "页面加载成功",
                    "is_business_view": 1,
                    "is_technical_view": 1
                },
                {
                    "step_number": 2,
                    "action": "输入用户名 'admin123'",
                    "expected_result": "用户名显示在输入框",
                    "is_business_view": 1,
                    "is_technical_view": 1
                },
                {
                    "step_number": 3,
                    "action": "输入密码 'admin123'",
                    "expected_result": "密码显示为圆点",
                    "is_business_view": 1,
                    "is_technical_view": 1
                },
                {
                    "step_number": 4,
                    "action": "点击登录按钮",
                    "expected_result": "跳转到首页",
                    "is_business_view": 1,
                    "is_technical_view": 1
                }
            ]
            
            for step_data in steps_data:
                step = TestStep(
                    test_case_id=test_case.id,
                    **step_data
                )
                db.add(step)
            
            db.commit()
            print(f"✅ 创建 {len(steps_data)} 个测试步骤")
        
        print("\n✅ 测试数据创建完成！")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    create_test_data()
