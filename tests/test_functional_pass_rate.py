"""
功能测试用例通过率测�?
验证测试用例执行的成功率是否达到90%以上

测试原则（强制执行）�?
1. 真实执行优先：所有测试必须使用真实环境，严禁使用Mock
2. 覆盖率要求：必须执行足够多的测试用例来统计通过�?
3. 测试准确性：测试通过率必�?>= 90%
4. 发现问题优先：测试的目的是发现代码问�?

注意：这些测试使用真实浏览器和真实测试网�?
"""
import sys
import os
import unittest
import asyncio
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.utils.browser_controller_v2 import BrowserControllerV2, BrowserConfig, ScreenshotConfig


class TestFunctionalPassRate(unittest.TestCase):
    """
    功能测试用例通过率测�?
    执行多个测试用例并统计通过�?
    """
    
    # 使用类变量来共享测试结果
    test_results = []
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.test_results = []
    
    @classmethod
    def tearDownClass(cls):
        """测试类清�?""
        pass
    
    def record_result(self, test_name: str, passed: bool, error_msg: str = None):
        """记录测试结果"""
        TestFunctionalPassRate.test_results.append({
            'name': test_name,
            'passed': passed,
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        })
    
    def test_01_navigate_to_website(self):
        """测试1: 访问网站 - 基础功能测试"""
        print("\n🧪 测试1: 访问网站")
        
        async def run_test():
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            try:
                await controller.initialize()
                await controller.navigate("https://example.com")
                
                # 验证页面加载成功
                page_info = await controller.get_page_info()
                self.assertIsNotNone(page_info)
                self.assertIn('title', page_info)
                
                self.record_result("访问网站", True)
                print("�?测试1通过: 访问网站成功")
                
            except Exception as e:
                self.record_result("访问网站", False, str(e))
                raise
            finally:
                await controller.close()
        
        asyncio.run(run_test())
    
    def test_02_take_screenshot(self):
        """测试2: 截图功能"""
        print("\n🧪 测试2: 截图功能")
        
        async def run_test():
            import tempfile
            
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            temp_file = tempfile.mktemp(suffix='.png')
            
            try:
                await controller.initialize()
                await controller.navigate("https://example.com")
                
                # 使用正确的截图配�?
                screenshot_config = ScreenshotConfig(type="png", full_page=False)
                screenshot_bytes = await controller.take_screenshot(screenshot_config)
                
                # 保存截图到文�?
                with open(temp_file, 'wb') as f:
                    f.write(screenshot_bytes)
                
                # 验证截图文件存在
                self.assertTrue(os.path.exists(temp_file))
                self.assertGreater(os.path.getsize(temp_file), 0)
                
                self.record_result("截图功能", True)
                print("�?测试2通过: 截图功能正常")
                
            except Exception as e:
                self.record_result("截图功能", False, str(e))
                raise
            finally:
                await controller.close()
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        
        asyncio.run(run_test())
    
    def test_03_scroll_page(self):
        """测试3: 页面滚动"""
        print("\n🧪 测试3: 页面滚动")
        
        async def run_test():
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            try:
                await controller.initialize()
                await controller.navigate("https://example.com")
                
                # 使用JavaScript滚动页面
                await controller._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.5)
                
                await controller._page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.5)
                
                self.record_result("页面滚动", True)
                print("�?测试3通过: 页面滚动正常")
                
            except Exception as e:
                self.record_result("页面滚动", False, str(e))
                raise
            finally:
                await controller.close()
        
        asyncio.run(run_test())
    
    def test_04_get_page_info(self):
        """测试4: 获取页面信息"""
        print("\n🧪 测试4: 获取页面信息")
        
        async def run_test():
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            try:
                await controller.initialize()
                await controller.navigate("https://example.com")
                
                # 获取页面信息
                page_info = await controller.get_page_info()
                self.assertIsNotNone(page_info)
                self.assertIn('title', page_info)
                self.assertIn('url', page_info)
                self.assertIn("example.com", page_info['url'])
                
                self.record_result("获取页面信息", True)
                print("�?测试4通过: 获取页面信息正常")
                
            except Exception as e:
                self.record_result("获取页面信息", False, str(e))
                raise
            finally:
                await controller.close()
        
        asyncio.run(run_test())
    
    def test_05_wait_for_load(self):
        """测试5: 等待页面加载"""
        print("\n🧪 测试5: 等待页面加载")
        
        async def run_test():
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            try:
                await controller.initialize()
                
                # 导航并等待加载（navigate方法内部已经等待�?
                await controller.navigate("https://example.com")
                
                # 额外等待确保页面完全加载
                await asyncio.sleep(1)
                
                self.record_result("等待页面加载", True)
                print("�?测试5通过: 等待页面加载正常")
                
            except Exception as e:
                self.record_result("等待页面加载", False, str(e))
                raise
            finally:
                await controller.close()
        
        asyncio.run(run_test())
    
    def test_06_multiple_navigations(self):
        """测试6: 多次导航测试"""
        print("\n🧪 测试6: 多次导航测试")
        
        async def run_test():
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            urls = [
                "https://example.com",
                "https://httpbin.org/get",
                "https://httpbin.org/html"
            ]
            
            try:
                await controller.initialize()
                
                for url in urls:
                    await controller.navigate(url)
                    await asyncio.sleep(0.5)
                    
                    # 验证页面加载
                    page_info = await controller.get_page_info()
                    self.assertIsNotNone(page_info)
                
                self.record_result("多次导航", True)
                print("�?测试6通过: 多次导航正常")
                
            except Exception as e:
                self.record_result("多次导航", False, str(e))
                raise
            finally:
                await controller.close()
        
        asyncio.run(run_test())
    
    def test_07_browser_restart(self):
        """测试7: 浏览器重启测�?""
        print("\n🧪 测试7: 浏览器重启测�?)
        
        async def run_test():
            config = BrowserConfig(headless=True)
            
            # 第一次启�?
            controller1 = BrowserControllerV2(config)
            try:
                await controller1.initialize()
                await controller1.navigate("https://example.com")
                await controller1.close()
            except Exception as e:
                await controller1.close()
                raise
            
            # 第二次启�?
            controller2 = BrowserControllerV2(config)
            try:
                await controller2.initialize()
                await controller2.navigate("https://httpbin.org/get")
                await controller2.close()
            except Exception as e:
                await controller2.close()
                raise
            
            self.record_result("浏览器重�?, True)
            print("�?测试7通过: 浏览器重启正�?)
        
        asyncio.run(run_test())
    
    def test_08_error_handling(self):
        """测试8: 错误处理测试"""
        print("\n🧪 测试8: 错误处理测试")
        
        async def run_test():
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            try:
                await controller.initialize()
                
                # 尝试访问不存在的元素（应该抛出异常）
                try:
                    await controller.click(-1, -1)  # 无效的坐�?
                    # 如果没有抛出异常，说明错误处理有问题
                    self.fail("应该抛出异常但未抛出")
                except Exception:
                    # 预期的异常，说明错误处理正常
                    pass
                
                self.record_result("错误处理", True)
                print("�?测试8通过: 错误处理正常")
                
            except Exception as e:
                self.record_result("错误处理", False, str(e))
                raise
            finally:
                await controller.close()
        
        asyncio.run(run_test())
    
    def test_09_viewport_configuration(self):
        """测试9: 视口配置测试"""
        print("\n🧪 测试9: 视口配置测试")
        
        async def run_test():
            # 测试不同的视口大�?
            configs = [
                BrowserConfig(headless=True, viewport_width=1920, viewport_height=1080),
                BrowserConfig(headless=True, viewport_width=1366, viewport_height=768),
                BrowserConfig(headless=True, viewport_width=1280, viewport_height=720),
            ]
            
            for config in configs:
                controller = BrowserControllerV2(config)
                try:
                    await controller.initialize()
                    await controller.navigate("https://example.com")
                    await controller.close()
                except Exception as e:
                    await controller.close()
                    raise
            
            self.record_result("视口配置", True)
            print("�?测试9通过: 视口配置正常")
        
        asyncio.run(run_test())
    
    def test_10_performance_test(self):
        """测试10: 性能测试 - 快速连续操�?""
        print("\n🧪 测试10: 性能测试")
        
        async def run_test():
            import tempfile
            
            config = BrowserConfig(headless=True)
            controller = BrowserControllerV2(config)
            
            temp_dir = tempfile.mkdtemp()
            
            try:
                await controller.initialize()
                
                start_time = datetime.now()
                
                # 快速连续导�?
                for i in range(5):
                    await controller.navigate("https://example.com")
                    screenshot_config = ScreenshotConfig(type="png", full_page=False)
                    screenshot_bytes = await controller.take_screenshot(screenshot_config)
                    
                    # 保存截图
                    temp_file = os.path.join(temp_dir, f'perf_test_{i}.png')
                    with open(temp_file, 'wb') as f:
                        f.write(screenshot_bytes)
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 验证性能�?次导航应该在30秒内完成�?
                self.assertLess(duration, 30, f"性能测试失败：{duration}�?)
                
                self.record_result("性能测试", True)
                print(f"�?测试10通过: 性能测试正常 ({duration:.2f}�?")
                
            except Exception as e:
                self.record_result("性能测试", False, str(e))
                raise
            finally:
                await controller.close()
                # 清理临时文件
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
        asyncio.run(run_test())
    
    def test_99_calculate_pass_rate(self):
        """测试99: 计算通过率统�?""
        print("\n📊 计算通过率统�?)
        
        # 统计结果（使用类变量�?
        total = len(TestFunctionalPassRate.test_results)
        passed = sum(1 for r in TestFunctionalPassRate.test_results if r['passed'])
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"测试统计报告")
        print(f"{'='*60}")
        print(f"总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"通过�? {pass_rate:.2f}%")
        print(f"{'='*60}")
        
        # 显示失败的测�?
        if failed > 0:
            print("\n失败的测�?")
            for result in TestFunctionalPassRate.test_results:
                if not result['passed']:
                    print(f"  - {result['name']}: {result['error']}")
        
        # 验证通过�?>= 90%
        self.assertGreaterEqual(
            pass_rate, 
            90, 
            f"测试通过�?{pass_rate:.2f}% 未达�?90% 要求"
        )
        
        print(f"\n�?通过率达�? {pass_rate:.2f}% >= 90%")


if __name__ == '__main__':
    unittest.main(verbosity=2)
