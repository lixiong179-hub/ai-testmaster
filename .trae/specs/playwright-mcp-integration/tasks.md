# Tasks

- [x] Task 1: 创建识别器抽象接口 — 新建 ElementRecognizer ABC 接口定义
  - [x] SubTask 1.1: 新建 `app/interfaces/element_recognizer.py`
  - [x] SubTask 1.2: 定义 `RecognitionResult` dataclass（locator_type、locator_value、confidence、raw_result）
  - [x] SubTask 1.3: 定义 `ElementRecognizer` ABC（recognize、batch_recognize 方法签名）

- [x] Task 2: 创建 Playwright MCP 客户端封装 — 新建 `playwright_mcp_client.py`
  - [x] SubTask 2.1: 创建 `PlaywrightMCPClient` 类，管理MCP Server连接和生命周期
  - [x] SubTask 2.2: 实现 `browser_snapshot()` — 获取页面Accessibility Tree
  - [x] SubTask 2.3: 实现 `browser_click(selector)` — 通过Accessibility Tree定位并点击
  - [x] SubTask 2.4: 实现 `browser_type(selector, text)` — 输入文本
  - [x] SubTask 2.5: 实现 `browser_navigate(url)` — 导航
  - [x] SubTask 2.6: 实现 `browser_screenshot()` — 截图（复用Playwright能力）
  - [x] SubTask 2.7: 实现连接管理和自动重连逻辑
  - [x] SubTask 2.8: 实现 `is_available()` 健康检查

- [x] Task 3: 创建 MCP 文本 LLM 封装 — 复用 analyze_text
  - [x] SubTask 3.1: 新建 `app/utils/mcp_text_llm.py`
  - [x] SubTask 3.2: 实现 `MCPAwareLLM` 类，封装 analyze_text 调用
  - [x] SubTask 3.3: 实现 `理解操作意图 → 生成定位器` 的 prompt 模板
  - [x] SubTask 3.4: 实现 `parse_locator_result()` — 解析LLM返回的JSON定位结果

- [x] Task 4: 实现 MCPRecognizer — Playwright MCP 识别器
  - [x] SubTask 4.1: 新建 `app/services/recognizers/mcp_recognizer.py`
  - [x] SubTask 4.2: 实现 `MCPRecognizer` 类，实现 `ElementRecognizer` 接口
  - [x] SubTask 4.3: 实现 `recognize()` — 调用MCP获取snapshot → LLM理解 → 返回定位器
  - [x] SubTask 4.4: 实现 `batch_recognize()` — 批量识别
  - [x] SubTask 4.5: 处理MCP不可用时的降级逻辑

- [x] Task 5: 实现 VisionRecognizer — 原有VLM识别器适配
  - [x] SubTask 5.1: 新建 `app/services/recognizers/vision_recognizer.py`
  - [x] SubTask 5.2: 实现 `VisionRecognizer` 类，实现 `ElementRecognizer` 接口
  - [x] SubTask 5.3: 迁移 `ElementLocatorService._recognize_element` 逻辑
  - [x] SubTask 5.4: 实现 `batch_recognize()` — 批量VLM识别

- [x] Task 6: 重构 ElementLocatorService 为策略模式
  - [x] SubTask 6.1: 修改 `app/services/element_locator_service.py` 构造函数
  - [x] SubTask 6.2: 注入 `ElementRecognizer` 实现（Vision 或 MCP）
  - [x] SubTask 6.3: 将 `recognize_element` 方法改为调用 `self.recognizer.recognize()`
  - [x] SubTask 6.4: 添加 `create_locator_service()` 工厂方法，根据配置创建对应识别器
  - [x] SubTask 6.5: 保留原有 `_recognize_element` 方法，标记为废弃（向后兼容）

- [x] Task 7: 简化 BatchLocatorService
  - [x] SubTask 7.1: 修改 `app/services/batch_locator_service.py`
  - [x] SubTask 7.2: 移除独立的VLM调用逻辑（复用ElementLocatorService）
  - [x] SubTask 7.3: 改为调用统一的 `ElementRecognizer.batch_recognize()`
  - [x] SubTask 7.4: 保留任务管理、超时、重试逻辑
  - [x] SubTask 7.5: 添加根据 `PLAYWRIGHT_MCP_ENABLED` 选择识别器的逻辑

- [x] Task 8: 执行引擎移除重复VLM调用
  - [x] SubTask 8.1: 修改 `app/services/test_execution_engine_v2.py`
  - [x] SubTask 8.2: 将 `_local_ai_self_heal` 改用 `MCPRecognizer.recognize()` 兜底
  - [x] SubTask 8.3: MCP失败时降级到VLM视觉模型
  - [x] SubTask 8.4: 保持 `AI_SELF_HEALING_ENABLED` 配置语义

- [x] Task 9: 配置项新增
  - [x] SubTask 9.1: 修改 `app/core/config.py`
  - [x] SubTask 9.2: 新增 `PLAYWRIGHT_MCP_ENABLED: bool = True` 配置项
  - [x] SubTask 9.3: 新增 `PLAYWRIGHT_MCP_SERVER_PORT: int = 3000` 配置项
  - [x] SubTask 9.4: 新增 `MCP_TEXT_LLM_MODEL: str = "deepseek-chat"` 配置项

- [x] Task 10: 清理和验证
  - [x] SubTask 10.1: 验证无代码重复（批量定位不独立调用VLM）
  - [x] SubTask 10.2: 验证测试执行引擎不再独立调用VLM进行元素定位
  - [x] SubTask 10.3: 验证两种识别器可以无缝切换

# Task Dependencies

- [Task 3] depends on [Task 1] — MCP文本LLM需要RecognitionResult类型定义
- [Task 4] depends on [Task 2, Task 3] — MCPRecognizer依赖MCP客户端和LLM封装
- [Task 5] depends on [Task 1] — VisionRecognizer依赖接口定义
- [Task 6] depends on [Task 4, Task 5] — ElementLocatorService注入识别器
- [Task 7] depends on [Task 6] — BatchLocatorService使用ElementLocatorService
- [Task 8] depends on [Task 4] — 执行引擎使用MCPRecognizer兜底
- [Task 9] is independent — 配置项独立
- [Task 10] depends on [Task 7, Task 8] — 清理验证依赖改造完成
