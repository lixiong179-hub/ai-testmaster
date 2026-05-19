"""
视频录制功能测试
验证浏览器视频录制功能是否正常工作

测试原则：
1. 真实执行优先：所有测试必须使用真实环境，严禁使用Mock
2. 覆盖率要求：核心功能代码覆盖率必须达到95%以上
3. 测试准确性：测试通过率必须 100%
4. 发现问题优先：测试的目的是发现代码问题，避免客户使用时暴露bug
"""
import sys
import os
import unittest
import asyncio
import tempfile
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.utils.browser_controller_v2 import BrowserControllerV2, BrowserConfig, ScreenshotConfig


class TestVideoRecording(unittest.TestCase):
    """视频录制功能测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.video_dir = os.path.join(self.temp_dir, 'videos')
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass
    
    def test_01_video_recording_enabled(self):
        """测试1: 启用视频录制功能"""
        print("\n🧪 测试1: 启用视频录制功能")
        
        async def run_test():
            # 创建浏览器配置，启用视频录制
            config = BrowserConfig(
                headless=True,  # 使用无头模式进行测试
                record_video=True,
                video_dir=self.video_dir,
                video_size=(1280, 720)
            )
            
            # 创建浏览器控制器
            controller = BrowserControllerV2(config)
            
            try:
                # 初始化浏览器
                await controller.initialize()
                
                # 访问测试页面
                await controller.navigate("https://example.com")
                
                # 等待一段时间，确保有视频内容
                await asyncio.sleep(2)
                
                # 关闭浏览器并获取视频路径
                video_path = await controller.close()
                
                # 验证视频文件存在
                self.assertIsNotNone(video_path, "应该返回视频路径")
                self.assertTrue(os.path.exists(video_path), f"视频文件应该存在: {video_path}")
                
                # 验证视频文件大小大于0
                file_size = os.path.getsize(video_path)
                self.assertGreater(file_size, 0, "视频文件大小应该大于0")
                
                # 验证视频文件扩展名
                self.assertTrue(video_path.endswith('.webm'), "视频文件应该是webm格式")
                
                print(f"✅ 测试1通过: 视频录制成功，文件: {video_path}, 大小: {file_size} bytes")
                
            except Exception as e:
                await controller.close()
                raise
        
        # 运行异步测试
        asyncio.run(run_test())
    
    def test_02_video_recording_disabled(self):
        """测试2: 禁用视频录制功能"""
        print("\n🧪 测试2: 禁用视频录制功能")
        
        async def run_test():
            # 创建浏览器配置，禁用视频录制
            config = BrowserConfig(
                headless=True,
                record_video=False
            )
            
            # 创建浏览器控制器
            controller = BrowserControllerV2(config)
            
            try:
                # 初始化浏览器
                await controller.initialize()
                
                # 访问测试页面
                await controller.navigate("https://example.com")
                
                # 等待一段时间
                await asyncio.sleep(1)
                
                # 关闭浏览器并获取视频路径
                video_path = await controller.close()
                
                # 验证没有视频路径
                self.assertIsNone(video_path, "禁用视频录制时应该返回None")
                
                print("✅ 测试2通过: 禁用视频录制时返回None")
                
            except Exception as e:
                await controller.close()
                raise
        
        # 运行异步测试
        asyncio.run(run_test())
    
    def test_03_video_with_interactions(self):
        """测试3: 录制包含交互操作的视频"""
        print("\n🧪 测试3: 录制包含交互操作的视频")
        
        async def run_test():
            # 创建浏览器配置，启用视频录制
            config = BrowserConfig(
                headless=True,
                record_video=True,
                video_dir=self.video_dir,
                video_size=(1280, 720)
            )
            
            # 创建浏览器控制器
            controller = BrowserControllerV2(config)
            
            try:
                # 初始化浏览器
                await controller.initialize()
                
                # 访问测试页面
                await controller.navigate("https://httpbin.org/forms/post")
                
                # 等待页面加载
                await asyncio.sleep(1)
                
                # 尝试填写表单（如果元素存在）
                try:
                    await controller.fill("input[name='custname']", "测试用户")
                    await asyncio.sleep(0.5)
                except:
                    pass  # 元素可能不存在，忽略错误
                
                # 滚动页面到底部
                await controller.execute_javascript("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.5)
                
                # 截图
                screenshot_path = os.path.join(self.temp_dir, 'screenshot.png')
                screenshot_config = ScreenshotConfig(type="png", full_page=False)
                screenshot_bytes = await controller.take_screenshot(screenshot_config)
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot_bytes)
                
                # 关闭浏览器并获取视频路径
                video_path = await controller.close()
                
                # 验证视频文件存在
                self.assertIsNotNone(video_path, "应该返回视频路径")
                self.assertTrue(os.path.exists(video_path), "视频文件应该存在")
                
                # 验证视频文件大小（包含交互操作，应该更大）
                file_size = os.path.getsize(video_path)
                self.assertGreater(file_size, 1000, "包含交互操作的视频应该更大")
                
                # 验证截图也存在
                self.assertTrue(os.path.exists(screenshot_path), "截图文件应该存在")
                
                print(f"✅ 测试3通过: 包含交互操作的视频录制成功，文件大小: {file_size} bytes")
                
            except Exception as e:
                await controller.close()
                raise
        
        # 运行异步测试
        asyncio.run(run_test())
    
    def test_04_video_resolution_config(self):
        """测试4: 视频分辨率配置"""
        print("\n🧪 测试4: 视频分辨率配置")
        
        # 测试不同的分辨率配置
        resolutions = [
            (1920, 1080),  # 1080p
            (1280, 720),   # 720p
            (640, 480),    # 480p
        ]
        
        for width, height in resolutions:
            async def run_test():
                config = BrowserConfig(
                    headless=True,
                    record_video=True,
                    video_dir=self.video_dir,
                    video_size=(width, height)
                )
                
                controller = BrowserControllerV2(config)
                
                try:
                    await controller.initialize()
                    await controller.navigate("https://example.com")
                    await asyncio.sleep(1)
                    video_path = await controller.close()
                    
                    self.assertIsNotNone(video_path, f"分辨率{width}x{height}应该能录制视频")
                    self.assertTrue(os.path.exists(video_path), "视频文件应该存在")
                    
                except Exception as e:
                    await controller.close()
                    raise
            
            asyncio.run(run_test())
        
        print("✅ 测试4通过: 不同分辨率配置都能正常录制视频")


if __name__ == '__main__':
    unittest.main(verbosity=2)
