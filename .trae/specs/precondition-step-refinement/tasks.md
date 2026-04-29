# Tasks

## 任务1: 创建前置条件步骤数据库模型
- [ ] 子任务 1.1: 在 `app/models/test_case.py` 中新增 `TestCasePreconditionStep` 模型
- [ ] 子任务 1.2: 在 `app/schemas/test_case.py` 中新增对应的Schema（Create/Update/Response）
- [ ] 子任务 1.3: 创建数据库迁移脚本，新增 `test_case_precondition_steps` 表

## 任务2: 新增前置条件步骤CRUD接口
- [ ] 子任务 2.1: 在 `app/api/v1/endpoints/test_case.py` 中新增获取前置条件步骤列表接口
- [ ] 子任务 2.2: 新增创建/编辑/删除前置条件步骤接口
- [ ] 子任务 2.3: 新增批量保存前置条件步骤接口

## 任务3: AI解析前置条件文本为步骤
- [ ] 子任务 3.1: 在 `app/utils/ai_client.py` 中新增 `parse_precondition_to_steps` 函数
- [ ] 子任务 3.2: 设计前置条件解析的prompt模板
- [ ] 子任务 3.3: 新增API端点 `/api/v1/test-cases/{case_id}/parse-precondition`

## 任务4: 测试执行引擎集成前置条件步骤
- [ ] 子任务 4.1: 在 `TestExecutionEngineV2._execute_precondition` 之后，新增执行用例前置条件步骤的逻辑
- [ ] 子任务 4.2: 前置条件步骤执行失败时，标记整个用例执行失败
- [ ] 子任务 4.3: 前置条件步骤的执行结果单独记录（在执行日志中体现）

## 任务5: 批量定位补充集成前置条件步骤
- [ ] 子任务 5.1: 在 `BatchLocatorService` 中新增执行前置条件步骤的逻辑
- [ ] 子任务 5.2: 前置条件步骤也需要补充元素定位
- [ ] 子任务 5.3: 执行前置条件步骤后，再执行测试步骤的定位补充

## 任务6: 前端技术视图新增前置条件步骤编辑区
- [ ] 子任务 6.1: 在 `src/views/case/CaseDetail.vue` 技术视图中新增「前置条件步骤」面板
- [ ] 子任务 6.2: 展示前置条件文本和步骤列表
- [ ] 子任务 6.3: 支持手动添加/删除/编辑前置条件步骤
- [ ] 子任务 6.4: 新增「AI解析」按钮，调用解析接口
- [ ] 子任务 6.5: 新增「批量补充定位」按钮（复用现有批量定位功能）

## 任务7: 技术视图构建响应集成前置条件步骤
- [ ] 子任务 7.1: 在 `TestCaseViewService.get_technical_view` 中新增查询前置条件步骤的逻辑
- [ ] 子任务 7.2: 在技术视图响应中新增 `precondition_steps` 字段

# Task Dependencies
- [任务2] 依赖于 [任务1]
- [任务3] 依赖于 [任务1]
- [任务4] 依赖于 [任务1]
- [任务5] 依赖于 [任务1]
- [任务6] 依赖于 [任务2, 任务3, 任务7]
- [任务7] 依赖于 [任务1]
