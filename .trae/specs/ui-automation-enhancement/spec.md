# AI视觉测试用例执行能力增强 Spec

## Why

当前测试执行器(TestExecutor)仅为模拟执行，无法真实操作浏览器或移动设备，测试用例通过率为0%。需要引入AI视觉识别能力，实现真正的UI自动化测试，目标测试用例通过率达到98%。

同时需要支持多种测试类型：
- **功能测试（纯AI视觉测试）**：Web端/C端通过AI视觉识别执行
- **接口测试**：后续扩展，通过API调用执行

执行前需要读取项目配置的被测对象信息作为前置操作。

**核心原则：所有执行必须是真实的，禁止使用任何模拟操作和数据。**

## What Changes

### 第一阶段：基础视觉测试能力（MVP）
- **新增统一视觉模型客户端**：封装多模态视觉识别能力，支持Kimi/Qwen/Zhipu/Baidu/Doubao等多种模型
- **新增浏览器控制器**：基于 Playwright 的真实浏览器操作
- **新增设备控制器**：基于 Appium 的移动设备控制（C端）
- **增强 TestExecutor**：支持按用例类型选择执行模式
- **新增视觉元素定位**：通过AI识别页面元素位置
- **新增执行过程可视化**：实时展示浏览器操作过程
- **新增项目配置读取**：执行前自动读取被测对象信息

### 第二阶段：智能验证与优化
- **新增智能结果验证**：AI判断测试步骤是否成功
- **新增失败自动分析**：AI分析失败原因并给出建议
- **新增元素重定位**：页面变化时自动重新定位元素
- **新增执行日志增强**：包含截图、AI分析结果

### 第三阶段：批量执行与效率提升
- **并行执行测试用例**：多浏览器实例同时执行
- **智能等待优化**：基于AI识别的智能等待策略
- **测试数据缓存**：缓存元素识别结果提升效率

## Impact

- Affected specs: 测试执行流程、AI分析能力、报告生成、项目配置管理
- Affected code: 
  - `app/services/test_executor.py` - 核心执行器重构，支持多类型执行
  - `app/utils/unified_vision_model.py` - 新增统一视觉模型客户端（支持多模型）
  - `app/services/browser_controller.py` - Web端浏览器控制
  - `app/services/device_controller.py` - C端设备控制
  - `app/models/project.py` - 扩展被测对象信息
  - `.env` - 新增视觉模型API配置（支持多模型配置）

## ADDED Requirements

### Requirement: 用例类型识别与执行模式选择

系统 SHALL 能够根据测试用例类型选择对应的执行模式。

#### Scenario: 功能测试用例执行
- **GIVEN** 测试用例类型为"功能测试"
- **WHEN** 系统执行该用例
- **THEN** 使用AI视觉测试模式执行
- **AND** 调用配置的视觉模型API进行元素识别（支持Kimi/Qwen/Zhipu/Baidu/Doubao等多种模型）
- **AND** 所有操作必须在真实浏览器中执行

#### Scenario: 接口测试用例执行（预留）
- **GIVEN** 测试用例类型为"接口测试"
- **WHEN** 系统执行该用例
- **THEN** 使用API测试模式执行
- **AND** 直接发送真实HTTP请求验证

#### Scenario: 执行模式自动识别
- **GIVEN** 测试任务包含多种类型用例
- **WHEN** 系统执行测试任务
- **THEN** 自动识别每个用例的类型
- **AND** 为每个用例选择正确的执行模式

### Requirement: 被测对象信息读取与前置操作

系统 SHALL 能够在执行测试前读取项目的被测对象信息并完成前置操作。

#### Scenario: Web项目前置操作
- **GIVEN** 项目类型为Web应用
- **AND** 项目配置了访问地址、账号、密码
- **WHEN** 执行功能测试用例前
- **THEN** 自动读取项目配置的URL
- **AND** 启动真实浏览器并导航到该URL
- **AND** 如有配置账号密码，AI识别登录表单并真实输入完成登录

#### Scenario: C端项目前置操作
- **GIVEN** 项目类型为移动应用
- **AND** 项目配置了设备连接信息、App包名
- **WHEN** 执行功能测试用例前
- **THEN** 自动读取设备连接信息
- **AND** 连接真实测试设备
- **AND** 启动被测App

#### Scenario: 被测对象信息校验
- **GIVEN** 准备执行功能测试
- **WHEN** 读取项目被测对象信息
- **THEN** 校验必要信息是否完整
- **AND** 如信息缺失，提示用户补充

### Requirement: AI视觉元素识别

系统 SHALL 能够通过AI视觉识别页面上的可交互元素。

#### Scenario: 识别登录页面元素
- **GIVEN** 用户打开登录页面
- **WHEN** 系统截取真实页面截图并发送给配置的视觉模型API
- **THEN** 返回元素列表，包含：元素类型、文本内容、屏幕坐标(x,y,width,height)
- **AND** 元素置信度 >= 90%

#### Scenario: 定位特定元素
- **GIVEN** 测试步骤描述"点击登录按钮"
- **WHEN** 系统分析真实页面截图
- **THEN** 返回"登录"按钮的精确坐标
- **AND** 坐标误差 <= 5像素

### Requirement: 真实浏览器执行测试步骤

系统 SHALL 能够控制真实浏览器执行测试步骤。

#### Scenario: 执行点击操作
- **GIVEN** 测试步骤"点击登录按钮"
- **AND** AI识别到按钮坐标 (x=100, y=200)
- **WHEN** 系统调用浏览器控制器
- **THEN** 在真实浏览器中点击该位置
- **AND** 等待页面真实响应完成

#### Scenario: 执行输入操作
- **GIVEN** 测试步骤"在用户名输入框输入'testuser'"
- **WHEN** 系统定位输入框并输入文本
- **THEN** 真实浏览器中输入该文本
- **AND** 输入内容与预期一致

### Requirement: 智能结果验证

系统 SHALL 能够通过AI判断测试步骤执行结果。

#### Scenario: 验证登录成功
- **GIVEN** 执行了登录操作
- **WHEN** 系统截取真实操作后页面截图
- **AND** 发送给AI分析
- **THEN** AI判断"登录成功"或"登录失败"
- **AND** 给出判断理由

#### Scenario: 验证页面跳转
- **GIVEN** 点击了"进入首页"按钮
- **WHEN** 系统对比真实跳转前后截图
- **THEN** AI验证是否成功跳转到首页
- **AND** 识别当前页面内容

### Requirement: 执行过程可视化与视频录制

系统 SHALL 能够展示测试执行过程，并支持视频录制以便后续查看。

#### Scenario: 实时展示执行过程
- **GIVEN** 测试任务开始执行
- **WHEN** 每执行一个步骤
- **THEN** 前端实时显示当前操作
- **AND** 展示真实页面截图
- **AND** 标注正在操作的元素

#### Scenario: 可见模式配置
- **GIVEN** 测试任务配置为可见模式
- **WHEN** 执行测试用例时
- **THEN** 浏览器以 `headless=False` 模式启动
- **AND** 用户可以实时观察浏览器操作过程
- **AND** 可见模式可在测试用例级别或全局级别配置

#### Scenario: 视频录制模式
- **GIVEN** 测试任务配置为视频录制模式
- **WHEN** 执行测试用例时
- **THEN** 系统自动录制整个测试执行过程
- **AND** 视频文件保存到指定目录
- **AND** 视频包含时间戳和用例标识

#### Scenario: 视频与执行结果关联
- **GIVEN** 测试执行完成
- **WHEN** 用户查看测试报告
- **THEN** 可以播放对应测试用例的执行视频
- **AND** 视频播放进度与执行步骤同步
- **AND** 点击执行步骤可跳转到视频对应时间点

#### Scenario: 执行回放
- **GIVEN** 测试执行完成
- **WHEN** 用户查看执行记录
- **THEN** 可以按步骤回放执行过程
- **AND** 每步显示真实截图和操作详情
- **AND** 可以播放完整执行视频

### Requirement: 测试步骤元素定位增强

系统 SHALL 解决纯文字描述测试步骤无法执行的问题，为每个步骤补充元素定位信息。

#### Scenario: 首次执行时AI识别并记录元素定位
- **GIVEN** 测试步骤只有文字描述（如"点击登录按钮"）
- **WHEN** 首次执行该步骤时
- **THEN** AI截取当前页面截图
- **AND** 根据步骤描述识别目标元素坐标
- **AND** 通过JavaScript获取元素的CSS选择器、XPath、ID等属性
- **AND** 将元素定位信息保存到数据库，与步骤关联
- **AND** 后续执行优先使用已记录的定位信息

#### Scenario: 元素定位信息可视化编辑
- **GIVEN** 测试步骤已记录元素定位信息
- **WHEN** 测试工程师查看用例时
- **THEN** 显示步骤的文字描述
- **AND** 显示关联的元素定位信息（CSS选择器、坐标等）
- **AND** 在页面截图上高亮显示该元素位置
- **AND** 支持手动修改定位信息
- **AND** 支持重新选择元素（点击截图选择）

#### Scenario: 元素定位失败时自动重新识别
- **GIVEN** 测试步骤有历史元素定位信息
- **WHEN** 执行时历史定位方式失效
- **THEN** 自动降级到AI视觉识别
- **AND** AI重新识别目标元素
- **AND** 更新步骤的元素定位信息
- **AND** 标记该步骤需要人工审核

#### Scenario: 批量补充元素定位信息
- **GIVEN** 多个测试步骤缺少元素定位信息
- **WHEN** 测试工程师选择批量补充时
- **THEN** 系统依次执行每个步骤（仅用于记录定位）
- **AND** AI识别每个步骤的目标元素
- **AND** 记录元素定位信息
- **AND** 生成定位信息补充报告

### Requirement: 测试用例双视图管理

系统 SHALL 支持测试用例的业务视图（给第三方验收）和技术视图（给自动化执行）分离管理。

#### Scenario: 测试用例业务视图（给第三方验收）
- **GIVEN** 测试用例需要导出给第三方公司验收
- **WHEN** 导出测试用例时
- **THEN** 只包含业务信息：
  - 用例标题、编号、优先级
  - 前置条件（业务描述）
  - 测试步骤（纯业务操作描述，如"点击登录按钮"）
  - 测试数据（具体输入值，如"用户名：testuser001"）
  - 预期结果（业务验证点）
- **AND** 不包含技术信息（元素定位、代码等）
- **AND** 导出格式支持Excel/PDF/Word

#### Scenario: 测试用例技术视图（给自动化执行）
- **GIVEN** 测试用例需要自动化执行
- **WHEN** 查看技术视图时
- **THEN** 显示完整技术信息：
  - 业务描述（继承自业务视图）
  - 元素定位信息（CSS选择器、XPath、AI坐标）
  - 测试数据生成规则（随机数据、边界值等）
  - 执行代码/脚本（可选）
  - 执行历史记录
- **AND** 支持编辑技术信息
- **AND** 修改技术信息不影响业务视图

#### Scenario: 测试数据生成与管理
- **GIVEN** 测试步骤需要输入测试数据
- **WHEN** AI生成测试用例时
- **THEN** 根据字段类型自动生成测试数据：
  - 文本字段：生成随机字符串（如"产品线_20240328_001"）
  - 数字字段：生成随机数字（如"100"）
  - 日期字段：生成当前日期（如"2024-03-28"）
  - 枚举字段：随机选择一个选项
- **AND** 支持边界值测试数据：
  - 最小长度：1个字符
  - 最大长度：上限值（如描述50字）
  - 超长：上限+1（验证截断或报错）
  - 特殊字符：!@#$%^&*()
  - 空值：""
- **AND** 测试数据与步骤关联存储
- **AND** 支持手动修改测试数据

#### Scenario: 测试数据参数化
- **GIVEN** 多个测试用例使用相同的测试数据
- **WHEN** 定义测试数据参数时
- **THEN** 支持参数化引用：
  - `${random.product_name}` - 随机产品线名称
  - `${random.phone}` - 随机手机号
  - `${date.today}` - 当前日期
  - `${user.name}` - 当前用户名
- **AND** 参数在执行时动态生成
- **AND** 相同参数在同一次执行中保持一致

### Requirement: 测试用例优化与成本降低

系统 SHALL 提供机制优化AI生成的测试用例，降低AI视觉成本，同时保证测试质量。

#### Scenario: 测试用例人工审核与修正
- **GIVEN** AI生成了测试用例
- **WHEN** 测试工程师审核用例时
- **THEN** 可以查看用例的完整信息（步骤、预期结果、关联的测试点）
- **AND** 可以编辑用例步骤和预期结果
- **AND** 可以标记用例为"已审核"或"需优化"
- **AND** 审核后的用例存入用例库，提高可复用性

#### Scenario: 元素定位方式优化（降低AI成本）
- **GIVEN** 首次执行测试用例时
- **WHEN** AI成功识别并执行了某步骤
- **THEN** 系统记录该元素的多重定位信息：
  - AI识别坐标（备用）
  - CSS选择器（优先）
  - XPath（次优先）
  - 元素属性（id、name、class等）
  - 元素文本内容
- **AND** 下次执行时优先使用CSS/XPath定位，失败后才调用AI
- **AND** 定位信息在用例级别持久化存储

#### Scenario: 智能元素定位策略
- **GIVEN** 执行测试用例的某步骤
- **WHEN** 系统尝试定位元素时
- **THEN** 按以下优先级尝试：
  1. 使用历史成功的CSS选择器
  2. 使用历史成功的XPath
  3. 使用元素属性（id/name等）
  4. 以上都失败，调用AI视觉识别
- **AND** 如果AI识别成功，更新元素定位信息
- **AND** 如果连续3次AI识别坐标一致，自动生成CSS选择器

#### Scenario: 页面结构变化自适应
- **GIVEN** 页面结构发生变化
- **WHEN** 历史定位方式（CSS/XPath）失效时
- **THEN** 系统自动降级到AI视觉识别
- **AND** 执行成功后，尝试基于新页面结构生成新的CSS选择器
- **AND** 更新用例的元素定位信息
- **AND** 通知测试工程师页面结构已变化

#### Scenario: 用例执行模式选择（成本vs质量平衡）
- **GIVEN** 测试用例有历史定位信息
- **WHEN** 执行测试时
- **THEN** 支持选择执行模式：
  - **严格模式**：始终使用AI视觉，保证最高准确性（成本高）
  - **智能模式**：优先使用历史定位，失败后AI兜底（成本中等）★推荐
  - **快速模式**：仅使用历史定位，失败则跳过（成本低，适合回归）
- **AND** 不同模式可在用例级别、任务级别配置

#### Scenario: 用例相似度检测与复用
- **GIVEN** 系统中有大量测试用例
- **WHEN** AI生成新用例时
- **THEN** 检测与现有用例的相似度
- **AND** 如果相似度>80%，提示"该用例可能已存在"
- **AND** 展示相似用例列表，供测试工程师选择复用或创建新用例
- **AND** 避免重复用例，降低维护成本

#### Scenario: 用例质量评分与优化建议
- **GIVEN** 测试用例已执行多次
- **WHEN** 系统分析用例数据时
- **THEN** 计算用例质量评分：
  - 执行成功率（权重40%）
  - AI识别稳定性（权重30%）
  - 执行时间（权重20%）
  - 维护频率（权重10%）
- **AND** 对低分用例给出优化建议：
  - "该用例AI识别不稳定，建议添加更明确的元素标识"
  - "该用例执行时间过长，建议优化等待策略"
  - "该用例经常失败，建议检查被测系统稳定性"

#### Scenario: 批量用例优化
- **GIVEN** 多个测试用例需要优化
- **WHEN** 测试工程师选择批量优化时
- **THEN** 系统分析这些用例的共同点
- **AND** 提供批量优化方案：
  - 统一添加某前置步骤
  - 统一修改某操作方式
  - 统一调整等待时间
- **AND** 预览优化后的用例
- **AND** 确认后批量更新

### Requirement: 失败自动分析与重试

系统 SHALL 能够分析失败原因并尝试自动修复。

#### Scenario: 元素定位失败分析
- **GIVEN** 元素定位失败
- **WHEN** 系统截取真实当前页面
- **AND** 发送给AI分析
- **THEN** AI给出失败原因（元素不存在/位置变化/页面加载失败等）
- **AND** 建议修复方案

#### Scenario: 元素重定位
- **GIVEN** 原元素定位失败
- **AND** AI分析页面已变化
- **WHEN** 系统尝试通过语义描述重新定位
- **THEN** 在新页面中找到相似元素
- **AND** 继续执行测试

## MODIFIED Requirements

### Requirement: 测试执行器重构

**原实现**: 纯模拟执行，仅打印日志

**新实现**: 
- 支持按用例类型选择执行模式（功能测试/接口测试）
- 支持读取项目被测对象信息
- 支持Web端AI视觉执行
- 支持C端AI视觉执行（预留）
- 支持智能结果验证
- 支持失败自动分析
- **所有操作必须是真实的，禁止模拟**

**Migration**: 
- 保留原有数据库模型
- 新增执行模式选择（功能测试/接口测试）
- 新增项目配置关联
- 渐进式迁移，不影响历史数据

### Requirement: 项目模型扩展

**新增字段**:
- `test_object_type`: 被测对象类型（web/app）
- `test_object_url`: Web访问地址
- `test_object_username`: 登录账号
- `test_object_password`: 登录密码
- `test_object_device_info`: 设备连接信息（C端）
- `test_object_app_package`: App包名（C端）
- `test_object_app_activity`: 启动Activity（C端）

## REMOVED Requirements

### Requirement: 模拟执行模式

**Reason**: 模拟执行无法验证真实功能，必须使用真实浏览器和设备执行

**Migration**: 
- 删除所有模拟执行代码
- 所有测试必须在真实环境中执行

## 技术方案

### 多执行模式架构

```
┌─────────────────────────────────────────────────────────────┐
│                     测试任务执行流程                          │
│                                                             │
│  1. 读取项目被测对象信息                                       │
│  2. 完成前置操作（启动真实浏览器/连接真实设备）                 │
│  3. 遍历测试用例                                              │
│     ├─ 识别用例类型（功能/接口）                               │
│     ├─ 选择对应执行模式                                       │
│     └─ 在真实环境中执行用例                                    │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
┌──────────────────┐              ┌──────────────────┐
│   功能测试模式    │              │   接口测试模式    │
│  (AI视觉测试)     │              │   (真实HTTP请求)  │
│  真实浏览器/设备  │              │                  │
└────────┬─────────┘              └──────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ Web端  │ │ C端    │
│真实浏览器│ │真实设备│
└────────┘ └────────┘
```

### 功能测试执行流程

```
1. 接收测试任务
   │
2. 读取项目被测对象信息
   │
3. 读取可见模式配置（用例/任务/全局级别）
   │
4. 执行前置操作（真实环境）
   ├─ Web: 启动真实浏览器（根据配置决定是否可见） → 导航URL → AI识别登录表单 → 真实输入登录
   └─ C端: 连接真实设备 → 启动真实App
   │
5. 遍历功能测试用例
   │
6. 对每个测试步骤：
   │
   ├─ 6.1 检查步骤是否有元素定位信息
   │   ├─ 如果有：使用已记录的定位信息（CSS/XPath/AI坐标）
   │   └─ 如果没有：
   │       ├─ 6.1.1 截取真实页面截图
   │       ├─ 6.1.2 AI识别目标元素（输入: 截图 + 步骤描述）
   │       ├─ 6.1.3 通过JavaScript获取元素属性（id/class等）
   │       ├─ 6.1.4 生成CSS选择器
   │       └─ 6.1.5 保存定位信息到数据库
   │
   ├─ 6.2 开始视频录制（如启用）
   │
   ├─ 6.3 使用定位信息执行操作
   │   ├─ 尝试CSS选择器定位
   │   ├─ 失败则尝试XPath定位
   │   ├─ 失败则使用AI坐标定位
   │   └─ 所有方式失败则标记步骤失败
   │
   ├─ 6.4 在真实浏览器/设备中执行操作(点击/输入等)
   │
   ├─ 6.5 等待真实页面响应
   │
   ├─ 6.6 截取真实执行后截图
   │
   ├─ 6.7 AI验证真实执行结果
   │       (输入: 真实前后截图 + 预期结果)
   │       (输出: 是否通过 + 理由)
   │
   ├─ 6.8 更新定位信息使用统计（成功/失败次数）
   │
   ├─ 6.9 停止视频录制（如启用）
   │
   └─ 6.10 记录真实执行结果、截图和视频路径
   │
7. 生成测试报告（包含视频链接）
   │
8. 关闭真实浏览器/断开真实设备
```

### 项目配置数据结构

```python
# 项目被测对象信息
class TestObjectInfo:
    type: str  # "web" | "app"
    
    # Web端配置
    url: str  # 访问地址
    username: str  # 登录账号
    password: str  # 登录密码
    
    # C端配置
    device_id: str  # 设备ID
    app_package: str  # App包名
    app_activity: str  # 启动Activity

# 可见模式配置（支持多级配置）
class VisibilityConfig:
    # 全局默认配置
    global_headless: bool = True  # 默认无头模式
    global_record_video: bool = False  # 默认不录制视频
    video_save_path: str = "./videos"  # 视频保存路径
    video_resolution: tuple = (1280, 720)  # 视频分辨率
    video_fps: int = 30  # 视频帧率
    video_retention_days: int = 7  # 视频保留天数
    
    # 测试任务级别配置（覆盖全局）
    task_headless: Optional[bool] = None
    task_record_video: Optional[bool] = None
    
    # 测试用例级别配置（最高优先级）
    case_headless: Optional[bool] = None
    case_record_video: Optional[bool] = None

# 测试数据
class TestData:
    """测试数据"""
    id: int
    step_id: int  # 关联的测试步骤ID
    
    # 数据信息
    field_name: str  # 字段名称（如"产品线名称"）
    field_type: str  # 字段类型（text/number/date/enum等）
    data_value: str  # 数据值（具体值或生成规则）
    
    # 数据生成规则
    generation_rule: Optional[str] = None  # 生成规则（如"${random.product_name}"）
    is_random: bool = False  # 是否随机生成
    is_boundary: bool = False  # 是否边界值测试数据
    
    # 边界值信息
    boundary_type: Optional[str] = None  # min/max/overflow/empty/special
    max_length: Optional[int] = None  # 最大长度限制
    
    # 使用统计
    usage_count: int = 0  # 使用次数
    created_at: datetime
    updated_at: datetime

# 测试步骤扩展（关联元素定位和技术信息）
class TestStepExtended:
    """测试步骤扩展信息（技术视图）"""
    step_id: int  # 关联的TestStep ID
    
    # 步骤状态
    has_locator: bool = False  # 是否已记录元素定位
    locator_status: str = "pending"  # pending(待补充) / recorded(已记录) / verified(已验证) / failed(定位失败)
    
    # 定位信息（一对一关联）
    locator: Optional[ElementLocator] = None
    
    # 测试数据（一对多关联）
    test_data: List[TestData] = field(default_factory=list)
    
    # 执行代码（可选，用于高级场景）
    execution_code: Optional[str] = None  # Python/JavaScript代码
    
    # 审核信息
    reviewed_by: Optional[int] = None  # 审核人ID
    reviewed_at: Optional[datetime] = None  # 审核时间
    review_comment: Optional[str] = None  # 审核意见
    
    # 视图分离标记
    is_business_view: bool = True  # 是否属于业务视图
    is_technical_view: bool = True  # 是否属于技术视图

# 元素定位信息（用于降低AI成本）
class ElementLocator:
    """元素定位信息"""
    id: int
    step_id: int  # 关联的测试步骤ID
    
    # 元素描述（用于AI识别）
    element_description: str  # 元素描述（如"登录按钮"）
    element_type: Optional[str] = None  # 元素类型（button/input/link等）
    
    # 多重定位策略（按优先级排序）
    css_selector: Optional[str] = None  # CSS选择器（优先）
    xpath: Optional[str] = None  # XPath（次优先）
    element_id: Optional[str] = None  # 元素ID
    element_name: Optional[str] = None  # 元素name属性
    element_class: Optional[str] = None  # 元素class
    element_text: Optional[str] = None  # 元素文本内容
    
    # AI识别坐标（备用）
    ai_coordinate: Optional[Dict] = None  # {"x": 100, "y": 200, "width": 50, "height": 30}
    ai_confidence: float = 0.0  # AI识别置信度
    
    # 使用统计
    success_count: int = 0  # 成功次数
    fail_count: int = 0  # 失败次数
    last_used_at: Optional[datetime] = None  # 最后使用时间
    
    # 定位来源
    source: str = "ai"  # ai(AI识别) / manual(人工录入) / auto(自动生成)
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间
    
    # 定位策略优先级
    @property
    def priority_order(self) -> List[str]:
        """返回定位策略优先级列表"""
        strategies = []
        if self.css_selector:
            strategies.append("css")
        if self.xpath:
            strategies.append("xpath")
        if self.element_id:
            strategies.append("id")
        if self.element_name:
            strategies.append("name")
        if self.ai_coordinate:
            strategies.append("ai")
        return strategies
    
    def to_dict(self) -> Dict:
        """转换为字典，用于执行时快速定位"""
        return {
            "css_selector": self.css_selector,
            "xpath": self.xpath,
            "element_id": self.element_id,
            "element_name": self.element_name,
            "ai_coordinate": self.ai_coordinate,
        }

# 用例执行模式（成本vs质量平衡）
class ExecutionStrategy(Enum):
    STRICT = "strict"      # 严格模式：始终使用AI视觉（成本高，质量最高）
    SMART = "smart"        # 智能模式：优先历史定位，失败后AI兜底（推荐）
    FAST = "fast"          # 快速模式：仅使用历史定位，失败则跳过（成本低）

# 用例质量评分
class TestCaseQuality:
    case_id: int
    
    # 评分维度（0-100分）
    success_rate_score: int = 0      # 执行成功率（权重40%）
    ai_stability_score: int = 0      # AI识别稳定性（权重30%）
    execution_time_score: int = 0    # 执行时间（权重20%）
    maintenance_score: int = 0       # 维护频率（权重10%）
    
    @property
    def total_score(self) -> int:
        """计算综合评分"""
        return int(
            self.success_rate_score * 0.4 +
            self.ai_stability_score * 0.3 +
            self.execution_time_score * 0.2 +
            self.maintenance_score * 0.1
        )
    
    # 优化建议
    optimization_suggestions: List[str] = field(default_factory=list)

### 视频录制技术方案

```python
# Playwright视频录制配置
browser = await playwright.chromium.launch(
    headless=False  # 可见模式
)

context = await browser.new_context(
    record_video_dir="./videos/",  # 视频保存目录
    record_video_size={"width": 1280, "height": 720}  # 视频分辨率
)

page = await context.new_page()

# 执行测试步骤...

await context.close()
# 视频自动保存到指定目录，文件名为 {hash}_video.webm
```

**视频录制流程**：
1. 根据配置决定是否启用视频录制
2. 启动浏览器时配置 `record_video_dir` 和 `record_video_size`
3. 每个测试用例创建独立的浏览器上下文
4. 执行测试步骤（自动录制）
5. 关闭上下文时自动保存视频
6. 将视频路径关联到测试结果
7. 定期清理过期视频文件

**可见模式配置优先级**：
```
用例级别配置 > 任务级别配置 > 全局配置 > 默认值

例如：
- 全局: headless=True (默认无头)
- 任务: headless=False (可见模式)
- 用例: headless=None (继承任务配置)
结果: 该用例使用可见模式
```

### 元素定位缓存与成本优化技术方案

```python
# 智能元素定位器（降低AI成本）
class SmartElementLocator:
    """
    智能元素定位器
    
    策略：
    1. 优先使用历史成功的CSS/XPath定位（0成本）
    2. 其次使用元素属性定位（0成本）
    3. 最后使用AI视觉识别（高成本）
    4. AI识别成功后，自动提取CSS选择器并缓存
    """
    
    def __init__(self, browser_controller, vision_model, db_session):
        self.browser = browser_controller
        self.vision = vision_model
        self.db = db_session
    
    async def locate_element(
        self, 
        step_id: int, 
        action_description: str,
        strategy: ExecutionStrategy = ExecutionStrategy.SMART
    ) -> Optional[Dict]:
        """
        智能定位元素
        
        Args:
            step_id: 步骤ID，用于查询历史定位信息
            action_description: 操作描述
            strategy: 执行策略（严格/智能/快速）
        
        Returns:
            元素定位信息
        """
        # 获取历史定位信息
        locator = self._get_locator_from_db(step_id)
        
        # 严格模式：直接使用AI
        if strategy == ExecutionStrategy.STRICT:
            return await self._ai_locate(action_description)
        
        # 快速模式：仅使用历史定位
        if strategy == ExecutionStrategy.FAST:
            return await self._try_historical_locators(locator)
        
        # 智能模式：优先历史定位，失败后AI兜底
        element = await self._try_historical_locators(locator)
        if element:
            self._update_locator_stats(step_id, success=True)
            return element
        
        # 历史定位失败，使用AI
        logger.info(f"步骤 {step_id}: 历史定位失败，降级到AI识别")
        element = await self._ai_locate(action_description)
        
        if element:
            # AI识别成功，更新定位信息
            await self._update_locator(step_id, element, action_description)
            self._update_locator_stats(step_id, success=True)
        else:
            self._update_locator_stats(step_id, success=False)
        
        return element
    
    async def _try_historical_locators(
        self, 
        locator: Optional[ElementLocator]
    ) -> Optional[Dict]:
        """尝试使用历史定位信息"""
        if not locator:
            return None
        
        # 按优先级尝试不同定位策略
        strategies = [
            ("css", locator.css_selector, self._locate_by_css),
            ("xpath", locator.xpath, self._locate_by_xpath),
            ("id", locator.element_id, self._locate_by_id),
            ("name", locator.element_name, self._locate_by_name),
        ]
        
        for strategy_name, value, locate_func in strategies:
            if value:
                try:
                    element = await locate_func(value)
                    if element:
                        logger.debug(f"使用 {strategy_name} 定位成功: {value}")
                        return element
                except Exception as e:
                    logger.debug(f"{strategy_name} 定位失败: {e}")
        
        return None
    
    async def _ai_locate(self, action_description: str) -> Optional[Dict]:
        """使用AI视觉识别元素"""
        screenshot = await self.browser.take_screenshot()
        
        prompt = f"识别操作 '{action_description}' 的目标元素坐标"
        response = self.vision.analyze_image(screenshot, prompt)
        
        # 解析AI响应，返回坐标信息
        # ...
    
    async def _update_locator(
        self, 
        step_id: int, 
        element: Dict, 
        action_description: str
    ):
        """更新元素定位信息"""
        # 尝试基于AI坐标生成CSS选择器
        css_selector = await self._generate_css_selector(element)
        
        # 保存到数据库
        locator = ElementLocator(
            step_id=step_id,
            css_selector=css_selector,
            ai_coordinate=element,
            ai_confidence=element.get("confidence", 0)
        )
        self.db.merge(locator)
        self.db.commit()
    
    async def _generate_css_selector(self, element: Dict) -> Optional[str]:
        """
        基于元素信息生成CSS选择器
        
        策略：
        1. 如果有id，使用 #id
        2. 如果有class，使用 .class
        3. 如果有data-testid，使用 [data-testid="xxx"]
        4. 组合使用：tag.class[attr="value"]
        """
        # 通过JavaScript获取元素属性
        js_code = f"""
        (function() {{
            var elements = document.querySelectorAll('*');
            for (var i = 0; i < elements.length; i++) {{
                var rect = elements[i].getBoundingClientRect();
                if (Math.abs(rect.x - {element['x']}) < 5 && 
                    Math.abs(rect.y - {element['y']}) < 5) {{
                    return {{
                        id: elements[i].id,
                        class: elements[i].className,
                        tag: elements[i].tagName.toLowerCase(),
                        'data-testid': elements[i].getAttribute('data-testid'),
                        name: elements[i].getAttribute('name')
                    }};
                }}
            }}
            return null;
        }})()
        """
        
        attrs = await self.browser.execute_javascript(js_code)
        
        if attrs:
            if attrs.get('id'):
                return f"#{attrs['id']}"
            if attrs.get('data-testid'):
                return f"[data-testid='{attrs['data-testid']}']"
            if attrs.get('class'):
                classes = attrs['class'].split()[:2]  # 最多取2个class
                return f".{'.'.join(classes)}"
        
        return None

# 成本统计与优化建议
class CostOptimizer:
    """AI成本优化分析器"""
    
    def analyze_cost_savings(self, project_id: int) -> Dict:
        """
        分析成本节省情况
        
        Returns:
            {
                "total_steps": 1000,           # 总步骤数
                "ai_calls": 200,               # AI调用次数
                "cache_hits": 800,             # 缓存命中次数
                "cost_savings_rate": "80%",    # 成本节省率
                "estimated_savings": "￥500"   # 估计节省金额
            }
        """
        # 统计使用历史定位vs AI调用的比例
        pass
    
    def get_optimization_suggestions(self, case_id: int) -> List[str]:
        """
        获取用例优化建议
        
        建议类型：
        1. "该用例AI调用频率高，建议添加data-testid属性"
        2. "该用例执行时间长，建议优化等待策略"
        3. "该用例定位不稳定，建议使用更稳定的CSS选择器"
        """
        pass
```

**成本优化效果预估**：

| 场景 | 无优化 | 有优化 | 节省 |
|------|--------|--------|------|
| 首次执行 | 100% AI调用 | 100% AI调用 | 0% |
| 第2次执行 | 100% AI调用 | 20% AI调用 | 80% |
| 第5次执行 | 100% AI调用 | 10% AI调用 | 90% |
| 回归测试 | 100% AI调用 | 5% AI调用 | 95% |

**质量保证措施**：
1. **降级机制**：历史定位失败自动降级到AI
2. **一致性校验**：定期抽样使用AI验证历史定位准确性
3. **页面变化检测**：发现页面结构变化时，自动更新定位信息
4. **人工审核**：低质量用例标记，提醒测试工程师优化

## 阶段交付与质量门禁

### 单元测试规范（强制执行）

**测试原则：**
1. **真实执行优先**：所有涉及外部依赖（浏览器、API、数据库）的测试必须使用真实环境，禁止使用Mock
2. **覆盖率要求**：单元测试覆盖率必须 >= 95%
3. **测试准确性**：测试通过率必须 100%，不允许为了通过而修改测试
4. **发现问题优先**：测试的目的是发现代码问题，不是为了追求通过率

**测试类型要求：**
- **Mock测试**：仅用于不依赖外部环境的纯逻辑代码
- **真实测试**：所有涉及浏览器、AI API、数据库的测试必须使用真实环境
- **可见验证**：浏览器测试必须使用 `headless=False` 模式，确保能观察到真实窗口

**测试失败处理：**
1. 测试失败时，首先分析代码问题
2. 修复代码中的实际问题
3. 不允许修改测试脚本来让测试通过
4. 不允许用Mock替代真实测试来规避问题

### 第一阶段质量门禁（MVP）

**自测要求（100%通过后才能进入下一阶段）：**

1. **单元测试覆盖率** >= 95%（强制执行）
2. **单元测试通过率** = 100%（强制执行）
3. **真实测试比例** = 100%（涉及外部依赖的测试必须使用真实环境）
4. **功能测试用例通过率** >= 90%（使用真实测试网站）
5. **元素识别准确率** >= 90%
6. **前置操作成功率** >= 95%
7. **可见模式配置生效** - 配置可在用例/任务/全局级别生效
8. **视频录制功能正常** - 视频完整、清晰、可回放
9. **视频与执行结果正确关联** - 点击步骤可跳转到视频对应时间点
10. **代码审查通过**（无严重问题）
11. **类型检查通过**（无类型错误）
12. **核心原则检查通过**（无模拟操作）

**代码评审要求：**
- 每个Task完成后必须进行代码评审
- 评审人员：至少1名其他开发人员
- 评审内容：代码质量、功能正确性、性能、安全性
- 评审通过标准：无阻塞性问题，所有建议已处理或记录

### 第二阶段质量门禁

1. **AI结果验证准确率** >= 85%
2. **失败分析准确率** >= 80%
3. **元素重定位成功率** >= 75%
4. **单元测试覆盖率** >= 95%（强制执行）
5. **单元测试通过率** = 100%（强制执行）
6. **真实测试比例** = 100%（强制执行）
7. **代码审查通过**

### 第三阶段质量门禁

1. **功能测试用例通过率** >= 98%
2. **元素识别准确率** >= 95%
3. **并发执行稳定性**（无内存泄漏、无崩溃）
4. **缓存命中率** >= 90%
5. **单元测试覆盖率** >= 95%（强制执行）
6. **单元测试通过率** = 100%（强制执行）
7. **真实测试比例** = 100%（强制执行）
8. **代码审查通过**

## 成功指标

| 指标 | 目标值 | 当前值 |
|------|--------|--------|
| 功能测试用例通过率 | >= 98% | 0% |
| 元素识别准确率 | >= 95% | - |
| 单用例执行时间 | <= 30秒 | - |
| AI识别响应时间 | <= 3秒 | - |
| 失败自动恢复率 | >= 80% | - |
| 前置操作成功率 | >= 99% | - |
| 视频录制成功率 | >= 99% | - |
| 视频播放流畅度 | >= 30fps | - |
| 可见模式配置成功率 | >= 99% | - |

## 第一阶段交付范围（MVP）

1. 统一视觉模型客户端封装（支持Kimi/Qwen/Zhipu/Baidu/Doubao）
2. Playwright浏览器控制器（Web端）- 真实浏览器
3. 项目被测对象信息读取
4. 前置操作自动化（启动真实浏览器、AI识别登录表单、真实输入登录）
5. **测试步骤元素定位补充** - 解决纯文字描述无法执行的问题
6. **测试数据生成与管理** - 自动生成具体测试数据和边界值数据
7. **测试用例双视图管理** - 业务视图（给第三方）和技术视图（给自动化）分离
8. 基础元素识别（点击、输入）- 真实操作
9. 执行过程可视化 - 展示真实截图
10. **可见模式配置** - 支持用例/任务/全局级别配置浏览器可见性
11. **视频录制功能** - 录制测试执行过程并保存
12. 简单结果验证（成功/失败）- 基于真实截图
13. 用例类型识别与执行模式选择

**核心原则**：
- ✅ 所有浏览器操作必须是真实的
- ✅ 所有截图必须来自真实页面
- ✅ 所有AI识别必须基于真实截图
- ❌ 禁止使用任何模拟操作
- ❌ 禁止使用任何模拟数据

**不包含在第一阶段**：
- C端设备控制（Appium）
- 复杂手势操作（滑动、拖拽、多点触控）
- 失败自动重试
-