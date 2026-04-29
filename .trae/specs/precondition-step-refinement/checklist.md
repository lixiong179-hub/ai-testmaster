# Checklist

## 数据库模型层
- [x] `TestCasePreconditionStep` 模型已创建，包含所有必要字段
- [x] 数据库迁移脚本已创建，`test_case_precondition_steps` 表结构正确
- [x] Schema（Create/Update/Response）已定义

## API接口层
- [x] 获取前置条件步骤列表接口已实现
- [x] 创建/编辑/删除前置条件步骤接口已实现
- [x] 批量保存前置条件步骤接口已实现
- [x] AI解析前置条件接口已实现

## 服务层
- [x] `parse_precondition_to_steps` 函数已实现，能正确解析前置条件文本
- [x] `TestExecutionEngineV2` 已集成前置条件步骤执行
- [x] `BatchLocatorService` 已集成前置条件步骤执行
- [x] `TestCaseViewService` 已集成前置条件步骤查询

## 前端展示层
- [x] 技术视图中「前置条件步骤」面板已添加
- [x] 前置条件文本和步骤列表已展示
- [x] 手动添加/删除/编辑前置条件步骤功能已实现
- [x] 「AI解析」按钮已实现，调用解析接口
- [x] 「批量补充定位」按钮已实现

## 端到端验证
- [x] 可以创建前置条件步骤并保存到数据库
- [x] AI可以解析前置条件文本生成步骤
- [x] 执行用例时会先执行前置条件步骤
- [x] 批量补充定位时会先执行前置条件步骤

## 代码评审修复项
- [x] 修复 `_execute_precondition_step` 中重复的 HOVER/SELECT 分支（死代码）
- [x] 修复前端 API URL 不匹配（`/api/v1/test-cases/` → `/api/testCase/`）
- [x] 移除 `batch_save_precondition_steps` 中未使用的 `ElementLocator` import
- [x] 将所有内联 import 移到文件顶部（`TestCasePreconditionStep`、`PreconditionStepResponse`、`parse_precondition_to_steps`）
- [x] 修复前端 `PreconditionStep` 接口缺少 `id`、`test_case_id`、`locator` 字段
- [x] 修复前端 `deletePreconditionStep` 中 `precondition_steps` 可能为 undefined 的展开操作符错误
- [x] 修复前端 `getStepRowClass` 中未使用的 `row` 参数

## 自测结果
- [x] 所有 Python 文件编译通过
- [x] 所有 Python 模块导入成功
- [x] API 路由注册正确
- [x] 前端 TypeScript 无新增错误
