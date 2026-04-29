# Tasks - MCP Direct Execution 混合方案

## Task 1: 修复 VisionRecognizer bug

修复 `VisionRecognizer.recognize()` 方法签名与调用不匹配的问题。

- [x] SubTask 1.1: 分析 `VisionRecognizer.recognize()` 期望参数 `page`，但 `smart_locate_element()` 传入 `browser`
- [x] SubTask 1.2: 修改 `VisionRecognizer.recognize()` 接收 `browser` 参数，内部通过 `browser._page` 获取
- [x] SubTask 1.3: 验证 VisionRecognizer 在 `use_mcp=False` 时能正常工作

## Task 2: 扩展 MCPRecognizer.execute_action()

完善 `MCPRecognizer.execute_action()` 方法，支持更多操作类型。

- [x] SubTask 2.1: 分析当前 `execute_action()` 实现，确认 click/type/hover/select 覆盖情况
- [x] SubTask 2.2: 完善操作类型映射（role/text/css/ref → MCP 操作）
- [x] SubTask 2.3: 添加操作执行结果反馈
- [x] SubTask 2.4: 验证 MCP 可用时操作能正确执行

## Task 3: 新增配置项 MCP_DIRECT_EXECUTION_ENABLED

在 `config.py` 中新增配置项。

- [x] SubTask 3.1: 在 `app/core/config.py` 新增 `MCP_DIRECT_EXECUTION_ENABLED: bool = False`
- [x] SubTask 3.2: 在 `app/core/config.py` 新增 `MCP_EXECUTION_OPERATION_TYPES: str = "click,type,hover,select"`

## Task 4: ElementLocatorService 新增执行策略路由

在 `ElementLocatorService` 中新增执行策略选择逻辑。

- [x] SubTask 4.1: 新增 `_should_direct_execute()` 方法判断是否直执
- [x] SubTask 4.2: 新增 `direct_execute_action()` 方法调用 MCP 执行
- [x] SubTask 4.3: 在 `smart_locate_element()` 成功后根据配置选择执行策略
- [x] SubTask 4.4: 直执失败时正确降级到 Controller 返回模式

## Task 5: 修改 TestExecutionEngineV2 调用逻辑

修改执行引擎，适配新的执行策略。

- [x] SubTask 5.1: 分析现有 `_execute_step()` 中对 `smart_locate_element()` 的调用
- [x] SubTask 5.2: 修改调用逻辑，适配 ElementLocatorService 的返回模式变化
- [x] SubTask 5.3: 确保 Controller 执行逻辑不受影响
- [x] SubTask 5.4: 确保降级逻辑正常工作

## Task 6: 单元测试

为新功能编写单元测试。

- [x] SubTask 6.1: 编写 VisionRecognizer bug 修复测试
- [x] SubTask 6.2: 编写 MCPRecognizer.execute_action() 测试
- [x] SubTask 6.3: 编写 ElementLocatorService 执行策略路由测试
- [x] SubTask 6.4: 编写降级逻辑测试
- [x] SubTask 6.5: 确保覆盖率 >= 95%

## Task 7: 代码评审修复

修复代码评审中发现的高严重度问题。

- [x] SubTask 7.1: H-1 修复 `_direct_executed` 标记污染缓存（使用 pop 移除标记）
- [x] SubTask 7.2: H-2 修复 `input_value` 明文日志（添加脱敏函数）
- [x] SubTask 7.3: H-3 确认 CSS 选择器注入风险（已使用 arguments 参数化，无需修复）
- [x] SubTask 7.4: H-4 修复 `recognize()` 未传递 `action_type` 参数

## Task Dependencies

- Task 1 可独立进行
- Task 2 可独立进行
- Task 3 可独立进行
- Task 4 依赖 Task 1, 2, 3 完成
- Task 5 依赖 Task 4 完成
- Task 6 依赖 Task 4, 5 完成
- Task 7 依赖 Task 4, 5, 6 完成

## 工作量评估

| Task | 改动范围 | 风险 |
|------|---------|------|
| Task 1 | 小（修复 bug） | 低 |
| Task 2 | 中（完善方法） | 低 |
| Task 3 | 小（配置项） | 低 |
| Task 4 | 中（核心逻辑） | 中 |
| Task 5 | 中（适配改动） | 中 |
| Task 6 | 中（测试） | 低 |
| Task 7 | 小（评审修复） | 低 |

**总体评估**：中等工作量，核心改动在 Task 4/5，风险可控。
