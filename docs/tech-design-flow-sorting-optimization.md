# 截图流程图排序优化 — 技术设计文档

## 一、项目背景与现状分析

### 1.1 核心问题
当前 AI 生成测试用例页面仅支持线性排序（1~N），存在以下痛点：
- 无法表达分支/异常/旁路流程，AI 生成用例可用率仅约 70%
- 前端排序数据未完整传递到后端，数据传递链路断裂
- 无法覆盖复杂业务场景（如登录异常、弹窗广告、条件分支等）

### 1.2 已完成工作
- 前端：FlowSortEditor/FlowNodeCard/EdgeConditionDialog 组件 + flowSort Store
- 后端：FlowSortDataSchema + PromptBuilder + FlowTreeMixin + API 端点改造
- 数据链路：mode/flow_sort_data 参数传递 + graph_prompt 支持

### 1.3 遗留问题（本次优化目标）
| 优先级 | 问题 | 影响 |
|--------|------|------|
| P1 | 流式端点未支持 graph 模式 | SSE 实时推送无法使用流程图排序 |
| P1 | @vue-flow CSS 在 scoped style 中导入 | 构建时重复打包，性能损耗 |
| P1 | 请求体缺少大小限制 | 恶意用户可提交超大 flow_sort_data |
| P2 | EdgeConditionDialog 未集成编辑功能 | 无法修改已有连线条件 |
| P2 | 缺少 FlowTreeMixin 单元测试 | 核心逻辑无测试覆盖 |
| P2 | 缺少 Schema 边界校验测试 | 字段校验规则未验证 |

---

## 二、优化范围

### 2.1 前端优化
1. **CSS 全局导入迁移**：将 `@vue-flow` CSS 从 FlowSortEditor.vue 移到全局入口
2. **EdgeConditionDialog 编辑集成**：在 FlowSortEditor 中支持双击/右键编辑已有连线

### 2.2 后端优化
1. **流式端点 graph 模式支持**：`ai_enhanced_generate_stream` 处理 mode='graph'
2. **请求体大小限制**：API 端点增加 flow_sort_data 的 nodes/edges 数量上限
3. **代码结构优化**：提取 graph 模式处理为独立服务函数

### 2.3 测试补充
1. **FlowTreeMixin 单元测试**：覆盖 _build_flow_tree/_build_branch_tree/_build_exception_tree/_build_bypass_tree
2. **FlowSortDataSchema 边界测试**：覆盖字段校验、类型限制、空值处理
3. **EdgeConditionDialog 组件测试**：覆盖创建/编辑/取消场景

---

## 三、技术方案

### 3.1 流式端点 graph 模式支持

**现状**：`ai_enhanced_generate_stream` 仅处理 `enhanced_mode`，未识别 `mode='graph'`。

**方案**：
```python
# 在 ai_enhanced_generate_stream 中添加 graph 模式分支
if request.mode == 'graph' and request.flow_sort_data:
    # 复用非流式端点的 graph 模式处理逻辑
    # 通过 SSE 推送生成进度
    graph_prompt = PromptBuilder.build_graph_prompt(...)
    # 调用 generate_test_case_enhanced 获取结果
    # 包装为 SSE 格式推送
```

**关键决策**：
- 复用现有 `PromptBuilder.build_graph_prompt`，避免重复实现
- SSE 推送格式与非流式端点保持一致（code/message/data 结构）

### 3.2 CSS 全局导入迁移

**现状**：FlowSortEditor.vue 的 scoped style 中通过 `@import` 导入 `@vue-flow` CSS。

**方案**：
```typescript
// main.ts 中添加全局导入
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/additional-components/dist/style.css'
```

**关键决策**：
- 全局导入一次，所有使用 VueFlow 的组件共享
- 删除 FlowSortEditor.vue 中的 `@import` 语句

### 3.3 请求体大小限制

**现状**：`flow_sort_data` 未限制 nodes/edges 数量，存在 DoS 风险。

**方案**：
```python
# AIGenerateEnhancedRequest 中增加校验
@field_validator('flow_sort_data')
@classmethod
def validate_flow_sort_data_size(cls, v):
    if v and len(v.nodes) > 100:
        raise ValueError('nodes数量不能超过100')
    if v and len(v.edges) > 200:
        raise ValueError('edges数量不能超过200')
    return v
```

### 3.4 EdgeConditionDialog 编辑集成

**现状**：EdgeConditionDialog 已支持 `edgeData` prop 回显，但 FlowSortEditor 未传入已有连线数据。

**方案**：
```typescript
// FlowSortEditor 中添加 edge-click 事件处理
const onEdgeClick = (event: EdgeMouseEvent) => {
  const edge = event.edge
  currentConnection.value = { source: edge.source, target: edge.target }
  currentEdgeForm.value = {
    edge_type: edge.data?.edge_type || 'normal',
    condition: edge.data?.condition || ''
  }
  conditionDialogVisible.value = true
}
```

---

## 四、落地步骤

### Phase 1: 后端改造（2h）
1. `test_case_ai_enhanced.py`：流式端点添加 graph 模式分支
2. `test_case.py`：FlowSortDataSchema 添加数量限制校验
3. 提取 `_handle_graph_generation` 共享函数

### Phase 2: 前端改造（1.5h）
1. `main.ts`：添加 @vue-flow CSS 全局导入
2. `FlowSortEditor.vue`：删除 scoped style 中的 @import
3. `FlowSortEditor.vue`：集成 edge-click 编辑功能

### Phase 3: 单元测试（2h）
1. `test_flow_tree_mixin.py`：FlowTreeMixin 测试
2. `test_flow_sort_schema.py`：Schema 边界测试
3. `EdgeConditionDialog.spec.ts`：组件行为测试

### Phase 4: 验证（0.5h）
1. `vue-tsc --noEmit`：TypeScript 类型检查
2. `pytest tests/`：Python 单元测试
3. `npm run test`：前端组件测试

---

## 五、预期效果

| 指标 | 当前 | 预期 |
|------|------|------|
| 流式端点 graph 模式 | 不支持 | ✅ 支持 |
| CSS 重复打包 | 每个页面重复 | ✅ 全局一次 |
| 请求体安全 | 无限制 | ✅ nodes≤100, edges≤200 |
| 连线编辑 | 不支持 | ✅ 双击编辑 |
| FlowTreeMixin 测试覆盖 | 0% | ≥95% |
| Schema 边界测试 | 0% | ≥95% |

---

## 六、风险评估

| 风险 | 等级 | 应对措施 |
|------|------|----------|
| 流式端点改造引入回归 | 中 | 保留原有 linear 分支逻辑，仅新增 graph 分支 |
| CSS 全局导入影响其他组件 | 低 | @vue-flow CSS 命名空间隔离，不影响全局样式 |
| 数量限制影响正常业务 | 低 | 100 nodes/200 edges 远超实际业务需求（通常<20） |

---

## 七、命名规范

- 文件：`test_flow_tree_mixin.py`、`flowSort.spec.ts`
- 类：`TestFlowTreeMixin`、`TestFlowSortDataSchema`
- 方法：`test_build_branch_tree_with_valid_data`
- 常量：`MAX_FLOW_NODES = 100`、`MAX_FLOW_EDGES = 200`
