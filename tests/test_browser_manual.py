"""
手动验证浏览器真实运行的测试
这个测试会保持浏览器打开，让您可以手动验证
"""
import pytest
import asyncio
from app.utils.browser_controller import create_browser_controller


@pytest.mark.asyncio
@pytest.mark.real_browser
async def test_browser_manual_verification():
    """
    手动验证测试 - 浏览器会保持打开10秒
    请观察是否能看到浏览器窗口
    """
    print("\n" + "="*60)
    print("手动验证测试")
    print("="*60)
    print("1. 你应该能看到一个浏览器窗口打开")
    print("2. 浏览器会导航到百度")
    print("3. 等待10秒后自动关闭")
    print("4. 如果你看不到浏览器窗口，说明测试有问题")
    print("="*60 + "\n")
    
    # 使用有头模式（可见窗口）
    print("正在启动浏览器...")
    controller = await create_browser_controller(
        browser_type="chromium",
        headless=False,  # 强制可见模式
        viewport_width=1280,
        viewport_height=720
    )
    
    print("✓ 浏览器已启动")
    print("请确认你看到了浏览器窗口！")
    
    try:
        # 导航到百度
        print("\n正在导航到百度...")
        await controller.navigate("https://www.baidu.com")
        print("✓ 已导航到百度")
        
        # 等待10秒，让您观察
        print("\n等待10秒，请观察浏览器窗口...")
        for i in range(10, 0, -1):
            print(f"倒计时: {i}秒")
            await asyncio.sleep(1)
        
        # 验证页面
        title = await controller.execute_javascript("document.title")
        print(f"\n✓ 页面标题: {title}")
        
        # 截图
        screenshot = await controller.take_screenshot()
        print(f"✓ 截图成功: {len(screenshot)} bytes")
        
        print("\n" + "="*60)
        print("测试完成！")
        print("如果你看到了浏览器窗口并加载了百度，说明测试有效")
        print("="*60 + "\n")
        
    finally:
        print("正在关闭浏览器...")
        await controller.close()
        print("✓ 浏览器已关闭")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
