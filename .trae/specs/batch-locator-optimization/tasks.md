# Tasks - 批量元素定位服务优化

## Task 1: 创建统一枚举和选择器注册中心

建立全链路共享的枚举定义和选择器映射注册中心，消除各模块的重复定义和不一致值。

- [x] SubTask 1.1: 创建LocatorStatus枚举类
  - 在`app/models/enums.py`中添加`LocatorStatus`枚举：PENDING="pending", RECORDED="recorded", FAILED="failed"
  - 确保所有模块引用此枚举而非硬编码字符串

- [x] SubTask 1.2: 创建SelectorRegistry选择器注册中心
  - 在`app/services/selector_registry.py`中创建`SelectorRegistry`类
  - 将`ElementLocatorService.PREDEFINED_SELECTORS`、`TestExecutionEngineV2._get_element_selector`、`_get_input_selector`、`_get_click_selector`中的映射集中到此处
  - 提供`get_selector(page_title, keyword)`统一查询接口
  - 支持从配置文件加载自定义选择器映射

## Task 2: 修复JavaScript注入安全漏洞

将所有浏览器JS执行从字符串拼接改为参数化传递，消除注入风险。

- [x] SubTask 2.1: 修复element_locator_service.py中的JS注入
  - `_get_element_attributes`中`elementFromPoint`调用改用参数化传递
  - `smart_locate_element`中`querySelector`验证改用参数化传递
  - 确保所有`execute_javascript`调用不拼接用户可控输入

- [x] SubTask 2.2: 修复test_execution_engine_v2.py中的JS注入
  - `_execute_input`中`document.activeElement.value`设置改用Playwright的`fill()`方法
  - `_execute_captcha`中验证码输入改用`fill()`方法
  - `_locate_with_selector`中`querySelector`验证改用参数化传递
  - `_get_element_attributes_from_coords`中`elementFromPoint`改用参数化传递

## Task 3: 统一locator_status枚举值

全链路替换硬编码的locator_status字符串为统一枚举。

- [x] SubTask 3.1: 更新element_locator_service.py
  - `record_locator`成功后设置`step.locator_status = LocatorStatus.RECORDED.value`
  - 识别失败时设置`step.locator_status = LocatorStatus.FAILED.value`

- [x] SubTask 3.2: 更新batch_locator_service.py
  - `_record_single_step`成功后设置`step.locator_status = LocatorStatus.RECORDED.value`
  - 失败时设置`step.locator_status = LocatorStatus.FAILED.value`

- [x] SubTask 3.3: 更新API端点test_case.py
  - `add_step_locator`中`locator_status`从"located"改为`LocatorStatus.RECORDED.value`
  - `add_step_locator`中`source`从默认"ai"改为"manual"
  - `update_technical_view`中`update_time`改为`updated_at`

- [x] SubTask 3.4: 更新test_case_view_service.py
  - 定位覆盖率统计中使用`LocatorStatus`枚举值
  - 技术视图查询中使用枚举值过滤

- [x] SubTask 3.5: 更新execution.py
  - 失败分析中`locator_status == "failed"`改为`locator_status == LocatorStatus.FAILED.value`

## Task 4: 优化批量定位核心流程

修复批量定位不执行步骤操作、不更新状态、无重试机制等核心问题。

- [x] SubTask 4.1: 实现步骤间页面状态维护
  - 在`batch_record_locators`中，对每个非首个步骤，先执行前序步骤的操作
  - 根据action_type执行对应操作（click/input/navigate等）
  - 步骤执行失败时标记该步骤为failed并继续后续步骤
  - navigate类型步骤直接使用browser.navigate

- [x] SubTask 4.2: 实现单步定位重试机制
  - 在`_record_single_step`中添加重试逻辑
  - 使用`BatchLocatorConfig.max_retries`配置
  - 每次重试前等待`step_delay`秒
  - 记录每次重试的结果到StepRecordResult

- [x] SubTask 4.3: 实现智能跳过低质量定位
  - 修改skip_existing逻辑：检查css_selector是否为空和ai_confidence是否低于阈值
  - 低质量定位（css_selector为空且confidence < 0.7）不跳过，重新记录
  - 高质量定位（css_selector非空或confidence >= 0.7）跳过

- [x] SubTask 4.4: 修复批量定位数据同步
  - `_record_single_step`成功后更新`step.has_locator = 1`和`step.locator_status`
  - 失败后更新`step.locator_status = LocatorStatus.FAILED.value`
  - 确保TestStep和ElementLocator状态一致

## Task 5: 优化批量任务管理

修复任务完成后报告不可获取、线程安全、并发限制等问题。

- [x] SubTask 5.1: 修复任务报告持久化
  - 任务完成后延迟30分钟再注销（而非立即注销）
  - 或将报告持久化到数据库，任务完成后仍可查询
  - 修改`batch_locator.py`中`get_batch_record_report`端点逻辑

- [x] SubTask 5.2: 添加并发任务限制
  - 在`BatchTaskManager`中添加`max_concurrent_tasks`配置（默认2）
  - `register_task`前检查当前运行任务数
  - 超过限制时返回错误信息

- [x] SubTask 5.3: 添加线程安全保护
  - `BatchTaskManager._tasks`使用`asyncio.Lock`保护
  - `BatchLocatorService._cancelled`标志位使用`asyncio.Event`
  - 确保register/unregister/cancel操作原子性

## Task 6: 优化ElementLocator模型

修复模型层的约束缺失、空值保护、乐观锁和原子更新问题。

- [x] SubTask 6.1: 添加step_id唯一约束
  - 创建Alembic迁移脚本，为`element_locators.step_id`添加UNIQUE约束
  - 确保一对一关系的数据完整性

- [x] SubTask 6.2: 修复get_best_locator空值保护
  - `ai_coordinate.copy()`前检查`ai_coordinate`是否为None或非dict
  - 返回安全的默认值而非抛出异常

- [x] SubTask 6.3: 实现原子统计更新
  - `record_success`/`record_failure`改用数据库原子更新：`UPDATE element_locators SET success_count = success_count + 1, version = version + 1 WHERE id = :id AND version = :version`
  - 更新失败（version不匹配）时抛出OptimisticLockError

- [x] SubTask 6.4: 添加ai_coordinate基本验证
  - 在ElementLocator模型中添加`_validate_coordinate`方法
  - 验证x/y/width/height为非负数
  - setter中调用验证

## Task 7: 优化AI识别prompt和置信度配置

使AI识别prompt动态化，置信度阈值可配置。

- [x] SubTask 7.1: 实现动态prompt生成
  - 在`_recognize_element`中根据页面标题和action_type动态生成prompt
  - 登录页面使用包含"登录表单"上下文的prompt
  - 非登录页面使用通用prompt
  - verify类型步骤使用侧重验证的prompt

- [x] SubTask 7.2: 置信度阈值可配置
  - `ElementLocatorService.__init__`添加`confidence_threshold`参数，默认0.8
  - 将`MIN_CONFIDENCE_THRESHOLD`常量替换为实例属性
  - `BatchLocatorService`可通过配置传入阈值

## Task 8: 优化技术视图N+1查询

消除技术视图查询中的N+1问题。

- [x] SubTask 8.1: 优化test_case_view_service.py技术视图查询
  - 使用`joinedload(TestStep.element_locator)`一次性加载所有步骤和定位信息
  - 或先批量查询步骤ID对应的ElementLocator，构建映射dict
  - 确保查询次数不超过2次

- [x] SubTask 8.2: 移除执行引擎硬编码坐标fallback
  - 删除`_coordinate_fallback_locate`方法
  - `smart_locate_with_ai_fallback`策略链末端改为返回None
  - 定位失败时由调用方标记步骤失败

## Task 9: 统一选择器映射引用

将各模块的预定义选择器映射替换为统一的SelectorRegistry。

- [x] SubTask 9.1: 更新element_locator_service.py
  - 移除`PREDEFINED_SELECTORS`常量
  - `smart_locate_element`中改用`SelectorRegistry.get_selector()`

- [x] SubTask 9.2: 更新test_execution_engine_v2.py
  - 移除`_get_element_selector`、`_get_input_selector`、`_get_click_selector`方法
  - `smart_locate_with_ai_fallback`中改用`SelectorRegistry.get_selector()`
  - `_execute_input`和`_execute_click`中改用`SelectorRegistry`

# Task Dependencies

```
Task 1 (枚举+注册中心) ─────┬──→ Task 3 (统一枚举值)
                            ├──→ Task 9 (统一选择器引用)
                            │
Task 2 (JS注入修复) ────────┤  (独立，可并行)
                            │
Task 4 (批量定位核心优化) ───┤  依赖 Task 3
                            │
Task 5 (任务管理优化) ───────┤  (独立，可并行)
                            │
Task 6 (模型优化) ───────────┤  (独立，可并行)
                            │
Task 7 (prompt+置信度) ─────┤  (独立，可并行)
                            │
Task 8 (N+1+坐标fallback) ──┘  (独立，可并行)

执行顺序建议:
1. Task 1 → Task 3 → Task 4 (核心链路，优先)
2. Task 2 (安全修复，高优先级，可与1并行)
3. Task 6 (模型修复，可与1并行)
4. Task 5, Task 7, Task 8 (可并行)
5. Task 9 (依赖Task 1完成)
```
