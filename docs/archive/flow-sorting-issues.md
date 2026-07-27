# 流程图排序功能问题跟踪清单

> 创建时间：2026-04-21
> 最后更新：2026-04-21
> 状态：修复中

---

## 问题状态概览

| 状态 | 数量 | 说明 |
|------|------|------|
| 🔴 待修复 | 3 | P0 级别，阻塞功能 |
| 🟡 待审查 | 2 | P1 级别，影响质量 |
| 🟢 已修复 | 0 | 已完成修复并验证 |
| ⚪ 新发现 | 0 | 修复过程中发现的新问题 |

---

## P0 级别问题（阻塞功能，必须修复）

### ISSUE-001: 后端 API 未接收 mode 和 flow_sort_data 参数

**严重级别：** 🔴 阻塞  
**发现时间：** 2026-04-21  
**涉及文件：** `app/api/v1/endpoints/test_case_ai.py`  
**问题描述：**  
`AIGenerateEnhancedRequest` Schema 中缺少 `mode` 和 `flow_sort_data` 字段定义，导致前端传递的流程图排序数据被后端直接忽略。

**影响范围：**  
- 前端传递的 `mode: 'graph'` 和 `flow_sort_data` 完全无效
- AI 无法获取流程图结构信息
- 流程图排序功能完全无法工作

**修复方案：**  
在 `AIGenerateEnhancedRequest` 中增加字段：
```python
from typing import Literal
from pydantic import Field

class AIGenerateEnhancedRequest(BaseModel):
    # ... 现有字段 ...
    mode: Literal['linear', 'graph'] = Field(default='linear', description="排序模式")
    flow_sort_data: Optional[FlowSortDataSchema] = Field(None, description="流程图排序数据")
```

**修复状态：** ⚪ 待修复  
**修复人：** 后端  
**预计耗时：** 30 分钟

---

### ISSUE-002: 后端未调用 PromptBuilder.build_graph_prompt

**严重级别：** 🔴 阻塞  
**发现时间：** 2026-04-21  
**涉及文件：** `app/api/v1/endpoints/test_case_ai.py`  
**问题描述：**  
API 端点调用 `generate_test_case_enhanced` 时，未将 `flow_sort_data` 转换为 `graph_prompt` 传入 context，导致 `ai_client_enhanced.py` 中的 `generate_test_case_enhanced` 函数 fallback 到旧版 Prompt 模板。

**影响范围：**  
- 即使修复 ISSUE-001，AI 仍使用旧版 Prompt
- 流程图结构信息无法传递给 AI
- `PromptBuilder.build_graph_prompt` 已实现但从未被调用

**修复方案：**  
在 API 端点中增加逻辑：
```python
if request_data.mode == 'graph' and request_data.flow_sort_data:
    from app.services.prompt_builder import PromptBuilder
    graph_prompt = PromptBuilder.build_graph_prompt(
        nodes=[n.model_dump() for n in request_data.flow_sort_data.nodes],
        edges=[e.model_dump() for e in request_data.flow_sort_data.edges],
        module_info=request_data.flow_sort_data.module_info,
        requirement_content=context.get('requirement_content', ''),
        test_point_json=json.dumps(context.get('current_test_point', {}), ensure_ascii=False),
        ui_specs_text=""
    )
    context['graph_prompt'] = graph_prompt
```

**修复状态：** ⚪ 待修复  
**修复人：** 后端  
**预计耗时：** 1 小时  
**依赖：** ISSUE-001

---

### ISSUE-003: 前端 edge.source/target 容错不足

**严重级别：** 🔴 阻塞  
**发现时间：** 2026-04-21  
**涉及文件：** `src/components/case/FlowSortEditor.vue`  
**问题描述：**  
`getFlowSortSubmitData` 方法中，当 `vueFlowNodes.value.find()` 找不到节点时，会 fallback 到 `edge.source`（即 `node_xxx` 格式），导致后端收到无效的 `screen_id`，`int()` 转换失败。

**影响范围：**  
- 前端节点数据异常时，后端会收到 `node_123` 这样的字符串
- 后端 `_safe_int()` 转换失败，返回 None
- Prompt 构建时跳过该连线，导致流程结构不完整

**修复方案：**  
```typescript
edges: vueFlowEdges.value.map(edge => {
  const sourceScreenId = vueFlowNodes.value.find(n => n.id === edge.source)?.data.screen_id
  const targetScreenId = vueFlowNodes.value.find(n => n.id === edge.target)?.data.screen_id
  
  if (!sourceScreenId || !targetScreenId) {
    console.warn(`连线 ${edge.id} 的 source/target 节点不存在，跳过`)
    return null
  }
  
  return {
    source: String(sourceScreenId),
    target: String(targetScreenId),
    edge_type: edge.data?.edge_type || 'normal',
    condition: edge.data?.condition || '',
    label: edge.label || ''
  }
}).filter(Boolean)  // 过滤掉 null 值
```

**修复状态：** ⚪ 待修复  
**修复人：** 前端  
**预计耗时：** 30 分钟

---

## P1 级别问题（影响质量，建议修复）

### ISSUE-004: PromptBuilder 缺少多模态图片数据支持

**严重级别：** 🟡 警告  
**发现时间：** 2026-04-21  
**涉及文件：** `app/services/case_generation_prompt_builder.py`  
**问题描述：**  
`build_graph_prompt` 只传递了 `ocr_text` 和 `screen_name`，没有传递图片 Base64 数据。如果 AI 模型是多模态模型（如 GPT-4V、Claude Vision），需要图片数据才能理解 UI 截图。

**影响范围：**  
- 多模态模型无法看到 UI 截图
- 仅依赖 OCR 文本，可能丢失布局、颜色、图标等视觉信息
- 测试用例质量下降

**修复方案：**  
待确认 AI 模型类型后决定：
- 如果是多模态模型：在 Prompt 中增加图片 Base64 数据
- 如果是纯文本模型：无需修改，当前实现已足够

**修复状态：** ⚪ 待审查  
**修复人：** 后端 + AI 架构  
**预计耗时：** 2 小时（需确认模型类型）  
**依赖：** 需确认项目使用的 AI 模型类型

---

### ISSUE-005: 新旧 Prompt 模板冲突

**严重级别：** 🟡 警告  
**发现时间：** 2026-04-21  
**涉及文件：** `app/utils/ai_client_enhanced.py`  
**问题描述：**  
`ai_client_enhanced.py` 中的 `generate_test_case_enhanced` 函数包含旧版 Prompt 模板（约 100 行），与 `PromptBuilder.build_graph_prompt` 的模板完全不同。如果 `graph_prompt` 未传入，会 fallback 到旧版模板，导致输出格式不一致。

**影响范围：**  
- 输出格式不统一，AI 可能返回不同结构的 JSON
- 前端解析可能失败
- 测试用例质量不稳定

**修复方案：**  
方案 A（推荐）：在 `generate_test_case_enhanced` 中增加校验，确保必须传入 `graph_prompt`
```python
def generate_test_case_enhanced(context: Dict[str, Any]) -> Dict[str, Any]:
    graph_prompt = context.get('graph_prompt')
    if not graph_prompt:
        raise ValueError("graph_prompt 必须传入，请使用 PromptBuilder.build_graph_prompt 生成")
    prompt = graph_prompt
    # ... 后续逻辑 ...
```

方案 B：删除旧版 Prompt 模板，统一使用 `PromptBuilder`

**修复状态：** ⚪ 待审查  
**修复人：** 后端  
**预计耗时：** 1 小时  
**依赖：** ISSUE-002

---

## P2 级别问题（可选优化）

### ISSUE-006: 前端 OCR 文本获取逻辑需验证

**严重级别：** 🟢 低风险  
**发现时间：** 2026-04-21  
**涉及文件：** `src/views/case/ai-generate.vue`, `src/components/case/FlowSortEditor.vue`  
**问题描述：**  
文档要求前端传递 `ocr_text` 和 `summary`，但需验证 `uiScreens` 数组中是否确实包含这些字段。

**影响范围：**  
- 如果 `uiScreens` 中不包含 `ocr_text`，前端会传递空字符串
- AI 无法获取页面元素信息

**修复方案：**  
在 `ai-generate.vue` 中增加日志，验证 `uiScreens` 数据结构：
```typescript
console.log('[UI Screens] 第一条数据:', uiScreens.value[0])
console.log('[UI Screens] 是否包含 ocr_text:', 'ocr_text' in (uiScreens.value[0] || {}))
console.log('[UI Screens] 是否包含 summary:', 'summary' in (uiScreens.value[0] || {}))
```

**修复状态：** ⚪ 待验证  
**修复人：** 前端  
**预计耗时：** 30 分钟

---

### ISSUE-007: 后端 flow_sort_data 解析逻辑需补充

**严重级别：** 🟢 低风险  
**发现时间：** 2026-04-21  
**涉及文件：** `app/api/v1/endpoints/test_case_ai.py`  
**问题描述：**  
需验证后端接收到 `flow_sort_data` 后，是否正确解析并传递给 `PromptBuilder`。

**影响范围：**  
- 如果解析逻辑有误，可能导致数据丢失
- AI 接收到不完整的流程结构

**修复方案：**  
在 API 端点中增加日志：
```python
logger.info(f"接收到 flow_sort_data: nodes={len(request_data.flow_sort_data.nodes)}, edges={len(request_data.flow_sort_data.edges)}")
```

**修复状态：** ⚪ 待验证  
**修复人：** 后端  
**预计耗时：** 30 分钟  
**依赖：** ISSUE-001, ISSUE-002

---

## 修复过程中新发现的问题

> 此区域用于记录在修复上述问题时发现的新问题

### ISSUE-NEW-001: 数据模型中不存在 ocr_text 字段

**严重级别：** 🔴 阻塞  
**发现时间：** 2026-04-21  
**发现阶段：** 审查 ISSUE-006 时  
**涉及文件：** 
- `app/schemas/ui_prototype.py` (UIScreenResponse)
- `src/api/uiPrototype.ts` (UIScreen interface)
- `app/models/ui_prototype.py` (UIPrototypeScreen model)
- `app/schemas/test_case.py` (FlowNodeSchema)
- `app/services/case_generation_prompt_builder.py` (build_graph_prompt)

**问题描述：**  
文档和代码中多处使用 `ocr_text` 字段，但实际数据模型中并不存在该字段：
1. 后端 `UIScreenResponse` 只有 `summary` 字段，没有 `ocr_text`
2. 前端 `UIScreen` 接口只有 `summary` 字段，没有 `ocr_text`
3. 数据库模型 `UIPrototypeScreen` 只有 `ui_spec` (JSON) 和 `summary` 字段
4. 但 `FlowNodeSchema` 和 `PromptBuilder.build_graph_prompt` 都使用了 `ocr_text` 字段

**影响范围：**  
- 前端传递的 `ocr_text` 始终为空字符串
- AI 无法获取页面元素的具体文本信息
- 测试用例生成质量下降

**根因分析：**  
经过深入排查 `ui_spec_parser` 代码，确认 `ui_spec` JSON 结构如下：
```json
{
  "screen_name": "页面名称",
  "purpose": "页面功能描述",
  "elements": [
    {
      "type": "button|input|text|link|...",
      "label": "可见的标签文字",
      "semantic": "语义化描述",
      "position": "top|center|bottom",
      "interactive": true/false
    }
  ],
  "navigation": { ... },
  "flows": { ... },
  "warnings": [ ... ]
}
```

`ocr_text` 是解析过程中的中间数据（OCR 提取的原始文本），**没有被保存到 `ui_spec` 中**。

**修复方案（推荐方案 B）：**  
方案 A：从 `ui_spec.elements` 中重建 OCR 文本（不推荐，信息不完整）
```python
# 在后端 API 端点中
ui_spec = screen.ui_spec or {}
elements = ui_spec.get('elements', [])
ocr_text = ' '.join([e.get('label', '') for e in elements if e.get('label')])
```

方案 B：在 `FlowNodeSchema` 中删除 `ocr_text` 字段，改用 `ui_spec_elements`（推荐）
```python
# 修改 FlowNodeSchema
class FlowNodeSchema(BaseModel):
    screen_id: int
    screen_order: int
    flow_type: str
    screen_name: str
    summary: Optional[str] = Field(None, max_length=5000, description="AI解析摘要")
    ui_spec_elements: Optional[List[Dict[str, Any]]] = Field(None, description="UI元素列表（从ui_spec提取）")
```

```python
# 修改 PromptBuilder.build_graph_prompt
for i, node in enumerate(main_nodes, 1):
    elements = node.get('ui_spec_elements', [])
    element_desc = ', '.join([f"{e.get('type')}:{e.get('label', '')}" for e in elements if e.get('label')])
    parts.append(f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}] 元素: {element_desc}")
```

方案 C：在数据库模型中增加 `ocr_text` 字段（需要数据库迁移，成本高）

**修复状态：** ✅ 已修复  
**修复人：** 后端 + 前端  
**预计耗时：** 2 小时  
**依赖：** 无

**修复内容：**
1. ✅ 修改 `FlowNodeSchema` - 将 `ocr_text` 替换为 `ui_spec_elements`
2. ✅ 修改前端 `FlowSortEditor.vue` - 从 `ui_spec.elements` 提取元素列表
3. ✅ 修改前端 `flowSort.ts` - 更新 `FlowNodeData` 接口类型
4. ✅ 修改 `PromptBuilder.build_graph_prompt` - 使用 `ui_spec_elements` 生成元素描述

---

### ISSUE-NEW-002: PromptBuilder 中节点匹配使用 screen_id 但前端传递的是字符串

**严重级别：** 🟡 警告  
**发现时间：** 2026-04-21  
**发现阶段：** 代码审查时  
**涉及文件：** `app/services/case_generation_prompt_builder.py`

**问题描述：**  
`build_graph_prompt` 中使用 `_safe_int(edge.get('target'))` 转换 edge 的 source/target，但前端传递的已经是字符串形式的 `screen_id`。虽然 `_safe_int` 可以处理字符串，但需要确保类型一致性。

**影响范围：**  
- 如果前端传递的 `screen_id` 不是纯数字字符串，转换会失败
- 节点匹配会跳过该连线

**修复方案：**  
无需修改，`_safe_int` 已处理字符串转换。但需在前端增加校验，确保 `screen_id` 是有效数字。

**修复状态：** 🟢 无需修复  
**修复人：** -  
**预计耗时：** -

---

## 修复进度

| 日期 | 操作 | 问题编号 | 状态 |
|------|------|----------|------|
| 2026-04-21 | 创建问题跟踪清单 | 全部 | 📝 初始化 |
| | | | |

---

## 备注

1. P0 问题必须在 24 小时内修复
2. P1 问题必须在 48 小时内修复
3. P2 问题可在后续迭代中处理
4. 每次修复后需更新对应问题的"修复状态"字段
5. 发现新问题需立即添加到本清单
