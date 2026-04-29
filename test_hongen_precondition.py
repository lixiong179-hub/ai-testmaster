"""
执行洪恩管理系统前置操作用例
测试前置操作自动化服务的完整流程
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.project import Project
from app.services.precondition_service import PreconditionService, TestObjectType


async def test_hongen_precondition():
    """测试洪恩管理系统前置操作"""
    print("=" * 70)
    print("执行洪恩管理系统前置操作用例")
    print("=" * 70)
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 查找洪恩项目
        project = db.query(Project).filter(
            Project.name.like("%洪恩%")
        ).first()
        
        if not project:
            print("❌ 未找到洪恩项目，尝试查找包含ihumand的项目...")
            project = db.query(Project).filter(
                Project.test_object_url.like("%ihumand%")
            ).first()
        
        if not project:
            print("❌ 未找到洪恩相关项目，请确认项目已创建")
            print("\n现有项目列表:")
            projects = db.query(Project).all()
            for p in projects[:10]:
                print(f"  - {p.name} (ID: {p.id})")
            return
        
        print(f"✅ 找到项目: {project.name}")
        print(f"  - 项目ID: {project.id}")
        print(f"  - 测试对象类型: {project.test_object_type}")
        print(f"  - 测试对象URL: {project.test_object_url}")
        print(f"  - 用户名: {project.test_object_username or '未配置'}")
        print(f"  - 密码: {'已配置' if project.test_object_password else '未配置'}")
        
        # 创建前置操作服务
        print("\n1. 初始化前置操作服务...")
        service = PreconditionService()
        await service.initialize()
        print("  ✅ 前置操作服务初始化成功")
        
        # 读取被测对象信息
        print("\n2. 读取被测对象信息...")
        test_object_info = await service.read_test_object_info(project)
        print(f"  ✅ 被测对象信息读取成功")
        print(f"  - 类型: {test_object_info.type.value}")
        print(f"  - URL: {test_object_info.url}")
        print(f"  - 用户名: {test_object_info.username}")
        print(f"  - 密码: {'已配置' if test_object_info.password else '未配置'}")
        
        # 执行Web前置操作
        print("\n3. 执行Web前置操作（启动浏览器、导航、登录）...")
        print("  正在启动浏览器，请稍候...")
        
        browser_controller = await service.execute_web_precondition(
            headless=False,  # 显示浏览器窗口
            browser_type="chromium",
            auto_login=True
        )
        
        print("  ✅ Web前置操作执行完成")
        print(f"  - 浏览器已启动: {service.is_browser_ready}")
        
        # 等待用户查看
        print("\n4. 登录完成，等待10秒供查看...")
        await asyncio.sleep(10)
        
        # 清理资源
        print("\n5. 清理资源...")
        await service.cleanup()
        print("  ✅ 资源清理完成")
        
        print("\n" + "=" * 70)
        print("洪恩管理系统前置操作用例执行完成！")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_hongen_precondition())
