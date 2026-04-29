"""
验证洪恩管理系统登录是否成功
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.project import Project
from app.services.precondition_service import PreconditionService


async def test_hongen_login():
    """测试洪恩管理系统登录并验证结果"""
    print("=" * 70)
    print("验证洪恩管理系统登录")
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
        print(f"  - URL: {project.test_object_url}")
        print(f"  - 用户名: {project.test_object_username}")
        print(f"  - 密码: {project.test_object_password}")
        
        # 创建前置操作服务
        service = PreconditionService()
        await service.initialize()
        
        # 读取被测对象信息
        test_object_info = await service.read_test_object_info(project)
        
        # 执行Web前置操作
        print("\n执行登录操作...")
        browser_controller = await service.execute_web_precondition(
            headless=False,
            browser_type="chromium",
            auto_login=True
        )
        
        print("✅ 登录操作执行完成")
        
        # 等待页面加载
        await asyncio.sleep(3)
        
        # 验证登录是否成功
        print("\n验证登录结果...")
        
        # 获取当前页面URL
        current_url = await browser_controller.execute_javascript("window.location.href")
        print(f"  当前页面URL: {current_url}")
        
        # 检查页面标题
        page_title = await browser_controller.execute_javascript("document.title")
        print(f"  页面标题: {page_title}")
        
        # 检查是否存在登录错误提示
        error_selectors = [
            ".el-message--error",
            ".error-message",
            ".login-error",
            "[class*='error']",
            "[class*='fail']"
        ]
        
        has_error = False
        for selector in error_selectors:
            try:
                elements = await browser_controller.execute_javascript(
                    f"document.querySelectorAll('{selector}').length"
                )
                if elements and int(elements) > 0:
                    error_text = await browser_controller.execute_javascript(
                        f"document.querySelector('{selector}')?.textContent || ''"
                    )
                    if error_text:
                        print(f"  ⚠️ 发现错误提示 [{selector}]: {error_text}")
                        has_error = True
            except:
                pass
        
        # 检查是否存在登录后的元素（如用户头像、退出按钮等）
        logged_in_selectors = [
            ".user-avatar",
            ".logout-btn",
            ".el-dropdown",
            "[class*='user']",
            "[class*='profile']",
            ".sidebar",
            ".main-container"
        ]
        
        logged_in = False
        for selector in logged_in_selectors:
            try:
                elements = await browser_controller.execute_javascript(
                    f"document.querySelectorAll('{selector}').length"
                )
                if elements and int(elements) > 0:
                    print(f"  ✅ 发现登录后元素 [{selector}]")
                    logged_in = True
            except:
                pass
        
        # 截图查看当前状态
        print("\n截取当前页面状态...")
        screenshot = await browser_controller.take_screenshot()
        screenshot_path = "hongen_login_result.png"
        with open(screenshot_path, "wb") as f:
            f.write(screenshot)
        print(f"  ✅ 截图已保存: {screenshot_path}")
        
        # 判断登录结果
        print("\n" + "=" * 70)
        if has_error:
            print("❌ 登录失败 - 发现错误提示")
        elif logged_in or "login" not in current_url.lower():
            print("✅ 登录成功！")
        else:
            print("⚠️ 登录状态不确定 - 仍在登录页面")
        print("=" * 70)
        
        # 等待查看
        print("\n等待10秒供查看...")
        await asyncio.sleep(10)
        
        # 清理资源
        await service.cleanup()
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_hongen_login())
