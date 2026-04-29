# Checklist - ADB 移动端 AI 执行引擎

## ADB 控制器

- [ ] Task 1.1: AdbController 类基本结构
- [ ] Task 1.2: click(x, y) 点击操作
- [ ] Task 1.3: input_text(text) 文本输入
- [ ] Task 1.4: swipe(x1, y1, x2, y2, duration) 滑动操作
- [ ] Task 1.5: take_screenshot() 截图
- [ ] Task 1.6: list_devices() 获取设备列表
- [ ] Task 1.7: is_device_connected() 设备连接检查
- [ ] Task 1.8: get_screen_size() 获取屏幕尺寸
- [ ] Task 1.9: press_key(keyevent) 系统按键
- [ ] Task 1.10: 超时和错误处理

## UIAutomator 元素提取器

- [ ] Task 2.1: UIAutomatorHelper 类
- [ ] Task 2.2: dump_page() 获取页面 XML
- [ ] Task 2.3: find_element() 按 Accessibility ID 查找
- [ ] Task 2.4: find_element_by_text() 按 text 查找
- [ ] Task 2.5: find_element_by_resource_id() 按 resource-id 查找
- [ ] Task 2.6: click_element() 查找并点击元素
- [ ] Task 2.7: XML 解析提取元素信息
- [ ] Task 2.8: 元素未找到错误处理

## 移动端 AI 执行服务

- [ ] Task 3.1: MobileAIExecutor 类
- [ ] Task 3.2: 集成 unified_vision_model 视觉识别
- [ ] Task 3.3: execute_action(description) 自然语言执行
- [ ] Task 3.4: recognize_element(description) 元素识别
- [ ] Task 3.5: parse_action(description) 动作解析
- [ ] Task 3.6: AI + UIAutomator 协同生成 Accessibility ID
- [ ] Task 3.7: 首跑缓存 Accessibility ID 逻辑
- [ ] Task 3.8: 后续回归使用缓存的 Accessibility ID
- [ ] Task 3.9: 缓存失效自动降级到 AI 识别
- [ ] Task 3.10: 错误处理和降级策略

## 执行引擎扩展

- [ ] Task 4.1: ExecutionMode 添加移动端模式
- [ ] Task 4.2: execute_test_case 支持 mobile_realtime
- [ ] Task 4.3: execute_test_case 支持 mobile_smart
- [ ] Task 4.4: _execute_step 支持移动端操作
- [ ] Task 4.5: 移动端和 Web 端自动检测切换

## API 接口扩展

- [ ] Task 5.1: device_id 参数
- [ ] Task 5.2: platform 参数
- [ ] Task 5.3: 移动端参数传递

## 移除 Appium 代码

- [ ] Task 6.1: 删除 mobile_controller.py
- [ ] Task 6.2: 清理 precondition_service.py 中的 MobileController
- [ ] Task 6.3: 清理 _perform_mobile_login 方法
- [ ] Task 6.4: 清理 _recognize_mobile_login_form 方法
- [ ] Task 6.5: 清理 mobile_login 相关配置
- [ ] Task 6.6: 更新 project.py 中的 platform、appium_url 字段

## 单元测试

- [ ] Task 7.1: ADB 控制器测试
- [ ] Task 7.2: UIAutomator 元素提取器测试
- [ ] Task 7.3: 移动端 AI 执行服务测试
- [ ] Task 7.4: 动作解析测试
- [ ] Task 7.5: 缓存机制测试
- [ ] Task 7.6: 错误处理测试
- [ ] Task 7.7: 测试覆盖率验证

## 整体验证

- [ ] 不引入新依赖（仅使用 adb 命令）
- [ ] 复用 unified_vision_model.py 视觉识别能力
- [ ] 支持跨设备（Accessibility ID）
- [ ] 首跑生成缓存，后续回归复用
- [ ] Appium 代码完全移除
