# Tasks - ADB 移动端 AI 执行引擎

## Task 1: 创建 ADB 控制器

创建 `app/utils/adb_controller.py`，封装常见 adb 操作。

- [ ] SubTask 1.1: 创建 AdbController 类，设备连接管理
- [ ] SubTask 1.2: 实现 `click(x, y)` 点击操作
- [ ] SubTask 1.3: 实现 `input_text(text)` 文本输入
- [ ] SubTask 1.4: 实现 `swipe(x1, y1, x2, y2, duration)` 滑动操作
- [ ] SubTask 1.5: 实现 `take_screenshot()` 截图
- [ ] SubTask 1.6: 实现 `list_devices()` 获取设备列表
- [ ] SubTask 1.7: 实现 `is_device_connected()` 设备连接检查
- [ ] SubTask 1.8: 实现 `get_screen_size()` 获取屏幕尺寸
- [ ] SubTask 1.9: 实现 `press_key(keyevent)` 系统按键
- [ ] SubTask 1.10: 添加超时和错误处理

## Task 2: 创建 UIAutomator 元素提取器

创建 `app/utils/uiautomator_helper.py`，获取页面元素结构。

- [ ] SubTask 2.1: 创建 UIAutomatorHelper 类
- [ ] SubTask 2.2: 实现 `dump_page()` 获取页面 XML
- [ ] SubTask 2.3: 实现 `find_element()` 按 Accessibility ID 查找元素
- [ ] SubTask 2.4: 实现 `find_element_by_text()` 按 text 查找元素
- [ ] SubTask 2.5: 实现 `find_element_by_resource_id()` 按 resource-id 查找元素
- [ ] SubTask 2.6: 实现 `click_element()` 查找并点击元素
- [ ] SubTask 2.7: 实现 XML 解析，提取元素信息（bounds、text、resource-id）
- [ ] SubTask 2.8: 添加元素未找到时的错误处理

## Task 3: 创建移动端 AI 执行服务

创建 `app/services/mobile_ai_executor.py`，集成视觉识别、UIAutomator 和 ADB 控制。

- [ ] SubTask 3.1: 创建 MobileAIExecutor 类
- [ ] SubTask 3.2: 集成 unified_vision_model 进行视觉识别
- [ ] SubTask 3.3: 实现 `execute_action(description)` 自然语言执行
- [ ] SubTask 3.4: 实现 `recognize_element(description)` 元素识别
- [ ] SubTask 3.5: 实现 `parse_action(description)` 解析动作类型（点击/输入/滑动）
- [ ] SubTask 3.6: 实现 AI + UIAutomator 协同生成 Accessibility ID
- [ ] SubTask 3.7: 实现首跑缓存 Accessibility ID 逻辑
- [ ] SubTask 3.8: 实现后续回归使用缓存的 Accessibility ID
- [ ] SubTask 3.9: 实现缓存失效时自动降级到 AI 实时识别
- [ ] SubTask 3.10: 添加错误处理和降级策略

## Task 4: 扩展执行引擎支持移动端

修改 `app/services/test_execution_engine_v2.py`，支持移动端执行模式。

- [ ] SubTask 4.1: 在 ExecutionMode 枚举中添加移动端模式
- [ ] SubTask 4.2: 修改 execute_test_case 支持 mobile_realtime 模式
- [ ] SubTask 4.3: 修改 execute_test_case 支持 mobile_smart 模式
- [ ] SubTask 4.4: 修改 _execute_step 支持移动端操作执行
- [ ] SubTask 4.5: 实现移动端和 Web 端的自动检测切换

## Task 5: API 接口扩展

修改 `app/api/v1/endpoints/execution.py`，支持移动端执行参数。

- [ ] SubTask 5.1: 添加 device_id 参数（指定 adb 设备）
- [ ] SubTask 5.2: 添加 platform 参数（android）
- [ ] SubTask 5.3: 传递移动端参数到执行引擎

## Task 6: 移除 Appium 代码

删除现有的 Appium 相关代码。

- [ ] SubTask 6.1: 删除 `app/utils/mobile_controller.py`
- [ ] SubTask 6.2: 清理 `app/services/precondition_service.py` 中的 MobileController 相关代码
- [ ] SubTask 6.3: 清理 `app/services/precondition_service.py` 中的 _perform_mobile_login 方法
- [ ] SubTask 6.4: 清理 `app/services/precondition_service.py` 中的 _recognize_mobile_login_form 方法
- [ ] SubTask 6.5: 清理 `app/services/precondition_service.py` 中的 mobile_login 相关配置
- [ ] SubTask 6.6: 更新 `app/schemas/project.py` 中的 platform、appium_url 字段（标记废弃或移除）

## Task 7: 单元测试

创建 `tests/test_adb_mobile_execution.py`，测试 ADB 控制、UIAutomator 和 AI 执行。

- [ ] SubTask 7.1: ADB 控制器基础测试
- [ ] SubTask 7.2: UIAutomator 元素提取器测试
- [ ] SubTask 7.3: 移动端 AI 执行服务测试
- [ ] SubTask 7.4: 动作解析测试
- [ ] SubTask 7.5: 缓存机制测试
- [ ] SubTask 7.6: 错误处理测试
- [ ] SubTask 7.7: 测试覆盖率验证

## Task Dependencies

- Task 1, 2 可并行开发
- Task 3 依赖 Task 1, 2 完成
- Task 4, 5 依赖 Task 3 完成
- Task 6 可与 Task 4, 5 并行进行
- Task 7 依赖所有功能开发完成后进行
