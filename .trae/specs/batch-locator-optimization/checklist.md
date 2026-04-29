# Checklist - 批量元素定位服务优化

## Task 1: 统一枚举和选择器注册中心

- [x] LocatorStatus枚举类已创建在`app/models/enums.py`，包含PENDING/RECORDED/FAILED三个值
- [x] SelectorRegistry类已创建在`app/services/selector_registry.py`
- [x] SelectorRegistry包含原PREDEFINED_SELECTORS的所有映射
- [x] SelectorRegistry提供统一的`get_selector(page_title, keyword)`接口
- [x] SelectorRegistry支持从配置文件加载自定义映射

## Task 2: JavaScript注入安全修复

- [x] element_locator_service.py中`_get_element_attributes`使用参数化JS传递
- [x] element_locator_service.py中`smart_locate_element`的querySelector验证使用参数化传递
- [x] test_execution_engine_v2.py中`_execute_input`使用Playwright fill()方法
- [x] test_execution_engine_v2.py中`_execute_captcha`使用Playwright fill()方法
- [x] test_execution_engine_v2.py中`_locate_with_selector`使用参数化传递
- [x] test_execution_engine_v2.py中`_get_element_attributes_from_coords`使用参数化传递
- [x] 所有execute_javascript调用中无用户可控输入的字符串拼接

## Task 3: 统一locator_status枚举值

- [x] element_locator_service.py使用LocatorStatus枚举
- [x] batch_locator_service.py使用LocatorStatus枚举
- [x] test_case.py API端点中locator_status使用LocatorStatus.RECORDED（非"located"）
- [x] test_case.py API端点中手动添加定位source为"manual"（非"ai"）
- [x] test_case.py API端点中update_time改为updated_at
- [x] test_case_view_service.py使用LocatorStatus枚举
- [x] execution.py使用LocatorStatus枚举
- [x] 全链路无硬编码的locator_status字符串

## Task 4: 批量定位核心流程优化

- [x] 批量定位时非首个步骤前执行前序步骤操作
- [x] 步骤执行失败时标记failed并继续后续步骤
- [x] navigate类型步骤直接使用browser.navigate
- [x] 单步定位失败时自动重试，最多max_retries次
- [x] 重试成功时正确记录定位信息
- [x] 所有重试失败时标记步骤failed
- [x] 低质量定位（css_selector为空且confidence<0.7）不跳过，重新记录
- [x] 高质量定位（css_selector非空或confidence>=0.7）正确跳过
- [x] 定位成功后更新step.has_locator=1和step.locator_status=RECORDED
- [x] 定位失败后更新step.locator_status=FAILED

## Task 5: 批量任务管理优化

- [x] 任务完成后报告至少保留30分钟可获取
- [x] 并发任务数量限制生效（默认最大2个）
- [x] 超过并发限制时返回明确错误信息
- [x] BatchTaskManager使用asyncio.Lock保护_tasks字典
- [x] BatchLocatorService._cancelled使用asyncio.Event替代布尔标志
- [x] register/unregister/cancel操作线程安全

## Task 6: ElementLocator模型优化

- [x] element_locators.step_id已添加UNIQUE约束
- [x] Alembic迁移脚本已创建并验证
- [x] get_best_locator中ai_coordinate空值检查生效
- [x] record_success/record_failure使用数据库原子更新
- [x] 更新时检查version字段实现乐观锁
- [x] ai_coordinate JSON字段基本验证生效（非负数检查）

## Task 7: AI识别prompt和置信度优化

- [x] _recognize_element根据页面类型动态生成prompt
- [x] 登录页面prompt包含"登录表单"上下文
- [x] 非登录页面prompt不包含误导性"登录表单"提示
- [x] verify类型步骤使用侧重验证的prompt
- [x] ElementLocatorService支持confidence_threshold参数
- [x] 默认置信度阈值为0.8（非0.9）
- [x] BatchLocatorService可通过配置传入置信度阈值

## Task 8: N+1查询优化和坐标fallback移除

- [x] 技术视图查询使用joinedload或批量查询
- [x] 技术视图查询次数不超过2次
- [x] _coordinate_fallback_locate方法已弃用
- [x] smart_locate_with_ai_fallback策略链末端返回None
- [x] 定位失败时调用方正确标记步骤失败

## Task 9: 统一选择器映射引用

- [x] element_locator_service.py中PREDEFINED_SELECTORS常量已移除
- [x] element_locator_service.py使用SelectorRegistry.get_selector()
- [x] test_execution_engine_v2.py中_get_element_selector已改用SelectorRegistry
- [x] test_execution_engine_v2.py中_get_input_selector已改用SelectorRegistry
- [x] test_execution_engine_v2.py中_get_click_selector已改用SelectorRegistry
- [x] test_execution_engine_v2.py使用SelectorRegistry.get_selector()

## 整体验证

- [x] 批量定位端到端流程正常：启动→前置操作→逐步骤定位（含页面状态维护）→报告生成
- [x] 无JavaScript注入漏洞（代码审查确认）
- [x] locator_status全链路一致（无硬编码字符串）
- [x] 数据库迁移脚本已创建
- [x] 现有API接口向后兼容
- [x] 所有修改文件语法检查通过
