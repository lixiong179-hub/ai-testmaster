"""
调试测试 - 检查页面实际错误
"""
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:3000"

async def check_page_errors():
    """检查页面错误"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # 监听控制台错误
        page = await context.new_page()
        
        console_errors = []
        page_errors = []
        
        async def handle_console(msg):
            if msg.type == 'error':
                console_errors.append(f"[Console {msg.type}] {msg.text}")
                logger.error(f"控制台错误: {msg.text}")
        
        async def handle_page_error(error):
            page_errors.append(f"[Page Error] {error}")
            logger.error(f"页面错误: {error}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_page_error)
        
        try:
            # 访问登录页面
            logger.info("=" * 60)
            logger.info("检查登录页面...")
            logger.info("=" * 60)
            
            await page.goto(f"{BASE_URL}/login", wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)
            
            # 检查页面是否加载成功
            title = await page.title()
            logger.info(f"页面标题: {title}")
            
            # 检查是否有错误提示
            error_selectors = [
                '.el-message--error',
                '.error-message',
                '[class*="error"]',
                '.exception',
                '.ant-result-title:has-text("Error")'
            ]
            
            for selector in error_selectors:
                try:
                    visible = await page.locator(selector).is_visible(timeout=1000)
                    if visible:
                        text = await page.locator(selector).inner_text()
                        logger.error(f"发现错误元素 [{selector}]: {text}")
                except:
                    pass
            
            # 检查登录表单
            logger.info("检查登录表单元素...")
            form_elements = {
                '账号输入框': 'input[placeholder*="账号"]',
                '密码输入框': 'input[placeholder*="密码"]',
                '验证码输入框': 'input[placeholder*="验证码"]',
                '登录按钮': 'button:has-text("登录")',
            }
            
            for name, selector in form_elements.items():
                try:
                    visible = await page.locator(selector).is_visible(timeout=2000)
                    count = await page.locator(selector).count()
                    logger.info(f"  {name}: {'✅' if visible else '❌'} (找到 {count} 个)")
                except Exception as e:
                    logger.error(f"  {name}: ❌ 错误: {e}")
            
            # 尝试登录
            logger.info("\n尝试登录...")
            await page.fill('input[placeholder*="账号"]', 'admin')
            await page.fill('input[placeholder*="密码"]', 'password123')
            await page.fill('input[placeholder*="验证码"]', '1234')
            
            # 清除之前的错误
            console_errors.clear()
            page_errors.clear()
            
            await page.click('button:has-text("登录")')
            await asyncio.sleep(3)
            
            # 检查登录后的页面
            current_url = page.url
            logger.info(f"登录后URL: {current_url}")
            
            # 检查是否登录成功
            if '/home' in current_url:
                logger.info("✅ 登录成功，进入首页")
                
                # 检查首页元素
                logger.info("\n检查首页元素...")
                home_elements = {
                    '仪表盘标题': 'text=仪表盘',
                    '菜单栏': '.el-menu',
                    '用户信息': '.el-dropdown',
                }
                
                for name, selector in home_elements.items():
                    try:
                        visible = await page.locator(selector).is_visible(timeout=2000)
                        logger.info(f"  {name}: {'✅' if visible else '❌'}")
                    except:
                        logger.error(f"  {name}: ❌")
                
                # 检查各功能页面
                pages_to_check = [
                    ('项目管理', '/project', ['项目列表', '.el-table']),
                    ('测试用例', '/case', ['用例列表', '.el-table']),
                    ('测试任务', '/task', ['任务列表', '.el-table']),
                    ('测试报告', '/report', ['报告列表', '.el-table']),
                ]
                
                for page_name, path, check_elements in pages_to_check:
                    logger.info(f"\n检查 {page_name} 页面...")
                    
                    # 清除错误
                    console_errors.clear()
                    page_errors.clear()
                    
                    await page.goto(f"{BASE_URL}{path}", wait_until='networkidle', timeout=10000)
                    await asyncio.sleep(2)
                    
                    # 检查控制台错误
                    if console_errors:
                        logger.error(f"  控制台错误 ({len(console_errors)}个):")
                        for err in console_errors[:3]:
                            logger.error(f"    - {err}")
                    else:
                        logger.info("  ✅ 无控制台错误")
                    
                    # 检查页面错误
                    if page_errors:
                        logger.error(f"  页面错误 ({len(page_errors)}个):")
                        for err in page_errors[:3]:
                            logger.error(f"    - {err}")
                    
                    # 检查关键元素
                    for element_name in check_elements:
                        try:
                            visible = await page.locator(f'text={element_name}').is_visible(timeout=1000)
                            if visible:
                                logger.info(f"  ✅ 找到: {element_name}")
                            else:
                                logger.warning(f"  ⚠️ 未找到: {element_name}")
                        except:
                            logger.error(f"  ❌ 检查失败: {element_name}")
                    
                    # 检查API错误
                    error_messages = await page.locator('.el-message--error').count()
                    if error_messages > 0:
                        logger.error(f"  ❌ 发现 {error_messages} 个错误消息")
            else:
                logger.error("❌ 登录失败，未跳转到首页")
                
                # 检查错误提示
                error_msg = await page.locator('.el-message--error').inner_text().catch(lambda: '')
                if error_msg:
                    logger.error(f"错误提示: {error_msg}")
        
        except Exception as e:
            logger.error(f"测试执行错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        finally:
            await browser.close()
            
            # 输出总结
            logger.info("\n" + "=" * 60)
            logger.info("测试总结")
            logger.info("=" * 60)
            logger.info(f"控制台错误总数: {len(console_errors)}")
            logger.info(f"页面错误总数: {len(page_errors)}")

if __name__ == "__main__":
    asyncio.run(check_page_errors())
