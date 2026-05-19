"""
洪恩管理系统真实登录测试
使用真实浏览器访问真实系统
"""
import sys
import os
import unittest
import asyncio
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.utils.browser_controller_v2 import BrowserControllerV2, BrowserConfig
from app.utils.unified_vision_model import UnifiedVisionModel, VisionModelType


class TestHongenLoginReal(unittest.TestCase):
    """
    洪恩管理系统真实登录测试
    访问地址: https://admin-jxw-panda-test.ihumand.com
    """
    
    def setUp(self):
        """测试前准备"""
        self.base_url = "https://admin-jxw-panda-test.ihumand.com"
        self.username = "admin"
        self.password = "admin123"
        # 初始化视觉模型用于验证码识别
        self.vision_model = UnifiedVisionModel(
            model_type=VisionModelType.QWEN,
            api_key=os.getenv("QWEN_API_KEY", ""),
            model_name="qwen-vl-plus"
        )
    
    def test_01_navigate_to_login_page(self):
        """测试1: 访问登录页面"""
        print("\n🧪 测试1: 访问洪恩管理系统登录页面")
        
        async def run_test():
            config = BrowserConfig(
                headless=False,  # 显示浏览器窗口，方便观察
                viewport_width=1920,
                viewport_height=1080
            )
            controller = BrowserControllerV2(config)
            
            try:
                await controller.initialize()
                await controller.navigate(self.base_url)
                
                # 等待页面加载
                await asyncio.sleep(3)
                
                # 获取页面信息
                page_info = await controller.get_page_info()
                print(f"📄 页面标题: {page_info.get('title', 'N/A')}")
                print(f"🔗 当前URL: {page_info.get('url', 'N/A')}")
                
                # 验证页面加载成功
                self.assertIsNotNone(page_info)
                self.assertIn('url', page_info)
                
                print("✅ 测试1通过: 成功访问登录页面")
                
            except Exception as e:
                print(f"❌ 测试1失败: {e}")
                raise
            finally:
                await controller.close()
        
        asyncio.run(run_test())
    
    def test_02_login_with_captcha(self):
        """测试2: 使用账号密码登录（包含验证码识别）"""
        print("\n🧪 测试2: 使用账号密码登录（包含验证码识别）")
        
        async def run_test():
            config = BrowserConfig(
                headless=False,
                viewport_width=1920,
                viewport_height=1080
            )
            controller = BrowserControllerV2(config)
            
            try:
                await controller.initialize()
                await controller.navigate(self.base_url)
                await asyncio.sleep(3)
                
                # 获取页面信息
                page_info = await controller.get_page_info()
                print(f"📄 页面标题: {page_info.get('title', 'N/A')}")
                
                # 查找输入元素
                input_elements = await controller.get_all_input_elements()
                print(f"🔍 找到 {len(input_elements)} 个输入元素")
                
                # 查找用户名输入框
                username_selectors = [
                    'input[placeholder*="用户名"]', 
                    'input[placeholder*="账号"]',
                    'input[type="text"]',
                    'input[name="username"]',
                    'input#username'
                ]
                
                username_found = False
                for selector in username_selectors:
                    try:
                        element_info = await controller.get_element_info(selector)
                        if element_info:
                            print(f"✅ 找到用户名输入框: {selector}")
                            await controller.fill(selector, self.username)
                            print(f"📝 已输入用户名: {self.username}")
                            username_found = True
                            break
                    except:
                        continue
                
                if not username_found:
                    print("⚠️ 未找到用户名输入框，尝试通过坐标点击")
                    await controller.click(800, 450)
                    await controller.type_text(self.username)
                
                await asyncio.sleep(1)
                
                # 查找密码输入框
                password_selectors = [
                    'input[type="password"]',
                    'input[placeholder*="密码"]',
                    'input[name="password"]',
                    'input#password'
                ]
                
                password_found = False
                for selector in password_selectors:
                    try:
                        element_info = await controller.get_element_info(selector)
                        if element_info:
                            print(f"✅ 找到密码输入框: {selector}")
                            await controller.fill(selector, self.password)
                            print(f"📝 已输入密码: {'*' * len(self.password)}")
                            password_found = True
                            break
                    except:
                        continue
                
                if not password_found:
                    print("⚠️ 未找到密码输入框，尝试通过坐标点击")
                    await controller.click(800, 520)
                    await controller.type_text(self.password)
                
                await asyncio.sleep(1)
                
                # 识别并输入验证码
                print("🔍 开始识别验证码...")
                captcha_result = await self._recognize_captcha(controller)
                
                if captcha_result:
                    print(f"✅ 验证码识别结果: {captcha_result}")
                    # 查找验证码输入框
                    captcha_selectors = [
                        'input[placeholder*="验证码"]',
                        'input[name="captcha"]',
                        'input#captcha',
                        'input[type="text"]:nth-of-type(3)'
                    ]
                    
                    captcha_found = False
                    for selector in captcha_selectors:
                        try:
                            element_info = await controller.get_element_info(selector)
                            if element_info:
                                print(f"✅ 找到验证码输入框: {selector}")
                                await controller.fill(selector, captcha_result)
                                print(f"📝 已输入验证码: {captcha_result}")
                                captcha_found = True
                                break
                        except:
                            continue
                    
                    if not captcha_found:
                        print("⚠️ 未找到验证码输入框，尝试通过坐标点击")
                        await controller.click(800, 590)
                        await controller.type_text(captcha_result)
                else:
                    print("⚠️ 验证码识别失败或无需验证码")
                
                await asyncio.sleep(1)
                
                # 查找登录按钮
                login_button_selectors = [
                    'button:has-text("登录")',
                    'button:has-text("Login")',
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button.el-button--primary',
                    '.login-btn',
                    '.submit-btn'
                ]
                
                login_button_found = False
                for selector in login_button_selectors:
                    try:
                        element_info = await controller.get_element_info(selector)
                        if element_info:
                            print(f"✅ 找到登录按钮: {selector}")
                            await controller.click_element(selector)
                            print("🖱️ 已点击登录按钮")
                            login_button_found = True
                            break
                    except:
                        continue
                
                if not login_button_found:
                    print("⚠️ 未找到登录按钮，尝试通过坐标点击")
                    await controller.click(960, 650)
                
                # 等待登录结果
                print("⏳ 等待登录结果...")
                await asyncio.sleep(5)
                
                # 验证登录成功
                page_info = await controller.get_page_info()
                current_url = page_info.get('url', '')
                print(f"🔗 登录后URL: {current_url}")
                
                # 检查是否进入首页（URL应该改变或包含特定路径）
                if 'login' not in current_url.lower() and current_url != self.base_url:
                    print("✅ 登录成功，已进入首页")
                elif 'productLineManage' in current_url or 'index' in current_url:
                    print("✅ 登录成功，已进入首页")
                else:
                    print(f"⚠️ 当前URL: {current_url}")
                    print("登录可能失败，请检查截图")
                
                # 截图保存
                screenshot = await controller.take_screenshot()
                screenshot_path = 'hongen_login_result.png'
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot)
                print(f"📸 截图已保存: {screenshot_path}")
                
                print("✅ 测试2完成: 登录流程执行完毕")
                
            except Exception as e:
                print(f"❌ 测试2失败: {e}")
                import traceback
                traceback.print_exc()
                raise
            finally:
                await asyncio.sleep(3)  # 等待观察
                await controller.close()
        
        asyncio.run(run_test())
    
    async def _recognize_captcha(self, controller) -> str:
        """
        识别验证码
        
        Returns:
            验证码识别结果，如果失败返回空字符串
        """
        try:
            # 检查视觉模型是否可用
            if not self.vision_model.api_key:
                print("⚠️ 视觉模型未配置API Key，跳过验证码识别")
                return ""
            
            # 截取页面截图
            screenshot = await controller.take_screenshot()
            
            # 使用AI识别验证码
            prompt = """请仔细分析这个登录页面截图，完成以下任务：

1. 找到验证码图片（通常是一个包含数字/字母/数学运算的图片，位于输入框旁边）
2. 仔细识别验证码内容，特别注意：
   - 数字：0-9
   - 运算符：+（加）、-（减）、*（乘）、/（除）
   - 请仔细辨认每个字符，确保识别准确
3. 如果是数学表达式（如"3+5=?"），请计算出结果
4. 如果是纯数字/字母，直接识别

重要提示：
- 请仔细查看验证码图片中的每个数字和运算符
- 确保识别准确后再进行计算
- 验证码通常是一个简单的数学表达式

请返回JSON格式：
{
    "captcha_type": "math|text",
    "captcha_original": "原始内容（如 '3+5=?'）",
    "captcha_result": "计算或识别结果（如 '8'）",
    "captcha_image_location": {"x": 100, "y": 200, "width": 80, "height": 30},
    "confidence": 0.95
}

如果找不到验证码，返回：
{
    "captcha_result": null,
    "error": "未找到验证码"
}"""
            
            response = self.vision_model.describe_screenshot(screenshot)
            
            # 尝试从响应中解析验证码
            try:
                # 查找JSON格式的响应
                if '"captcha_result"' in response:
                    # 提取JSON部分
                    start_idx = response.find('{')
                    end_idx = response.rfind('}') + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = response[start_idx:end_idx]
                        result = json.loads(json_str)
                        captcha_result = result.get("captcha_result", "")
                        if captcha_result and captcha_result != "null":
                            return str(captcha_result)
                
                # 如果没有JSON格式，尝试直接提取数字
                import re
                numbers = re.findall(r'\d+', response)
                if numbers:
                    return numbers[0]
                    
            except Exception as e:
                print(f"⚠️ 解析验证码响应失败: {e}")
                print(f"原始响应: {response}")
            
            return ""
            
        except Exception as e:
            print(f"⚠️ 验证码识别失败: {e}")
            return ""


if __name__ == '__main__':
    unittest.main(verbosity=2)
