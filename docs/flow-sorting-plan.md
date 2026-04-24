# 截图流程图排序优化方案

> 版本：v1.0 | 日期：2026-04-21 | 状态：待评审

---

## 一、背景与问题

### 1.1 现状

当前 AI 生成测试用例页面（`src/views/case/ai-generate.vue`）支持用户上传 UI 原型截图后，通过 HTML5 原生拖拽进行线性排序（1~N 顺序编号），排序结果连同 OCR 文本一起送入 AI 模型生成测试用例。

**系统采用多源数据融合策略：**
- **需求文档**：提供业务规则、功能描述、验收标准
- **UI 原型图解析数据**：提供页面结构、元素信息、交互关系
- **系统自动生成的测试点**：提供测试维度、优先级、覆盖范围

三者交叉验证与互补，有效提升测试用例的完整性和质量。**系统的生成质量与用户提供信息的完整性呈正相关**：用户提供的需求文档越详尽、UI 原型图越完整、补充说明越具体，系统生成的测试用例质量越高，场景覆盖越全面。

### 1.2 核心问题

| 问题 | 现状 | 影响 |
|------|------|------|
| 编号体系 | 仅支持 1~N 纯顺序编号 | 无法表达分支/异常/旁路流程 |
| 交互方式 | 原生 HTML5 拖拽，无连线能力 | 用户无法表达流程跳转关系 |
| AI 上下文 | 线性序号 + OCR 文本 | AI 无法区分主干/分支/异常，导致步骤错乱、分支遗漏 |
| 数据传递断层 | 前端排序数据未完整传递到后端 | AI 拿到的只是"一堆页面"而非"有顺序有关系的流程" |
| 可用率 | 约 70% | 30% 用例需手动修正分支缺失、逻辑颠倒问题 |

### 1.3 优化目标

| 指标 | 当前值 | 目标值 | 提升幅度 |
|------|--------|--------|----------|
| AI 用例一次性可用率 | 70% | 90% | +20% |
| 分支/异常场景覆盖率 | ~60% | ≥90% | +30% |
| 测试人员手动修改频次 | 基准 | 降低 60% | -60% |
| 测试人员满意度 | - | ≥8 分（10 分制） | 新增指标 |

---

## 二、技术方案

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端（Vue 3）                         │
│  ┌──────────────────┐    ┌──────────────────────────────┐   │
│  │  模式切换开关     │    │  流程图编辑器 (@vue-flow)     │   │
│  │  线性 / 流程图    │───▶│  - 节点：截图卡片             │   │
│  └──────────────────┘    │  - 连线：箭头 + 条件标注      │   │
│                          │  - 标签：主干/分支/异常/旁路  │   │
│                          └──────────────┬───────────────┘   │
│                                         │                   │
│                          ┌──────────────▼───────────────┐   │
│                          │  输出 JSON 数据结构           │   │
│                          │  { nodes, edges, module_info }│   │
│                          └──────────────┬───────────────┘   │
└─────────────────────────────────────────┼───────────────────┘
                                          │ POST /api/v1/case/ai-generate-enhanced
                                          ▼
┌─────────────────────────────────────────────────────────────┐
│                        后端（FastAPI）                       │
│  ┌──────────────────┐    ┌──────────────────────────────┐   │
│  │  模式识别         │    │  Prompt 构建引擎             │   │
│  │  linear / graph   │───▶│  - 主干流程（按序）          │   │
│  └──────────────────┘    │  - 分支流程（条件触发）       │   │
│                          │  - 异常流程（异常场景）       │   │
│                          │  - 旁路流程（出现时机）       │   │
│                          └──────────────┬───────────────┘   │
│                                         │                   │
│                          ┌──────────────▼───────────────┐   │
│                          │  AI 模型（DeepSeek）          │   │
│                          │  输入：结构化 Prompt          │   │
│                          │  输出：JSON 测试用例          │   │
│                          └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 前端技术选型

| 技术项 | 选型 | 理由 |
|--------|------|------|
| 流程图库 | `@vue-flow/core@1.x` | Vue 3 原生支持，拖拽/连线/节点定制开箱即用 |
| 拖拽插件 | `@vue-flow/additional-components` | 提供 Background、Controls、MiniMap 等组件 |
| UI 框架 | Element Plus（现有） | 保持项目统一，不引入新 UI 库 |
| 状态管理 | Pinia（现有） | 项目已有，用于存储流程图数据 |

**安装命令：**
```bash
npm install @vue-flow/core@1 @vue-flow/additional-components@1
```

### 2.3 数据结构设计

#### 2.3.1 前端输出 JSON

```json
{
  "mode": "graph",
  "nodes": [
    {
      "id": "node_1",
      "screen_id": 101,
      "image_url": "/api/v1/file/preview-screen/101",
      "ocr_text": "登录页面，包含用户名、密码输入框和登录按钮",
      "screen_name": "登录页",
      "flow_type": "main",
      "position": { "x": 0, "y": 0 }
    },
    {
      "id": "node_2",
      "screen_id": 102,
      "image_url": "/api/v1/file/preview-screen/102",
      "ocr_text": "功能页面，包含筛选条件输入框和查询按钮",
      "screen_name": "查询页",
      "flow_type": "main",
      "position": { "x": 300, "y": 0 }
    },
    {
      "id": "node_3",
      "screen_id": 103,
      "image_url": "/api/v1/file/preview-screen/103",
      "ocr_text": "高级筛选弹窗，包含更多筛选条件",
      "screen_name": "高级筛选",
      "flow_type": "branch",
      "position": { "x": 300, "y": 250 }
    },
    {
      "id": "node_4",
      "screen_id": 104,
      "image_url": "/api/v1/file/preview-screen/104",
      "ocr_text": "错误提示：请输入有效字符",
      "screen_name": "错误提示",
      "flow_type": "exception",
      "position": { "x": 600, "y": 250 }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "node_1",
      "target": "node_2",
      "edge_type": "normal",
      "condition": null,
      "label": "正常流转"
    },
    {
      "id": "edge_2",
      "source": "node_2",
      "target": "node_3",
      "edge_type": "branch",
      "condition": "用户点击高级筛选按钮",
      "label": "条件分支"
    },
    {
      "id": "edge_3",
      "source": "node_2",
      "target": "node_4",
      "edge_type": "exception",
      "condition": "输入非法字符或超长文本",
      "label": "异常跳转"
    }
  ],
  "module_info": {
    "name": "后台管理系统-查询功能",
    "description": "测试查询功能的主干、分支、异常流程"
  }
}
```

#### 2.3.2 字段说明

**节点（nodes）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 节点唯一标识，格式 `node_{序号}` |
| screen_id | number | 是 | 关联的 UI 屏幕 ID |
| image_url | string | 是 | 图片预览 URL |
| ocr_text | string | 是 | OCR 识别文本 |
| screen_name | string | 是 | 屏幕名称 |
| flow_type | string | 是 | 流程类型：`main`/`branch`/`exception`/`bypass` |
| position | object | 是 | 节点在画布中的坐标 `{x, y}` |

**连线（edges）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 连线唯一标识，格式 `edge_{序号}` |
| source | string | 是 | 起始节点 ID |
| target | string | 是 | 目标节点 ID |
| edge_type | string | 是 | 连线类型：`normal`/`branch`/`exception`/`bypass` |
| condition | string | 否 | 触发条件描述 |
| label | string | 是 | 连线标签文本 |

**流程类型枚举：**

| 值 | 中文 | 颜色 | 说明 |
|----|------|------|------|
| main | 主干流程 | 蓝色 `#409eff` | 主路径，按顺序执行 |
| branch | 分支流程 | 绿色 `#67c23a` | 满足条件时执行的分支路径 |
| exception | 异常流程 | 红色 `#f56c6c` | 异常场景下触发的路径 |
| bypass | 旁路流程 | 橙色 `#e6a23c` | 旁路步骤（如弹窗），不影响主流程 |

### 2.4 后端 Prompt 模板

#### 2.4.1 流程图模式 Prompt

```text
你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下多源信息生成详细的、可执行的测试用例。

## 测试点信息
{test_point_json}

## 需求文档内容
{requirement_content}

## 模块信息
{module_name}
{module_description}

## UI 原型图流程结构

### 主干流程（按顺序执行，必须完整覆盖）
步骤 1: [截图1 - {screen_name}] {ocr_text}
步骤 2: [截图2 - {screen_name}] {ocr_text}
步骤 3: [截图3 - {screen_name}] {ocr_text}

### 分支流程（满足条件时执行，每个分支作为独立测试场景）
分支 A: 从步骤 2 分支，触发条件「{condition}」
  → [截图4 - {screen_name}] {ocr_text}

### 异常流程（异常场景下触发，需标注异常场景和预期错误提示）
异常 A: 从步骤 2 异常跳转，异常场景「{condition}」
  → [截图5 - {screen_name}] {ocr_text}

### 旁路流程（出现时机和关闭方式，不影响主流程）
旁路 A: 进入步骤 1 时自动弹出，关闭后继续主流程
  → [截图6 - {screen_name}] {ocr_text}

## 生成要求
1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏
2. 每个分支流程需标注触发条件，作为独立测试场景生成用例
3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例
4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理
5. 若提供了需求文档，结合业务规则验证每个步骤的验收标准；若未提供，仅根据 UI 原型图推断业务逻辑
6. 若提供了测试点，优先覆盖测试点中的测试维度；若未提供，根据 UI 元素自动生成测试点
7. 输出格式：JSON，包含 title/module/precondition/steps/expected_result/case_type/priority/case_category

## 输出 JSON 格式：
{
  "title": "用例标题",
  "module": "模块名称",
  "precondition": "前置条件",
  "test_data": {"normal": {}, "boundary": {}, "abnormal": {}},
  "steps": [
    {"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}
  ],
  "expected_result": "总体预期结果",
  "case_type": "ui_automation",
  "case_category": "ui_automation",
  "priority": 2
}

请根据以上流程结构生成测试用例。
```

#### 2.4.2 线性模式 Prompt（兼容旧版）

保持现有 `_build_generation_prompt` 方法不变，作为兜底选项。

### 2.6 数据传递链路修复（关键）

#### 2.6.1 现状问题分析

**当前系统存在严重的数据传递断层**：前端拖拽排序后的数据未完整传递到后端，AI 拿到的只是"一堆页面"而非"有顺序有关系的流程"。

**数据传递链路现状：**

```
前端拖拽排序（有顺序、有流程关系）
    ↓
传递 ui_screen_ids = [101, 102, 103]  ← 仅传递 ID 列表，丢失排序顺序
    ↓
后端根据 ID 从数据库重新查询
    ↓
按数据库 screen_order 排序（非前端排序顺序）  ← 排序被覆盖
    ↓
AI 拿到：页面列表（无顺序、无流程关系、无 OCR 原始文本）  ← 信息严重缺失
```

**数据项对比表：**

| 数据项 | 前端有 | 传给后端 | 后端使用 | AI 拿到 |
|--------|--------|----------|----------|---------|
| 截图 ID 列表 | ✅ | ✅ | ✅ | ✅ |
| 截图排序顺序 | ✅ | ❌ | ❌ | ❌ |
| OCR 原始文本 | ✅ | ❌ | ❌ | ❌ |
| AI 解析摘要（summary） | ❌ | - | ✅ | ✅ |
| UI 规格（页面结构） | ❌ | - | ✅ | ✅ |
| 流程类型（主干/分支） | ❌ | ❌ | ❌ | ❌ |
| 连线关系 + 触发条件 | ❌ | ❌ | ❌ | ❌ |

**根因定位：**

查看 `app/services/case_generation_core.py` 的 `get_context_for_generation` 方法：

```python
# 后端根据 ui_screen_ids 从数据库重新查询
if ui_screen_ids:
    for screen_id in ui_screen_ids:
        screen = db.query(UIPrototypeScreen).filter(...).first()
        if screen:
            context["ui_descriptions"].append({
                "screen_id": screen.id,
                "screen_name": screen.screen_name,
                "summary": screen.summary,        # 只有 AI 解析后的摘要
                "element_count": screen.element_count,
                # ❌ 没有 screen_order 排序信息
                # ❌ 没有 OCR 原始文本
                # ❌ 没有流程类型
            })
```

#### 2.6.2 修复方案

**修复目标：** 前端排序后的完整数据（顺序、流程关系、OCR 文本）必须传递到后端，并注入 AI Prompt。

**与多源数据融合策略的关系：**

本次优化不改变现有的多源数据融合架构，而是在 **UI 原型图解析数据** 这一数据源中，新增"流程结构"维度，使 AI 能够理解页面之间的先后顺序和跳转关系。

**优化前数据融合：**
```
需求文档（业务规则） + UI 原型图（页面结构） + 测试点（测试维度）
    ↓
AI 生成用例（知道有哪些页面，但不知道页面顺序和流程关系）
```

**优化后数据融合：**
```
需求文档（业务规则） + UI 原型图（页面结构 + 流程关系） + 测试点（测试维度）
    ↓
AI 生成用例（知道页面顺序、主干/分支/异常流程、触发条件）
```

**修复后数据流：**

```
前端流程图排序（有顺序、有流程关系、有 OCR）
    ↓
传递完整 flow_sort_data JSON
    ├── mode: "graph"
    ├── nodes: [{screen_id, screen_order, flow_type, ocr_text, ...}]
    ├── edges: [{source, target, edge_type, condition, ...}]
    └── module_info: {name, description}
    ↓
后端接收并解析 flow_sort_data
    ├── 按前端 screen_order 排序（不覆盖）
    ├── 构建流程树（主干/分支/异常/旁路）
    └── 注入 context["flow_structure"]
    ↓
PromptBuilder 构建结构化 Prompt
    ├── 主干流程（按序）
    ├── 分支流程（条件触发）
    ├── 异常流程（异常场景）
    └── 旁路流程（出现时机）
    ↓
AI 拿到：完整流程结构（有顺序、有关系、有 OCR）  ← 信息完整
```

#### 2.6.3 前端新增传递字段

```typescript
// ai-generate.vue 中提交给后端的数据
const submitData = {
  project_id: formData.project_id,
  test_point_ids: formData.test_point_ids,
  requirement_file_ids: formData.requirement_file_ids,
  ui_screen_ids: formData.ui_screen_ids,
  
  // === 新增字段 ===
  mode: sortMode.value,                    // 排序模式：linear | graph
  flow_sort_data: {                        // 流程图排序完整数据
    nodes: flowSortNodes.value.map((node, index) => ({
      screen_id: node.screen_id,
      screen_order: index + 1,             // 前端排序序号（从 1 开始）
      flow_type: node.flow_type,           // main | branch | exception | bypass
      screen_name: node.screen_name,
      ocr_text: node.ocr_text,             // OCR 原始文本
      summary: node.summary                // AI 解析摘要（可选）
    })),
    edges: flowSortEdges.value.map(edge => ({
      source: edge.source,
      target: edge.target,
      edge_type: edge.edge_type,           // normal | branch | exception | bypass
      condition: edge.condition,           // 触发条件
      label: edge.label                    // 连线标签
    })),
    module_info: {
      name: selectedUiPrototypeProject.value?.name || '',
      description: selectedUiPrototypeProject.value?.description || ''
    }
  }
}
```

#### 2.6.4 后端新增处理逻辑

**1. Schema 定义（`app/schemas/test_case.py`）：**

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class FlowNodeSchema(BaseModel):
    screen_id: int
    screen_order: int                              # 前端排序序号
    flow_type: Literal['main', 'branch', 'exception', 'bypass']
    screen_name: str
    ocr_text: Optional[str]                        # OCR 原始文本
    summary: Optional[str]                         # AI 解析摘要

class FlowEdgeSchema(BaseModel):
    source: str
    target: str
    edge_type: Literal['normal', 'branch', 'exception', 'bypass']
    condition: Optional[str]
    label: str

class FlowSortDataSchema(BaseModel):
    nodes: List[FlowNodeSchema]
    edges: List[FlowEdgeSchema]
    module_info: Optional[dict]

class AIGenerateEnhancedRequest(BaseModel):
    # ... 现有字段 ...
    mode: Literal['linear', 'graph'] = Field(default='linear', description="排序模式")
    flow_sort_data: Optional[FlowSortDataSchema] = Field(None, description="流程图排序数据")
```

**2. 上下文构建修改（`app/services/case_generation_core.py`）：**

```python
async def get_context_for_generation(
    self,
    project_id: int,
    user_id: int,
    flow_sort_data: Optional[FlowSortDataSchema] = None,  # 新增参数
    # ... 其他参数保持不变 ...
) -> Dict[str, Any]:
    context = {
        "requirement_content": "",
        "ui_descriptions": [],
        "ui_specs": [],
        "test_points": [],
        "flow_structure": None,  # 新增：流程结构
        "ocr_texts": {},         # 新增：OCR 文本映射
        # ... 其他字段 ...
    }

    # === 新增：处理流程图排序数据 ===
    if flow_sort_data and flow_sort_data.mode == 'graph':
        # 1. 按前端 screen_order 排序（不覆盖）
        sorted_nodes = sorted(flow_sort_data.nodes, key=lambda n: n.screen_order)
        
        # 2. 构建流程结构
        context["flow_structure"] = {
            "main_flow": [n for n in sorted_nodes if n.flow_type == 'main'],
            "branch_flows": self._build_branch_tree(flow_sort_data.edges, sorted_nodes),
            "exception_flows": self._build_exception_tree(flow_sort_data.edges, sorted_nodes),
            "bypass_flows": self._build_bypass_tree(flow_sort_data.edges, sorted_nodes)
        }
        
        # 3. 注入 OCR 文本映射
        context["ocr_texts"] = {n.screen_id: n.ocr_text for n in sorted_nodes if n.ocr_text}
        
        # 4. 构建 UI 描述（使用前端排序顺序）
        for node in sorted_nodes:
            context["ui_descriptions"].append({
                "screen_id": node.screen_id,
                "screen_name": node.screen_name,
                "screen_order": node.screen_order,      # 新增：前端排序序号
                "flow_type": node.flow_type,            # 新增：流程类型
                "summary": node.summary or "",
                "ocr_text": node.ocr_text or ""         # 新增：OCR 原始文本
            })
    
    # ... 其余逻辑保持不变 ...
```

**3. Prompt 构建修改（`app/services/case_generation_prompt_builder.py`）：**

```python
class PromptBuilder:
    @staticmethod
    def build_graph_prompt(
        flow_structure: Dict[str, Any],
        ocr_texts: Dict[int, str],
        ui_specs: List[Dict[str, Any]],
        module_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建流程图模式的 Prompt"""
        
        parts = []
        parts.append("你是一名资深测试工程师，拥有10年以上的测试经验。")
        parts.append("请根据以下流程结构生成详细的、可执行的测试用例。\n")
        
        # 模块信息
        if module_info:
            parts.append(f"## 模块信息")
            parts.append(module_info.get('name', ''))
            parts.append(module_info.get('description', ''))
            parts.append("")
        
        # 主干流程（按 screen_order 排序）
        main_flow = flow_structure.get('main_flow', [])
        parts.append("### 主干流程（按顺序执行，必须完整覆盖）")
        for i, node in enumerate(main_flow, 1):
            ocr = ocr_texts.get(node.screen_id, node.get('ocr_text', ''))
            parts.append(
                f"步骤 {i}: [截图{i} - {node.screen_name}] {ocr}"
            )
        parts.append("")
        
        # 分支流程
        branch_flows = flow_structure.get('branch_flows', [])
        if branch_flows:
            parts.append("### 分支流程（满足条件时执行，每个分支作为独立测试场景）")
            for idx, branch in enumerate(branch_flows, ord('A')):
                parts.append(
                    f"分支 {chr(idx)}: 从步骤 {branch['source_step']} 分支，"
                    f"触发条件「{branch['condition']}」"
                )
                ocr = ocr_texts.get(branch['target_screen_id'], '')
                parts.append(f"  → [截图 - {branch['target_name']}] {ocr}")
            parts.append("")
        
        # 异常流程
        exception_flows = flow_structure.get('exception_flows', [])
        if exception_flows:
            parts.append("### 异常流程（异常场景下触发，需标注异常场景和预期错误提示）")
            for idx, exc in enumerate(exception_flows, ord('A')):
                parts.append(
                    f"异常 {chr(idx)}: 从步骤 {exc['source_step']} 异常跳转，"
                    f"异常场景「{exc['condition']}」"
                )
                ocr = ocr_texts.get(exc['target_screen_id'], '')
                parts.append(f"  → [截图 - {exc['target_name']}] {ocr}")
            parts.append("")
        
        # 旁路流程
        bypass_flows = flow_structure.get('bypass_flows', [])
        if bypass_flows:
            parts.append("### 旁路流程（出现时机和关闭方式，不影响主流程）")
            for idx, bypass in enumerate(bypass_flows, ord('A')):
                parts.append(
                    f"旁路 {chr(idx)}: 进入步骤 {bypass['source_step']} 时"
                    f"{bypass.get('condition', '自动弹出')}，关闭后继续主流程"
                )
                ocr = ocr_texts.get(bypass['target_screen_id'], '')
                parts.append(f"  → [截图 - {bypass['target_name']}] {ocr}")
            parts.append("")
        
        # 生成要求
        parts.append("## 生成要求")
        parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
        parts.append("2. 每个分支流程需标注触发条件，作为独立测试场景生成用例")
        parts.append("3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例")
        parts.append("4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理")
        parts.append("5. 输出格式：JSON，包含 title/module/precondition/steps/expected_result/case_type/priority/case_category")
        
        return "\n".join(parts)
    
    @staticmethod
    def _build_branch_tree(edges: List[Dict], nodes: List[Dict]) -> List[Dict]:
        """构建分支流程树"""
        branch_edges = [e for e in edges if e.edge_type == 'branch']
        result = []
        
        for edge in branch_edges:
            source_node = next((n for n in nodes if n.id == edge.source), None)
            target_node = next((n for n in nodes if n.id == edge.target), None)
            
            if source_node and target_node:
                result.append({
                    'source_step': source_node.screen_order,
                    'target_screen_id': target_node.screen_id,
                    'target_name': target_node.screen_name,
                    'condition': edge.condition or '未指定'
                })
        
        return result
    
    # _build_exception_tree 和 _build_bypass_tree 逻辑类似
```

#### 2.6.5 修复验收标准

| 检查项 | 通过标准 | 验证方式 |
|--------|----------|----------|
| 前端排序顺序传递 | 前端拖拽后，后端接收的 screen_order 与前端一致 | 日志验证 |
| OCR 文本传递 | 每个节点的 ocr_text 完整传递到后端 | 日志验证 |
| 流程关系传递 | edges 数据完整传递，后端正确解析 | 单元测试 |
| Prompt 包含流程结构 | graph 模式 Prompt 包含主干/分支/异常/旁路 | 单元测试 |
| 线性模式兼容 | linear 模式下行为与优化前完全一致 | 回归测试 |

---

### 2.7 回滚机制

#### 2.7.1 前端开关

```vue
<el-radio-group v-model="sortMode" size="small">
  <el-radio-button value="linear">线性排序（旧版）</el-radio-button>
  <el-radio-button value="graph">流程图排序（新版）</el-radio-button>
</el-radio-group>
```

#### 2.7.2 后端兼容

```python
def build_prompt(screenshot_data: dict, mode: str) -> str:
    if mode == "linear":
        return build_linear_prompt(screenshot_data)  # 原有逻辑
    elif mode == "graph":
        return build_graph_prompt(screenshot_data)   # 新逻辑
    else:
        raise ValueError(f"Unknown mode: {mode}")
```

---

## 三、界面原型

### 3.1 流程图模式界面

```
┌─────────────────────────────────────────────────────────────────────┐
│  [● 线性排序] [○ 流程图排序]                    [生成用例] [清空]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  画布区域（可缩放、可拖拽平移）                                      │
│                                                                     │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐                 │
│  │ 截图 1   │─────▶│ 截图 2   │─────▶│ 截图 3   │                 │
│  │ [主干]   │      │ [主干]   │      │ [主干]   │                 │
│  │ 登录页   │      │ 查询页   │      │ 列表页   │                 │
│  └──────────┘      └────┬─────┘      └──────────┘                 │
│                          │                                        │
│                   ┌──────┴──────┐                                  │
│                   ▼             ▼                                  │
│            ┌──────────┐  ┌──────────┐                             │
│            │ 截图 4   │  │ 截图 5   │                             │
│            │ [分支]   │  │ [异常]   │                             │
│            │ 高级筛选 │  │ 错误提示 │                             │
│            └──────────┘  └──────────┘                             │
│                                                                     │
│  [+ 添加截图]  [自动布局]  [预览 Prompt]                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 节点卡片设计

```
┌─────────────────────────────┐
│ ● [主干 ▼]                  │  ← 左上角：连接点 + 流程类型下拉
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │     [截图缩略图]         │ │  ← 中间：截图预览
│ │                         │ │
│ └─────────────────────────┘ │
│ 登录页                      │  ← 底部：屏幕名称 + OCR 摘要
│ 用户名、密码输入框...        │
└─────────────────────────────┘
```

### 3.3 连线交互

1. 鼠标悬停节点 → 右侧出现 `●` 连接点
2. 拖拽连接点到目标节点 → 自动绘制箭头
3. 连线完成 → 弹出浮层选择连线类型：
   - `正常流转`（默认，无需填写条件）
   - `条件分支`（需填写触发条件）
   - `异常跳转`（需填写异常场景）
   - `旁路步骤`（需填写出现时机）

---

## 四、文件变更清单

### 4.1 新增文件

| 文件路径 | 说明 |
|----------|------|
| `src/components/case/FlowSortEditor.vue` | 流程图排序编辑器组件 |
| `src/components/case/FlowNodeCard.vue` | 流程图节点卡片组件 |
| `src/components/case/EdgeConditionDialog.vue` | 连线条件填写弹窗 |
| `src/stores/flowSort.ts` | 流程图排序状态管理 |
| `app/services/case_generation_prompt_builder.py` | Prompt 构建服务（新增 graph 模式） |

### 4.2 修改文件

| 文件路径 | 修改内容 |
|----------|----------|
| `src/views/case/ai-generate.vue` | 替换原有拖拽排序区域，集成 FlowSortEditor |
| `app/services/case_generation_steps.py` | 增加 graph 模式上下文处理逻辑 |
| `app/api/v1/endpoints/test_case_ai_enhanced.py` | 增加 mode 参数接收与路由 |
| `app/schemas/test_case.py` | 增加 FlowSortData Schema |
| `package.json` | 新增 @vue-flow 依赖 |

---

## 五、验收标准

### 5.1 功能验收

| 检查项 | 通过标准 | 验证方式 |
|--------|----------|----------|
| 模式切换 | 线性/流程图模式切换流畅，数据不丢失 | 手动测试 |
| 节点操作 | 添加、删除、拖拽节点正常 | 手动测试 |
| 连线操作 | 创建、删除、修改连线正常 | 手动测试 |
| 条件填写 | 连线条件弹窗正常提交 | 手动测试 |
| JSON 输出 | 输出符合 2.3.1 定义的 JSON 结构 | 单元测试 |
| Prompt 生成 | graph 模式 Prompt 包含完整流程结构 | 单元测试 |
| 回滚机制 | 切换线性模式后功能与优化前一致 | 回归测试 |

### 5.2 质量验收

| 指标 | 目标值 | 验证方式 |
|------|--------|----------|
| AI 用例一次性可用率 | ≥90% | 10 个真实场景测试 |
| 分支/异常场景覆盖率 | ≥90% | 10 个真实场景测试 |
| 手动修改频次降低 | ≥60% | 对比优化前后修改量 |
| 测试人员满意度 | ≥8 分（10 分制） | 问卷调查 |
| 节点加载性能 | ≤1 秒（20 个节点内） | 性能测试 |
| 画布渲染性能 | 60fps（50 个节点内） | 性能测试 |

---

## 六、风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 前端交互复杂，用户学习成本高 | 排序数据质量下降 | 中 | M1 阶段做 5 分钟可用性测试，复杂则降级为下拉选择 |
| AI 对 graph Prompt 理解不佳 | 生成质量未提升 | 中 | 保留线性 Prompt 兜底，A/B 测试对比效果 |
| @vue-flow 与现有 Vue 3 版本冲突 | 无法集成 | 低 | 提前验证版本兼容性，备选方案：原生 SVG |
| 画布节点过多导致性能问题 | 页面卡顿 | 低 | 限制单次最多 50 个节点，超出提示分批 |

---

## 七、里程碑

| 里程碑 | 目标 | 预计耗时 | 产出物 | 负责人 |
|--------|------|----------|--------|--------|
| M1 | 前端交互设计 + 原型验证 | 0.5 天 | 原型图、交互文档 | 前端 |
| M2 | 前端功能开发 | 0.5 天 | FlowSortEditor 组件、JSON 输出 | 前端 |
| M3 | 后端 Prompt 构建逻辑 | 0.5 天 | PromptBuilder 服务、API 适配 | 后端 |
| M4 | AI Prompt 优化 + 回滚开关 | 0.25 天 | 新版 Prompt 模板、兼容开关 | 后端 |
| M5 | 10 个真实场景验证 | 0.25 天 | 测试报告、回滚决策 | 全员 |

---

## 八、附录

### 8.1 现有代码位置

| 功能 | 文件路径 |
|------|----------|
| AI 生成用例页面 | `src/views/case/ai-generate.vue` |
| 现有拖拽排序逻辑 | `ai-generate.vue` L179-L207, L2336-L2416 |
| AI 用例生成服务 | `app/services/case_generation_ai.py` |
| AI 用例生成步骤服务 | `app/services/case_generation_steps.py` |
| AI 生成 API 端点 | `app/api/v1/endpoints/test_case_ai_enhanced.py` |
| UI 屏幕 Schema | `app/schemas/ui_prototype.py` |

### 8.2 参考文档

- @vue-flow 官方文档：https://vueflow.dev/
- Element Plus 文档：https://element-plus.org/
