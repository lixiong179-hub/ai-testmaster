"""
验证浏览器真实运行的测试
使用有头模式，可以看到浏览器窗口
"""
import pytest
import asyncio
import time
from app.utils.browser_controller import create_browser_controller


@pytest.mark.asyncio
@pytest.mark.real_browser
async def test_browser_visible():
    """
    测试浏览器真实可见运�?
    这个测试会打开一个可见的浏览器窗口，持续5�?
    """
    print("\n" + "="*50)
    print("正在启动可见浏览器进行真实测�?..")
    print("你应该能看到浏览器窗口打开")
    print("="*50 + "\n")
    
    # 使用有头模式（可见窗口）
    controller = await create_browser_controller(
        browser_type="chromium",
        headless=False,  # 可见模式
        viewport_width=1280,
        viewport_height=720
    )
    
    try:
        print("�?浏览器已启动")
        
        # 导航到页�?
        await controller.navigate("https://www.baidu.com")
        print("�?已导航到百度")
        
        # 等待几秒钟，让用户能看到浏览�?
        print("等待5秒，请观察浏览器窗口...")
        await asyncio.sleep(5)
        
        # 执行JavaScript验证
        title = await controller.execute_javascript("document.title")
        print(f"�?页面标题: {title}")
        
        # 截图验证
        screenshot = await controller.take_screenshot()
        print(f"�?截图成功，大�? {len(screenshot)} bytes")
        
        # 验证截图是有效的PNG
        assert screenshot[:8] == b'\x89PNG\r\n\x1a\n'
        print("�?截图格式正确 (PNG)")
        
        print("\n" + "="*50)
        print("测试完成！浏览器真实运行正常")
        print("="*50 + "\n")
        
    finally:
        await controller.close()
        print("�?浏览器已关闭")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
