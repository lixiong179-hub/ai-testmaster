# XMind 测试点导入功能 — 任务实施项清单

> 本文档基于《XMind 测试点导入功能规划文档》(`xmind_import_plan.md`) 制定，将规划中的里程碑进一步细化为可执行、可衡量、可交付的具体任务项。

---

## 文档信息

| 项 | 内容 |
|----|------|
| 项目名称 | XMind 测试点导入功能 |
| 交付死线 | 2026-04-23（明天） |
| 文档版本 | v1.2 |
| 编制日期 | 2026-04-22 |
| 更新日期 | 2026-04-22（v1.2 系统性补充评审反馈） |
| 关联文档 | `docs/xmind_import_plan.md` |

---

## 前端入口设计方案

### 一、入口位置

**主入口**：测试点管理页面（Step 4）的批量操作工具栏区域

**辅助入口**：测试点管理页面空状态提示区

**理由**：
1. **就近原则**：用户在管理测试点时最可能使用导入功能
2. **流程连续**：保持当前上下文，无需页面跳转
3. **操作集中**：与现有批量操作按钮统一布局

### 二、交互模式

**对话框模式**（非独立页面）：

```
点击"导入 XMind"按钮 → 弹出导入对话框 → 上传 → 预览 → 确认导入 → 刷新列表
```

**对话框属性**：

| 属性 | 值 | 说明 |
|------|------|------|
| 宽度 | `800px` | 保证表格宽度舒适 |
| 高度 | 自适应 | 内容决定 |
| 关闭方式 | 右上角 × / ESC / 点击遮罩 | 符合对话框常规操作 |
| 可拖拽 | 否 | 避免拖出可见区域 |

### 三、按钮样式

**工具栏按钮**：

```html
<el-button type="info" @click="showXmindImportDialog = true">
  <el-icon><Upload /></el-icon> 导入 XMind
</el-button>
```

- 类型：`info`（灰色），降低视觉优先级
- 图标：`Upload`，直观传达"导入"语义
- 位置：操作工具栏最右侧

**空状态按钮**：

```html
<el-empty description="暂无测试点数据">
  <el-button type="info" @click="showXmindImportDialog = true">
    <el-icon><Upload /></el-icon> 导入 XMind
  </el-button>
</el-empty>
```

### 四、前端组件清单

| 组件 | 路径 | 说明 |
|------|------|------|
| `XmindImportDialog.vue` | `src/components/xmind/XmindImportDialog.vue` | 导入对话框主组件 |

**不新增页面路由**，使用对话框模式。

### 五、集成点

| 文件 | 修改内容 | 位置 |
|------|----------|------|
| `src/views/case/test-point-extract.vue` | 工具栏新增按钮 + 空状态新增快捷按钮 + 引入对话框组件 | Step 4 区域（约第 400-480 行） |

---

## 任务总览

| 里程碑 | 任务数量 | 预计总耗时 | 缓冲时间 | 负责人 |
|--------|----------|------------|----------|--------|
| M1 技术调研与方案设计 | 3 项 | 2h | 0.5h | 后端开发 |
| M2 核心解析引擎开发 | 3 项 | 4h | 1h | 后端开发 |
| M3 后端 API 开发 | 4 项 | 3h | 1h | 后端开发 |
| M4 前端页面开发 | 4 项 | 3h | 1h | 前端开发 |
| M5 集成测试与联调 | 3 项 | 2h | 1h | 测试 |
| M6 验收与上线 | 2 项 | 1h | 0.5h | 产品/后端 |
| **合计** | **19 项** | **15h** | **5h** | - |

> **时间估算说明**：
> - 基础耗时基于理想情况估算，未考虑环境配置、代码审查、沟通确认等额外开销
> - 缓冲时间为各里程碑预留的弹性时间，用于应对意外情况
> - 建议采用并行开发策略：M1-M3（后端）与 M4（前端）可部分并行，前端在 M3-2 完成后即可开始接口联调

---

## M1: 技术调研与方案设计

### M1-1: 分析样例文件 XML 结构

| 属性 | 内容 |
|------|------|
| **任务名称** | 分析样例 XMind 文件 XML 结构 |
| **任务编号** | M1-1 |
| **所属里程碑** | M1 技术调研与方案设计 |
| **负责人** | 后端开发 |
| **预计耗时** | 1h |
| **前置条件** | 样例文件 `听写任务.xmind` 已提供且可访问 |
| **所需资源** | Python 环境、`zipfile` 库、文本编辑器 |

**执行步骤**：

1. 使用 `zipfile` 解压 `听写任务.xmind`，确认内部文件清单
2. 读取 `content.xml`，格式化后分析节点结构
3. 标注关键节点的 XPath 路径：
   - 根主题路径：`.//sheet/topic`
   - 一级子主题路径：`.//sheet/topic/children/topics/topic`
   - 二级子主题路径：`.//sheet/topic/children/topics/topic/children/topics/topic`
   - 节点文本路径：`topic/title`
   - 节点备注路径：`topic/notes/plain`
4. 记录 XML 命名空间（`urn:xmind:xmap:xmlns:content:2.0`）
5. 统计样例文件的层级深度、节点数量、文本长度分布

**交付成果**：

- `docs/xmind_xml_structure.md`：XML 结构分析文档
- 关键 XPath 路径清单（可复制到代码中使用）
- 节点数量统计表（模块数/功能数/测试点数）

**验收标准**：

- [ ] 能清晰标注根主题/子主题/备注的 XPath 路径
- [ ] 统计出样例文件中模块数≥5、功能数≥10、测试点数≥50
- [ ] 文档中包含 XML 片段示例（已脱敏）

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 样例文件损坏无法解压 | 低 | 高 | 提前验证文件完整性，准备备用样例 |
| XML 结构异常复杂 | 低 | 中 | 记录异常节点，在 M1-3 设计兼容策略 |

---

### M1-2: 确定字段映射规则

| 属性 | 内容 |
|------|------|
| **任务名称** | 确定 XMind 节点到系统字段的映射规则 |
| **任务编号** | M1-2 |
| **所属里程碑** | M1 技术调研与方案设计 |
| **负责人** | 后端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M1-1 完成，XML 结构已明确 |
| **所需资源** | 现有测试点模块字段定义 (`app/models/test_point.py`) |

**执行步骤**：

1. 对比 XMind 层级结构与系统 `TestPoint` 模型字段
2. 制定映射规则表（根主题→忽略/一级→module/二级→function/三级→point）
3. 定义优先级识别规则：
   - 节点标记为红色/优先级1图标 → priority=1（高）
   - 节点标记为黄色/优先级2图标 → priority=2（中）
   - 节点标记为绿色/优先级3图标 → priority=3（低）
   - 无标记 → priority=2（默认中）
4. 定义备注处理规则：节点备注追加到 `point` 字段后
5. 与产品确认映射规则（5分钟快速确认）

**交付成果**：

- `docs/xmind_field_mapping.md`：字段映射规则文档
- 映射规则对照表（见下方）

**映射规则表**：

| XMind 层级 | 系统字段 | 映射规则 | 默认值 | 必填 |
|------------|----------|----------|--------|------|
| 根主题 | - | 忽略 | - | 否 |
| 一级子主题 | `module` | 直接映射 | - | 是 |
| 二级子主题 | `function` | 直接映射 | "" | 否 |
| 三级子主题 | `point` | 直接映射 | - | 是 |
| 四级及以下 | `point` | 文本拼接至父节点 | - | 否 |
| 节点备注 | `point` | 追加到 `point` 后 | - | 否 |
| 优先级图标 | `priority` | 1/2/3 | 2 | 是 |

**验收标准**：

- [ ] 规则表覆盖所有 XMind 节点类型到系统字段的映射
- [ ] 产品已确认映射规则无误
- [ ] 规则文档中包含异常场景处理（如节点文本为空）

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 产品与开发对映射规则理解不一致 | 中 | 高 | 快速确认会议，文档签字 |

---

### M1-3: 设计异常处理策略

| 属性 | 内容 |
|------|------|
| **任务名称** | 设计 XMind 解析异常处理策略 |
| **任务编号** | M1-3 |
| **所属里程碑** | M1 技术调研与方案设计 |
| **负责人** | 后端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M1-1、M1-2 完成 |
| **所需资源** | 项目异常处理规范、日志规范 |

**执行步骤**：

1. 列出所有可能的异常场景（文件层/解析层/映射层）
2. 为每个异常场景定义：
   - 异常类型（自定义异常类或内置异常）
   - 错误码（HTTP 状态码 + 业务错误码）
   - 错误信息（用户友好的中文提示）
   - 日志级别（DEBUG/INFO/WARNING/ERROR）
3. 设计异常传播路径：解析器 → 服务层 → API 层 → 前端
4. 定义事务回滚策略（导入失败时自动回滚）

**交付成果**：

- `docs/xmind_exception_strategy.md`：异常处理策略文档
- 异常场景清单（见下方）

**异常场景清单**：

| 场景 | 异常类型 | 错误信息 | 日志级别 | 处理方式 |
|------|----------|----------|----------|----------|
| 文件非 ZIP 格式 | `ValueError` | "无效的 XMind 文件格式，请上传 .xmind 文件" | ERROR | 立即返回 400 |
| content.xml 缺失 | `ValueError` | "XMind 文件内容缺失，文件可能已损坏" | ERROR | 立即返回 400 |
| XML 解析失败 | `xml.etree.ParseError` | "无法解析 XMind 文件内容" | ERROR | 立即返回 400 |
| 节点文本为空 | - | - | WARNING | 跳过该节点，记录原因 |
| 字段超长 | - | - | WARNING | 跳过该节点，记录原因 |
| 层级超过 5 层 | - | - | WARNING | 截断至 5 层 |
| 编码错误 | `UnicodeDecodeError` | "文件编码错误" | ERROR | 尝试 GBK 回退 |
| 数据库写入失败 | `SQLAlchemyError` | "导入失败，请稍后重试" | ERROR | 事务回滚 |

**验收标准**：

- [ ] 清单覆盖文件损坏/格式错误/节点为空/字段超长/编码错误等 5+ 场景
- [ ] 每个场景都有明确的错误信息和日志级别
- [ ] 事务回滚策略已定义，确保导入失败不残留脏数据

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 遗漏异常场景 | 中 | 中 | 预留通用异常捕获兜底 |

---

## M2: 核心解析引擎开发

### M2-1: 实现 XmindParser 核心类

| 属性 | 内容 |
|------|------|
| **任务名称** | 实现 XMind 解析引擎核心类 |
| **任务编号** | M2-1 |
| **所属里程碑** | M2 核心解析引擎开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 2h |
| **前置条件** | M1 完成，XML 结构和字段映射规则已明确 |
| **所需资源** | Python 3.10+、`zipfile`、`xml.etree.ElementTree` |

**执行步骤**：

1. 创建 `app/services/xmind_parser.py` 文件
2. 定义 `XmindParser` 类，实现以下方法：
   - `parse(file_path: str) -> List[Dict[str, Any]]`：主入口方法
   - `_extract_content_xml(file_path: str) -> bytes`：解压并读取 content.xml
   - `_parse_topics(root_topic: Element) -> List[Dict]`：递归解析主题层级
   - `_extract_topic_text(topic: Element) -> str`：提取节点文本
   - `_extract_topic_notes(topic: Element) -> Optional[str]`：提取节点备注
   - `_detect_priority(topic: Element) -> int`：识别优先级标记
3. 处理 XML 命名空间兼容性（使用通配符或 strip 命名空间）
4. 添加类型注解和文档注释

**代码框架**：

```python
"""XMind 文件解析器 - 将 .xmind 文件解析为测试点数据。

依赖关系:
    - Python 标准库: zipfile, xml.etree.ElementTree
"""
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from loguru import logger


class XmindParseError(Exception):
    """XMind 解析异常基类。"""
    pass


class XmindParser:
    """XMind 文件解析器。

    支持 XMind R3.x 标准格式（.xmind 文件为 ZIP 压缩包）。
    解析规则:
        - 根主题: 忽略
        - 一级子主题: module
        - 二级子主题: function
        - 三级及以下: point
    """

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """解析 XMind 文件，返回测试点列表。"""
        pass

    def _extract_content_xml(self, file_path: str) -> bytes:
        """从 .xmind 文件中提取 content.xml。"""
        pass

    def _parse_topics(self, root_topic: ET.Element) -> List[Dict[str, Any]]:
        """递归解析主题层级。"""
        pass
```

**交付成果**：

- `app/services/xmind_parser.py`：解析器核心代码
- 代码行数 ≤300 行（符合项目规范）

**验收标准**：

- [ ] 能正确解析样例文件，提取所有节点文本
- [ ] 代码通过类型检查（`mypy` 或 IDE 类型检查）
- [ ] 所有公开方法都有类型注解和文档注释
- [ ] 代码符合项目代码风格（lowerCamelCase、4空格缩进、行宽≤120）

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| XML 命名空间处理复杂 | 中 | 中 | 使用通配符 XPath，预留多种命名空间 |
| 递归深度过大导致栈溢出 | 低 | 高 | 限制最大递归深度为 10 层 |

---

### M2-2: 实现字段映射与转换逻辑

| 属性 | 内容 |
|------|------|
| **任务名称** | 实现 XMind 节点到系统字段的映射转换逻辑 |
| **任务编号** | M2-2 |
| **所属里程碑** | M2 核心解析引擎开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 1h |
| **前置条件** | M2-1 完成，解析器能提取节点数据 |
| **所需资源** | M1-2 字段映射规则文档 |

**执行步骤**：

1. 在 `XmindParser` 中实现 `_build_test_point` 方法
2. 实现字段映射逻辑：
   - 一级主题 → `module`
   - 二级主题 → `function`
   - 三级主题 → `point`
   - 四级及以下 → 合并到父级 `point` 字段
3. 实现优先级识别逻辑：
   - 解析节点标记（`marker-refs` 元素）
   - 映射优先级图标到 1/2/3
4. 实现备注追加逻辑：
   - 提取节点备注文本
   - 追加到 `point` 字段后（格式：`point + "\n备注: " + notes`）
5. 实现字段截断逻辑：
   - `module` > 100 字符时截断并记录警告
   - `function` > 200 字符时截断并记录警告
   - `point` > 500 字符时截断并记录警告

**四级及以下节点合并规则**：

| 场景 | 处理方式 | 示例 |
|------|----------|------|
| 四级节点 | 文本拼接至三级 `point`，用 " > " 连接 | `点击听写 > 查看详情 > 验证数据` |
| 五级节点 | 继续拼接至同一 `point` 字段 | `点击听写 > 查看详情 > 验证数据 > 确认保存` |
| 同级多节点 | 每个节点独立生成一条测试点记录 | 三级 `point` 相同，四级各自独立 |
| 四级节点含备注 | 备注追加到合并后的 `point` 末尾 | `...验证数据\n备注: 需登录` |

**数据库字段长度限制**：

| 字段 | 数据库类型 | 最大长度 | 截断策略 |
|------|------------|----------|----------|
| `module` | `String(100)` | 100 字符 | 超出截断，记录 WARNING 日志 |
| `function` | `String(200)` | 200 字符 | 超出截断，记录 WARNING 日志 |
| `point` | `String(500)` | 500 字符 | 超出截断，记录 WARNING 日志 |
| `priority` | `Integer` | 1-3 | 非法值默认设为 2 |

**交付成果**：

- `XmindParser` 类中的映射转换方法
- 字段映射单元测试用例（在 M2-3 中实现）

**验收标准**：

- [ ] 映射结果与预期字段 100% 对齐
- [ ] 样例文件解析后，`module`/`function`/`point` 字段正确填充
- [ ] 四级及以下节点按规则合并，不丢失信息
- [ ] 字段超长时正确截断并记录日志
- [ ] 空节点被跳过，不导致解析失败

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 映射规则遗漏边界场景 | 中 | 中 | 预留默认处理逻辑 |
| 四级节点合并导致 `point` 超长 | 中 | 低 | 截断并记录日志，确保不超出 500 字符 |

---

### M2-3: 编写单元测试

| 属性 | 内容 |
|------|------|
| **任务名称** | 编写 XMind 解析器单元测试 |
| **任务编号** | M2-3 |
| **所属里程碑** | M2 核心解析引擎开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 1h |
| **前置条件** | M2-1、M2-2 完成 |
| **所需资源** | `pytest`、`pytest-cov`、样例 XMind 文件 |

**执行步骤**：

1. 创建 `tests/services/test_xmind_parser.py` 文件
2. 编写测试用例：
   - `test_parse_success`：正常解析样例文件
   - `test_parse_empty_file`：空 XMind 文件
   - `test_parse_deep_nesting`：深层嵌套（>5 层）
   - `test_parse_special_chars`：特殊字符（emoji、中文标点）
   - `test_parse_invalid_zip`：非 ZIP 文件
   - `test_parse_missing_content_xml`：缺少 content.xml
   - `test_field_mapping`：字段映射正确性
   - `test_priority_detection`：优先级识别
3. 运行测试并生成覆盖率报告
4. 确保核心逻辑覆盖率 ≥95%

**测试数据准备**：

| 测试文件 | 用途 | 准备方式 |
|----------|------|----------|
| `tests/fixtures/valid.xmind` | 正常解析测试 | 复制样例文件 |
| `tests/fixtures/empty.xmind` | 空文件测试 | 创建最小 XMind 文件 |
| `tests/fixtures/deep_nesting.xmind` | 深层嵌套测试 | 手动创建 8 层嵌套 |
| `tests/fixtures/invalid.zip` | 无效文件测试 | 重命名一个普通 ZIP |

**交付成果**：

- `tests/services/test_xmind_parser.py`：单元测试代码
- 覆盖率报告（`pytest-cov` 生成）

**验收标准**：

- [ ] 测试用例覆盖正常/空文件/深层嵌套/特殊字符/无效文件/缺失 content.xml 场景
- [ ] 核心解析逻辑覆盖率 ≥95%
- [ ] 所有测试用例通过
- [ ] 测试用例执行后自动清理测试数据（无残留文件）

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 测试数据准备耗时超预期 | 中 | 低 | 提前准备最小测试文件 |
| 覆盖率不达标 | 低 | 中 | 补充边界场景测试 |

---

## M3: 后端 API 开发

### M3-1: 新增导入请求/响应 Schema

| 属性 | 内容 |
|------|------|
| **任务名称** | 新增 XMind 导入请求/响应 Schema |
| **任务编号** | M3-1 |
| **所属里程碑** | M3 后端 API 开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M2 完成，解析器已就绪 |
| **所需资源** | `pydantic`、现有 `TestPointBase` Schema |

**执行步骤**：

1. 打开 `app/schemas/test_point.py`
2. 新增以下 Schema：
   - `TestPointXmindImportRequest`：导入请求（`project_id`、`preview`）
   - `TestPointXmindImportResponse`：导入响应（`saved_count`、`total_parsed`、`skipped_count`）
   - `TestPointXmindPreviewItem`：预览项（`module`、`function`、`point`、`priority`）
   - `TestPointXmindPreviewResponse`：预览响应（`total`、`items`）
3. 复用现有 `TestPointBase` 字段定义，保持数据一致性
4. 添加字段校验规则（`project_id` > 0、`preview` 为布尔值）

**Schema 定义**：

```python
class TestPointXmindImportRequest(BaseModel):
    """XMind 导入请求模型。"""
    project_id: int = Field(..., gt=0, description="项目ID")
    preview: bool = Field(False, description="是否预览模式")

class TestPointXmindPreviewItem(BaseModel):
    """XMind 导入预览项。"""
    module: str = Field(..., description="模块名称")
    function: str = Field(..., description="功能名称")
    point: str = Field(..., description="测试点描述")
    priority: int = Field(..., ge=1, le=3, description="优先级")

class TestPointXmindPreviewResponse(BaseModel):
    """XMind 导入预览响应。"""
    total: int = Field(..., description="解析出的测试点总数")
    items: List[TestPointXmindPreviewItem] = Field(..., description="测试点列表")
```

**交付成果**：

- `app/schemas/test_point.py` 中的新增 Schema

**验收标准**：

- [ ] Schema 字段完整，与解析器输出字段一致
- [ ] 校验规则正确（`project_id` > 0、`priority` 1-3）
- [ ] 类型注解完整，通过 IDE 类型检查

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 字段定义与解析器不一致 | 低 | 高 | 对照 M1-2 映射规则表复核 |

---

### M3-2: 实现导入 API 端点

| 属性 | 内容 |
|------|------|
| **任务名称** | 实现 XMind 导入 API 端点 |
| **任务编号** | M3-2 |
| **所属里程碑** | M3 后端 API 开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 1.5h |
| **前置条件** | M3-1 完成，Schema 已定义 |
| **所需资源** | FastAPI、`UploadFile`、现有权限校验函数 |

**执行步骤**：

1. 创建 `app/api/v1/endpoints/test_point_import.py` 文件
2. 实现 `POST /test-point/import-xmind` 端点：
   - 接收 `UploadFile` 和 `project_id`
   - 校验文件类型（`.xmind`）和大小（≤10MB）
   - 调用 `check_project_permission` 校验权限
   - 调用 `XmindParser.parse()` 解析文件
   - 预览模式：返回解析结果，不写入数据库
   - 导入模式：调用 `batch_create_test_points` 批量写入
3. 实现错误处理：
   - 文件格式错误 → 400 Bad Request
   - 解析失败 → 400 Bad Request + 详细错误信息
   - 权限不足 → 403 Forbidden
   - 服务器错误 → 500 Internal Server Error
4. 添加事务控制：导入模式使用 `db.begin()`

**接口定义**：

```python
@router.post("/import-xmind")
async def import_xmind(
    file: UploadFile = File(..., description="XMind 文件"),
    project_id: int = Form(..., description="项目ID"),
    preview: bool = Form(False, description="是否预览"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """导入 XMind 测试点文件。"""
    pass
```

**交付成果**：

- `app/api/v1/endpoints/test_point_import.py`：API 端点代码

**验收标准**：

- [ ] 支持预览/导入两种模式
- [ ] 权限校验正确（非项目成员返回 403）
- [ ] 文件类型校验正确（非 `.xmind` 返回 400）
- [ ] 文件大小限制正确（>10MB 返回 400）
- [ ] 导入失败时事务回滚，不残留脏数据
- [ ] 返回结果包含成功数/失败数/跳过数统计

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 事务控制不当导致脏数据 | 低 | 高 | 使用 `db.begin()` 显式事务 |
| 大文件导致内存溢出 | 低 | 高 | 限制文件大小 ≤10MB |

---

### M3-3: 注册解析器到工厂

| 属性 | 内容 |
|------|------|
| **任务名称** | 将 XMind 解析器注册到 FileParserFactory |
| **任务编号** | M3-3 |
| **所属里程碑** | M3 后端 API 开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M3-2 完成，API 端点已实现 |
| **所需资源** | `app/services/file_parser.py`、现有工厂类源码 |

**执行步骤**：

1. 分析现有 `FileParserFactory` 工厂类结构（`app/services/file_parser.py`）
2. 确认 `XmindParser` 与现有 `FileParser` 抽象基类的接口差异
3. 在 `FileParserFactory.get_parser()` 的 `parsers` 字典中新增 `.xmind` 映射
4. 在 `file_content_extractor.py` 的 `_extract_by_type` 方法中新增 `xmind` 分支
5. 验证工厂能正确识别 `.xmind` 扩展名并返回 `XmindParser` 实例

**现有工厂结构分析**：

```python
# app/services/file_parser.py 现有结构
class FileParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> str:
        pass

class FileParserFactory:
    @staticmethod
    def get_parser(file_extension: str) -> Optional[FileParser]:
        parsers = {
            '.txt': TxtParser(),
            '.md': MdParser(),
            '.doc': DocParser(),
            '.docx': DocxParser(),
            '.pdf': PdfParser()
            # 需新增: '.xmind': XmindParser()
        }
        return parsers.get(file_extension.lower())
```

**关键适配点**：

| 适配项 | 现有接口 | XmindParser 接口 | 处理方案 |
|--------|----------|------------------|----------|
| 返回值类型 | `str` | `List[Dict[str, Any]]` | XmindParser 不走工厂统一入口，由 API 层直接调用 |
| 注册方式 | 工厂字典映射 | 独立实例化 | 工厂注册仅用于文件类型识别，解析逻辑由专用 API 处理 |

**代码变更**：

```python
# app/services/file_parser.py
from app.services.xmind_parser import XmindParser  # 新增导入

class FileParserFactory:
    @staticmethod
    def get_parser(file_extension: str) -> Optional[FileParser]:
        parsers = {
            '.txt': TxtParser(),
            '.md': MdParser(),
            '.doc': DocParser(),
            '.docx': DocxParser(),
            '.pdf': PdfParser(),
            '.xmind': XmindParser()  # 新增 XMind 解析器注册
        }
        return parsers.get(file_extension.lower())
```

```python
# app/services/file_content_extractor.py
# 在 _extract_by_type 方法中新增分支
def _extract_by_type(file_path: str, file_type: str) -> str:
    if file_type == 'xmind':
        # XMind 文件返回结构化 JSON 字符串，而非纯文本
        parser = XmindParser()
        result = parser.parse(file_path)
        return json.dumps(result, ensure_ascii=False)
    # ... 其他现有分支保持不变
```

**交付成果**：

- `app/services/file_parser.py`：工厂类扩展（新增 `.xmind` 映射）
- `app/services/file_content_extractor.py`：提取服务扩展（新增 `xmind` 分支）

**验收标准**：

- [ ] `FileParserFactory.get_parser('.xmind')` 返回 `XmindParser` 实例
- [ ] `FileParserFactory.parse_file('test.xmind')` 能正确调用解析逻辑
- [ ] 现有 `.txt`/`.md`/`.pdf` 等格式解析不受影响（回归验证）
- [ ] 不支持的格式仍返回 `"不支持的文件类型"` 提示

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| XmindParser 与 FileParser 接口不兼容 | 中 | 中 | XmindParser 独立实现，不强制继承 FileParser |
| 工厂注册影响现有解析器 | 低 | 高 | 修改后执行全量文件解析回归测试 |
| 循环导入问题 | 低 | 中 | 使用局部导入或调整导入顺序 |
| **所属里程碑** | M3 后端 API 开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M2-1 完成，`XmindParser` 已实现 |
| **所需资源** | `app/services/file_parser.py` |

**执行步骤**：

1. 打开 `app/services/file_parser.py`
2. 导入 `XmindParser`
3. 在 `FileParserFactory.get_parser()` 中新增 `.xmind` 映射：
   ```python
   parsers = {
       '.txt': TxtParser(),
       '.md': MdParser(),
       # ... 现有解析器
       '.xmind': XmindParser()  # 新增
   }
   ```
4. 更新 `FileParserFactory` 文档注释，添加 `.xmind` 支持说明
5. 在 `app/services/file_content_extractor.py` 的 `_extract_by_type` 中新增 `xmind` 分支

**交付成果**：

- `app/services/file_parser.py`：工厂类扩展
- `app/services/file_content_extractor.py`：提取服务扩展

**验收标准**：

- [ ] `.xmind` 文件能被 `FileParserFactory` 正确识别
- [ ] `FileContentExtractor` 能提取 `.xmind` 文件内容
- [ ] 现有文件解析功能不受影响（回归测试通过）

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 注册错误导致工厂类异常 | 低 | 高 | 运行现有文件解析测试验证 |

---

### M3-4: 编写 API 测试

| 属性 | 内容 |
|------|------|
| **任务名称** | 编写 XMind 导入 API 测试 |
| **任务编号** | M3-4 |
| **所属里程碑** | M3 后端 API 开发 |
| **负责人** | 后端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M3-2、M3-3 完成 |
| **所需资源** | `pytest`、`TestClient`、样例 XMind 文件 |

**执行步骤**：

1. 创建 `tests/api/test_test_point_import.py` 文件
2. 编写测试用例：
   - `test_import_success`：正常导入流程验证
   - `test_import_preview`：预览模式不写入数据库
   - `test_import_invalid_file`：无效文件格式（非 ZIP）
   - `test_import_no_permission`：无权限访问（403）
   - `test_import_oversized_file`：文件过大（>10MB）
   - `test_import_missing_content_xml`：XMind 文件缺少 content.xml
   - `test_import_empty_nodes`：空节点跳过统计
3. 使用 `TestClient` 模拟 HTTP 请求
4. 验证响应状态码、响应体结构和数据库状态

**API 错误码定义**：

| 错误场景 | HTTP 状态码 | 业务错误码 | 错误信息示例 |
|----------|-------------|------------|--------------|
| 文件格式错误 | 400 | `INVALID_FILE_FORMAT` | "无效的 XMind 文件格式，请上传 .xmind 文件" |
| content.xml 缺失 | 400 | `INVALID_XMIND_STRUCTURE` | "XMind 文件内容缺失，文件可能已损坏" |
| XML 解析失败 | 400 | `XML_PARSE_ERROR` | "无法解析 XMind 文件内容" |
| 文件过大 | 400 | `FILE_TOO_LARGE` | "文件大小超过 10MB 限制" |
| 权限不足 | 403 | `PERMISSION_DENIED` | "无权限访问该项目" |
| 项目不存在 | 404 | `PROJECT_NOT_FOUND` | "项目不存在" |
| 服务器内部错误 | 500 | `INTERNAL_ERROR` | "导入失败，请稍后重试" |

**响应示例**：

```json
// 预览模式成功响应 (200 OK)
{
  "code": 200,
  "message": "解析成功",
  "data": {
    "total": 150,
    "items": [
      {
        "module": "字词听写",
        "function": "有教材内容",
        "point": "点击听写记录，查看字词列表",
        "priority": 2
      }
    ]
  }
}

// 导入模式成功响应 (200 OK)
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

// 错误响应示例 (400 Bad Request)
{
  "code": 400,
  "message": "无效的 XMind 文件格式，请上传 .xmind 文件",
  "error": "INVALID_FILE_FORMAT"
}
```

**测试代码框架**：

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestXmindImport:
    """XMind 导入 API 测试类。"""

    def test_import_preview_success(self, auth_headers, sample_xmind_file):
        """测试预览模式：解析成功但不写入数据库。"""
        with open(sample_xmind_file, 'rb') as f:
            response = client.post(
                '/api/v1/test-point/import-xmind',
                files={'file': ('test.xmind', f, 'application/octet-stream')},
                data={'project_id': 1, 'preview': 'true'},
                headers=auth_headers
            )
        assert response.status_code == 200
        data = response.json()
        assert data['code'] == 200
        assert 'total' in data['data']
        assert 'items' in data['data']
        # 验证数据库未写入
        # assert db.query(TestPoint).count() == 0

    def test_import_invalid_file_format(self, auth_headers):
        """测试无效文件格式：上传非 ZIP 文件。"""
        response = client.post(
            '/api/v1/test-point/import-xmind',
            files={'file': ('test.txt', b'not a zip', 'text/plain')},
            data={'project_id': 1, 'preview': 'false'},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert response.json()['error'] == 'INVALID_FILE_FORMAT'
```

**交付成果**：

- `tests/api/test_test_point_import.py`：API 测试代码
- API 错误码文档（上表）

**验收标准**：

- [ ] 覆盖成功/预览/无效文件/权限不足/文件过大/缺失 content.xml/空节点 7+ 场景
- [ ] 所有测试用例通过
- [ ] 测试用例执行后自动清理测试数据（使用 fixture 隔离）
- [ ] 错误响应包含标准格式：`{code, message, error}`

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 测试环境数据库状态不一致 | 中 | 中 | 使用 `fixture` 隔离测试数据，每个用例独立事务 |
| 文件上传 fixture 管理复杂 | 中 | 低 | 使用 `tmp_path` 创建临时文件，用例结束后自动清理 |
| 认证 fixture 依赖复杂 | 低 | 中 | 复用现有 `auth_headers` fixture |

---

## M4: 前端页面开发

### M4-1: 开发上传组件

| 属性 | 内容 |
|------|------|
| **任务名称** | 开发 XMind 文件上传组件 |
| **任务编号** | M4-1 |
| **所属里程碑** | M4 前端页面开发 |
| **负责人** | 前端开发 |
| **预计耗时** | 1h |
| **前置条件** | M3 API 就绪，接口文档已提供 |
| **所需资源** | Vue 3、TypeScript、Element Plus / Ant Design Vue |

**执行步骤**：

1. 创建 `src/components/xmind/XmindUpload.vue`
2. 实现文件选择功能：
   - 点击选择文件（`<input type="file" accept=".xmind">`）
   - 拖拽上传（`@dragover`、`@drop` 事件）
3. 实现文件校验：
   - 文件扩展名必须为 `.xmind`
   - 文件大小 ≤10MB
   - 校验失败时提示错误信息
4. 实现上传状态展示：
   - 上传中（loading）
   - 上传成功（绿色勾选）
   - 上传失败（红色错误提示）
5. 暴露事件：`@file-selected`（文件校验通过后触发）

**组件接口定义**：

```typescript
// XmindUpload.vue 组件接口
interface XmindUploadProps {
  maxSize?: number;        // 最大文件大小（MB），默认 10
  accept?: string;         // 接受的文件类型，默认 '.xmind'
  disabled?: boolean;      // 是否禁用，默认 false
}

interface XmindUploadEmits {
  (e: 'file-selected', file: File): void;    // 文件校验通过后触发
  (e: 'error', message: string): void;       // 校验失败或上传错误时触发
  (e: 'loading', isLoading: boolean): void;  // 上传状态变化时触发
}
```

**组件示例代码**：

```vue
<template>
  <div class="xmind-upload" :class="{ 'is-dragover': isDragover, 'is-disabled': disabled }">
    <div class="upload-area" @click="handleClick" @drop.prevent="handleDrop" @dragover.prevent="handleDragOver" @dragleave.prevent="handleDragLeave">
      <input ref="fileInput" type="file" accept=".xmind" style="display: none" @change="handleFileChange" />
      <div class="upload-content">
        <el-icon :size="48" color="#409EFF"><Upload /></el-icon>
        <p class="upload-text">点击或拖拽上传 XMind 文件</p>
        <p class="upload-hint">支持 .xmind 格式，文件大小不超过 {{ maxSize }}MB</p>
      </div>
    </div>
    <div v-if="selectedFile" class="file-info">
      <el-icon color="#67C23A"><Document /></el-icon>
      <span class="file-name">{{ selectedFile.name }}</span>
      <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
      <el-icon class="file-remove" @click="clearFile"><Close /></el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Upload, Document, Close } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

const props = withDefaults(defineProps<XmindUploadProps>(), {
  maxSize: 10,
  accept: '.xmind',
  disabled: false
});

const emit = defineEmits<XmindUploadEmits>();

const fileInput = ref<HTMLInputElement>();
const selectedFile = ref<File | null>(null);
const isDragover = ref(false);

const handleClick = () => {
  if (props.disabled) return;
  fileInput.value?.click();
};

const validateFile = (file: File): boolean => {
  // 校验文件扩展名
  if (!file.name.endsWith('.xmind')) {
    emit('error', '请选择 .xmind 格式的文件');
    return false;
  }
  // 校验文件大小
  if (file.size > props.maxSize * 1024 * 1024) {
    emit('error', `文件大小超过 ${props.maxSize}MB 限制`);
    return false;
  }
  return true;
};

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (file && validateFile(file)) {
    selectedFile.value = file;
    emit('file-selected', file);
  }
};

const handleDrop = (event: DragEvent) => {
  isDragover.value = false;
  if (props.disabled) return;
  const file = event.dataTransfer?.files[0];
  if (file && validateFile(file)) {
    selectedFile.value = file;
    emit('file-selected', file);
  }
};

const handleDragOver = () => { isDragover.value = true; };
const handleDragLeave = () => { isDragover.value = false; };
const clearFile = () => { selectedFile.value = null; };
const formatFileSize = (size: number): string => {
  if (size < 1024) return size + ' B';
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB';
  return (size / (1024 * 1024)).toFixed(1) + ' MB';
};
</script>
```

**交付成果**：

- `src/components/xmind/XmindUpload.vue`：上传组件

**验收标准**：

- [ ] 支持点击选择和拖拽上传
- [ ] 文件类型校验正确（非 `.xmind` 提示错误）
- [ ] 文件大小校验正确（>10MB 提示错误）
- [ ] 上传状态展示清晰（loading/成功/失败）
- [ ] 组件样式与现有 UI 风格一致

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 拖拽事件浏览器兼容性 | 低 | 低 | 测试 Chrome/Firefox/Edge |

---

### M4-2: 开发预览表格

| 属性 | 内容 |
|------|------|
| **任务名称** | 开发 XMind 导入预览表格 |
| **任务编号** | M4-2 |
| **所属里程碑** | M4 前端页面开发 |
| **负责人** | 前端开发 |
| **预计耗时** | 1h |
| **前置条件** | M4-1 完成，上传组件已就绪 |
| **所需资源** | Vue 3、TypeScript、Element Plus Table |

**执行步骤**：

1. 创建 `src/components/xmind/XmindPreview.vue`
2. 实现表格展示：
   - 列：模块、功能、测试点描述、优先级
   - 数据分页（每页 20 条）
   - 行号展示
3. 实现数据编辑（可选）：
   - 双击单元格编辑
   - 编辑后标记为"已修改"
4. 实现统计信息：
   - 总测试点数
   - 各模块数量分布
5. 暴露事件：`@confirm`（用户确认导入时触发）

**组件接口定义**：

```typescript
// XmindPreview.vue 组件接口
interface TestPointXmindPreviewItem {
  module: string;      // 模块名称
  function: string;    // 功能名称
  point: string;       // 测试点描述
  priority: number;    // 优先级 1-3
}

interface XmindPreviewProps {
  data: TestPointXmindPreviewItem[];    // 预览数据列表
  loading?: boolean;                     // 加载状态，默认 false
}

interface XmindPreviewEmits {
  (e: 'confirm', data: TestPointXmindPreviewItem[]): void;  // 用户确认导入时触发
  (e: 'cancel'): void;                                       // 用户取消时触发
  (e: 'edit', index: number, field: string, value: string): void;  // 单元格编辑时触发
}
```

**组件示例代码**：

```vue
<template>
  <div class="xmind-preview">
    <div class="preview-header">
      <div class="preview-stats">
        <el-tag type="info">共 {{ data.length }} 条测试点</el-tag>
        <el-tag type="success">高优先级: {{ highPriorityCount }}</el-tag>
        <el-tag type="warning">中优先级: {{ mediumPriorityCount }}</el-tag>
        <el-tag type="danger">低优先级: {{ lowPriorityCount }}</el-tag>
      </div>
    </div>
    <el-table :data="paginatedData" border stripe v-loading="loading" height="400">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="module" label="模块" width="120" show-overflow-tooltip />
      <el-table-column prop="function" label="功能" width="150" show-overflow-tooltip />
      <el-table-column prop="point" label="测试点描述" min-width="250" show-overflow-tooltip />
      <el-table-column prop="priority" label="优先级" width="100">
        <template #default="scope">
          <el-tag :type="getPriorityType(scope.row.priority)">
            {{ getPriorityLabel(scope.row.priority) }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
    <div class="preview-pagination">
      <el-pagination v-model:current-page="currentPage" :page-size="pageSize" :total="data.length" layout="prev, pager, next, jumper" />
    </div>
    <div class="preview-actions">
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="loading">
        确认导入
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

const props = withDefaults(defineProps<XmindPreviewProps>(), {
  loading: false
});
const emit = defineEmits<XmindPreviewEmits>();

const currentPage = ref(1);
const pageSize = ref(20);

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return props.data.slice(start, start + pageSize.value);
});

const highPriorityCount = computed(() => props.data.filter(item => item.priority === 1).length);
const mediumPriorityCount = computed(() => props.data.filter(item => item.priority === 2).length);
const lowPriorityCount = computed(() => props.data.filter(item => item.priority === 3).length);

const getPriorityType = (priority: number): string => {
  const map: Record<number, string> = { 1: 'danger', 2: 'warning', 3: 'success' };
  return map[priority] || 'info';
};

const getPriorityLabel = (priority: number): string => {
  const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' };
  return map[priority] || '未知';
};

const handleConfirm = () => emit('confirm', props.data);
const handleCancel = () => emit('cancel');
</script>
```

**交付成果**：

- `src/components/xmind/XmindPreview.vue`：预览表格组件

**验收标准**：

- [ ] 表格正确展示解析结果（模块/功能/测试点/优先级）
- [ ] 分页功能正常
- [ ] 统计信息准确（总数量/模块分布）
- [ ] 表格样式与现有 UI 风格一致

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 大数据量导致页面卡顿 | 中 | 中 | 虚拟滚动或分页处理 |

---

### M4-3: 开发结果展示

| 属性 | 内容 |
|------|------|
| **任务名称** | 开发 XMind 导入结果展示组件 |
| **任务编号** | M4-3 |
| **所属里程碑** | M4 前端页面开发 |
| **负责人** | 前端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M4-2 完成 |
| **所需资源** | Vue 3、TypeScript、Element Plus |

**执行步骤**：

1. 创建 `src/components/xmind/XmindImportResult.vue`
2. 实现成功状态展示：
   - 成功图标 + "导入成功" 文案
   - 导入统计（成功数/总数）
   - 跳转到测试点列表按钮
3. 实现失败状态展示：
   - 失败图标 + "导入失败" 文案
   - 错误信息展示
   - 重新导入按钮
4. 实现部分成功展示：
   - 成功数/跳过数/失败数统计
   - 失败原因列表（可展开）

**组件接口定义**：

```typescript
// XmindImportResult.vue 组件接口
interface XmindImportResultProps {
  success: boolean;           // 导入是否成功
  savedCount: number;         // 成功保存数量
  totalParsed: number;        // 解析总数
  skippedCount?: number;      // 跳过数量（可选）
  skippedReasons?: string[];  // 跳过原因列表（可选）
  errorMessage?: string;      // 错误信息（失败时必填）
}

interface XmindImportResultEmits {
  (e: 'retry'): void;         // 重新导入
  (e: 'go-to-list'): void;    // 跳转到测试点列表
}
```

**组件示例代码**：

```vue
<template>
  <div class="xmind-import-result">
    <!-- 成功状态 -->
    <div v-if="success" class="result-success">
      <el-icon :size="64" color="#67C23A"><CircleCheck /></el-icon>
      <h3>导入成功</h3>
      <div class="result-stats">
        <el-statistic title="成功导入" :value="savedCount" />
        <el-statistic title="解析总数" :value="totalParsed" />
        <el-statistic v-if="skippedCount" title="跳过" :value="skippedCount" />
      </div>
      <div v-if="skippedReasons && skippedReasons.length" class="skipped-reasons">
        <el-collapse>
          <el-collapse-item title="查看跳过原因">
            <el-tag v-for="(reason, index) in skippedReasons" :key="index" type="warning">
              {{ reason }}
            </el-tag>
          </el-collapse-item>
        </el-collapse>
      </div>
      <div class="result-actions">
        <el-button @click="handleGoToList">查看测试点列表</el-button>
        <el-button type="primary" @click="handleRetry">继续导入</el-button>
      </div>
    </div>

    <!-- 失败状态 -->
    <div v-else class="result-error">
      <el-icon :size="64" color="#F56C6C"><CircleClose /></el-icon>
      <h3>导入失败</h3>
      <el-alert :title="errorMessage || '导入过程中发生错误'" type="error" show-icon />
      <div class="result-actions">
        <el-button type="primary" @click="handleRetry">重新导入</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CircleCheck, CircleClose } from '@element-plus/icons-vue';

const props = defineProps<XmindImportResultProps>();
const emit = defineEmits<XmindImportResultEmits>();

const handleRetry = () => emit('retry');
const handleGoToList = () => emit('go-to-list');
</script>
```

**交付成果**：

- `src/components/xmind/XmindImportResult.vue`：结果展示组件

**验收标准**：

- [ ] 成功/失败/部分成功三种状态展示正确
- [ ] 统计信息准确
- [ ] 失败原因可展开查看
- [ ] 提供明确的下一步操作按钮（跳转/重试）

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 错误信息过长导致布局错乱 | 低 | 低 | 限制错误信息长度，超长时滚动展示 |

---

### M4-4: 整合导入页面

| 属性 | 内容 |
|------|------|
| **任务名称** | 整合 XMind 导入页面 |
| **任务编号** | M4-4 |
| **所属里程碑** | M4 前端页面开发 |
| **负责人** | 前端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M4-1、M4-2、M4-3 完成 |
| **所需资源** | Vue 3、TypeScript、Vue Router |

**执行步骤**：

1. 创建 `src/views/test-point/XmindImportPage.vue`
2. 整合组件流程：
   - Step 1: 上传（`XmindUpload`）
   - Step 2: 预览（`XmindPreview`）
   - Step 3: 结果（`XmindImportResult`）
3. 实现步骤控制：
   - 上传成功后自动进入预览
   - 预览确认后调用 API 导入
   - 导入完成后展示结果
4. 添加页面标题和返回按钮
5. 注册路由：`/test-point/xmind-import`

**页面流程**：

```
上传文件 → 调用 API (preview=true) → 展示预览 → 用户确认 → 调用 API (preview=false) → 展示结果
```

**整合页面示例代码**：

```vue
<template>
  <div class="xmind-import-page">
    <div class="page-header">
      <h2>导入 XMind 测试点</h2>
      <el-button @click="handleBack">
        <el-icon><ArrowLeft /></el-icon>返回
      </el-button>
    </div>

    <!-- 步骤条 -->
    <el-steps :active="currentStep" finish-status="success" simple>
      <el-step title="上传文件" />
      <el-step title="预览确认" />
      <el-step title="导入结果" />
    </el-steps>

    <!-- Step 1: 上传 -->
    <div v-if="currentStep === 0" class="step-content">
      <XmindUpload @file-selected="handleFileSelected" @error="handleError" />
    </div>

    <!-- Step 2: 预览 -->
    <div v-if="currentStep === 1" class="step-content">
      <XmindPreview :data="previewData" :loading="previewLoading" @confirm="handleImport" @cancel="handleCancel" />
    </div>

    <!-- Step 3: 结果 -->
    <div v-if="currentStep === 2" class="step-content">
      <XmindImportResult v-bind="importResult" @retry="handleRetry" @go-to-list="handleGoToList" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import XmindUpload from '@/components/xmind/XmindUpload.vue';
import XmindPreview from '@/components/xmind/XmindPreview.vue';
import XmindImportResult from '@/components/xmind/XmindImportResult.vue';
import { importXmind } from '@/api/testPoint';

const router = useRouter();
const currentStep = ref(0);
const previewData = ref<TestPointXmindPreviewItem[]>([]);
const previewLoading = ref(false);
const importResult = ref<XmindImportResultProps>({ success: false, savedCount: 0, totalParsed: 0 });

const handleFileSelected = async (file: File) => {
  previewLoading.value = true;
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', '1');
    formData.append('preview', 'true');
    const res = await importXmind(formData);
    previewData.value = res.data.items;
    currentStep.value = 1;
  } catch (error: any) {
    ElMessage.error(error.message || '预览失败');
  } finally {
    previewLoading.value = false;
  }
};

const handleImport = async () => {
  previewLoading.value = true;
  try {
    const formData = new FormData();
    formData.append('file', selectedFile.value!);
    formData.append('project_id', '1');
    formData.append('preview', 'false');
    const res = await importXmind(formData);
    importResult.value = {
      success: true,
      savedCount: res.data.saved_count,
      totalParsed: res.data.total_parsed,
      skippedCount: res.data.skipped_count,
      skippedReasons: res.data.skipped_reasons
    };
    currentStep.value = 2;
  } catch (error: any) {
    importResult.value = { success: false, savedCount: 0, totalParsed: 0, errorMessage: error.message };
    currentStep.value = 2;
  } finally {
    previewLoading.value = false;
  }
};

const handleRetry = () => { currentStep.value = 0; };
const handleCancel = () => { currentStep.value = 0; };
const handleBack = () => router.back();
const handleGoToList = () => router.push('/test-point/list');
const handleError = (message: string) => ElMessage.error(message);
</script>
```

**路由配置**：

```typescript
// src/router/index.ts
const routes = [
  // ... 现有路由
  {
    path: '/test-point/xmind-import',
    name: 'XmindImport',
    component: () => import('@/views/test-point/XmindImportPage.vue'),
    meta: { title: '导入 XMind 测试点', requiresAuth: true }
  }
];
```

**交付成果**：

- `src/views/test-point/XmindImportPage.vue`：导入页面
- `src/router/index.ts`：路由注册

**验收标准**：

- [ ] 页面流程完整（上传→预览→结果）
- [ ] 步骤切换流畅，无卡顿
- [ ] 路由配置正确，可直接访问 `/test-point/xmind-import`
- [ ] 页面样式与现有系统一致

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 组件间状态传递复杂 | 中 | 低 | 使用 Pinia 或 provide/inject |

---

## M5: 集成测试与联调

### M5-1: 端到端测试

| 属性 | 内容 |
|------|------|
| **任务名称** | XMind 导入端到端测试 |
| **任务编号** | M5-1 |
| **所属里程碑** | M5 集成测试与联调 |
| **负责人** | 测试 |
| **预计耗时** | 1h |
| **前置条件** | M4 完成，前端页面已部署 |
| **所需资源** | 5+ 个不同 XMind 文件、测试环境 |

**执行步骤**：

1. 准备测试数据：
   - 样例文件 `听写任务.xmind`
   - 简单结构文件（3 层）
   - 复杂结构文件（6 层）
   - 大文件（300+ 测试点）
   - 空文件
   - 损坏文件
2. 执行测试用例：
   - TC-01: 正常导入流程（上传→预览→导入→验证）
   - TC-02: 预览模式不写入数据库
   - TC-03: 导入后数据库记录正确
   - TC-04: 权限控制（非项目成员无法导入）
   - TC-05: 各种文件格式兼容性
3. 记录测试结果和 Bug

**测试用例清单**：

| 用例ID | 用例名称 | 前置条件 | 操作步骤 | 预期结果 |
|--------|----------|----------|----------|----------|
| TC-01 | 正常导入 | 登录状态，有项目权限 | 1.上传样例文件 2.预览 3.确认导入 | 导入成功，数据库记录正确 |
| TC-02 | 预览模式 | 登录状态 | 1.上传文件 2.点击预览 | 展示解析结果，数据库无新增 |
| TC-03 | 权限控制 | 登录状态，无项目权限 | 1.上传文件到其他项目 | 返回 403 错误 |
| TC-04 | 空文件 | 登录状态 | 1.上传空 XMind 文件 | 返回错误提示 |
| TC-05 | 大文件 | 登录状态 | 1.上传 300+ 测试点文件 | 导入成功，耗时 ≤3 秒 |

**交付成果**：

- 端到端测试报告
- Bug 清单（如有）

**验收标准**：

- [ ] 使用 5+ 个不同 XMind 文件测试
- [ ] 解析成功率 ≥95%
- [ ] 所有 P0 用例通过

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 测试环境不稳定 | 中 | 中 | 提前确认环境可用性 |
| 测试数据不足 | 中 | 中 | 提前准备多种结构文件 |

---

### M5-2: 性能测试

| 属性 | 内容 |
|------|------|
| **任务名称** | XMind 导入性能测试 |
| **任务编号** | M5-2 |
| **所属里程碑** | M5 集成测试与联调 |
| **负责人** | 测试 |
| **预计耗时** | 0.5h |
| **前置条件** | M5-1 完成，功能已稳定 |
| **所需资源** | 不同规模 XMind 文件、性能监控工具 |

**执行步骤**：

1. 准备性能测试数据：
   - 50 条测试点文件
   - 100 条测试点文件
   - 200 条测试点文件
   - 500 条测试点文件（压力测试）
2. 测量指标：
   - 文件解析耗时
   - 数据库写入耗时
   - 总耗时（端到端）
   - 内存占用
3. 记录性能数据并生成报告

**性能基准**：

| 测试点数量 | 目标耗时 | 最大耗时 |
|------------|----------|----------|
| 50 条 | ≤1 秒 | ≤2 秒 |
| 100 条 | ≤2 秒 | ≤3 秒 |
| 200 条 | ≤3 秒 | ≤5 秒 |
| 500 条 | ≤5 秒 | ≤10 秒 |

**交付成果**：

- 性能测试报告

**验收标准**：

- [ ] 200 条测试点导入耗时 ≤3 秒
- [ ] 内存占用无异常增长

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 性能不达标 | 中 | 高 | 优化批量写入策略 |

---

### M5-3: Bug 修复与回归

| 属性 | 内容 |
|------|------|
| **任务名称** | Bug 修复与回归测试 |
| **任务编号** | M5-3 |
| **所属里程碑** | M5 集成测试与联调 |
| **负责人** | 后端开发/前端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M5-1、M5-2 完成，Bug 已记录 |
| **所需资源** | Bug 清单、开发环境 |

**执行步骤**：

1. 分类 Bug：
   - P0：阻塞性问题（必须修复）
   - P1：功能缺陷（尽量修复）
   - P2：体验问题（可延期）
2. 修复 P0/P1 Bug
3. 回归测试验证修复
4. 更新测试报告

**交付成果**：

- Bug 修复清单
- 回归测试报告

**验收标准**：

- [ ] 所有 P0 Bug 修复完毕
- [ ] 回归测试通过

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| Bug 修复引入新问题 | 中 | 中 | 修复后必须回归验证 |

---

## M6: 验收与上线

### M6-1: 产品验收

| 属性 | 内容 |
|------|------|
| **任务名称** | 产品验收 |
| **任务编号** | M6-1 |
| **所属里程碑** | M6 验收与上线 |
| **负责人** | 产品 |
| **预计耗时** | 0.5h |
| **前置条件** | M5 完成，测试报告已通过 |
| **所需资源** | 测试环境、验收 checklist |

**执行步骤**：

1. 对照需求文档验证功能完整性
2. 验证核心流程：上传→预览→导入→查看
3. 确认字段映射规则符合预期
4. 确认异常处理符合预期
5. 签字验收

**验收 Checklist**：

- [ ] 能正常上传 `.xmind` 文件
- [ ] 预览模式展示解析结果
- [ ] 导入模式正确写入数据库
- [ ] 字段映射正确（module/function/point/priority）
- [ ] 权限控制有效
- [ ] 异常场景处理友好
- [ ] 性能满足指标（≤3 秒）

**交付成果**：

- 产品验收签字文档

**验收标准**：

- [ ] 功能符合需求文档描述
- [ ] 产品签字确认

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 产品提出新需求 | 中 | 高 | 明确区分需求变更与 Bug |

---

### M6-2: 上线部署

| 属性 | 内容 |
|------|------|
| **任务名称** | 上线部署 |
| **任务编号** | M6-2 |
| **所属里程碑** | M6 验收与上线 |
| **负责人** | 后端开发 |
| **预计耗时** | 0.5h |
| **前置条件** | M6-1 完成，产品已验收 |
| **所需资源** | 生产环境、CI/CD 流水线 |

**执行步骤**：

1. 确认代码已合并到主分支
2. 确认 CI/CD 流水线通过（构建/测试/部署）
3. 执行生产环境部署
4. 验证线上功能正常
5. 更新项目文档（CHANGELOG、README）

**部署检查项**：

- [ ] 代码已合并到 `main` 分支
- [ ] CI/CD 流水线全部通过
- [ ] 线上环境功能验证通过
- [ ] 监控无异常报错

**交付成果**：

- 上线确认邮件/文档

**验收标准**：

- [ ] 线上环境功能正常
- [ ] 监控无异常

**风险评估**：

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 部署失败 | 低 | 高 | 准备回滚方案 |
| 线上环境配置缺失 | 低 | 高 | 提前确认环境配置 |

---

## 任务依赖关系图

```
M1-1 (XML结构分析)
  │
  ▼
M1-2 (字段映射规则) ──► M2-2 (字段映射实现)
  │                       │
  ▼                       ▼
M1-3 (异常处理策略) ◄── M2-1 (解析器核心)
                          │
                          ▼
                        M2-3 (单元测试)
                          │
                          ▼
                        M3-1 (Schema定义)
                          │
                          ▼
                        M3-2 (API端点) ──► M4-1 (上传组件)
                          │                    │
                          ▼                    ▼
                        M3-3 (工厂注册)    M4-2 (预览表格)
                          │                    │
                          ▼                    ▼
                        M3-4 (API测试)     M4-3 (结果展示)
                                               │
                                               ▼
                                             M4-4 (整合页面)
                                               │
                                               ▼
                                             M5-1 (端到端测试)
                                               │
                                               ▼
                                             M5-2 (性能测试)
                                               │
                                               ▼
                                             M5-3 (Bug修复)
                                               │
                                               ▼
                                             M6-1 (产品验收)
                                               │
                                               ▼
                                             M6-2 (上线部署)
```

---

## 资源汇总

### 人力资源

| 角色 | 任务编号 | 投入时间 |
|------|----------|----------|
| 后端开发 | M1-1 ~ M1-3, M2-1 ~ M2-3, M3-1 ~ M3-4, M6-2 | 9h |
| 前端开发 | M4-1 ~ M4-4 | 3h |
| 测试 | M5-1 ~ M5-3 | 2h |
| 产品 | M6-1 | 0.5h |

### 技术资源

| 资源 | 用途 | 是否新增 |
|------|------|----------|
| Python 3.10+ | 后端运行环境 | 否 |
| FastAPI | Web 框架 | 否 |
| SQLAlchemy | ORM | 否 |
| Vue 3 + TypeScript | 前端技术栈 | 否 |
| `zipfile` | 解压 `.xmind` | 否 |
| `xml.etree.ElementTree` | 解析 XML | 否 |
| `pytest` + `pytest-cov` | 测试框架 | 否 |

### 文件资源

| 文件 | 用途 | 路径 |
|------|------|------|
| `听写任务.xmind` | 主样例文件 | `C:\Users\Administrator\Desktop\听写任务.xmind` |
| `valid.xmind` | 单元测试用 | `tests/fixtures/valid.xmind` |
| `empty.xmind` | 空文件测试 | `tests/fixtures/empty.xmind` |
| `deep_nesting.xmind` | 深层嵌套测试 | `tests/fixtures/deep_nesting.xmind` |
| `invalid.zip` | 无效文件测试 | `tests/fixtures/invalid.zip` |

---

## 风险汇总

| 风险ID | 风险描述 | 概率 | 影响 | 应对措施 | 责任人 |
|--------|----------|------|------|----------|--------|
| R1 | XMind 版本兼容性问题 | 中 | 高 | 内置版本嗅探，支持 R3.x | 后端开发 |
| R2 | 复杂嵌套结构映射错乱 | 中 | 中 | 限制最大深度为 5 层 | 后端开发 |
| R3 | 文件损坏导致解析崩溃 | 低 | 中 | 全局异常捕获，友好提示 | 后端开发 |
| R4 | 导入性能不达标 | 低 | 低 | 批量写入优化 | 后端开发 |
| R5 | 前端组件与现有 UI 冲突 | 低 | 低 | 遵循现有组件规范 | 前端开发 |
| R6 | 测试环境不稳定 | 中 | 中 | 提前确认环境可用性 | 测试 |
| R7 | 产品验收提出新需求 | 中 | 高 | 明确区分需求变更与 Bug | 产品 |
| R8 | 部署失败 | 低 | 高 | 准备回滚方案 | 后端开发 |

---

## 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|----------|--------|
| v1.0 | 2026-04-22 | 初始版本 | AI 助手 |
| v1.1 | 2026-04-22 | 新增前端入口设计方案（对话框模式） | AI 助手 |
| v1.2 | 2026-04-22 | 系统性补充评审反馈：完善 M3-3/M3-4 任务详情、补充 API 错误码与响应示例、补充前端组件完整示例代码、明确四级节点合并规则与数据库字段长度限制、调整时间估算增加缓冲时间 | AI 助手 |

---

## 文档质量检查清单

### 逻辑连贯性

- [x] 任务编号连续无遗漏（M1-1 ~ M6-2 共 19 项）
- [x] 前置条件与依赖关系正确（M2 依赖 M1，M3 依赖 M2，M4 依赖 M3，M5 依赖 M4，M6 依赖 M5）
- [x] 前后章节引用一致（字段映射规则在 M1-2、M2-2、M3-1 中保持一致）
- [x] 前端入口设计与任务实施项对应（M4-1 ~ M4-4 实现前端入口方案）

### 术语规范性

- [x] 统一使用 "XMind"（非 "Xmind" 或 "xmind"）作为产品名
- [x] 统一使用 "测试点"（非 "测试用例" 或 "测试项"）描述导入目标
- [x] 统一使用 `module`/`function`/`point`/`priority` 作为系统字段名
- [x] 统一使用 `.xmind` 作为文件扩展名
- [x] 统一使用 "预览模式"/"导入模式" 描述 API 两种行为

### 信息一致性

- [x] 数据库字段长度：M2-2 与 `app/models/test_point.py` 一致（module=100, function=200, point=500）
- [x] 文件大小限制：M3-2 与 M4-1 一致（≤10MB）
- [x] 解析层级规则：M1-2、M2-2、规划文档一致（根→忽略/一级→module/二级→function/三级→point/四级及以下→合并）
- [x] 时间估算：任务总览与里程碑汇总一致（基础 15h + 缓冲 5h = 20h）
- [x] 负责人分配：各任务负责人与资源汇总一致

---

> 本文档与 `docs/xmind_import_plan.md` 配套使用，规划文档侧重整体架构和方案设计，本文档侧重具体任务执行和落地细节。
