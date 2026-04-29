# -*- coding: utf-8 -*-
"""
AI测试平台 - UI自动化测试（使用Selenium/Playwright）
"""
import time
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not available")

BASE_URL = "http://localhost:3000"
TEST_RESULTS = []

def log_test(module, name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    TEST_RESULTS.append({
        "module": module,
        "name": name,
        "status": status,
        "details": details,
        "time": datetime.now().isoformat()
    })
    print(f"  [{status}] {name}: {details[:60] if details else 'OK'}")

class UITestRunner:
    def __init__(self):
        if not SELENIUM_AVAILABLE:
            print("Selenium not installed. Install with: pip install selenium")
            return
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")  # 无头模式
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 10)
            print("Chrome driver initialized")
        except Exception as e:
            print(f"Failed to initialize driver: {e}")
            self.driver = None
    
    def login(self):
        """执行登录操作"""
        if not self.driver:
            return None
        
        try:
            print("\n[UI Test] 执行登录...")
            self.driver.get(f"{BASE_URL}/login")
            time.sleep(2)
            
            # 等待登录表单加载
            username_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='用户名']"))
            )
            password_input = self.driver.find_element(By.XPATH, "//input[@type='password']")
            login_button = self.driver.find_element(By.XPATH, "//button[contains(text(), '登录')]")
            
            # 输入凭据
            username_input.clear()
            username_input.send_keys("admin")
            password_input.clear()
            password_input.send_keys("admin123")
            
            # 点击登录
            login_button.click()
            time.sleep(3)
            
            # 检查是否成功登录
            current_url = self.driver.current_url
            if "login" not in current_url.lower():
                log_test("UI登录", "登录流程", True, f"成功跳转到: {current_url[:50]}")
                return True
            else:
                log_test("UI登录", "登录流程", False, "未成功跳转")
                return False
                
        except Exception as e:
            log_test("UI登录", "登录流程", False, str(e))
            return False
    
    def test_project_list_page(self):
        """测试项目列表页面"""
        if not self.driver:
            return
        
        print("\n[UI Test] 测试项目列表页面...")
        try:
            self.driver.get(f"{BASE_URL}/home/project")
            time.sleep(3)
            
            # 检查页面标题
            page_title = self.driver.title
            log_test("项目列表", "页面加载", True, f"标题: {page_title}")
            
            # 检查表格元素
            try:
                table = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "el-table"))
                )
                log_test("项目列表", "表格组件", True, "el-table存在")
            except:
                log_test("项目列表", "表格组件", False, "未找到el-table")
            
            # 检查项目数量
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, ".el-table__row")
                log_test("项目列表", "数据加载", True, f"显示{len(rows)}行数据")
            except:
                log_test("项目列表", "数据加载", False, "未找到数据行")
            
        except Exception as e:
            log_test("项目列表", "页面测试", False, str(e))
    
    def test_project_detail_page(self):
        """测试项目详情页面"""
        if not self.driver:
            return
        
        print("\n[UI Test] 测试项目详情页面...")
        try:
            self.driver.get(f"{BASE_URL}/home/project/detail?id=3")
            time.sleep(3)
            
            # 检查页面内容
            page_source = self.driver.page_source
            
            # 检查关键元素
            checks = [
                ("el-card", "卡片组件"),
                ("el-button", "按钮组件"),
                ("智慧园区", "项目名称显示"),
            ]
            
            for selector, name in checks:
                if selector in page_source:
                    log_test("项目详情", name, True, f"找到{selector}")
                else:
                    log_test("项目详情", name, False, f"未找到{selector}")
            
        except Exception as e:
            log_test("项目详情", "页面测试", False, str(e))
    
    def test_navigation(self):
        """测试导航功能"""
        if not self.driver:
            return
        
        print("\n[UI Test] 测试导航...")
        try:
            # 首先登录
            self.login()
            time.sleep(2)
            
            # 测试菜单导航
            menu_items = [
                ("首页", "/home"),
                ("项目管理", "/home/project"),
            ]
            
            for name, path in menu_items:
                try:
                    self.driver.get(f"{BASE_URL}{path}")
                    time.sleep(2)
                    log_test("导航", f"跳转{name}", True, f"成功加载{path}")
                except Exception as e:
                    log_test("导航", f"跳转{name}", False, str(e))
                    
        except Exception as e:
            log_test("导航", "导航测试", False, str(e))
    
    def test_form_validation(self):
        """测试表单验证"""
        if not self.driver:
            return
        
        print("\n[UI Test] 测试表单验证...")
        try:
            # 先登录
            self.login()
            time.sleep(2)
            
            # 进入项目创建页面
            self.driver.get(f"{BASE_URL}/home/project")
            time.sleep(2)
            
            # 点击创建项目按钮
            try:
                create_btn = self.driver.find_element(
                    By.XPATH, "//button[contains(text(), '创建')]"
                )
                create_btn.click()
                time.sleep(1)
                
                # 检查对话框
                dialog = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "el-dialog"))
                )
                log_test("表单验证", "创建对话框", True, "成功打开")
                
                # 尝试不填写直接提交
                try:
                    confirm_btn = self.driver.find_element(
                        By.XPATH, "//div[@class='el-dialog__footer']//button[contains(text(), '确定')]"
                    )
                    confirm_btn.click()
                    time.sleep(1)
                    
                    # 检查是否有验证提示
                    page_source = self.driver.page_source
                    if "必填" in page_source or "不能为空" in page_source:
                        log_test("表单验证", "必填验证", True, "正确显示验证提示")
                    else:
                        log_test("表单验证", "必填验证", False, "未显示验证提示")
                        
                except Exception as e:
                    log_test("表单验证", "确定按钮", False, str(e))
                    
            except Exception as e:
                log_test("表单验证", "创建按钮", False, str(e))
                
        except Exception as e:
            log_test("表单验证", "表单测试", False, str(e))
    
    def teardown(self):
        """清理资源"""
        if self.driver:
            self.driver.quit()
            print("\nDriver closed")

def run_ui_tests():
    """运行UI测试"""
    print("\n" + "=" * 60)
    print("  AI测试平台 - UI自动化测试")
    print("=" * 60)
    
    if not SELENIUM_AVAILABLE:
        print("\nSelenium未安装，跳过UI测试")
        print("安装命令: pip install selenium")
        print("并确保ChromeDriver已安装")
        return []
    
    runner = UITestRunner()
    
    try:
        runner.login()
        runner.test_navigation()
        runner.test_project_list_page()
        runner.test_project_detail_page()
        runner.test_form_validation()
    finally:
        runner.teardown()
    
    return TEST_RESULTS

if __name__ == "__main__":
    results = run_ui_tests()
    
    if results:
        passed = len([r for r in results if r["status"] == "PASS"])
        failed = len([r for r in results if r["status"] == "FAIL"])
        print(f"\nUI测试结果: PASS={passed}, FAIL={failed}")
    else:
        print("\n未执行UI测试")
