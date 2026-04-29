# Tasks - 双模式测试执行引擎

## Task 1: 执行引擎添加 execution_mode 参数

为 `test_execution_engine_v2.py` 的 `execute_test_case()` 和 `_execute_step()` 方法添加 `execution_mode` 参数，支持 "preprocess" | "realtime" | "smart" 三种模式。

- [x] SubTask 1.1: 在 `execute_test_case()` 方法签名中添加 `execution_mode: str = "smart"` 参数
- [x] SubTask 1.2: 在 `_execute_step()` 方法签名中添加 `execution_mode: str = "smart"` 参数
- [x] SubTask 1.3: 将 execution_mode 参数传递到需要的地方

## Task 2: 实现实时识别兜底逻辑

在 `_execute_step()` 中实现无预存定位时的实时识别分支逻辑。

- [x] SubTask 2.1: 分析现有 `_execute_step()` 第503-520行代码逻辑
- [x] SubTask 2.2: 添加 preprocess 模式分支：无 locator_record 时抛出异常
- [x] SubTask 2.3: 添加 realtime 模式分支：无 locator_record 时调用 smart_locate_element()
- [x] SubTask 2.4: 保持 smart 模式分支：优先使用预存定位，失败后AI兜底（现有逻辑）

## Task 3: 复用现有执行逻辑

确保不重复代码，复用现有的 `_execute_with_self_healing()` 等方法。

- [x] SubTask 3.1: 验证 `_execute_with_self_healing()` 可接受动态传入的 locator_record
- [x] SubTask 3.2: 验证 `smart_locate_element()` 返回格式与 `get_locator()` 一致
- [x] SubTask 3.3: 确保新增分支调用现有方法，不重复实现

## Task 4: 实现自动缓存机制

在智能模式下，实时识别成功后自动写入缓存。

- [x] SubTask 4.1: 在 ElementLocatorService 中添加 `realtime_record_locator()` 方法（可选，复用 record_locator）
- [x] SubTask 4.2: 在 realtime/smart 模式识别成功后调用 record_locator 写入缓存
- [x] SubTask 4.3: 设置 source="ai_realtime" 标记缓存来源

## Task 5: API 接口扩展

在执行相关 API 接口中添加 execution_mode 参数。

- [x] SubTask 5.1: 查找所有执行相关的 API 端点
- [x] SubTask 5.2: 在执行请求 schema 中添加 execution_mode 字段
- [x] SubTask 5.3: 在 API handler 中传递 execution_mode 到执行引擎

## Task 6: 前端执行模式选择器

在用例/任务执行页面添加执行模式选择器。

- [x] SubTask 6.1: 在执行按钮点击时弹出模式选择对话框
- [x] SubTask 6.2: 实现三种模式选项（预处理/实时/智能）
- [x] SubTask 6.3: 将选择的模式通过 API 传递到后端

## Task 7: 单元测试

为新功能编写单元测试，确保覆盖率 >= 95%。

- [x] SubTask 7.1: 编写 preprocess 模式异常抛出测试
- [x] SubTask 7.2: 编写 realtime 模式实时识别测试
- [x] SubTask 7.3: 编写 smart 模式缓存命中/失效测试
- [x] SubTask 7.4: 编写 execution_mode 参数传递测试

## Task Dependencies

- Task 1, 2, 3 有依赖关系，需按顺序完成
- Task 4 依赖 Task 2, 3 完成
- Task 5 依赖 Task 1, 2, 3 完成
- Task 6 可与 Task 5 并行开发
- Task 7 依赖所有功能开发完成后进行
