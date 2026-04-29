"""
调试测试 - 检查坐标列表问题
"""
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.database import Base
from app.models.project import Project
from app.models.user import User
from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.services.test_execution_engine_v2 import TestExecutionEngineV2 as TestExecutionEngine
from app.services.element_locator_service import ElementLocatorService
from app.utils.browser_controller import create_browser_controller
from app.utils.unified_vision_model import get_default_vision_model

async def debug_coordinate():
    """调试坐标问题"""
    print("开始调试...")
    
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 创建测试用户
        test_user = db.query(User).filter(User.id == 99999).first()
        if not test_user:
            test_user = User(
                id=99999,
                username="testuser",
                email="test@example.com",
                password_hash="test_hash"
            )
            db.add(test_user)
            db.commit()
        
        # 创建项目
        project = Project(
            id=99999,
            name="调试项目",
            user_id=99999,
            description="调试",
            test_object_type="web",
            test_object_url="https://admin-jxw-panda-test.ihumand.com/#/index",
            test_object_username="admin123",
            test_object_password="admin321"
        )
        db.add(project)
        db.commit()
        
        # 创建浏览器
        browser = await create_browser_controller(headless=True)
        vision_model = get_default_vision_model()
        
        # 创建元素定位服务
        locator_service = ElementLocatorService(db, browser, vision_model)
        
        # 导航到页面
        await browser.navigate("https://admin-jxw-panda-test.ihumand.com/#/index")
        await asyncio.sleep(2)
        
        # 记录验证码定位
        print("\n记录验证码定位...")
        locator = await locator_service.record_locator(
            step_id=99995,
            action_description="识别并输入验证码"
        )
        
        print(f"\n定位信息:")
        print(f"  ID: {locator.id}")
        print(f"  Step ID: {locator.step_id}")
        print(f"  AI坐标: {locator.ai_coordinate}")
        print(f"  坐标类型: {type(locator.ai_coordinate)}")
        if locator.ai_coordinate:
            for key, value in locator.ai_coordinate.items():
                print(f"    {key}: {value} (类型: {type(value)})")
        
        # 测试 get_best_locator
        print(f"\n调用 get_best_locator()...")
        best_locator = locator.get_best_locator()
        print(f"  结果: {best_locator}")
        print(f"  值类型: {type(best_locator.get('value') if best_locator else None)}")
        if best_locator and best_locator.get('value'):
            value = best_locator['value']
            if isinstance(value, dict):
                for key, val in value.items():
                    print(f"    {key}: {val} (类型: {type(val)})")
        
        # 清理
        await browser.close()
        db.query(ElementLocator).filter(ElementLocator.step_id == 99995).delete()
        db.query(Project).filter(Project.id == 99999).delete()
        db.query(User).filter(User.id == 99999).delete()
        db.commit()
        
        print("\n调试完成!")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_coordinate())
