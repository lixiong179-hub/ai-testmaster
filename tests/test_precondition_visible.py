"""
前置操作服务可见浏览器测�?

此测试使�?headless=False 模式，让您看到真实浏览器窗口
"""
import pytest
import asyncio
from unittest.mock import Mock

from app.services.precondition_service import (
    PreconditionService,
    TestObjectType,
    create_precondition_service
)


@pytest.mark.asyncio
@pytest.mark.real_browser
async def test_visible_browser_execution():
    """
    可见浏览器测试：执行Web前置操作
    
    此测试会打开一个可见的浏览器窗口，让您看到测试执行过程
    """
    print("\n" + "="*60)
    print("可见浏览器测试开�?)
    print("="*60)
    print("您将看到浏览器窗口打开并执行以下操作：")
    print("1. 启动真实浏览器（chromium�?)
    print("2. 导航到百度首�?)
    print("3. 在搜索框输入文本")
    print("4. 等待5秒后关闭浏览�?)
    print("="*60 + "\n")
    
    # 创建服务
    service = await create_precondition_service()
    
    try:
        # 创建项目
        project = Mock()
        project.name = "可见浏览器测试项�?
        project.test_object_type = "web"
        project.test_object_url = "https://www.baidu.com"
        project.test_object_username = None
        project.test_object_password = None
        project.test_object_device_info = None
        project.test_object_app_package = None
        project.test_object_app_activity = None
        
        print("[1/4] 读取项目信息...")
        await service.read_test_object_info(project)
        print("�?项目信息读取成功")
        
        print("[2/4] 启动可见浏览器并导航到百�?..")
        browser = await service.execute_web_precondition(
            headless=False,  # 可见模式
            browser_type="chromium",
            auto_login=False
        )
        print("�?浏览器启动成功，页面已导�?)
        
        # 验证浏览器已启动
        assert service.is_browser_ready is True
        
        # 在搜索框输入文本
        print("[3/4] 在搜索框输入文本...")
        search_input = await browser.execute_javascript(
            "document.querySelector('#kw')"
        )
        
        if search_input:
            # 获取搜索框位�?
            rect = await browser.execute_javascript(
                "document.querySelector('#kw').getBoundingClientRect()"
            )
            
            if rect:
                x = int(rect["x"] + rect["width"] / 2)
                y = int(rect["y"] + rect["height"] / 2)
                
                # 使用_click_and_type输入文本
                await service._click_and_type(x, y, "AI测试大师")
                print("�?文本输入成功")
                
                # 验证输入
                value = await browser.execute_javascript(
                    "document.querySelector('#kw').value"
                )
                assert value == "AI测试大师"
                print(f"�?验证成功：搜索框内容 = '{value}'")
        
        print("[4/4] 等待5�?..")
        for i in range(5, 0, -1):
            print(f"  倒计�? {i}�?)
            await asyncio.sleep(1)
        
        print("\n�?可见浏览器测试完成！")
        
    finally:
        print("[清理] 关闭浏览�?..")
        await service.cleanup()
        print("�?浏览器已关闭")
        print("="*60)


@pytest.mark.asyncio
@pytest.mark.real_browser
async def test_visible_browser_login_simulation():
    """
    可见浏览器测试：模拟登录流程
    
    此测试会打开一个可见的浏览器窗口，模拟在httpbin表单页面输入数据
    注意：不会实际提交表�?
    """
    print("\n" + "="*60)
    print("可见浏览器表单输入模拟测�?)
    print("="*60)
    print("您将看到浏览器窗口打开并执行以下操作：")
    print("1. 启动真实浏览器（chromium�?)
    print("2. 导航到httpbin表单页面")
    print("3. 在表单中输入测试数据（不会提交）")
    print("4. 等待5秒后关闭浏览�?)
    print("="*60 + "\n")
    
    from app.utils.browser_controller import create_browser_controller
    
    service = await create_precondition_service()
    
    try:
        # 创建可见浏览�?
        print("[1/4] 启动可见浏览�?..")
        browser = await create_browser_controller(
            browser_type="chromium",
            headless=False,  # 可见模式
            viewport_width=1280,
            viewport_height=720
        )
        service.browser_controller = browser
        print("�?浏览器启动成�?)
        
        # 导航到httpbin表单页面
        print("[2/4] 导航到httpbin表单页面...")
        await browser.navigate("https://httpbin.org/forms/post")
        print("�?页面导航成功")
        
        # 获取页面信息
        page_info = await browser.get_page_info()
        print(f"  当前URL: {page_info['url']}")
        print(f"  页面标题: {page_info['title']}")
        
        # 在表单中输入测试数据
        print("[3/4] 在表单中输入测试数据...")
        
        # 输入客户名称
        custname_input = await browser.execute_javascript(
            "document.querySelector('input[name=\"custname\"]')"
        )
        if custname_input:
            rect = await browser.execute_javascript(
                "document.querySelector('input[name=\"custname\"]').getBoundingClientRect()"
            )
            if rect:
                x = int(rect["x"] + rect["width"] / 2)
                y = int(rect["y"] + rect["height"] / 2)
                await service._click_and_type(x, y, "测试用户")
                print("�?客户名称输入成功")
        
        # 输入电话
        tele_input = await browser.execute_javascript(
            "document.querySelector('input[name=\"custtel\"]')"
        )
        if tele_input:
            rect = await browser.execute_javascript(
                "document.querySelector('input[name=\"custtel\"]').getBoundingClientRect()"
            )
            if rect:
                x = int(rect["x"] + rect["width"] / 2)
                y = int(rect["y"] + rect["height"] / 2)
                await service._click_and_type(x, y, "13800138000")
                print("�?电话输入成功")
        
        print("[4/4] 等待5�?..")
        for i in range(5, 0, -1):
            print(f"  倒计�? {i}�?)
            await asyncio.sleep(1)
        
        print("\n�?表单输入模拟测试完成�?)
        print("注意：测试数据未提交，仅用于演示输入功能")
        
    finally:
        print("[清理] 关闭浏览�?..")
        await service.cleanup()
        print("�?浏览器已关闭")
        print("="*60)
