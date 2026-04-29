# 批量元素定位服务优化 Spec

## Why

当前批量元素定位服务（BatchLocatorService）和元素定位服务（ElementLocatorService）存在多个严重问题：JavaScript注入安全漏洞、数据状态不一致（locator_status枚举值混乱）、批量定位不执行步骤操作导致后续步骤页面状态错误、任务完成后报告不可获取、以及大量代码重复和性能问题。这些问题导致定位准确率低、执行不可靠，需要系统性优化。

## What Changes

- **修复JavaScript注入安全漏洞** — 所有JS执行改用Playwright参数化传递，消除字符串拼接注入风险
- **统一locator_status枚举定义** — 创建枚举类，全链路使用统一枚举值，消除pending/recorded/failed/located不一致
- **优化批量定位流程** — 批量定位时执行前序步骤使页面到达正确状态，再进行AI识别
- **修复批量定位数据同步** — 定位成功后更新TestStep.has_locator和locator_status
- **修复任务管理问题** — 延迟注销任务使报告可获取，添加并发限制和线程安全
- **实现重试机制** — 利用已有的max_retries配置，在单步定位失败时自动重试
- **智能跳过低质量定位** — 跳过已有定位时检查置信度和选择器质量，低质量定位重新记录
- **统一选择器映射** — 消除三处重复的预定义选择器逻辑，集中管理
- **修复API端点字段错误** — update_time→updated_at、source默认值、locator_status值
- **优化AI识别prompt** — 根据页面类型和操作描述动态生成prompt，不硬编码"登录表单"
- **置信度阈值可配置** — MIN_CONFIDENCE_THRESHOLD改为构造参数
- **修复N+1查询** — 技术视图使用joinedload批量查询ElementLocator
- **修复ElementLocator模型问题** — step_id添加唯一约束、ai_coordinate空值保护、乐观锁实际使用

## Impact

- Affected specs: ui-automation-enhancement, ai-test-case-executability-optimization
- Affected code:
  - `app/services/batch_locator_service.py` — 核心批量定位流程优化
  - `app/services/element_locator_service.py` — JS注入修复、prompt优化、选择器统一
  - `app/services/test_execution_engine_v2.py` — JS注入修复、选择器映射统一、坐标fallback移除
  - `app/api/v1/endpoints/batch_locator.py` — 任务管理修复、并发限制
  - `app/api/v1/endpoints/test_case.py` — locator_status枚举统一、source字段、update_time修复
  - `app/models/element_locator.py` — 唯一约束、空值保护、乐观锁、原子更新
  - `app/models/test_case.py` — locator_status枚举引用
  - `app/services/test_case_view_service.py` — N+1查询优化

## ADDED Requirements

### Requirement: JavaScript执行安全化

系统 SHALL 在所有通过浏览器执行JavaScript的场景中使用参数化传递，禁止字符串拼接。

#### Scenario: 元素属性获取使用参数化JS
- **GIVEN** 系统需要通过坐标获取页面元素属性
- **WHEN** 调用`_get_element_attributes`获取元素信息
- **THEN** 使用Playwright的`page.evaluate`参数化传递坐标值
- **AND** 不再将坐标值拼接到JS字符串中

#### Scenario: 输入操作使用参数化JS
- **GIVEN** 测试执行引擎需要通过JS设置输入框值
- **WHEN** 执行输入操作
- **THEN** 使用Playwright的`fill()`方法或参数化`evaluate`
- **AND** 不再将input_value拼接到JS字符串中

#### Scenario: 选择器验证使用参数化JS
- **GIVEN** 系统需要验证CSS选择器是否有效
- **WHEN** 调用`querySelector`验证选择器
- **THEN** 使用参数化传递选择器字符串
- **AND** 不再将选择器拼接到JS字符串中

### Requirement: locator_status枚举统一

系统 SHALL 在所有模块中使用统一的定位状态枚举。

#### Scenario: 使用统一枚举值
- **GIVEN** 任何模块需要读取或更新步骤的定位状态
- **WHEN** 操作locator_status字段
- **THEN** 使用以下统一定义：
  - `pending`: 待补充（初始状态）
  - `recorded`: 已记录（AI或手动补充成功）
  - `failed`: 定位失败（AI识别失败或定位信息无效）
- **AND** 禁止使用"located"等非标准值
- **AND** 枚举类定义在`app/models/enums.py`中

#### Scenario: API端点使用统一枚举
- **GIVEN** API端点需要设置步骤的定位状态
- **WHEN** 手动添加定位信息时
- **THEN** 设置`locator_status = LocatorStatus.RECORDED`
- **AND** 设置`source = "manual"`

### Requirement: 批量定位步骤间页面状态维护

系统 SHALL 在批量定位时维护正确的页面状态，确保每个步骤识别时页面处于正确状态。

#### Scenario: 顺序步骤的页面状态维护
- **GIVEN** 测试用例有3个步骤：步骤1"点击菜单展开"、步骤2"点击子菜单项"、步骤3"填写表单"
- **WHEN** 执行批量定位
- **THEN** 步骤1识别时，页面处于初始状态（前置操作后的状态）
- **AND** 步骤2识别前，先执行步骤1的操作（点击菜单展开），使页面到达步骤2的正确状态
- **AND** 步骤3识别前，先执行步骤1和步骤2的操作，使页面到达步骤3的正确状态

#### Scenario: 步骤执行失败时的处理
- **GIVEN** 批量定位过程中某个步骤执行失败
- **WHEN** 前序步骤无法使页面到达正确状态
- **THEN** 跳过该步骤的定位记录
- **AND** 标记该步骤locator_status为"failed"
- **AND** 继续处理后续步骤（如可能）

#### Scenario: navigate类型步骤的特殊处理
- **GIVEN** 步骤类型为navigate
- **WHEN** 执行该步骤使页面到达正确状态
- **THEN** 直接使用browser.navigate导航到目标URL
- **AND** 不需要AI识别元素

### Requirement: 批量定位数据同步

系统 SHALL 在元素定位成功后同步更新TestStep的定位状态字段。

#### Scenario: 定位成功后更新状态
- **GIVEN** 批量定位服务成功为某个步骤记录了元素定位信息
- **WHEN** ElementLocator记录已保存到数据库
- **THEN** 更新`TestStep.has_locator = 1`
- **AND** 更新`TestStep.locator_status = LocatorStatus.RECORDED`

#### Scenario: 定位失败后更新状态
- **GIVEN** 批量定位服务为某个步骤记录定位信息失败
- **WHEN** AI识别返回置信度低于阈值或元素属性获取失败
- **THEN** 更新`TestStep.locator_status = LocatorStatus.FAILED`
- **AND** 保持`TestStep.has_locator = 0`

### Requirement: 批量定位重试机制

系统 SHALL 在单步定位失败时自动重试。

#### Scenario: 单步定位失败自动重试
- **GIVEN** 批量定位配置max_retries=3
- **WHEN** 某个步骤的AI识别返回置信度低于阈值
- **THEN** 自动重新截取截图并重试AI识别
- **AND** 最多重试3次
- **AND** 每次重试前等待step_delay秒

#### Scenario: 重试成功
- **GIVEN** 第一次AI识别失败
- **WHEN** 第二次重试时AI识别成功
- **THEN** 记录定位信息
- **AND** 标记步骤定位成功

#### Scenario: 所有重试均失败
- **GIVEN** 配置max_retries=3
- **WHEN** 3次重试均失败
- **THEN** 标记步骤定位失败
- **AND** 继续处理下一个步骤

### Requirement: 智能跳过低质量定位

系统 SHALL 在跳过已有定位时检查定位质量，低质量定位应重新记录。

#### Scenario: 跳过高质量定位
- **GIVEN** 步骤已有ElementLocator记录
- **AND** css_selector不为空且ai_confidence >= 0.7
- **WHEN** 批量定位检查是否跳过
- **THEN** 跳过该步骤，不重新定位

#### Scenario: 重新记录低质量定位
- **GIVEN** 步骤已有ElementLocator记录
- **AND** css_selector为空且ai_confidence < 0.7
- **WHEN** 批量定位检查是否跳过
- **THEN** 不跳过，重新进行AI识别和定位记录
- **AND** 更新已有的ElementLocator记录

### Requirement: 批量任务管理优化

系统 SHALL 优化批量定位任务的生命周期管理。

#### Scenario: 任务完成后报告可获取
- **GIVEN** 批量定位任务已完成
- **WHEN** 用户通过API获取任务报告
- **THEN** 返回完整的批量记录报告
- **AND** 报告在任务完成后至少保留30分钟

#### Scenario: 并发任务数量限制
- **GIVEN** 系统已有2个批量定位任务正在运行
- **WHEN** 用户启动第3个批量定位任务
- **THEN** 返回错误提示"同时运行的批量定位任务数量已达上限"
- **AND** 最大并发数可配置（默认2）

#### Scenario: 任务管理器线程安全
- **GIVEN** 多个请求同时操作BatchTaskManager
- **WHEN** 并发register/unregister/cancel操作
- **THEN** 操作结果正确，无竞态条件
- **AND** 使用asyncio.Lock保护共享数据

### Requirement: 统一选择器映射管理

系统 SHALL 将分散在三处的预定义选择器映射集中管理。

#### Scenario: 选择器映射集中定义
- **GIVEN** 系统需要预定义选择器映射
- **WHEN** 任何模块需要查找预定义选择器
- **THEN** 从统一的SelectorRegistry获取
- **AND** 不再在各模块中重复定义选择器映射

#### Scenario: 选择器映射可扩展
- **GIVEN** 需要为新系统添加预定义选择器
- **WHEN** 管理员添加新的选择器映射
- **THEN** 通过配置文件或数据库添加
- **AND** 不需要修改代码

### Requirement: AI识别prompt动态化

系统 SHALL 根据页面类型和操作描述动态生成AI识别prompt。

#### Scenario: 登录页面元素识别
- **GIVEN** 当前页面是登录页面
- **AND** 步骤描述为"在用户名输入框中输入用户名"
- **WHEN** 调用AI识别元素
- **THEN** prompt包含"这是一个登录表单页面"的上下文提示
- **AND** prompt包含具体的操作描述

#### Scenario: 非登录页面元素识别
- **GIVEN** 当前页面不是登录页面
- **AND** 步骤描述为"点击新增按钮"
- **WHEN** 调用AI识别元素
- **THEN** prompt不包含"登录表单"的误导性提示
- **AND** prompt根据页面标题或URL动态生成上下文

#### Scenario: 根据action_type调整prompt
- **GIVEN** 步骤的action_type为"verify"
- **WHEN** 调用AI识别元素
- **THEN** prompt侧重于识别验证目标元素的位置和状态
- **AND** 不要求返回可交互元素的坐标

### Requirement: 置信度阈值可配置

系统 SHALL 支持自定义AI识别置信度阈值。

#### Scenario: 使用自定义置信度阈值
- **GIVEN** ElementLocatorService初始化时传入confidence_threshold=0.7
- **WHEN** AI识别返回置信度0.75
- **THEN** 识别结果被接受
- **AND** 元素定位信息被记录

#### Scenario: 使用默认置信度阈值
- **GIVEN** ElementLocatorService初始化时未传入confidence_threshold
- **WHEN** AI识别返回置信度0.85
- **THEN** 使用默认阈值0.8
- **AND** 0.85 >= 0.8，识别结果被接受

### Requirement: 技术视图N+1查询优化

系统 SHALL 在查询技术视图时避免N+1查询问题。

#### Scenario: 批量查询元素定位信息
- **GIVEN** 测试用例有20个步骤
- **WHEN** 查询技术视图
- **THEN** 使用joinedload或批量查询一次性获取所有步骤的ElementLocator
- **AND** 数据库查询次数不超过2次（1次步骤+1次定位）

## MODIFIED Requirements

### Requirement: ElementLocator模型增强

**原实现**: step_id有索引但无唯一约束，ai_coordinate无空值保护，乐观锁未实际使用，统计更新非原子操作

**修改后**:
- step_id添加UNIQUE约束，确保一对一关系
- get_best_locator中ai_coordinate添加空值检查
- record_success/record_failure使用数据库原子更新（`UPDATE ... SET success_count = success_count + 1`）
- 更新时检查version字段实现乐观锁
- ai_coordinate JSON字段添加基本Schema验证

### Requirement: API端点字段修复

**原实现**: add_step_locator中locator_status设为"located"（不在枚举中），source默认为"ai"（应为"manual"），update_technical_view中引用不存在的update_time字段

**修改后**:
- locator_status使用LocatorStatus.RECORDED枚举值
- 手动添加定位时source设为"manual"
- update_technical_view中使用正确的updated_at字段名

### Requirement: 执行引擎坐标fallback移除

**原实现**: `_coordinate_fallback_locate`使用硬编码的1920x1080坐标映射，confidence仅0.2-0.3

**修改后**:
- 移除硬编码坐标fallback
- 定位失败时返回None，由调用方决定处理方式
- 在策略链末端仅保留AI实时识别作为最终回退

## REMOVED Requirements

### Requirement: 硬编码坐标fallback定位

**Reason**: 硬编码坐标只适用于特定布局的登录页面，confidence极低（0.2-0.3），对其他页面完全无效，且调用方不检查confidence就使用，导致误操作

**Migration**: 移除`_coordinate_fallback_locate`方法，定位失败时返回None，由调用方（smart_locate_with_ai_fallback）决定是否标记步骤失败
