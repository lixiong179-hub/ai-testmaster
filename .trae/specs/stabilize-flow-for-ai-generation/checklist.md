# Checklist

## Phase 1：前端边条件必填
- [x] EdgeConditionDialog 对 branch/exception/bypass 的 condition 做空值校验
- [x] branch 条件缺失时提示"请填写分支触发条件"
- [x] exception 条件缺失时提示"请填写异常场景"
- [x] bypass 条件缺失时提示"请填写旁路出现时机"
- [x] normal 边允许空条件，不做拦截
- [x] 单元测试覆盖：条件填写/未填写时的通过/拦截行为

## Phase 2：主干顺序显式化（前端）
- [x] FlowSortEditor 节点模型支持 `main_order` 字段
- [x] UI 提供主干节点"前移/后移"操作
- [x] 提交时 main 节点按 `main_order` 排序写入 `flow_sort_data.nodes`
- [x] 非 main 节点不受 `main_order` 影响，保持现有策略
- [x] 单元测试覆盖：排序逻辑、UI 交互

## Phase 3：后端读取 main_order
- [x] context_mixin.py 构建主干节点列表时检测 `main_order`
- [x] 存在 `main_order` 时严格按升序排列主干节点
- [x] 缺失 `main_order` 时回退现有排序逻辑（兼容旧数据）
- [x] 单元测试覆盖：有/无 `main_order` 的场景

## Phase 4：提交前完整性检查（前端）
- [x] ai-generate.vue 提交前检查至少 1 个 main 节点
- [x] main 节点 >= 2 时检查主干连接关系完整性
- [x] 检查所有节点 `screen_name` 非空
- [x] 检查非 normal 边 condition 非空（兜底）
- [x] warning 不拦截提交，以弹窗/Toast 展示
- [x] 单元测试覆盖：各检查项触发/不触发场景

## Phase 5：后端 schema / warning 增强
- [x] flow_tree_mixin.py 对缺失 condition 的 branch/exception/bypass 记录 warning 日志
- [x] context 中追加 `condition_incomplete_hint` 弱提示文案
- [x] 保留兜底逻辑（"未指定"），不中断流程
- [x] 入参 schema 增加 screen_name 非空校验
- [x] 入参 schema 增加 flow_type / edge_type 合法性校验
- [x] 入参 schema 增加 branch/exception/bypass 的 condition 非空校验
- [x] 非法入参返回 400 并附带明确错误信息
- [x] 单元测试覆盖：prompt 构建、schema 校验

## Phase 6：提交结构增强
- [x] 节点 schema 增加 `main_order` 字段（integer，可选）
- [x] 边 schema 增加 `expected_result` 字段（string，可选）
- [x] 前端提交时透传 `main_order` 与 `expected_result`
- [x] 后端对 `expected_result` 先透传/忽略，不破坏现有逻辑

## 综合验收
- [x] 同一张图仅调整视觉位置，不会改变 AI 主干步骤顺序
- [x] branch / exception / bypass 未填条件时，前端不能静默放过
- [x] 后端对新旧数据都兼容（有 main_order 按 main_order，无则回退）
- [x] 提交前能识别明显低质量图并给出 warning
- [x] AI prompt 中主干、分支、异常的描述更稳定，不再频繁出现"未指定"
