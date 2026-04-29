"""
Task 0-7 完整端到端测试 V2
使用更准确的选择器，修复多元素匹配问题

测试范围:
- Task 0: 基础架构与核心功能
- Task 1: AI测试用例生成
- Task 2: 测试数据管理
- Task 3: 测试执行任务管理
- Task 4: 测试报告与结果分析
- Task 5: 测试数据生成与管理
- Task 6: 元素定位智能优化
- Task 7: 执行过程可视化与视频录制

注意: 真实测试，严禁使用Mock
"""
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'e2e_test_v2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 测试配置
BASE_URL = "http://localhost:3000"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.test_results = []
        self.console_errors = []
        self.page_errors = []
    
    async def setup(self):
        """初始化浏览器"""
        logger.info("=" * 80)
        logger.info("启动浏览器...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False, slow_mo=100)
        self.context = await self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.page = await self.context.new_page()
        
        # 监听错误
        self.page.on("console", self._handle_console)
        self.page.on("pageerror", self._handle_page_error)
        
        logger.info("✅ 浏览器启动成功")
    
    def _handle_console(self, msg):
        """处理控制台消息"""
        if msg.type == 'error':
            self.console_errors.append(msg.text)
            logger.error(f"[Console Error] {msg.text}")
    
    def _handle_page_error(self, error):
        """处理页面错误"""
        self.page_errors.append(str(error))
        logger.error(f"[Page Error] {error}")
    
    async def teardown(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            logger.info("✅ 浏览器已关闭")
    
    async def log_step(self, step_name: str):
        """记录测试步骤"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 {step_name}")
        logger.info('='*60)
        # 清除之前的错误
        self.console_errors.clear()
        self.page_errors.clear()
    
    async def check_errors(self, context: str = ""):
        """检查是否有错误"""
        has_error = False
        if self.console_errors:
            logger.error(f"{context} - 发现 {len(self.console_errors)} 个控制台错误:")
            for err in self.console_errors[:3]:
                logger.error(f"  - {err}")
            has_error = True
        if self.page_errors:
            logger.error(f"{context} - 发现 {len(self.page_errors)} 个页面错误:")
            for err in self.page_errors[:3]:
                logger.error(f"  - {err}")
            has_error = True
        return has_error
    
    async def login(self):
        """登录系统"""
        await self.log_step("Task 0: 用户登录")
        
        try:
            # 访问登录页面
            logger.info("访问登录页面...")
            await self.page.goto(f"{BASE_URL}/login", wait_until='networkidle')
            await asyncio.sleep(1)
            
            # 检查是否有页面错误
            if await self.check_errors("登录页面加载"):
                return False
            
            # 切换到账号登录（第一个标签）
            logger.info("切换到账号登录...")
            await self.page.locator('.el-tabs__item').first.click()
            await asyncio.sleep(0.5)
            
            # 输入用户名 - 使用更精确的选择器（第一个表单）
            logger.info(f"输入用户名: {ADMIN_USERNAME}")
            await self.page.locator('.el-tab-pane:visible input[placeholder*="账号"]').fill(ADMIN_USERNAME)
            
            # 输入密码
            logger.info("输入密码...")
            await self.page.locator('.el-tab-pane:visible input[placeholder*="密码"]').fill(ADMIN_PASSWORD)
            
            # 输入验证码
            logger.info("输入验证码...")
            await self.page.locator('.el-tab-pane:visible input[placeholder*="验证码"]').fill('1234')
            
            # 点击登录 - 使用可见区域内的按钮
            logger.info("点击登录按钮...")
            await self.page.locator('.el-tab-pane:visible button:has-text("登录")').click()
            
            # 等待登录成功
            logger.info("等待登录成功...")
            await self.page.wait_for_url('**/home**', timeout=10000)
            await asyncio.sleep(1)
            
            # 检查登录后是否有错误
            if await self.check_errors("登录后"):
                return False
            
            # 验证登录成功
            dashboard = await self.page.locator('text=仪表盘').is_visible()
            if dashboard:
                logger.info("✅ 登录成功")
                return True
            else:
                logger.error("❌ 登录失败：未找到仪表盘")
                return False
                
        except Exception as e:
            logger.error(f"❌ 登录失败: {e}")
            await self.page.screenshot(path='screenshots/login_failed.png')
            return False
    
    # =========================================================================
    # Task 0: 基础架构与核心功能
    # =========================================================================
    async def test_task0_basic_architecture(self):
        """Task 0: 基础架构与核心功能测试"""
        await self.log_step("Task 0: 基础架构与核心功能测试")
        
        results = []
        
        # 测试1: 页面导航
        try:
            logger.info("测试页面导航...")
            
            # 导航到项目管理
            logger.info("  导航到项目管理...")
            await self.page.locator('.el-sub-menu:has-text("项目管理")').click()
            await asyncio.sleep(0.5)
            await self.page.locator('.el-menu-item:has-text("项目列表")').click()
            await self.page.wait_for_url('**/project**', timeout=5000)
            await asyncio.sleep(1)
            
            has_error = await self.check_errors("项目管理页面")
            results.append(("项目管理导航", not has_error))
            logger.info(f"  {'✅' if not has_error else '❌'} 项目管理页面")
            
            # 导航到测试用例管理
            logger.info("  导航到测试用例管理...")
            await self.page.locator('.el-sub-menu:has-text("测试用例管理")').click()
            await asyncio.sleep(0.5)
            await self.page.locator('.el-menu-item:has-text("用例列表")').click()
            await self.page.wait_for_url('**/case**', timeout=5000)
            await asyncio.sleep(1)
            
            has_error = await self.check_errors("测试用例页面")
            results.append(("测试用例导航", not has_error))
            logger.info(f"  {'✅' if not has_error else '❌'} 测试用例页面")
            
            # 导航到测试任务管理
            logger.info("  导航到测试任务管理...")
            await self.page.locator('.el-sub-menu:has-text("测试任务管理")').click()
            await asyncio.sleep(0.5)
            await self.page.locator('.el-menu-item:has-text("任务列表")').click()
            await self.page.wait_for_url('**/task**', timeout=5000)
            await asyncio.sleep(1)
            
            has_error = await self.check_errors("测试任务页面")
            results.append(("测试任务导航", not has_error))
            logger.info(f"  {'✅' if not has_error else '❌'} 测试任务页面")
            
            # 导航到测试报告
            logger.info("  导航到测试报告...")
            await self.page.locator('.el-menu-item:has-text("测试报告")').click()
            await self.page.wait_for_url('**/report**', timeout=5000)
            await asyncio.sleep(1)
            
            has_error = await self.check_errors("测试报告页面")
            results.append(("测试报告导航", not has_error))
            logger.info(f"  {'✅' if not has_error else '❌'} 测试报告页面")
            
        except Exception as e:
            logger.error(f"❌ 页面导航测试失败: {e}")
            results.append(("页面导航", False))
        
        return results
    
    # =========================================================================
    # Task 1: AI测试用例生成
    # =========================================================================
    async def test_task1_ai_case_generation(self):
        """Task 1: AI测试用例生成功能测试"""
        await self.log_step("Task 1: AI测试用例生成功能测试")
        
        results = []
        
        try:
            # 导航到AI生成用例页面
            logger.info("导航到AI生成用例页面...")
            await self.page.locator('.el-sub-menu:has-text("测试用例管理")').click()
            await asyncio.sleep(0.5)
            await self.page.locator('.el-menu-item:has-text("AI生成用例")').click()
            await self.page.wait_for_url('**/case/ai-generate**', timeout=5000)
            await asyncio.sleep(1)
            
            has_error = await self.check_errors("AI生成用例页面")
            
            # 检查页面元素
            logger.info("检查页面元素...")
            title_visible = await self.page.locator('h2:has-text("AI生成测试用例")').is_visible()
            form_visible = await self.page.locator('.el-form').is_visible()
            
            if title_visible and form_visible and not has_error:
                logger.info("  ✅ AI生成用例页面正常")
                results.append(("AI生成页面", True))
            else:
                logger.error(f"  ❌ AI生成用例页面异常 (title={title_visible}, form={form_visible}, error={has_error})")
                results.append(("AI生成页面", False))
                
        except Exception as e:
            logger.error(f"❌ AI测试用例生成测试失败: {e}")
            results.append(("AI生成用例功能", False))
        
        return results
    
    # =========================================================================
    # Task 2: 测试数据管理
    # =========================================================================
    async def test_task2_test_data_management(self):
        """Task 2: 测试数据管理功能测试"""
        await self.log_step("Task 2: 测试数据管理功能测试")
        
        results = []
        
        try:
            # 导航到用例列表 - 使用正确的路由路径
            logger.info("导航到用例列表...")
            await self.page.goto(f"{BASE_URL}/home/case")
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
            
            has_error = await self.check_errors("用例列表页面")
            
            # 检查页面是否正常加载
            page_ok = await self.page.locator('.test-case-list, .el-card').first.is_visible()
            title_ok = await self.page.locator('h2:has-text("测试用例列表")').is_visible()
            
            if page_ok and title_ok and not has_error:
                logger.info("  ✅ 用例列表页面正常")
                results.append(("用例列表页面", True))
            else:
                logger.error(f"  ❌ 用例列表页面异常 (page={page_ok}, title={title_ok})")
                results.append(("用例列表页面", False))
                
        except Exception as e:
            logger.error(f"❌ 测试数据管理测试失败: {e}")
            results.append(("测试数据管理", False))
        
        return results
    
    # =========================================================================
    # Task 3: 测试执行任务管理
    # =========================================================================
    async def test_task3_test_task_management(self):
        """Task 3: 测试执行任务管理测试"""
        await self.log_step("Task 3: 测试执行任务管理测试")
        
        results = []
        
        try:
            # 导航到任务列表 - 使用正确的路由路径
            logger.info("导航到任务列表...")
            await self.page.goto(f"{BASE_URL}/home/task")
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
            
            has_error = await self.check_errors("任务列表页面")
            
            # 检查页面是否正常
            page_ok = await self.page.locator('.task-list, .el-card').first.is_visible()
            title_ok = await self.page.locator('text=测试任务列表').is_visible()
            
            if page_ok and title_ok and not has_error:
                logger.info("  ✅ 任务列表页面正常")
                results.append(("任务列表页面", True))
            else:
                logger.error(f"  ❌ 任务列表页面异常 (page={page_ok}, title={title_ok})")
                results.append(("任务列表页面", False))
                
        except Exception as e:
            logger.error(f"❌ 测试任务管理测试失败: {e}")
            results.append(("测试任务管理", False))
        
        return results
    
    # =========================================================================
    # Task 4: 测试报告与结果分析
    # =========================================================================
    async def test_task4_test_report(self):
        """Task 4: 测试报告与结果分析测试"""
        await self.log_step("Task 4: 测试报告与结果分析测试")
        
        results = []
        
        try:
            # 导航到测试报告 - 使用正确的路由路径
            logger.info("导航到测试报告...")
            await self.page.goto(f"{BASE_URL}/home/report")
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
            
            has_error = await self.check_errors("测试报告页面")
            
            # 检查页面是否正常
            page_ok = await self.page.locator('.report-list, .el-card').first.is_visible()
            title_ok = await self.page.locator('text=测试报告列表').is_visible()
            
            if page_ok and title_ok and not has_error:
                logger.info("  ✅ 测试报告页面正常")
                results.append(("测试报告页面", True))
            else:
                logger.error(f"  ❌ 测试报告页面异常 (page={page_ok}, title={title_ok})")
                results.append(("测试报告页面", False))
                
        except Exception as e:
            logger.error(f"❌ 测试报告测试失败: {e}")
            results.append(("测试报告", False))
        
        return results
    
    # =========================================================================
    # Task 5: 测试数据生成与管理
    # =========================================================================
    async def test_task5_test_data_generation(self):
        """Task 5: 测试数据生成与管理测试"""
        await self.log_step("Task 5: 测试数据生成与管理测试")
        
        results = []
        
        try:
            # 直接导航到需求管理页面
            logger.info("导航到需求管理...")
            await self.page.goto(f"{BASE_URL}/home/requirement")
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
            
            has_error = await self.check_errors("需求管理页面")
            
            # 检查页面是否正常
            page_ok = await self.page.locator('.el-card').first.is_visible()
            title_ok = await self.page.locator('.card-header:has-text("需求列表")').is_visible()
            
            if page_ok and title_ok and not has_error:
                logger.info("  ✅ 需求管理页面正常")
                results.append(("需求管理页面", True))
            else:
                logger.error(f"  ❌ 需求管理页面异常 (page={page_ok}, title={title_ok})")
                results.append(("需求管理页面", False))
                
        except Exception as e:
            logger.error(f"❌ 测试数据生成测试失败: {e}")
            results.append(("测试数据生成", False))
        
        return results
    
    # =========================================================================
    # Task 6: 元素定位智能优化
    # =========================================================================
    async def test_task6_element_locator(self):
        """Task 6: 元素定位智能优化测试"""
        await self.log_step("Task 6: 元素定位智能优化测试")
        
        results = []
        
        try:
            # 导航到用例列表
            logger.info("导航到用例列表...")
            await self.page.goto(f"{BASE_URL}/case")
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(1)
            
            has_error = await self.check_errors("元素定位页面")
            
            if not has_error:
                logger.info("  ✅ 元素定位页面正常")
                results.append(("元素定位页面", True))
            else:
                logger.error(f"  ❌ 元素定位页面有错误")
                results.append(("元素定位页面", False))
                
        except Exception as e:
            logger.error(f"❌ 元素定位智能优化测试失败: {e}")
            results.append(("元素定位优化", False))
        
        return results
    
    # =========================================================================
    # Task 7: 执行过程可视化与视频录制
    # =========================================================================
    async def test_task7_execution_visualization(self):
        """Task 7: 执行过程可视化与视频录制测试"""
        await self.log_step("Task 7: 执行过程可视化与视频录制测试")
        
        results = []
        
        try:
            # 导航到任务列表
            logger.info("导航到任务列表...")
            await self.page.goto(f"{BASE_URL}/task")
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(1)
            
            has_error = await self.check_errors("执行可视化页面")
            
            if not has_error:
                logger.info("  ✅ 执行可视化页面正常")
                results.append(("执行可视化页面", True))
            else:
                logger.error(f"  ❌ 执行可视化页面有错误")
                results.append(("执行可视化页面", False))
                
        except Exception as e:
            logger.error(f"❌ 执行过程可视化测试失败: {e}")
            results.append(("执行可视化", False))
        
        return results
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "=" * 80)
        logger.info("开始 Task 0-7 完整端到端测试 V2")
        logger.info("=" * 80)
        
        # 初始化
        await self.setup()
        
        # 登录
        login_success = await self.login()
        if not login_success:
            logger.error("登录失败，终止测试")
            await self.teardown()
            return
        
        all_results = []
        
        # Task 0: 基础架构
        results = await self.test_task0_basic_architecture()
        all_results.extend([(f"Task 0: {name}", status) for name, status in results])
        
        # Task 1: AI测试用例生成
        results = await self.test_task1_ai_case_generation()
        all_results.extend([(f"Task 1: {name}", status) for name, status in results])
        
        # Task 2: 测试数据管理
        results = await self.test_task2_test_data_management()
        all_results.extend([(f"Task 2: {name}", status) for name, status in results])
        
        # Task 3: 测试任务管理
        results = await self.test_task3_test_task_management()
        all_results.extend([(f"Task 3: {name}", status) for name, status in results])
        
        # Task 4: 测试报告
        results = await self.test_task4_test_report()
        all_results.extend([(f"Task 4: {name}", status) for name, status in results])
        
        # Task 5: 测试数据生成
        results = await self.test_task5_test_data_generation()
        all_results.extend([(f"Task 5: {name}", status) for name, status in results])
        
        # Task 6: 元素定位优化
        results = await self.test_task6_element_locator()
        all_results.extend([(f"Task 6: {name}", status) for name, status in results])
        
        # Task 7: 执行可视化
        results = await self.test_task7_execution_visualization()
        all_results.extend([(f"Task 7: {name}", status) for name, status in results])
        
        # 清理
        await self.teardown()
        
        # 输出测试报告
        await self.print_test_report(all_results)
    
    async def print_test_report(self, results):
        """打印测试报告"""
        logger.info("\n" + "=" * 80)
        logger.info("测试报告")
        logger.info("=" * 80)
        
        passed = sum(1 for _, status in results if status)
        total = len(results)
        
        for name, status in results:
            icon = "✅" if status else "❌"
            logger.info(f"{icon} {name}")
        
        logger.info("=" * 80)
        logger.info(f"总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
        logger.info("=" * 80)
        
        if passed == total:
            logger.info("🎉 所有测试通过！")
        else:
            logger.warning(f"⚠️  有 {total - passed} 个测试失败")


async def main():
    """主函数"""
    runner = TestRunner()
    await runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
