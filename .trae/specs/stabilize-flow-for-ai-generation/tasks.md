# Tasks

## Phase 1：前端边条件必填（高优先级，投入产出比最高）
- [x] Task 1：EdgeConditionDialog 增加 condition 必填校验
  - [x] SubTask 1.1：在 `EdgeConditionDialog.vue` 的确认逻辑前，按 `edge_type` 校验 `condition` 非空
  - [x] SubTask 1.2：branch 未填时提示"请填写分支触发条件"
  - [x] SubTask 1.3：exception 未填时提示"请填写异常场景"
  - [x] SubTask 1.4：bypass 未填时提示"请填写旁路出现时机"
  - [x] SubTask 1.5：normal 边保持不校验，允许空条件
  - [x] SubTask 1.6：补充单元测试：校验通过/失败场景

## Phase 2：主干顺序显式化（前端）
- [x] Task 2：FlowSortEditor 支持 main_order 编辑与提交
  - [x] SubTask 2.1：在节点数据模型中新增 `main_order` 字段
  - [x] SubTask 2.2：UI 上为主干节点增加"前移/后移"操作
  - [x] SubTask 2.3：提交时 main 节点按 `main_order` 排序后写入
  - [x] SubTask 2.4：非 main 节点保持现有策略
  - [x] SubTask 2.5：补充单元测试：排序逻辑、UI交互

## Phase 3：后端读取 main_order（高优先级）
- [x] Task 3：Context 构建优先按 main_order 排序主干节点
  - [x] SubTask 3.1：修改 `context_mixin.py`，检测 `main_order`
  - [x] SubTask 3.2：存在 `main_order` 时严格按升序排列
  - [x] SubTask 3.3：缺失 `main_order` 时回退到现有排序逻辑
  - [x] SubTask 3.4：补充单元测试：有/无 main_order 的场景

## Phase 4：提交前完整性检查（前端）
- [x] Task 4：ai-generate.vue 提交前增加 warning 级检查
  - [x] SubTask 4.1：检查至少存在 1 个 main 节点
  - [x] SubTask 4.2：main 节点 >= 2 时检查主干连接关系
  - [x] SubTask 4.3：检查所有节点 `screen_name` 非空
  - [x] SubTask 4.4：检查非 normal 边 condition 非空
  - [x] SubTask 4.5：warning 以弹窗/Toast 展示，不拦截提交
  - [x] SubTask 4.6：补充单元测试

## Phase 5：后端 schema / warning 增强
- [x] Task 5：PromptBuilder 对缺失条件记录 warning 并弱提示
  - [x] SubTask 5.1：在 `flow_tree_mixin.py` 中遍历边时检测 condition
  - [x] SubTask 5.2：缺失时记录 warning 日志
  - [x] SubTask 5.3：context 中追加 `condition_incomplete_hint` 弱提示
  - [x] SubTask 5.4：保留现有兜底逻辑
  - [x] SubTask 5.5：补充单元测试

- [x] Task 6：后端入参 schema 增加轻量校验
  - [x] SubTask 6.1：screen_name 非空校验
  - [x] SubTask 6.2：flow_type 合法性校验
  - [x] SubTask 6.3：edge_type 合法性校验
  - [x] SubTask 6.4：branch/exception/bypass 的 condition 非空校验
  - [x] SubTask 6.5：错误信息明确，返回 400
  - [x] SubTask 6.6：补充单元测试

## Phase 6：提交结构增强（顺手预留）
- [x] Task 7：flow_sort_data 结构扩展
  - [x] SubTask  7.1：节点 schema 增加 `main_order` 字段
  - [x] SubTask 7.2：边 schema 增加 `expected_result` 字段
  - [x] SubTask 7.3：前端提交时透传这两个字段
  - [x] SubTask 7.4：后端先透传/忽略 `expected_result`

# Task Dependencies
- Task 2 依赖 Task 1
- Task 3 依赖 Task 2
- Task 4 可与 Task 1/2 并行
- Task 5/6 可与 Task 3 并行
- Task 7 可与 Task 2/3 并行
