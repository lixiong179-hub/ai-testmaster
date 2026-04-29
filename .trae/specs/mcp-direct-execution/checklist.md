# Checklist - MCP Direct Execution 混合方案

## VisionRecognizer Bug 修复

- [x] Task 1.1: 分析确认 bug 原因（recognize 方法签名与调用不匹配）
- [x] Task 1.2: VisionRecognizer.recognize() 正确接收 browser 参数并通过 browser._page 获取
- [x] Task 1.3: VisionRecognizer 在 use_mcp=False 时能正常工作

## MCPRecognizer.execute_action() 扩展

- [x] Task 2.1: execute_action() 覆盖 click/type/hover/select 操作
- [x] Task 2.2: 操作类型映射正确（role/text/css/ref → MCP 操作）
- [x] Task 2.3: 操作执行结果正确反馈
- [x] Task 2.4: MCP 可用时操作能正确执行

## 配置项新增

- [x] Task 3.1: MCP_DIRECT_EXECUTION_ENABLED 配置存在，默认 False
- [x] Task 3.2: MCP_EXECUTION_OPERATION_TYPES 配置存在，定义支持的操作类型

## ElementLocatorService 执行策略路由

- [x] Task 4.1: _should_direct_execute() 方法正确判断是否直执
- [x] Task 4.2: direct_execute_action() 方法正确调用 MCP 执行
- [x] Task 4.3: smart_locate_element() 根据配置选择执行策略
- [x] Task 4.4: 直执失败时正确降级

## TestExecutionEngineV2 调用逻辑

- [x] Task 5.1: _execute_step() 调用 smart_locate_element() 不受影响
- [x] Task 5.2: Controller 执行逻辑不受影响
- [x] Task 5.3: 降级逻辑正常工作

## 单元测试

- [x] Task 6.1: VisionRecognizer bug 修复测试通过
- [x] Task 6.2: MCPRecognizer.execute_action() 测试通过
- [x] Task 6.3: ElementLocatorService 执行策略路由测试通过
- [x] Task 6.4: 降级逻辑测试通过
- [x] Task 6.5: 覆盖率 >= 95%

## 代码评审修复

- [x] H-1: _direct_executed 标记使用 pop 移除，不会污染数据库缓存
- [x] H-2: input_value 日志脱敏处理（首尾保留，中间替换为 ***）
- [x] H-3: CSS 选择器注入风险确认（已使用 arguments 参数化，无需修复）
- [x] H-4: recognize() 调用时正确传递 action_type 参数

## 整体验证

- [x] MCP_DIRECT_EXECUTION_ENABLED=False 时，系统行为不变（向后兼容）
- [x] MCP_DIRECT_EXECUTION_ENABLED=True 时，MCP 可用的操作直接执行
- [x] MCP 不可用或执行失败时，降级到 Controller
- [x] 缓存机制正常工作（不影响 ElementLocator 缓存）
- [x] 90 个单元测试全部通过
