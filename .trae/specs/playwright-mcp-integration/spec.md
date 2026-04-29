# Playwright MCP 引入 Spec

## Why

当前Web端测试执行依赖批量预补充元素定位（BatchLocatorService），每步执行前都需要VLM识别坐标，成本高（¥0.002/步）、速度慢（3-5秒/步）、不稳定（依赖截图质量）。微软官方的Playwright MCP通过Accessibility Tree实现元素定位，用普通文本LLM替代视觉模型，成本降低95%，速度提升10倍。需要引入Playwright MCP作为Web端元素定位的默认方式，同时简化批量定位服务或将其降级为备选。

## What Changes

- **引入Playwright MCP Server** — 通过npx @playwright/mcp启动MCP服务器，支持Chrome/Firefox/WebKit
- **新增AccessibilityTreeLocator** — 基于Playwright MCP的Accessibility Tree实现元素定位，复用element_locator_service的prompt和方法签名
- **重构ElementLocatorService** — 将AI识别能力抽象为ElementRecognizer接口，VisionRecognizer（原有）和MCPRecognizer（新增）分别实现
- **简化BatchLocatorService** — 批量定位流程改为调用AccessibilityTreeLocator或MCPRecognizer，而非独立调用VLM
- **复用现有UnifiedVisionModel** — MCP方案使用已有的analyze_text纯文本LLM调用，不引入新的AI客户端
- **执行引擎自适应选择** — 根据配置或页面类型自动选择MCP或传统方案

## Impact

- Affected specs: vision-model-optimization, batch-locator-optimization, ai-test-case-executability-optimization, ui-automation-enhancement
- Affected code:
  - `app/utils/playwright_mcp_client.py` — **新建**：Playwright MCP客户端封装
  - `app/services/element_locator_service.py` — 重构为策略模式，支持Vision/MCP双识别器
  - `app/services/batch_locator_service.py` — 简化为调用统一识别接口
  - `app/services/test_execution_engine_v2.py` — 移除独立的AI Self-Healing调用，改用MCP兜底
  - `app/core/config.py` — 新增 PLAYWRIGHT_MCP_ENABLED 配置
  - `app/interfaces/element_recognizer.py` — **新建**：识别器抽象接口
  - `app/utils/mcp_text_llm.py` — **新建**：复用analyze_text的文本LLM调用封装

## ADDED Requirements

### Requirement: Playwright MCP Server启动与管理

系统 SHALL 提供Playwright MCP Server的启动和管理能力。

#### Scenario: MCP Server自动启动
- **GIVEN** 系统配置 `PLAYWRIGHT_MCP_ENABLED=True`
- **WHEN** 测试执行引擎初始化时
- **THEN** 自动启动 `npx @playwright/mcp` 作为子进程
- **AND** MCP Server监听本地端口（如 `localhost:3000`）
- **AND** 建立STDIO连接

#### Scenario: MCP Server连接稳定性
- **GIVEN** MCP Server运行中
- **WHEN** 连接断开或超时
- **THEN** 自动重连（最多3次）
- **AND** 记录连接状态日志
- **AND** 重连失败时降级到视觉模型方案

#### Scenario: MCP Server仅Web端启用
- **GIVEN** 测试对象类型为 APP（移动端）
- **WHEN** 执行初始化
- **THEN** 不启动MCP Server
- **AND** 继续使用Appium方案

### Requirement: AccessibilityTreeLocator元素定位

系统 SHALL 通过Playwright MCP的Accessibility Tree实现元素定位，复用ElementLocatorService的方法签名。

#### Scenario: 通过role+text定位按钮
- **GIVEN** 页面包含"登录"按钮（Accessibility Tree中有 `{role: "button", name: "登录"}`）
- **WHEN** 调用 `recognize_element(screenshot, "点击登录按钮")`
- **THEN** 发送 `{role: "button", text: "登录"}` 给MCP
- **AND** MCP返回元素的引用ID
- **AND** 执行点击操作

#### Scenario: 通过css selector定位
- **GIVEN** 需要点击id为"submit-btn"的元素
- **WHEN** 调用 `recognize_element(screenshot, "点击提交按钮")`
- **THEN** 发送 `{css: "#submit-btn"}` 给MCP
- **AND** MCP返回元素引用

#### Scenario: 元素不存在时的处理
- **GIVEN** 页面没有匹配的"登录"按钮
- **WHEN** MCP定位返回空结果
- **THEN** 返回定位失败，附带失败原因
- **AND** 不抛出异常

### Requirement: 识别器抽象接口

系统 SHALL 定义统一的元素识别接口ElementRecognizer，VisionRecognizer和MCPRecognizer分别实现。

#### Scenario: ElementRecognizer接口定义
```python
class ElementRecognizer(ABC):
    @abstractmethod
    async def recognize(self, page, operation_description: str) -> RecognitionResult:
        pass

    @abstractmethod
    async def batch_recognize(self, page, operations: List[str]) -> List[RecognitionResult]:
        pass
```

#### Scenario: VisionRecognizer实现
- **GIVEN** 配置选择视觉模型方案
- **WHEN** 调用 `element_locator.recognize()`
- **THEN** 使用原有的VLM识别流程（截图→VLM→坐标）

#### Scenario: MCPRecognizer实现
- **GIVEN** 配置选择MCP方案
- **WHEN** 调用 `element_locator.recognize()`
- **THEN** 使用Playwright MCP的Accessibility Tree定位
- **AND** 调用文本LLM（analyze_text）理解操作意图

### Requirement: 复用analyze_text文本LLM调用

系统 SHALL 使用UnifiedVisionModel已有的analyze_text方法，不引入新的AI客户端。

#### Scenario: MCP模式下的LLM理解
- **GIVEN** 用户步骤为"点击登录按钮"
- **WHEN** MCP获取Accessibility Tree后需要理解操作目标
- **THEN** 调用 `vision_model.analyze_text(prompt)` 其中prompt包含页面snapshot和操作描述
- **AND** 返回理解结果（定位器类型和参数）

#### Scenario: prompt模板
```
页面Accessibility Tree:
{accessibility_tree}

用户操作：点击登录按钮

请根据Accessibility Tree确定要操作元素的定位方式。
返回JSON格式：
{{
  "locator_type": "role|text|css|xpath",
  "locator_value": "对应的值",
  "confidence": 0.0-1.0
}}
```

### Requirement: 执行引擎MCP兜底替代AI Self-Healing

系统 SHALL 在元素定位失败时，使用MCP作为兜底方案，而非独立的VLM调用。

#### Scenario: 定位失败触发MCP兜底
- **GIVEN** 元素定位失败（locator无效或缺失）
- **WHEN** 配置 `AI_SELF_HEALING_ENABLED=True` 且 `PLAYWRIGHT_MCP_ENABLED=True`
- **THEN** 启用MCP Accessibility Tree重新定位
- **AND** 不单独调用VLM截图+识别

#### Scenario: MCP兜底也失败
- **GIVEN** MCP兜底定位也失败
- **WHEN** 达到重试上限
- **THEN** 标记步骤失败，记录详细日志
- **AND** 不再尝试其他方案

### Requirement: 配置项新增

系统 SHALL 提供Playwright MCP相关的配置项。

#### Scenario: MCP启用配置
- **GIVEN** 管理员配置 `PLAYWRIGHT_MCP_ENABLED=true`
- **WHEN** 系统启动
- **THEN** Web端测试默认使用MCP方案

#### Scenario: MCP禁用时降级
- **GIVEN** 配置 `PLAYWRIGHT_MCP_ENABLED=false`
- **WHEN** Web端测试执行
- **THEN** 回退到原有的批量定位+视觉模型方案

## MODIFIED Requirements

### Requirement: ElementLocatorService重构为策略模式

**原实现**: 硬编码调用VLM识别（`self._recognize_element`）

**修改后**:
- 注入 `ElementRecognizer` 实现（VisionRecognizer 或 MCPRecognizer）
- 构造函数接收 `recognizer: ElementRecognizer` 参数
- `recognize_element` 方法调用 `recognizer.recognize()`
- 默认 recognizer 从配置读取或按页面类型自动选择

### Requirement: BatchLocatorService简化

**原实现**: 独立调用VLM进行批量识别，有独立的prompt和流程

**修改后**:
- 复用 ElementLocatorService 的统一识别接口
- 批量定位调用 `recognizer.batch_recognize()`
- 移除独立的VLM调用逻辑（避免代码重复）
- 保留批量定位的任务管理、超时、重试逻辑

### Requirement: test_execution_engine_v2移除重复VLM调用

**原实现**: `_local_ai_self_heal` 独立调用 `vision_model.analyze_image`

**修改后**:
- `_local_ai_self_heal` 改用 `MCPRecognizer.recognize()` 兜底
- 或完全移除_self_heal，依赖MCP的实时定位能力
- 保留 `AI_SELF_HEALING_ENABLED` 配置，但效果变为"启用MCP兜底"

## REMOVED Requirements

### Requirement: BatchLocatorService独立的VLM调用逻辑

**Reason**: 批量定位将复用ElementLocatorService的能力，避免代码重复。MCP模式下不再需要独立的批量定位服务。

**Migration**: 批量定位场景下优先使用MCP的batch_recognize能力

### Requirement: 独立的AI Self-Healing VLM调用

**Reason**: MCP的Accessibility Tree提供了更稳定的实时定位能力，不再需要独立的Self-Healing VLM调用作为兜底。

**Migration**: Self-Healing能力由MCP的实时定位替代，保持`AI_SELF_HEALING_ENABLED`配置语义但实现方式改变

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     TestExecutionEngineV2                       │
│                                                                  │
│  ┌──────────────┐    ┌─────────────────┐                       │
│  │ ElementLocator│───▶│ ElementRecognizer│                       │
│  │  Service     │    │    (Interface)   │                       │
│  └──────────────┘    └─────────────────┘                       │
│         │                   ▲                                   │
│         │          ┌───────┴───────┐                           │
│         │          │               │                           │
│  ┌──────┴──────┐ ┌─┴───────────┐ ┌─┴───────────┐               │
│  │VisionRecognizer│ │MCPRecognizer│ │              │               │
│  │  (原有VLM)  │ │(Playwright) │ │              │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│                           │                                      │
│                    ┌──────┴──────┐                              │
│                    │ Playwright   │                              │
│                    │ MCP Server   │                              │
│                    │ (npx @pw/mcp)│                              │
│                    └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘

配置驱动：
- PLAYWRIGHT_MCP_ENABLED=true → 使用MCPRecognizer
- PLAYWRIGHT_MCP_ENABLED=false → 使用VisionRecognizer
```

## 与Vision Model Optimization的关系

- **VisionModelOptimization** 专注UI原型解析的双模式（vision/text）
- **本Spec** 专注Web端测试执行的元素定位（Vision/MCP双方案）
- 两者共享 `UnifiedVisionModel.analyze_text` 纯文本LLM调用能力
- MCP模式下UI原型解析仍可用text模式（OCR+LLM），形成完整零VLM链路
