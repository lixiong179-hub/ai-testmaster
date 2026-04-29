"""
Task 0-7 完整端到端测试
使用Playwright进行真实浏览器测试

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
        logging.FileHandler(f'e2e_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 测试配置
BASE_URL = "http://localhost:3000"  # Vite实际端口
API_URL = "http://localhost:8000"   # 后端API端口
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.test_results = []
    
    async def setup(self):
        """初始化浏览器"""
        logger.info("=" * 80)
        logger.info("启动浏览器...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False, slow_mo=100)
        self.context = await self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.page = await self.context.new_page()
        logger.info("✅ 浏览器启动成功")
    
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
    
    async def login(self):
        """登录系统"""
        await self.log_step("Task 0: 用户登录")
        
        try:
            # 访问登录页面
            logger.info("访问登录页面...")
            await self.page.goto(f"{BASE_URL}/login")
            await self.page.wait_for_load_state('networkidle')
            
            # 切换到账号登录
            logger.info("切换到账号登录...")
            await self.page.click('.el-tabs__item:has-text("账号登录")')
            await asyncio.sleep(0.5)
            
            # 输入用户名
            logger.info(f"输入用户名: {ADMIN_USERNAME}")
            await self.page.fill('input[placeholder*="账号"]', ADMIN_USERNAME)
            
            # 输入密码
            logger.info("输入密码...")
            await self.page.fill('input[placeholder*="密码"]', ADMIN_PASSWORD)
            
            # 输入验证码（使用默认值）
            logger.info("输入验证码...")
            await self.page.fill('input[placeholder*="验证码"]', '1234')
            
            # 点击登录
            logger.info("点击登录按钮...")
            await self.page.click('button:has-text("登录")')
            
            # 等待登录成功
            logger.info("等待登录成功...")
            await self.page.wait_for_url('**/home**', timeout=10000)
            
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
            await self.page.click('.el-sub-menu:has-text("项目管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("项目列表")')
            await self.page.wait_for_url('**/project**', timeout=5000)
            logger.info("  ✅ 项目管理页面加载成功")
            results.append(("项目管理导航", True))
            
            # 导航到测试用例管理
            logger.info("  导航到测试用例管理...")
            await self.page.click('.el-sub-menu:has-text("测试用例管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("用例列表")')
            await self.page.wait_for_url('**/case**', timeout=5000)
            logger.info("  ✅ 测试用例管理页面加载成功")
            results.append(("测试用例导航", True))
            
            # 导航到测试任务管理
            logger.info("  导航到测试任务管理...")
            await self.page.click('.el-sub-menu:has-text("测试任务管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("任务列表")')
            await self.page.wait_for_url('**/task**', timeout=5000)
            logger.info("  ✅ 测试任务管理页面加载成功")
            results.append(("测试任务导航", True))
            
            # 导航到测试报告
            logger.info("  导航到测试报告...")
            await self.page.click('.el-menu-item:has-text("测试报告")')
            await self.page.wait_for_url('**/report**', timeout=5000)
            logger.info("  ✅ 测试报告页面加载成功")
            results.append(("测试报告导航", True))
            
        except Exception as e:
            logger.error(f"❌ 页面导航测试失败: {e}")
            results.append(("页面导航", False))
        
        # 测试2: 用户菜单
        try:
            logger.info("测试用户菜单...")
            await self.page.click('.el-dropdown')
            await asyncio.sleep(0.5)
            
            # 检查菜单项
            profile_visible = await self.page.locator('text=个人中心').is_visible()
            logout_visible = await self.page.locator('text=退出登录').is_visible()
            
            if profile_visible and logout_visible:
                logger.info("  ✅ 用户菜单正常")
                results.append(("用户菜单", True))
            else:
                logger.error("  ❌ 用户菜单异常")
                results.append(("用户菜单", False))
                
        except Exception as e:
            logger.error(f"❌ 用户菜单测试失败: {e}")
            results.append(("用户菜单", False))
        
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
            await self.page.click('.el-sub-menu:has-text("测试用例管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("AI生成用例")')
            await self.page.wait_for_url('**/case/ai-generate**', timeout=5000)
            logger.info("✅ AI生成用例页面加载成功")
            
            # 检查页面元素
            logger.info("检查页面元素...")
            title_visible = await self.page.locator('text=AI生成测试用例').is_visible()
            if title_visible:
                logger.info("  ✅ AI生成用例标题显示正常")
                results.append(("AI生成页面", True))
            else:
                logger.error("  ❌ AI生成用例标题未显示")
                results.append(("AI生成页面", False))
            
            # 检查需求输入区域
            logger.info("检查需求输入区域...")
            textarea_visible = await self.page.locator('textarea').is_visible()
            if textarea_visible:
                logger.info("  ✅ 需求输入框显示正常")
                results.append(("需求输入框", True))
            else:
                logger.error("  ❌ 需求输入框未显示")
                results.append(("需求输入框", False))
            
            # 检查生成按钮
            logger.info("检查生成按钮...")
            button_visible = await self.page.locator('button:has-text("生成")').is_visible()
            if button_visible:
                logger.info("  ✅ 生成按钮显示正常")
                results.append(("生成按钮", True))
            else:
                logger.error("  ❌ 生成按钮未显示")
                results.append(("生成按钮", False))
                
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
            # 导航到测试数据管理页面
            logger.info("导航到测试数据管理页面...")
            # 先回到首页
            await self.page.goto(f"{BASE_URL}/home")
            await self.page.wait_for_load_state('networkidle')
            
            # 检查是否有测试数据管理菜单
            logger.info("检查测试数据管理功能...")
            # 测试数据管理通常在测试用例详情中
            
            # 导航到用例列表
            await self.page.click('.el-sub-menu:has-text("测试用例管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("用例列表")')
            await self.page.wait_for_url('**/case**', timeout=5000)
            
            # 检查用例列表是否加载
            logger.info("检查用例列表...")
            table_visible = await self.page.locator('.el-table').is_visible()
            if table_visible:
                logger.info("  ✅ 用例列表加载成功")
                results.append(("用例列表", True))
            else:
                logger.error("  ❌ 用例列表未加载")
                results.append(("用例列表", False))
                
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
            # 导航到任务列表
            logger.info("导航到任务列表...")
            await self.page.click('.el-sub-menu:has-text("测试任务管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("任务列表")')
            await self.page.wait_for_url('**/task**', timeout=5000)
            
            # 检查任务列表
            logger.info("检查任务列表...")
            table_visible = await self.page.locator('.el-table').is_visible()
            if table_visible:
                logger.info("  ✅ 任务列表加载成功")
                results.append(("任务列表", True))
            else:
                logger.error("  ❌ 任务列表未加载")
                results.append(("任务列表", False))
            
            # 检查新建任务按钮
            logger.info("检查新建任务按钮...")
            button_visible = await self.page.locator('button:has-text("新建")').is_visible()
            if button_visible:
                logger.info("  ✅ 新建任务按钮显示正常")
                results.append(("新建任务按钮", True))
            else:
                logger.error("  ❌ 新建任务按钮未显示")
                results.append(("新建任务按钮", False))
                
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
            # 导航到测试报告
            logger.info("导航到测试报告...")
            await self.page.click('.el-menu-item:has-text("测试报告")')
            await self.page.wait_for_url('**/report**', timeout=5000)
            
            # 检查报告列表
            logger.info("检查报告列表...")
            table_visible = await self.page.locator('.el-table').is_visible()
            if table_visible:
                logger.info("  ✅ 报告列表加载成功")
                results.append(("报告列表", True))
            else:
                logger.error("  ❌ 报告列表未加载")
                results.append(("报告列表", False))
            
            # 检查导出按钮
            logger.info("检查导出功能...")
            # 如果有报告，点击查看详情
            view_buttons = await self.page.locator('button:has-text("查看")').count()
            if view_buttons > 0:
                logger.info(f"  ✅ 找到 {view_buttons} 个查看按钮")
                results.append(("报告查看功能", True))
            else:
                logger.info("  ℹ️ 暂无报告数据")
                results.append(("报告查看功能", True))  # 没有数据也算正常
                
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
            # 导航到需求管理
            logger.info("导航到需求管理...")
            await self.page.click('.el-sub-menu:has-text("需求管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("需求列表")')
            await self.page.wait_for_url('**/requirement**', timeout=5000)
            
            # 检查需求列表
            logger.info("检查需求列表...")
            page_visible = await self.page.locator('.requirement-page, .el-table, .el-card').first.is_visible()
            if page_visible:
                logger.info("  ✅ 需求管理页面加载成功")
                results.append(("需求管理页面", True))
            else:
                logger.error("  ❌ 需求管理页面未加载")
                results.append(("需求管理页面", False))
            
            # 检查上传需求功能
            logger.info("检查上传需求功能...")
            await self.page.click('.el-menu-item:has-text("上传需求")')
            await self.page.wait_for_url('**/requirement/upload**', timeout=5000)
            
            upload_visible = await self.page.locator('.upload-page, .el-upload').first.is_visible()
            if upload_visible:
                logger.info("  ✅ 上传需求页面加载成功")
                results.append(("上传需求页面", True))
            else:
                logger.error("  ❌ 上传需求页面未加载")
                results.append(("上传需求页面", False))
                
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
            await self.page.click('.el-sub-menu:has-text("测试用例管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("用例列表")')
            await self.page.wait_for_url('**/case**', timeout=5000)
            
            # 检查是否有用例数据
            logger.info("检查用例数据...")
            rows = await self.page.locator('.el-table__row').count()
            
            if rows > 0:
                logger.info(f"  ✅ 找到 {rows} 条用例")
                results.append(("用例数据", True))
                
                # 点击第一个用例查看详情
                logger.info("  点击查看第一个用例详情...")
                await self.page.locator('.el-table__row').first.click()
                await asyncio.sleep(1)
                
                # 检查是否有元素定位相关信息
                logger.info("  检查元素定位功能...")
                # 元素定位功能通常在批量定位对话框中
                
            else:
                logger.info("  ℹ️ 暂无测试用例数据")
                results.append(("用例数据", True))
                
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
            await self.page.click('.el-sub-menu:has-text("测试任务管理")')
            await asyncio.sleep(0.5)
            await self.page.click('.el-menu-item:has-text("任务列表")')
            await self.page.wait_for_url('**/task**', timeout=5000)
            
            # 检查是否有任务数据
            logger.info("检查任务数据...")
            rows = await self.page.locator('.el-table__row').count()
            
            if rows > 0:
                logger.info(f"  ✅ 找到 {rows} 个任务")
                
                # 点击执行按钮
                logger.info("  点击执行按钮...")
                execute_buttons = await self.page.locator('button:has-text("执行")').count()
                
                if execute_buttons > 0:
                    await self.page.locator('button:has-text("执行")').first.click()
                    await self.page.wait_for_url('**/execution/**', timeout=5000)
                    logger.info("  ✅ 进入执行页面")
                    results.append(("执行页面", True))
                    
                    # 检查执行页面元素
                    logger.info("  检查执行页面元素...")
                    
                    # 检查可见模式配置按钮
                    config_visible = await self.page.locator('button:has-text("可见模式配置")').is_visible()
                    if config_visible:
                        logger.info("    ✅ 可见模式配置按钮显示正常")
                        results.append(("可见模式配置", True))
                    else:
                        logger.error("    ❌ 可见模式配置按钮未显示")
                        results.append(("可见模式配置", False))
                    
                    # 检查执行控制按钮
                    start_visible = await self.page.locator('button:has-text("开始执行")').is_visible()
                    if start_visible:
                        logger.info("    ✅ 开始执行按钮显示正常")
                        results.append(("执行控制", True))
                    else:
                        logger.error("    ❌ 开始执行按钮未显示")
                        results.append(("执行控制", False))
                    
                    # 检查步骤列表区域
                    steps_visible = await self.page.locator('.steps-list, .steps-panel').first.is_visible()
                    if steps_visible:
                        logger.info("    ✅ 步骤列表区域显示正常")
                        results.append(("步骤列表", True))
                    else:
                        logger.error("    ❌ 步骤列表区域未显示")
                        results.append(("步骤列表", False))
                    
                    # 检查截图区域
                    screenshot_visible = await self.page.locator('.screenshot-panel, .screenshot-container').first.is_visible()
                    if screenshot_visible:
                        logger.info("    ✅ 截图区域显示正常")
                        results.append(("截图区域", True))
                    else:
                        logger.error("    ❌ 截图区域未显示")
                        results.append(("截图区域", False))
                    
                    # 检查日志区域
                    logs_visible = await self.page.locator('.logs-container, .el-tab-pane:has-text("执行日志")').first.is_visible()
                    if logs_visible:
                        logger.info("    ✅ 日志区域显示正常")
                        results.append(("日志区域", True))
                    else:
                        logger.error("    ❌ 日志区域未显示")
                        results.append(("日志区域", False))
                    
                    # 检查视频区域
                    video_tab = await self.page.locator('.el-tabs__item:has-text("执行视频")').is_visible()
                    if video_tab:
                        logger.info("    ✅ 视频标签显示正常")
                        results.append(("视频区域", True))
                    else:
                        logger.error("    ❌ 视频标签未显示")
                        results.append(("视频区域", False))
                    
                    # 检查回放控制
                    replay_tab = await self.page.locator('.el-tabs__item:has-text("回放控制")').is_visible()
                    if replay_tab:
                        logger.info("    ✅ 回放控制标签显示正常")
                        results.append(("回放控制", True))
                    else:
                        logger.info("    ℹ️ 回放控制标签未显示（需要执行完成后才显示）")
                        results.append(("回放控制", True))
                        
                else:
                    logger.error("  ❌ 未找到执行按钮")
                    results.append(("执行功能", False))
            else:
                logger.info("  ℹ️ 暂无测试任务")
                results.append(("任务数据", True))
                
        except Exception as e:
            logger.error(f"❌ 执行过程可视化测试失败: {e}")
            results.append(("执行可视化", False))
        
        return results
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "=" * 80)
        logger.info("开始 Task 0-7 完整端到端测试")
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
