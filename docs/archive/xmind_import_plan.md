# XMind 测试点导入功能规划文档

## 1. 项目背景

### 1.1 现状分析

当前项目已具备完善的测试点管理体系，支持以下核心能力：

- **测试点模型**：采用 `module`（模块）→ `function`（功能）→ `point`（测试点）三级结构
- **数据存储**：通过 SQLAlchemy ORM 映射到 `test_points` 表，支持项目隔离
- **API 接口**：提供完整的 CRUD 端点，包括批量保存（`POST /testPoint/batch-save`）、列表查询、详情获取
- **文件解析**：已支持 `.txt`、`.md`、`.doc`、`.docx`、`.pdf` 等格式的文本提取
- **AI 提取**：支持从需求文档中通过 AI 自动提取测试点

**现有文件解析架构**：

```
app/services/file_parser.py          # 文件解析器工厂（工厂模式）
app/services/file_content_extractor.py # 文件内容提取服务
app/crud/test_point.py               # 测试点数据库操作
app/api/v1/endpoints/test_point_*.py # 测试点 API 端点
```

### 1.2 痛点与需求

测试团队在日常工作中大量使用 XMind 思维导图进行测试点梳理，但当前系统**不支持直接导入 `.xmind` 文件**，导致：

1. **手工录入成本高**：测试人员需将 XMind 中的测试点逐条手动录入系统，效率低下
2. **结构易失真**：人工转录过程中可能出现层级错位、字段遗漏
3. **版本不同步**：XMind 文件更新后，系统中的测试点无法自动同步

**样例文件分析**（`听写任务.xmind`，XMind R3.7.6 版本）：

- **文件格式**：标准 `.xmind`（ZIP 压缩包，内含 `content.xml`）
- **节点结构**：
  - 根主题：`听写任务`
  - 一级子主题（模块）：`字词听写`、`单词听写`、`句子听写`、`批改结果`、`生词本`
  - 二级子主题（功能）：`有教材内容`、`无教材内容`、`有内容`、`无内容`
  - 三级及以下（测试点）：具体交互步骤、界面规则、异常处理

### 1.3 目标价值

- **效率提升**：将 XMind 导入耗时从小时级降至秒级
- **结构保真**：自动映射 XMind 层级到测试点三级结构，减少人工干预
- **流程闭环**：测试点从 XMind 梳理 → 系统导入 → AI 生成用例，形成完整工作流

---

## 2. 项目目标

### 2.1 核心目标

实现 XMind 测试点文件的一键导入功能，将 `.xmind` 文件中的层级结构自动解析并映射为系统测试点数据。

### 2.2 量化指标

| 指标项 | 目标值 | 验证方式 |
|--------|--------|----------|
| 解析成功率 | ≥95% | 使用 10+ 个不同结构 XMind 文件测试，统计成功解析比例 |
| 导入耗时 | ≤3 秒（50-200 条测试点） | 使用 `time.perf_counter()` 测量端到端耗时 |
| 字段对齐率 | 100% | 导入后校验 `module`/`function`/`point`/`priority` 字段完整性 |
| 单元测试覆盖率 | ≥95% | 使用 `pytest-cov` 生成覆盖率报告 |
| 兼容性 | XMind R3.x 标准格式 | 支持 XMind 8 / XMind 2020 / XMind Zen 导出的 `.xmind` 文件 |

### 2.3 非功能性目标

- **零侵入**：不修改现有测试点模型、Schema、CRUD 逻辑
- **可扩展**：解析器设计遵循开闭原则，便于后续支持其他思维导图格式
- **可回滚**：导入失败时提供明确的错误信息，不残留脏数据

---

## 3. 项目范围

### 3.1 包含范围

1. **XMind 文件解析引擎**
   - 支持 `.xmind` 标准格式（ZIP + XML）
   - 提取主题层级结构（根主题 → 子主题 → 孙主题）
   - 识别节点文本、备注、优先级标记

2. **字段映射与转换**
   - 一级主题 → `module`（模块）
   - 二级主题 → `function`（功能）
   - 三级及以下主题 → `point`（测试点描述）
   - 优先级标记（如有）→ `priority`（1/2/3）

3. **导入 API 端点**
   - `POST /test-point/import-xmind`：上传 XMind 文件并导入
   - 支持预览模式（先解析展示，确认后再保存）
   - 返回导入结果统计（成功数/失败数/跳过的节点）

4. **前端导入页面**
   - XMind 文件上传组件（拖拽/选择）
   - 导入预览表格（展示解析后的测试点列表）
   - 导入结果反馈（成功/失败明细）

5. **单元测试**
   - 解析器核心逻辑测试
   - 字段映射规则测试
   - 边界场景测试（空文件、深层嵌套、特殊字符）

### 3.2 不包含范围

1. **非标准 XMind 格式**：如 `.xmind.zip`、`.xmind.tar` 等变体格式
2. **图片/附件解析**：XMind 节点中的图片、附件不提取
3. **双向同步**：仅支持导入，不支持将系统测试点导出为 XMind
4. **在线 XMind 服务**：不支持 XMind Cloud、XMind Workbook 等在线格式

### 3.3 影响范围

| 模块 | 影响类型 | 说明 |
|------|----------|------|
| `app/services/file_parser.py` | 扩展 | 新增 `XmindParser` 解析器，注册到 `FileParserFactory` |
| `app/services/file_content_extractor.py` | 扩展 | 新增 `.xmind` 文件类型分支 |
| `app/api/v1/endpoints/test_point_*.py` | 扩展 | 新增 `POST /test-point/import-xmind` 端点 |
| `app/schemas/test_point.py` | 扩展 | 新增 `TestPointXmindImportRequest` / `TestPointXmindImportResponse` Schema |
| `app/crud/test_point.py` | 无影响 | 复用现有 `batch_create_test_points` 函数 |
| `app/models/test_point.py` | 无影响 | 模型字段不变 |
| 前端页面 | 新增 | 新增 XMind 导入页面/组件 |

---

## 4. 核心功能模块

### 4.1 XMind 解析引擎（`app/services/xmind_parser.py`）

#### 4.1.1 技术选型

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 第三方库 `xmind` | 封装完善，API 简洁 | 停止维护，不支持新版 XMind | ❌ 不采用 |
| 第三方库 `xmind3-sdk` | 官方 SDK，兼容性好 | 依赖重，学习成本高 | ❌ 不采用 |
| **原生 `zipfile` + `xml.etree`** | 零依赖，轻量可控，符合项目规范 | 需自行处理 XML 结构 | ✅ **采用** |

**选型理由**：

1. **零依赖**：项目已有规则要求"第三方库标注安装命令"，减少依赖可降低维护成本
2. **轻量可控**：`.xmind` 本质为 ZIP 包，内部 `content.xml` 结构清晰，原生解析足够
3. **符合规范**：项目架构设计原则要求"最小改动、外科手术式修改"

#### 4.1.2 解析流程

```python
# 伪代码示意
import zipfile
import xml.etree.ElementTree as ET

class XmindParser:
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        # 1. 解压 .xmind 文件
        with zipfile.ZipFile(file_path, 'r') as zf:
            content_xml = zf.read('content.xml')
        
        # 2. 解析 XML
        root = ET.fromstring(content_xml)
        
        # 3. 提取主题层级
        sheet = root.find('.//sheet')
        root_topic = sheet.find('.//topic')
        
        # 4. 递归遍历子主题
        test_points = []
        for module_topic in root_topic.findall('.//children/topics/topic'):
            module_name = module_topic.find('title').text
            for func_topic in module_topic.findall('.//children/topics/topic'):
                function_name = func_topic.find('title').text
                for point_topic in func_topic.findall('.//children/topics/topic'):
                    point_desc = point_topic.find('title').text
                    test_points.append({
                        'module': module_name,
                        'function': function_name,
                        'point': point_desc,
                        'priority': 2  # 默认中优先级
                    })
        return test_points
```

#### 4.1.3 字段映射规则

| XMind 层级 | 系统字段 | 映射规则 | 默认值 |
|------------|----------|----------|--------|
| 根主题 | - | 忽略（通常为产品/项目名） | - |
| 一级子主题 | `module` | 直接映射为模块名称 | 必填 |
| 二级子主题 | `function` | 直接映射为功能名称 | 空字符串 |
| 三级及以下 | `point` | 拼接节点文本（含备注） | 必填 |
| 节点标记（优先级图标） | `priority` | 🔴→1（高）、🟡→2（中）、🟢→3（低） | 2 |
| 节点备注 | `point` | 追加到测试点描述后 | - |

#### 4.1.4 异常处理策略

| 异常场景 | 处理方式 | 日志级别 |
|----------|----------|----------|
| 文件非标准 ZIP 格式 | 抛出 `ValueError("无效的 XMind 文件格式")` | ERROR |
| content.xml 缺失 | 抛出 `ValueError("XMind 文件内容缺失")` | ERROR |
| XML 命名空间不匹配 | 使用通配符 XPath (`//topic`) 兼容 | WARNING |
| 节点文本为空 | 跳过该节点，记录跳过原因 | WARNING |
| 层级超过 5 层 | 截断至 5 层，深层节点文本拼接至 `point` | WARNING |
| 编码问题 | 统一使用 UTF-8 解码，失败时尝试 GBK | ERROR |

### 4.2 导入 API 端点（`app/api/v1/endpoints/test_point_import.py`）

#### 4.2.1 接口设计

```http
POST /api/v1/test-point/import-xmind
Content-Type: multipart/form-data

Request:
  - file: File (.xmind)
  - project_id: int (必填)
  - preview: bool = false (是否预览模式)

Response (preview=true):
  {
    "code": 200,
    "message": "解析成功",
    "data": {
      "total": 150,
      "items": [
        {"module": "字词听写", "function": "有教材内容", "point": "点击听写记录...", "priority": 2}
      ]
    }
  }

Response (preview=false):
  {
    "code": 200,
    "message": "导入成功",
    "data": {
      "saved_count": 148,
      "total_parsed": 150,
      "skipped_count": 2,
      "skipped_reasons": ["节点文本为空", "字段超长"]
    }
  }
```

#### 4.2.2 权限校验

- 复用现有 `check_project_permission` 函数
- 校验 `project_id` 归属当前用户
- 文件上传大小限制：≤10MB

#### 4.2.3 事务控制

- 预览模式：不开启数据库事务，仅解析返回
- 导入模式：使用 `db.begin()` 显式事务，失败时自动回滚

### 4.3 前端导入组件

#### 4.3.1 页面流程

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. 上传 XMind   │ --> │  2. 预览解析结果 │ --> │  3. 确认导入    │
│   文件选择/拖拽   │     │   表格展示测试点  │     │  显示成功/失败  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

#### 4.3.2 组件清单

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `XmindUpload` | `src/components/xmind/XmindUpload.vue` | 文件上传组件（支持拖拽） |
| `XmindPreview` | `src/components/xmind/XmindPreview.vue` | 解析预览表格（可编辑） |
| `XmindImportResult` | `src/components/xmind/XmindImportResult.vue` | 导入结果展示 |
| `XmindImportPage` | `src/views/test-point/XmindImportPage.vue` | 导入页面（整合上述组件） |

---

## 5. 技术架构

### 5.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端层 (Vue3 + TS)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ XmindUpload  │  │ XmindPreview │  │ XmindImportResult    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API 层 (FastAPI)                         │
│  POST /api/v1/test-point/import-xmind                           │
│  ├── 权限校验 (check_project_permission)                         │
│  ├── 文件校验 (大小/格式)                                         │
│  ├── 调用 XmindParser 解析                                       │
│  ├── 字段映射与转换                                               │
│  └── 预览模式/导入模式分支                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      服务层 (Services)                           │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ XmindParser      │  │ FileParserFactory│  (扩展注册)        │
│  │ (新增)           │  │ (现有扩展)        │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      数据层 (CRUD + Model)                       │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ batch_create_    │  │ TestPoint Model  │  (现有，无修改)     │
│  │ test_points      │  │                  │                    │
│  │ (现有复用)        │  │                  │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 新增文件清单

| 文件路径 | 类型 | 说明 |
|----------|------|------|
| `app/services/xmind_parser.py` | 新增 | XMind 解析引擎核心 |
| `app/api/v1/endpoints/test_point_import.py` | 新增 | XMind 导入 API 端点 |
| `app/schemas/test_point.py` | 扩展 | 新增导入请求/响应 Schema |
| `app/services/file_parser.py` | 扩展 | 注册 `XmindParser` 到工厂 |
| `app/services/file_content_extractor.py` | 扩展 | 新增 `.xmind` 分支 |
| `src/components/xmind/XmindUpload.vue` | 新增 | 上传组件 |
| `src/components/xmind/XmindPreview.vue` | 新增 | 预览组件 |
| `src/components/xmind/XmindImportResult.vue` | 新增 | 结果组件 |
| `src/views/test-point/XmindImportPage.vue` | 新增 | 导入页面 |
| `src/api/testPoint.ts` | 扩展 | 新增导入 API 调用 |
| `tests/services/test_xmind_parser.py` | 新增 | 解析器单元测试 |
| `tests/api/test_test_point_import.py` | 新增 | API 接口测试 |

### 5.3 修改文件清单

| 文件路径 | 修改内容 | 影响范围 |
|----------|----------|----------|
| `app/services/file_parser.py` | 在 `FileParserFactory` 中新增 `.xmind` 映射 | 工厂类 |
| `app/services/file_content_extractor.py` | 在 `_extract_by_type` 中新增 `xmind` 分支 | 提取服务 |
| `app/schemas/test_point.py` | 新增 `TestPointXmindImportRequest`、`TestPointXmindImportResponse` | Schema |
| `app/api/v1/endpoints/test_point.py` | 注册导入路由 | 路由注册 |
| `src/api/testPoint.ts` | 新增 `importXmind` 函数 | API 封装 |
| `src/router/index.ts` | 新增导入页面路由 | 路由配置 |

---

## 6. 实施计划

### 6.1 里程碑规划

| 里程碑 | 目标 | 预计耗时 | 产出物 | 负责人 | 前置条件 |
|--------|------|----------|--------|--------|----------|
| **M1** | 技术调研与方案设计 | 2h | 《XMind 解析技术选型报告》+ 字段映射规则文档 | 后端开发 | 样例文件已提供 |
| **M2** | 核心解析引擎开发 | 4h | `XmindParser` 类 + 单元测试 | 后端开发 | M1 完成 |
| **M3** | 后端 API 开发 | 3h | `POST /test-point/import-xmind` 端点 | 后端开发 | M2 完成 |
| **M4** | 前端页面开发 | 3h | XMind 导入页面 + 组件 | 前端开发 | M3 API 就绪 |
| **M5** | 集成测试与联调 | 2h | 测试报告 + Bug 修复 | 测试 | M4 完成 |
| **M6** | 验收与上线 | 1h | 上线确认 + 文档更新 | 产品 | M5 通过 |

### 6.2 详细任务分解

#### M1: 技术调研与方案设计（2h）

| 任务ID | 任务名称 | 负责人 | 起止时间 | 前置条件 | 交付成果 | 验收标准 |
|--------|----------|--------|----------|----------|----------|----------|
| M1-1 | 分析样例文件 XML 结构 | 后端开发 | 0-1h | 样例文件已提供 | XML 节点结构文档 | 能清晰标注根主题/子主题/备注的 XPath 路径 |
| M1-2 | 确定字段映射规则 | 后端开发 | 1-1.5h | M1-1 完成 | 字段映射规则表 | 规则表覆盖所有 XMind 节点类型到系统字段的映射 |
| M1-3 | 设计异常处理策略 | 后端开发 | 1.5-2h | M1-2 完成 | 异常处理清单 | 清单覆盖文件损坏/格式错误/节点为空等 5+ 场景 |

#### M2: 核心解析引擎开发（4h）

| 任务ID | 任务名称 | 负责人 | 起止时间 | 前置条件 | 交付成果 | 验收标准 |
|--------|----------|--------|----------|----------|----------|----------|
| M2-1 | 实现 XmindParser 核心类 | 后端开发 | 0-2h | M1 完成 | `app/services/xmind_parser.py` | 能正确解析样例文件，提取所有节点文本 |
| M2-2 | 实现字段映射与转换逻辑 | 后端开发 | 2-3h | M2-1 完成 | 字段映射函数 | 映射结果与预期字段 100% 对齐 |
| M2-3 | 编写单元测试 | 后端开发 | 3-4h | M2-2 完成 | `tests/services/test_xmind_parser.py` | 覆盖率 ≥95%，包含正常/空文件/深层嵌套/特殊字符场景 |

#### M3: 后端 API 开发（3h）

| 任务ID | 任务名称 | 负责人 | 起止时间 | 前置条件 | 交付成果 | 验收标准 |
|--------|----------|--------|----------|----------|----------|----------|
| M3-1 | 新增导入请求/响应 Schema | 后端开发 | 0-0.5h | M2 完成 | `TestPointXmindImportRequest` / `TestPointXmindImportResponse` | Schema 字段完整，校验规则正确 |
| M3-2 | 实现导入 API 端点 | 后端开发 | 0.5-2h | M3-1 完成 | `app/api/v1/endpoints/test_point_import.py` | 支持预览/导入两种模式，权限校验正确 |
| M3-3 | 注册解析器到工厂 | 后端开发 | 2-2.5h | M3-2 完成 | `FileParserFactory` 扩展 | `.xmind` 文件能被工厂正确识别 |
| M3-4 | 编写 API 测试 | 后端开发 | 2.5-3h | M3-3 完成 | `tests/api/test_test_point_import.py` | 覆盖成功/失败/权限不足场景 |

#### M4: 前端页面开发（3h）

| 任务ID | 任务名称 | 负责人 | 起止时间 | 前置条件 | 交付成果 | 验收标准 |
|--------|----------|--------|----------|----------|----------|----------|
| M4-1 | 开发上传组件 | 前端开发 | 0-1h | M3 API 就绪 | `XmindUpload.vue` | 支持拖拽上传，文件类型校验 |
| M4-2 | 开发预览表格 | 前端开发 | 1-2h | M4-1 完成 | `XmindPreview.vue` | 表格展示解析结果，支持分页 |
| M4-3 | 开发结果展示 | 前端开发 | 2-2.5h | M4-2 完成 | `XmindImportResult.vue` | 展示成功/失败统计，失败原因可展开 |
| M4-4 | 整合导入页面 | 前端开发 | 2.5-3h | M4-3 完成 | `XmindImportPage.vue` | 页面流程完整，用户体验流畅 |

#### M5: 集成测试与联调（2h）

| 任务ID | 任务名称 | 负责人 | 起止时间 | 前置条件 | 交付成果 | 验收标准 |
|--------|----------|--------|----------|----------|----------|----------|
| M5-1 | 端到端测试 | 测试 | 0-1h | M4 完成 | 测试报告 | 使用 5+ 个不同 XMind 文件测试，成功率 ≥95% |
| M5-2 | 性能测试 | 测试 | 1-1.5h | M5-1 完成 | 性能报告 | 200 条测试点导入耗时 ≤3 秒 |
| M5-3 | Bug 修复与回归 | 后端/前端 | 1.5-2h | M5-2 完成 | 修复清单 | 所有 P0/P1 Bug 修复完毕 |

#### M6: 验收与上线（1h）

| 任务ID | 任务名称 | 负责人 | 起止时间 | 前置条件 | 交付成果 | 验收标准 |
|--------|----------|--------|----------|----------|----------|----------|
| M6-1 | 产品验收 | 产品 | 0-0.5h | M5 完成 | 验收签字 | 功能符合需求文档描述 |
| M6-2 | 上线部署 | 后端开发 | 0.5-1h | M6-1 完成 | 上线确认 | 线上环境功能正常 |

---

## 7. 资源需求

### 7.1 人力资源

| 角色 | 人数 | 职责 | 投入时间 |
|------|------|------|----------|
| 后端开发 | 1 | 解析引擎、API 开发、单元测试 | 9h |
| 前端开发 | 1 | 上传组件、预览页面、结果展示 | 3h |
| 测试 | 1 | 集成测试、性能测试、Bug 验证 | 2h |
| 产品 | 1 | 需求确认、验收、上线审批 | 1h |

### 7.2 技术资源

| 资源 | 说明 | 是否新增 |
|------|------|----------|
| Python 3.10+ | 项目现有运行环境 | 否 |
| FastAPI | 项目现有 Web 框架 | 否 |
| SQLAlchemy | 项目现有 ORM | 否 |
| Vue 3 + TypeScript | 项目现有前端技术栈 | 否 |
| `zipfile` | Python 标准库，用于解压 `.xmind` | 否 |
| `xml.etree.ElementTree` | Python 标准库，用于解析 XML | 否 |
| `pytest` | 项目现有测试框架 | 否 |
| `pytest-cov` | 项目现有覆盖率工具 | 否 |

**结论**：零新增第三方依赖，完全符合项目"最小改动"原则。

### 7.3 样例资源

| 资源 | 用途 | 状态 |
|------|------|------|
| `听写任务.xmind` | 主样例文件，用于开发与测试 | 已提供 |
| 其他 XMind 文件 | 兼容性测试（不同版本/结构） | 需补充 5+ 个 |

---

## 8. 风险评估

### 8.1 风险矩阵

| 风险ID | 风险描述 | 发生概率 | 影响程度 | 风险等级 | 应对措施 |
|--------|----------|----------|----------|----------|----------|
| R1 | XMind 版本兼容性问题（不同版本 XML 结构差异） | 中 | 高 | **高** | 内置版本嗅探，支持 R3.x 核心结构，对其他版本抛出明确错误提示 |
| R2 | 复杂嵌套结构导致字段映射错乱 | 中 | 中 | **中** | 限制最大解析深度为 5 层，深层节点文本拼接至 `point` |
| R3 | 文件损坏或非标准格式导致解析崩溃 | 低 | 中 | **低** | 全局异常捕获，返回友好错误信息，不残留脏数据 |
| R4 | 导入性能不达标（>3 秒） | 低 | 低 | **低** | 批量写入使用 `batch_create_test_points`，避免逐条 commit |
| R5 | 前端组件与现有 UI 框架冲突 | 低 | 低 | **低** | 遵循现有组件设计规范，复用 UI 组件库 |

### 8.2 致命陷阱与规避

**陷阱**：XMind 文件内部 `content.xml` 的命名空间在不同版本中存在差异（如 `urn:xmind:xmap:xmlns:content:2.0` vs `urn:xmind:xmap:xmlns:content:1.0`），若使用固定命名空间的 XPath，可能导致解析失败。

**规避动作**：

1. 使用通配符 XPath（如 `.//{*}topic`）或忽略命名空间的方式解析 XML
2. 在单元测试中覆盖至少 2 个不同版本的 XMind 文件
3. 解析失败时返回明确的版本不兼容提示，引导用户导出为兼容版本

---

## 9. 验收标准

### 9.1 功能验收

| 验收项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| 文件上传 | 支持拖拽和点击选择 `.xmind` 文件 | 手工测试 |
| 解析正确性 | 样例文件解析后，测试点数量与手动清点一致 | 对比测试 |
| 字段映射 | 所有测试点的 `module`/`function`/`point` 字段正确 | 抽样校验 |
| 预览模式 | 预览表格展示解析结果，不写入数据库 | 数据库查询验证 |
| 导入模式 | 导入后数据库记录与预览结果一致 | 数据库查询验证 |
| 权限控制 | 非项目成员无法导入 | 接口测试 |

### 9.2 性能验收

| 验收项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| 解析耗时 | 50-200 条测试点文件解析 ≤3 秒 | `time.perf_counter()` 测量 |
| 并发处理 | 同时上传 5 个文件不崩溃 | 压力测试 |

### 9.3 质量验收

| 验收项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| 单元测试覆盖率 | 核心解析/导入逻辑 ≥95% | `pytest-cov` 报告 |
| 代码规范 | 符合项目代码规范（lowerCamelCase、类型注解等） | 静态检查 |
| 零侵入 | 现有测试点模块功能不受影响 | 回归测试 |

---

## 10. 项目规范与约束

### 10.1 代码风格规范

- **变量/函数**：lowerCamelCase
- **类名**：UpperCamelCase
- **常量**：UPPER_SNAKE_CASE
- **缩进**：4 空格
- **行宽**：≤120 字符
- **类型注解**：公开方法必须加类型注解与文档注释
- **字符串**：统一使用 f-string

### 10.2 架构设计规范

- **单文件限制**：≤300 行
- **依赖注入**：依赖构造函数注入，禁止直接 new 实例
- **模块结构**：新增模块遵循项目现有结构（`app/services/`、`app/api/v1/endpoints/` 等）
- **扩展原则**：优先扩展现有工厂/服务，不修改现有核心逻辑

### 10.3 安全规范

- **文件校验**：上传文件必须校验扩展名（`.xmind`）和 MIME 类型
- **大小限制**：单文件 ≤10MB，防止 ZIP 炸弹攻击
- **路径安全**：禁止解析文件名中的路径遍历字符（`../`）
- **权限校验**：所有导入操作必须校验项目归属权

### 10.4 测试规范

- **覆盖率**：核心分支覆盖率 ≥95%
- **用例设计**：正常、空值、异常、边界四种场景
- **真实数据**：使用真实 XMind 文件作为测试数据
- **数据清理**：测试执行后自动清理数据库测试数据

### 10.5 AI 生成约束

- **禁止 TODO**：未实现逻辑抛 `NotImplementedError`
- **异常捕获**：IO、网络、解析强制异常捕获
- **空安全**：深层属性必须空安全兜底
- **重复逻辑**：自动抽工具方法
- **废弃代码**：删除废弃注释代码

---

## 11. 附录

### 11.1 样例文件结构

```xml
<!-- content.xml 简化结构 -->
<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0">
  <sheet id="...">
    <title>旅行计划</title>
    <topic id="...">
      <title>听写任务</title>  <!-- 根主题（忽略） -->
      <children>
        <topics type="attached">
          <topic id="...">
            <title>字词听写</title>  <!-- 一级：module -->
            <children>
              <topics type="attached">
                <topic id="...">
                  <title>有教材内容</title>  <!-- 二级：function -->
                  <children>
                    <topics type="attached">
                      <topic id="...">
                        <title>界面详见UI</title>  <!-- 三级：point -->
                      </topic>
                    </topics>
                  </children>
                </topic>
              </topics>
            </children>
          </topic>
        </topics>
      </children>
    </topic>
  </sheet>
</xmap-content>
```

### 11.2 现有测试点模块字段对照

| 系统字段 | 类型 | 长度 | 必填 | 说明 |
|----------|------|------|------|------|
| `module` | String | 100 | 是 | 模块名称 |
| `function` | String | 200 | 否 | 功能名称 |
| `point` | String | 500 | 是 | 测试点描述 |
| `priority` | Integer | - | 是 | 1=高/2=中/3=低 |
| `ai_prompt` | Text | - | 否 | AI 提示词 |
| `project_id` | Integer | - | 是 | 所属项目 |

### 11.3 相关文件索引

| 文件路径 | 说明 |
|----------|------|
| `app/models/test_point.py` | 测试点数据模型 |
| `app/schemas/test_point.py` | 测试点 Schema |
| `app/crud/test_point.py` | 测试点 CRUD 操作 |
| `app/services/file_parser.py` | 文件解析器工厂 |
| `app/services/file_content_extractor.py` | 文件内容提取服务 |
| `app/api/v1/endpoints/test_point_mutate.py` | 测试点变更端点（批量保存） |
| `app/api/v1/endpoints/test_point_query.py` | 测试点查询端点 |
| `tests/test_crud_test_point.py` | 测试点 CRUD 测试 |
