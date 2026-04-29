# MCP Direct Execution 混合方案 Spec

## Why

当前系统存在以下问题：
1. **重复执行**：AI 识别成功后，返回 locator 给 Controller，Controller 再执行一遍
2. **VisionRecognizer bug**：`recognize()` 方法签名与实际调用不匹配，传的是 `browser` 但方法期望 `page`
3. **资源浪费**：同时运行两个 Playwright 实例（Controller + MCP），但只做识别

## What Changes

### 1. 修复 VisionRecognizer bug
- **文件**：`app/services/recognizers/vision_recognizer.py`
- **问题**：`recognize(self, page, ...)` 但调用时传的是 `browser`
- **修复**：改为 `recognize(self, browser, ...)`，内部通过 `browser._page` 获取

### 2. 扩展 MCPRecognizer 执行能力
- **文件**：`app/services/recognizers/mcp_recognizer.py`
- **增强**：`execute_action()` 方法，完善执行逻辑
- **支持**：click、type、hover、select_option、wait_for 等操作

### 3. 新增执行策略路由
- **文件**：`app/services/element_locator_service.py`
- **新增**：根据配置选择「识别后 Controller 执行」或「识别后 MCP 直执」
- **配置项**：`MCP_DIRECT_EXECUTION_ENABLED: bool = False`

### 4. 修改执行引擎调用逻辑
- **文件**：`app/services/test_execution_engine_v2.py`
- **改动**：识别成功后，优先让 MCP 直接执行操作
- **回退**：MCP 执行失败时降级到 Controller

### 5. 新增配置项
- **文件**：`app/core/config.py`
- **新增**：`MCP_DIRECT_EXECUTION_ENABLED: bool = False`
- **说明**：默认关闭，保持向后兼容

## Impact

- **Affected specs**：
  - `playwright-mcp-integration` — 复用现有 MCP 客户端
  - `dual-mode-execution` — 复用执行模式逻辑

- **Affected code**：
  - `app/services/recognizers/vision_recognizer.py` — 修复 bug
  - `app/services/recognizers/mcp_recognizer.py` — 扩展执行能力
  - `app/services/element_locator_service.py` — 新增执行策略路由
  - `app/services/test_execution_engine_v2.py` — 修改调用逻辑
  - `app/core/config.py` — 新增配置项

## ADDED Requirements

### Requirement: MCP 直执执行

当 `MCP_DIRECT_EXECUTION_ENABLED=True` 时，系统 SHALL 在 AI 识别成功后直接调用 `MCPRecognizer.execute_action()` 执行操作，而不是返回 locator 给 Controller。

#### Scenario: MCP 直执成功
- **GIVEN** 配置 `MCP_DIRECT_EXECUTION_ENABLED=True`
- **WHEN** 步骤执行需要 AI 识别
- **THEN** AI 识别成功后，MCP 直接执行操作，跳过 Controller

#### Scenario: MCP 直执失败降级
- **GIVEN** 配置 `MCP_DIRECT_EXECUTION_ENABLED=True`
- **WHEN** MCP 执行操作失败
- **THEN** 降级到 Controller 执行，并记录降级日志

### Requirement: VisionRecognizer Bug 修复

VisionRecognizer 的 `recognize()` 方法 SHALL 正确处理 `browser` 参数，内部通过 `browser._page` 获取 page 对象。

#### Scenario: Vision 识别成功
- **WHEN** VisionRecognizer.recognize() 被调用
- **THEN** 正确获取 page 并执行截图

## MODIFIED Requirements

### Requirement: ElementLocatorService 执行策略

`ElementLocatorService` SHALL 新增执行策略路由，支持「识别后直执」和「识别后 Controller 执行」两种模式。

#### Scenario: 识别后 Controller 执行（默认）
- **GIVEN** `MCP_DIRECT_EXECUTION_ENABLED=False` 或 MCP 不可用
- **WHEN** 识别成功
- **THEN** 返回 locator_info 给 Controller 执行

#### Scenario: 识别后 MCP 直执
- **GIVEN** `MCP_DIRECT_EXECUTION_ENABLED=True` 且 MCP 可用
- **WHEN** 识别成功
- **THEN** 调用 `mcp_recognizer.execute_action()` 直执操作

## REMOVED Requirements

无

## 技术细节

### 执行流程对比

**当前流程（Controller 执行）**：
```
Controller.navigate(url)
Controller.click(selector)  ← 实际操作
    ↓
AI 识别元素
    ↓
返回 locator
    ↓
Controller.click(selector)  ← 重复执行？不，这是获取 locator 后执行
```

**MCP 直执流程**：
```
Controller.navigate(url)
    ↓
AI 识别 + MCP.execute_action()
    ↓
操作直接完成（单次执行）
```

### 两种模式的权衡

| 模式 | 优点 | 缺点 |
|------|------|------|
| **Controller 执行（默认）** | 功能完整（JS/滚动/Cookie）| 需转换 locator |
| **MCP 直执** | 减少转换开销 | 缺少 JS/滚动/Cookie |

### 建议

1. **默认关闭** (`MCP_DIRECT_EXECUTION_ENABLED=False`)
2. **简单操作可开启**：click、type、hover、select
3. **复杂场景仍用 Controller**：需要 JS、滚动、Cookie 等

## Migration

- 向后兼容：默认 `MCP_DIRECT_EXECUTION_ENABLED=False`
- 已有缓存不受影响：缓存的 locator 仍然可用
- 需要时可以随时切换