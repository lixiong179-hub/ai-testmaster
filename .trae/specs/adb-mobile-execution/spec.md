# ADB 移动端 AI 执行引擎 Spec

## Why

Midscene.js 支持通过 adb 直接控制 Android 设备，实现：
1. **无需 Appium 服务器**，轻量级集成
2. 自然语言描述操作，AI 实时识别 + adb 执行
3. 无需预定义元素定位信息

项目现有 Appium 方案存在以下问题：
1. 需要 Appium 服务器，重量级依赖
2. 需要配置 App 包名、Activity 等信息
3. 需要预定义元素定位才能执行
4. 无法做到 Midscene.js 一样的"说一句话就执行"

**核心痛点：坐标方案不跨设备**
- 不同设备分辨率不同，绝对坐标会失效
- 需要结合 UIAutomator 生成稳定的元素定位符

需要添加纯 adb 控制 + AI 实时识别能力，让移动端测试也能"说一句话就执行"。

## What Changes

- **新增 ADB 控制器** — `app/utils/adb_controller.py`，封装常见 adb 操作
- **新增 UIAutomator 元素提取器** — `app/utils/uiautomator_helper.py`，获取页面元素结构
- **新增移动端 AI 执行服务** — `app/services/mobile_ai_executor.py`，集成视觉识别 + adb 执行
- **复用现有 AI 能力** — `unified_vision_model.py` 的视觉识别能力
- **扩展执行引擎** — 扩展 `execution_mode` 支持移动端场景
- **移除 Appium 代码** — 删除 `mobile_controller.py` 和 `precondition_service.py` 中的 Appium 相关代码

## 移除的代码

| 文件 | 移除内容 |
|------|----------|
| `app/utils/mobile_controller.py` | 完全删除 |
| `app/services/precondition_service.py` | MobileController 初始化、_perform_mobile_login、_recognize_mobile_login_form 等 |
| `app/schemas/project.py` | platform、appium_url 字段（可选移除或标记废弃） |

## 技术方案

### 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                 移动端 AI 执行流程（首跑）                        │
│                                                                 │
│  用户输入："点击登录按钮"                                        │
│                    │                                            │
│                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  MobileAIExecutor                                        │   │
│  │  1. ADB 截图：adb exec-out screencap -p                 │   │
│  │  2. AI 识别：Kimi/智谱 分析截图                          │   │
│  │  3. AI 返回：按钮坐标 (x=500, y=800)                   │   │
│  │  4. ADB 点击：adb shell input tap 500 800               │   │
│  │  5. UIAutomator：获取页面元素结构                        │   │
│  │  6. 生成：Accessibility ID / resource-id                 │   │
│  │  7. 缓存到 ElementLocator                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 移动端执行流程（后续回归）                        │
│                                                                 │
│  用户输入："点击登录按钮"                                        │
│                    │                                            │
│                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  MobileAIExecutor                                        │   │
│  │  1. 读取缓存的 Accessibility ID                         │   │
│  │  2. UIAutomator 查找元素                                 │   │
│  │  3. 获取元素坐标                                         │   │
│  │  4. ADB 点击坐标                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 前置条件对比

| 步骤 | Appium | ADB + UIAutomator |
|------|--------|-------------------|
| 安装软件 | Appium Server | 无（系统自带 adb） |
| 启动服务 | 需要启动 Appium | 无 |
| 配置 App | 包名、Activity | 不需要 |
| 元素定位 | XPath（需预定义） | AI 实时识别 + UIAutomator |
| 跨设备支持 | XPath 通用 | Accessibility ID 通用 |
| 准备时间 | 5-10 分钟 | 10 秒 |

### ADB 命令封装

| 操作 | ADB 命令 | 用途 |
|------|---------|------|
| 点击 | `adb shell input tap x y` | 点击指定坐标 |
| 输入文本 | `adb shell input text "xxx"` | 输入文本 |
| 滑动 | `adb shell input swipe x1 y1 x2 y2` | 滑动操作 |
| 按键 | `adb shell input keyevent xx` | 按键事件 |
| 截图 | `adb exec-out screencap -p` | 获取屏幕截图 |
| 设备列表 | `adb devices` | 获取已连接设备 |
| 系统按键 | `adb shell input keyevent 4` | 返回键 |

### UIAutomator 命令

| 操作 | 命令 | 用途 |
|------|------|------|
| 页面 dump | `adb shell uiautomator dump` | 获取页面 XML |
| 点击元素 | `adb shell input tap` + 坐标 | 点击元素 |
| 获取元素 | 解析 XML | 提取 Accessibility ID |

### AI 视觉识别 + 元素缓存流程

```
首跑流程：
1. adb exec-out screencap -p → 获取屏幕截图
2. vision_model.recognize_bytes() → AI 返回坐标 + 元素描述
3. uiautomator dump → 获取页面 XML 结构
4. 匹配 AI 描述的元素 → 提取 Accessibility ID / resource-id
5. 缓存坐标 + Accessibility ID 到 ElementLocator

后续流程：
1. 读取缓存的 Accessibility ID
2. uiautomator dump → 获取当前页面 XML
3. 查找匹配 Accessibility ID 的元素
4. 获取元素坐标
5. adb shell input tap x y → 执行点击
```

### 元素定位符优先级

| 优先级 | 定位符 | 示例 |
|--------|--------|------|
| 1 | resource-id | `com.example:id/login_btn` |
| 2 | accessibility-id | `login_button` |
| 3 | text | `text="登录"` |
| 4 | content-desc | `content-desc="登录按钮"` |
| 5 | 相对坐标 | 屏幕下方1/3处 |

## ADDED Requirements

### Requirement: ADB 控制器

系统 SHALL 提供 ADB 控制器封装常见移动端操作。

#### Scenario: 点击操作
- **WHEN** 调用 `adb.click(x, y)`
- **THEN** 执行 `adb shell input tap x y`

#### Scenario: 文本输入
- **WHEN** 调用 `adb.input_text("hello")`
- **THEN** 执行 `adb shell input text "hello"`

#### Scenario: 滑动操作
- **WHEN** 调用 `adb.swipe(x1, y1, x2, y2, duration=500)`
- **THEN** 执行 `adb shell input swipe x1 y1 x2 y2`

#### Scenario: 截图获取
- **WHEN** 调用 `adb.take_screenshot()`
- **THEN** 执行 `adb exec-out screencap -p` 返回 bytes

#### Scenario: 获取设备列表
- **WHEN** 调用 `adb.list_devices()`
- **THEN** 返回已连接设备列表

#### Scenario: 设备连接检查
- **WHEN** 调用 `adb.is_device_connected()`
- **THEN** 检查设备是否在线

### Requirement: UIAutomator 元素提取器

系统 SHALL 提供 UIAutomator 封装获取页面元素结构。

#### Scenario: 获取页面元素
- **WHEN** 调用 `uiautomator.dump_page()`
- **THEN** 执行 `adb shell uiautomator dump` 返回 XML
- **AND** 解析 XML 返回元素列表

#### Scenario: 查找元素
- **WHEN** 调用 `uiautomator.find_element(accessibility_id="login")`
- **THEN** 在页面 XML 中查找匹配元素
- **AND** 返回元素坐标

#### Scenario: 点击元素
- **WHEN** 调用 `uiautomator.click_element(accessibility_id="login")`
- **THEN** 查找元素 → 获取坐标 → ADB 点击

### Requirement: 移动端 AI 执行服务

系统 SHALL 提供移动端 AI 执行服务，集成视觉识别、UIAutomator 和 ADB 控制。

#### Scenario: 自然语言点击（首跑）
- **GIVEN** 用户操作描述为"点击登录按钮"
- **WHEN** 调用 `mobile_executor.execute_action("点击登录按钮")`
- **THEN** 执行流程：
  1. `adb.take_screenshot()` 获取截图
  2. `vision_model.recognize_bytes()` AI 识别元素
  3. `uiautomator.dump_page()` 获取页面结构
  4. AI 描述 + UIAutomator → 生成 Accessibility ID
  5. `adb.click(x, y)` 执行点击
  6. 缓存 Accessibility ID + 坐标

#### Scenario: 自然语言点击（后续回归）
- **GIVEN** 缓存中存在 Accessibility ID
- **WHEN** 调用 `mobile_executor.execute_action("点击登录按钮")`
- **THEN** 执行流程：
  1. 读取缓存的 Accessibility ID
  2. `uiautomator.find_element()` 查找元素
  3. 获取元素坐标
  4. `adb.click(x, y)` 执行点击

#### Scenario: 识别失败处理
- **GIVEN** AI 无法识别目标元素
- **WHEN** vision_model 返回空结果或置信度 < 0.7
- **THEN** 抛出 `MobileAIError("无法识别目标元素")`
- **AND** 返回当前截图供分析

#### Scenario: 缓存失效降级
- **GIVEN** 缓存的 Accessibility ID 在当前页面找不到
- **WHEN** 执行时元素匹配失败
- **THEN** 降级到 AI 实时识别
- **AND** 更新缓存

### Requirement: 移动端执行模式

系统 SHALL 支持移动端执行模式，扩展现有的 `execution_mode`。

#### Scenario: 移动端实时识别模式
- **GIVEN** `execution_mode="mobile_realtime"`
- **WHEN** 执行移动端测试步骤
- **THEN** 使用 ADB + AI 视觉识别 + UIAutomator

#### Scenario: 移动端智能模式（缓存优先）
- **GIVEN** `execution_mode="mobile_smart"`
- **WHEN** 执行移动端测试步骤
- **THEN** 优先使用缓存的 Accessibility ID
- **AND** 缓存失效时自动降级到 AI 识别

## 与 Midscene.js 对比

| 能力 | Midscene.js | 本方案 |
|------|-------------|--------|
| adb 控制 | ✅ | ✅ |
| 自然语言执行 | ✅ | ✅ |
| AI 视觉识别 | GPT-4o/Qwen | Kimi/智谱等 |
| 坐标点击 | ✅ | ✅ |
| UIAutomator 结合 | ❌ | ✅ |
| 跨设备适配 | XPath | Accessibility ID |
| 无需预定位 | ✅ | ✅ |
| 技术栈 | Node.js | Python |
| 前置配置 | 无 | 仅 USB 连接 |
| **引入新依赖** | - | ❌ 仅 adb |

## 交付标准

### 功能验收

1. `adb_controller.py` 封装常见 adb 操作（点击、输入、滑动、截图）
2. `uiautomator_helper.py` UIAutomator 元素提取和点击
3. `mobile_ai_executor.py` 集成 AI + UIAutomator + ADB
4. 支持自然语言描述操作，首跑后自动生成 Accessibility ID 缓存
5. 后续执行优先使用缓存，支持跨设备
6. 缓存失效时自动降级到 AI 实时识别

### 移除验收

1. `mobile_controller.py` 完全删除
2. `precondition_service.py` 中的 MobileController 相关代码删除
3. 不影响 Web 端测试功能

### 质量标准

1. 不造成代码冗余
2. 复用现有代码
3. 单元测试覆盖率 >= 95%
4. ADB 操作超时处理
5. UIAutomator 页面解析容错
6. 设备断开连接检测

## 实施计划

### Phase 1: ADB 控制器
- `app/utils/adb_controller.py`

### Phase 2: UIAutomator 元素提取器
- `app/utils/uiautomator_helper.py`

### Phase 3: 移动端 AI 执行服务
- `app/services/mobile_ai_executor.py`

### Phase 4: 集成到执行引擎
- 扩展 `execution_mode` 支持移动端

### Phase 5: 移除 Appium 代码
- 删除 `mobile_controller.py`
- 清理 `precondition_service.py` 中的 Appium 相关代码
