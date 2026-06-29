# 网址驱动快速测试 Spec

## Why
当前平台从"想测试一个网站"到"测试真正执行"需 7 步操作、30+ 表单字段、2 次表格交互，且被测 URL 硬编码在项目层（`web_env_configs.test.url`），需求文件/UI 原型/测试点/用例全部前置依赖。市场先进平台（Octomind Auto-discovery、QA Use、TestNeo）已实现"输入 URL 即可自动探索页面、生成用例、执行并出报告"的闭环。本 spec 聚焦构建一个端到端"网址驱动快速测试"能力，让用户仅需提供项目网址（可选自然语言描述与登录凭据）即可在 5 分钟内拿到首份测试报告，补齐 `intelligent-testing-platform-v2` 未覆盖的"URL 自动建项"与"一键任务编排"两个核心缺口。

## 技术选型

| 能力 | 选型 | 理由 |
|------|------|------|
| 浏览器自动化 | Playwright（复用 `app/utils/browser_controller_base.py` 的 `BrowserControllerV2`） | 项目已集成，支持 Accessibility Tree、headless、自动登录 |
| 页面流爬取 | Playwright + Accessibility Tree + 链接发现 | 无需引入新依赖；Accessibility Tree 比 DOM 解析更稳定 |
| DOM 快照 | `page.accessibility.snapshot()` + 可交互元素提取 | 复用 `intelligent-testing-platform-v2` 已设计但未落地的 `DOMSnapshot` 数据模型 |
| AI 解析/生成 | DeepSeek（`deepseek-v4-flash`，复用 `app/ai/`） | 项目主力模型，已有 Fallback 降级 |
| 缓存 | Redis（复用现有连接） | DOM 快照与页面流缓存，避免重复爬取 |
| 任务编排 | 复用 `TestTask` + Pipeline + `test_execution_engine_v2` | 不新造执行引擎，沿用既有能力 |
| 实时进度 | WebSocket（复用 `app/services/push_service.py`） | 已有推送基础设施 |
| 前端 | Vue3 + Element Plus + Pinia（复用 `src/utils/websocket.ts`） | 与现有技术栈一致 |

## 架构设计

```
用户输入网址(+可选描述/凭据)
        │
        ▼
┌─────────────────────────────────────────────┐
│ QuickLauncher 编排入口                       │
│  app/services/url_driven/quick_launcher.py   │
└─────────────────────────────────────────────┘
        │
        ├─① SiteExplorer 站点探索引擎
        │     app/services/url_driven/site_explorer.py
        │     · 登录检测 + 自动登录（复用 login_mixin）
        │     · DOM 快照采集（Accessibility Tree）
        │     · 页面流发现（同源链接 BFS，深度≤3，黑名单过滤）
        │     · Redis 缓存（key=url sha256，TTL 可配）
        │
        ├─② AutoProjectBuilder URL 自动建项
        │     app/services/url_driven/auto_project_builder.py
        │     · 从 URL 推导项目名（域名 + 时间戳）
        │     · 自动填充 web_env_configs.test/staging/prod
        │     · 标记 project.source = "url_quick_test"
        │
        ├─③ AutoCaseGenerator 页面结构驱动用例生成
        │     app/services/url_driven/auto_case_generator.py
        │     · 从页面流推导测试点（核心入口：登录/搜索/表单/导航）
        │     · AI 基于真实 DOM 元素生成用例（注入元素清单，禁编造）
        │     · 复用 element_verified_ratio 字段做元素锚定校验
        │
        ├─④ TaskAssembler 一键任务编排
        │     app/services/url_driven/task_assembler.py
        │     · 自动创建 TestTask + 选全部生成用例
        │     · 选 execution_mode=smart
        │     · 触发 test_execution_engine_v2 执行
        │
        └─⑤ 报告与进度推送
              · WebSocket 实时推送阶段进度
              · 复用 report_service 生成报告
              · 失败用例自动记录 Bug（复用 dogfood 机制）
```

## What Changes
- **新增站点探索引擎** — URL → 自动登录 → DOM 快照 → 页面流 BFS 发现，产出 `site_map` 产物
- **新增 URL 自动建项** — 从网址自动创建 Project 并填充三套环境配置，标记来源
- **新增页面结构驱动用例生成** — 基于真实 DOM 元素推导测试点并生成用例，复用已落地的 `element_verified_ratio` 字段做锚定校验
- **新增一键任务编排** — 自动装配 TestTask、选例、选执行模式并启动，消除手动 7 步
- **新增快速测试 API** — `POST /api/v1/quick-test/launch` 一键启动，WebSocket 推送进度
- **新增前端快速测试页** — URL 输入 + 可选描述/凭据 + 一键启动 + 进度区 + 结果区
- **复用**：TestCase 4 个验证字段（已落地）、browser_controller、push_service、TestTask、Pipeline、report_service

## Impact
- Affected specs:
  - `intelligent-testing-platform-v2` — 复用其 NL2Test/DOM 快照设计思路与已落地的 TestCase 验证字段；本 spec 不依赖其未落地的 code_grounding 模块，独立实现精简版站点探索
  - `dogfood-self-testing` / `dogfood-requirement-driven-self-test` — 复用其浏览器缺陷捕获与 Bug 自动记录机制
  - `playwright-mcp-integration` — 站点探索可选择性复用 MCP 能力
- Affected code:
  - `app/services/url_driven/__init__.py` — **新建**：子包入口
  - `app/services/url_driven/quick_launcher.py` — **新建**：编排入口
  - `app/services/url_driven/site_explorer.py` — **新建**：站点探索引擎
  - `app/services/url_driven/auto_project_builder.py` — **新建**：URL 自动建项
  - `app/services/url_driven/auto_case_generator.py` — **新建**：页面驱动用例生成
  - `app/services/url_driven/task_assembler.py` — **新建**：一键任务编排
  - `app/api/v1/endpoints/quick_test.py` — **新建**：快速测试 API
  - `app/schemas/quick_test.py` — **新建**：请求/响应 schema
  - `app/models/project.py` — 新增 `source` 字段（标识 url_quick_test 来源）
  - `app/core/config.py` — 新增 `URL_QUICK_TEST_MAX_DEPTH`、`URL_QUICK_TEST_PAGE_TIMEOUT`、`URL_QUICK_TEST_CACHE_TTL`
  - `app/main.py` — 注册 quick_test 路由
  - `src/views/quick-test/QuickTest.vue` — **新建**：快速测试页面
  - `src/api/quickTest.ts` — **新建**：前端 API 封装
  - `src/router/routes.ts` — 新增 `/quick-test` 路由
  - `src/layouts/MainLayout.vue` — 侧边栏新增"快速测试"菜单项

## 预期效果
- 用户操作步骤：7 步 / 30+ 字段 → **1 步（输入网址）**
- 首次出报告耗时：**≤ 5 分钟**（站点探索 ≤90s + 用例生成 ≤120s + 执行 ≤90s）
- 生成的用例可执行率：**> 70%**（基于真实 DOM 元素，禁编造）
- 页面流覆盖：单次探索 ≥1 个核心入口页面（登录/搜索/表单/导航之一）

## 资源需求
- 后端工程师 ×1：站点探索 + 自动建项 + 用例生成 + 任务编排（约 2.5 周）
- 前端工程师 ×1：快速测试页 + WebSocket 进度 + 结果展示（约 1 周）
- 测试：单元测试 + 端到端验证（约 0.5 周，与开发并行收尾）
- 基础设施：无新增（复用现有 MySQL/Redis/Playwright）
- 预计总工期：**3 周**

## 用户体验流程

### 入口设计（用户在哪儿操作）
三重入口，确保用户在任何位置都能一键触达：
1. **首页醒目卡片**（主入口）：登录后首页顶部置顶一张"快速测试"卡片，含闪电图标 + 文案"输入网址，5分钟出测试报告" + 大输入框 + "开始测试"按钮。用户无需导航，登录即可见、即可输入。
2. **侧边栏菜单**：侧边栏第一个菜单项"⚡ 快速测试"（闪电图标），点击进入 `/quick-test` 专属页面，提供完整输入+高级选项+历史记录。
3. **全局快捷入口**：顶部导航栏右侧"⚡"图标，点击弹出快速输入框（类似全局搜索），随时可用。

### 操作步骤（用户怎么操作）— 最短路径
以首页卡片为例（3 步完成）：
1. 用户登录后，首页顶部看到"快速测试"卡片
2. 在输入框粘贴被测网址（如 `https://demo.playwright.dev/todomvc`）
3. 点击"开始测试"按钮（或按回车）

**可选高级选项**（折叠区，默认收起）：
- 自然语言描述（如"重点测登录和搜索功能"）→ 聚焦测试范围
- 登录凭据（用户名 + 密码）→ 用于探索需登录站点
- 浏览器选项（headless 开关、viewport 尺寸）→ 高级用户可调

提交后页面**不刷新**，原地切换到"进度视图"。

### 进度视图（提交后看到什么）
4 个阶段进度条，实时刷新（WebSocket 推送）：

| 阶段 | 图标 | 进行中显示 | 完成后显示 |
|------|------|-----------|-----------|
| 1 站点探索 | 🔍 | "正在访问页面..." + 旋转动画 | "发现 3 个页面，识别到登录/搜索/表单入口" |
| 2 用例生成 | ✨ | "正在生成用例..." + 进度百分比 | "已生成 12 条用例" |
| 3 任务执行 | ▶️ | 实时用例执行列表（✓通过/✗失败/⏳进行中） | "执行完成：8通过 4失败" |
| 4 报告生成 | 📊 | "正在生成报告..." | "报告已就绪" |

- 每阶段显示预计剩余时间
- 失败用例实时红色高亮，可点"查看详情"看中间产物（探索到的页面截图、生成的用例预览）
- 用户可随时点"暂停"或"取消"
- 顶部显示总进度条 + 已用时长

### 结果视图（最终输出什么）
完成后自动展示结果摘要，包含 5 个区块：

**① 报告摘要卡片**（顶部置顶）
- 通过率环形图（如 67%）
- 用例总数 / 通过数 / 失败数 / 总耗时
- 缺陷严重度分布（P0/P1/P2/P3 计数，P0 红色醒目）

**② 用例列表**（主体）
每条用例卡片含：
- 标题 + 执行状态标签（通过✓绿 / 失败✗红 / 待确认⚠橙）
- 步骤列表（自然语言描述，每步标注元素验证状态）
- 预期结果 vs 实际结果
- 失败用例：失败截图（可点开放大）+ 错误原因
- 操作按钮："重新执行" / "查看详情"（跳用例详情页）

**③ 缺陷清单**（自动从失败用例提取）
- 按严重度排序，P0 置顶
- 每条含：缺陷描述、复现步骤、截图、关联用例
- 可一键"创建 Bug"（复用 dogfood Bug 自动记录机制）

**④ 生成资产**（本次产出沉淀）
- 自动创建的项目名（如 `demo.playwright.dev_20260626`），含三套环境配置
- 已存入项目的用例数（如"12 条用例已保存到项目"）
- 探索到的页面清单（可点开看页面截图和元素清单）

**⑤ 操作按钮区**
- "查看完整报告"→ 跳转报告中心详情页
- "再次执行"→ 用相同配置重新跑
- "编辑用例"→ 跳转用例编辑页（修改后可重新执行）
- "下载报告"→ 导出 PDF/HTML
- "保存到其他项目"→ 将用例复制到指定项目

### 失败与降级提示
- 站点探索失败：红色提示"无法访问该网址，请检查 URL 或网络"，允许"重试"或"换一个网址"
- 登录失败：黄色提示"登录凭据无效，是否以未登录状态继续探索？" + 两个按钮（继续/重新输入凭据）
- AI 生成失败：黄色提示"AI 服务暂时不可用，已降级生成基础登录用例"
- 单用例执行超时：该用例标记失败，继续执行下一条，不整体中断；顶部显示"2 条用例超时"

### 历史记录（侧边栏菜单页特有）
`/quick-test` 页面除输入区外，还显示"最近快速测试"列表（最近 10 次）：
- 每条含：网址、执行时间、通过率、用例数、状态
- 点击可重新查看结果视图，或"再次执行"

## ADDED Requirements

### Requirement: 站点探索引擎
系统 SHALL 接收一个网址，自动完成登录检测、DOM 快照采集、同源页面流 BFS 发现，产出结构化 `site_map`，作为后续建项与用例生成的确定性输入。

#### 数据模型
```python
@dataclass
class PageSnapshot:
    url: str                       # 页面 URL
    title: str                     # 页面标题
    elements: List[Dict[str, Any]]  # 可交互元素（role/name/locator/css_selector）
    forms: List[Dict[str, Any]]    # 表单结构
    navigation: List[Dict[str, str]]  # 同源导航链接 {text, href}
    is_login_page: bool            # 是否登录页
    screenshot_path: Optional[str] # 截图路径
    captured_at: str               # ISO8601 时间戳

@dataclass
class SiteMap:
    entry_url: str
    pages: List[PageSnapshot]      # 探索到的页面列表
    max_depth_reached: int
    explored_count: int
    skipped_count: int
    cache_key: str                 # sha256(entry_url)
```

#### 实现约束
- 复用 `BrowserControllerV2` 启动 headless 浏览器
- 登录采用轻量 CSS 选择器路径 `_login_with_selectors`（定位 `input[type=password]`、用户名输入框、提交按钮），**不依赖 AI vision_model**，无 AI key 也可登录；登录失败降级为仅探索登录页
- `_detect_login_page(page)` 签名偏离 spec 原设计 `(snapshot)`：改用 `page.evaluate` JS 检测 `input[type="password"]` + 登录按钮，因 Accessibility Tree 的 textbox 角色无法区分 password 类型（用户已确认接受此改进）
- 登录失败后**仅保留登录页快照，不进入 BFS**（严格按 spec Scenario）；公开站点（非登录页）正常 BFS
- 页面流 BFS：深度 ≤ `URL_QUICK_TEST_MAX_DEPTH`（默认 3），同源限制，黑名单过滤（`/logout`、`/delete` 等危险路径）
- 单页加载超时 `URL_QUICK_TEST_PAGE_TIMEOUT`（默认 30s），超时跳过该页
- Redis 缓存 `SiteMap`，TTL `URL_QUICK_TEST_CACHE_TTL`（默认 86400s）
- IO/网络/解析强制异常捕获，单页失败不阻断整体探索

#### Scenario: 探索公开站点
- **GIVEN** 用户提交 URL `https://example.com`，无登录凭据
- **WHEN** SiteExplorer 探索
- **THEN** 采集首页 DOM 快照（Accessibility Tree 可交互元素）
- **AND** BFS 发现同源链接，深度 ≤3，过滤黑名单路径
- **AND** 输出 `SiteMap`，包含 ≥1 个 `PageSnapshot`
- **AND** 整个探索过程 ≤90 秒

#### Scenario: 探索需登录站点
- **GIVEN** 用户提交 URL 与登录凭据 {username, password}
- **WHEN** SiteExplorer 检测到登录页（存在 password 输入框 + 登录按钮）
- **THEN** 自动填写凭据并登录
- **AND** 登录成功后继续探索登录后页面
- **AND** 登录失败时降级为仅探索登录页，记录警告

#### Scenario: 缓存命中
- **GIVEN** 同一 URL 的 SiteMap 在 TTL 内已缓存
- **WHEN** 再次发起探索
- **THEN** 直接返回缓存的 SiteMap，不重复访问页面

#### Scenario: 单页超时不阻断
- **GIVEN** 某页面加载超过 30s
- **WHEN** 超时触发
- **THEN** 跳过该页，记录 `skipped_count++`，继续探索其他页面

### Requirement: URL 自动建项
系统 SHALL 从用户提供的网址自动创建 Project 并填充三套环境配置，无需用户手动填写表单。

#### 实现约束
- 项目名推导：`{域名}_{YYYYMMDD}`，去重处理（追加序号）
- `web_env_configs.test/staging/prod` 三套均填入该 URL（用户可在后续修改 staging/prod）
- Project 新增 `source` 字段，值为 `"url_quick_test"`，用于区分传统手动建项
- 创建后自动触发站点探索（异步，通过 WebSocket 推送进度）
- 单文件 ≤350 行，参数化查询，禁硬编码密钥

#### Scenario: 自动建项成功
- **GIVEN** 用户提交 URL `https://shop.example.com`
- **WHEN** AutoProjectBuilder 执行
- **THEN** 创建 Project，名称为 `shop.example.com_20260626`（重名则追加 `_2`）
- **AND** 三套环境 URL 均填入 `https://shop.example.com`
- **AND** `project.source = "url_quick_test"`
- **AND** 返回 `project_id`，触发异步站点探索

#### Scenario: URL 非法
- **GIVEN** 用户提交 URL `not-a-url`
- **WHEN** 校验失败
- **THEN** 返回 422，提示"URL 格式非法"，不创建项目

### Requirement: 页面结构驱动用例生成
系统 SHALL 基于站点探索产出的真实 DOM 元素，自动推导测试点并生成可执行用例，禁止编造不存在的元素。

#### 实现约束
- 测试点推导规则（从 PageSnapshot 元素识别核心入口）：
  - 存在 password 输入框 + 登录按钮 → 登录测试点
  - 存在 search 输入框 → 搜索测试点
  - 存在 form → 表单提交测试点
  - 存在导航链接 → 导航跳转测试点
- AI 生成 Prompt 注入"被测页面实际元素"清单（Markdown 表格），明确禁止编造
- 复用已落地的 `TestCase.element_verified_ratio` 字段做元素锚定校验
- 无匹配元素时用例标记 `element_verified_ratio = 0.0`，不阻断生成
- 每个测试点生成 3-5 条用例（正向 + 边界 + 异常）

#### Scenario: 基于真实元素生成
- **GIVEN** SiteMap 包含登录页，元素清单含"用户名输入框/密码输入框/登录按钮"
- **WHEN** AutoCaseGenerator 生成
- **THEN** 生成登录用例，步骤中 target_element 全部来自元素清单
- **AND** `element_verified_ratio > 0.8`

#### Scenario: 元素不存在标记
- **GIVEN** AI 生成的步骤引用了元素清单中不存在的"提交订单按钮"
- **WHEN** 锚定校验
- **THEN** 该步骤 `element_verified = false`
- **AND** 用例 `element_verified_ratio` 降低，但不阻断生成

### Requirement: 一键任务编排与启动
系统 SHALL 自动创建 TestTask、选全部生成用例、选 smart 执行模式并启动执行，消除手动 7 步。

#### 实现约束
- 复用 `app/api/v1/endpoints/test_task.py` 的 `create_test_task` 与 `start_test_task` 逻辑（抽取为可内部调用的服务方法）
- 任务名：`{项目名}_快速测试_{时间戳}`
- `case_ids` = 全部生成用例 ID
- `execution_mode = "smart"`
- 启动后通过 WebSocket 推送执行进度
- 复用 `test_execution_engine_v2` 执行
- 执行完成复用 `report_service` 生成报告

#### Scenario: 一键启动
- **GIVEN** 用例生成完成，共 8 条用例
- **WHEN** TaskAssembler 执行
- **THEN** 创建 TestTask，关联 8 条用例，execution_mode=smart
- **AND** 立即触发执行
- **AND** 返回 task_id，前端可订阅 WebSocket 进度

### Requirement: 快速测试 API 端点
系统 SHALL 提供 `POST /api/v1/quick-test/launch` 端点，接收 URL + 可选描述/凭据，返回 task_id。

#### Schema
```python
class QuickTestLaunchRequest(BaseModel):
    url: HttpUrl
    description: Optional[str] = None   # 可选自然语言描述，聚焦测试范围
    credentials: Optional[Dict[str, str]] = None  # {username, password}

class QuickTestLaunchResponse(BaseModel):
    task_id: int
    project_id: int
    estimated_duration_sec: int
    websocket_channel: str              # WebSocket 订阅通道
```

#### Scenario: 启动快速测试
- **GIVEN** 用户提交 `{url, description?, credentials?}`
- **WHEN** 调用 `POST /api/v1/quick-test/launch`
- **THEN** 自动建项 → 探索 → 生成 → 编排 → 启动
- **AND** 返回 task_id 与 websocket_channel
- **AND** 全程 ≤5 分钟产出首份报告

#### Scenario: 进度查询
- **GIVEN** 任务已启动
- **WHEN** 订阅 websocket_channel
- **THEN** 实时推送阶段：站点探索中→用例生成中→执行中→完成

#### 实现约束（Phase 5 已落地，sub-agent 报告 3 处偏离 spec，已确认接受）
- **stage 命名偏离**：spec Scenario 文案为"站点探索中→用例生成中→执行中→完成"4 段；后端 `QuickLauncher` 实际推送 4 阶段为 `site_exploring`(10/30) → `case_generating`(40/60) → `task_assembling`(70/90) → `completed`(100)。原因：`TaskAssembler` 启动执行引擎后，编排链路即视为完成；后续用例执行进度由执行引擎通过既有 `task:{task_id}` 通道推送，前端"任务执行/报告生成"两阶段由执行引擎进度合成，不在 quick_test 通道重复实现。
- **URL 非法状态码偏离**：spec 隐含 422，Pydantic `HttpUrl` 校验失败时项目全局 `request_validation_exception_handler` 统一转 400；端点内 `ValueError`（业务校验失败）显式返回 422。
- **限流实现方式偏离**：spec 文案"复用 RateLimitMiddleware"指算法复用，但 `RateLimitMiddleware` 为全局 IP 级（1000/5000 次/分钟），无法满足 launch 端点单用户细粒度限流，故抽取其内存算法（deque + 时间窗口清理）实现独立的 `_PerUserRateLimiter` 类，按 `user_id` 计数，单用户 10 次/分钟。
- **鉴权复用 `auth_deps.get_current_user`**：launch 与 status 端点均挂载 `Depends(get_current_user)`，status 端点追加 `executor_id = current_user.id` 过滤防越权。
- **stage 推断兜底**：`_derive_stage(task)` 根据 `TaskStatus` + `progress` 推断当前阶段，`progress=None` 兜底为 0，未知 `status` label 兜底为"未知"。
- 28 单测全通过，覆盖率 100%。

### Requirement: 前端快速测试入口与三重视图
系统 SHALL 提供首页卡片 + 侧边栏菜单页 + 全局快捷入口三重入口，并实现"输入视图 → 进度视图 → 结果视图"三态切换，覆盖完整用户体验流程（详见上文"用户体验流程"章节）。

#### 组件拆分（单文件 ≤350 行）
- `src/views/quick-test/QuickTest.vue` — 容器组件，三态切换路由
- `src/views/quick-test/components/QuickInputCard.vue` — 首页卡片 + 输入区（URL/描述/凭据折叠）
- `src/views/quick-test/components/QuickProgressView.vue` — 进度视图（4 阶段进度条 + 实时用例列表）
- `src/views/quick-test/components/QuickResultView.vue` — 结果视图（5 区块：摘要/用例/缺陷/资产/操作）
- `src/views/quick-test/components/CaseCard.vue` — 单条用例卡片（可复用于进度与结果视图）
- `src/views/quick-test/components/QuickHistoryList.vue` — 历史记录列表（侧边栏页特有）
- `src/components/QuickTestGlobalEntry.vue` — 全局快捷入口图标 + 弹出输入框
- `src/api/quickTest.ts` — API 封装（launch/status/history，TS 严格模式，禁 any）

#### 三态切换状态机
```
IDLE（输入视图） ──提交URL──> RUNNING（进度视图）
                                  │
                                  ├─成功─> COMPLETED（结果视图）
                                  ├─失败─> FAILED（结果视图+降级提示）
                                  └─取消─> IDLE（回到输入）
```
- 视图切换不刷新页面，使用 `v-if` 按状态渲染
- 状态持久化到 Pinia store，刷新页面后可恢复到当前阶段

#### UI 规格
- **首页卡片**：登录后首页顶部置顶，闪电图标 + 文案"输入网址，5分钟出测试报告" + URL 大输入框 + "开始测试"按钮（回车可触发）
- **输入区**：URL 输入框（必填，URL 格式校验）+ "高级选项"折叠区（描述/凭据/浏览器选项）
- **进度区**：4 阶段进度条（站点探索/用例生成/任务执行/报告生成），每阶段图标+状态+预计剩余时间；执行阶段实时展示用例卡片列表（✓通过/✗失败/⏳进行中）；顶部总进度条+已用时长；"暂停"/"取消"按钮
- **结果区**：5 区块布局（报告摘要卡片 / 用例列表 / 缺陷清单 / 生成资产 / 操作按钮区），详见"用户体验流程-结果视图"
- **失败用例**：红色高亮，失败截图可点开放大，含错误原因与复现步骤
- **响应式**：适配桌面（≥1280px）与平板（≥768px），移动端暂不支持

#### WebSocket 订阅
- 订阅通道 `quick_test:{task_id}`（复用 `src/utils/websocket.ts`）
- 推送消息 schema：`{stage: "explore|generate|execute|report", status: "running|done|failed", progress: 0-100, detail: {...}, cases?: [...]}`
- 断线自动重连，重连后拉取当前进度状态补齐

#### 实现约束（Phase 6 已落地，sub-agent 报告 5 处偏离 spec，已确认接受）
- **stage→中文标签映射**：spec UX 章节描述 4 阶段为"站点探索/用例生成/任务执行/报告生成"，但后端实际推送 `site_exploring/case_generating/task_assembling/completed`。前端在 `src/views/quick-test/quickTestTypes.ts` 的 `STAGE_LABELS` 映射表把后端 `task_assembling` 合并映射为"任务执行"（spec 的"任务执行+报告生成"两阶段合并展示），`completed` 映射为"报告生成"，与 Phase 5 后端偏离一致。
- **首页入口位置**：spec 文案"首页顶部置顶"由于项目无独立 Dashboard 页（`/home` redirect 到 `/home/project`），最小改动方案在 `ProjectList.vue` 顶部插入「⚡ 快速测试」el-card 卡片，不破坏现有项目列表卡片结构。
- **Pinia 持久化方案**：spec 文案"状态持久化到 Pinia store"，但项目未安装 `pinia-plugin-persistedstate`，沿用项目现有风格（与 token 一致）手动 `localStorage` 实现持久化，封装在 `store/quickTest.ts` 内的 `persist()/restore()` 方法 + `safeGetItem/safeSetItem/safeRemoveItem` 防御。
- **WebSocket 通道接入方式**：现有 `wsClient` 单例硬编码 `/ws/task/{taskId}`，无法满足自定义通道需求。复用 `connectWebSocket(path, options)` 函数式 API（URL 构造 `${protocol}//${host}/ws${path}`，token 走子协议），在 `useQuickTestFlow.ts` composable 内手写指数退避重连（min(1000*2^attempts, 30000)，max 8 次后停止），重连后调 `store.refreshStatus()` 拉取当前进度补齐。
- **历史记录 API 降级**：spec 文案"最近 10 次快速测试记录"对应后端无专门历史 API。`QuickHistoryList.vue` 降级方案：`onMounted` 时若 `store.taskId` 存在则调 `quickTestApi.getStatus(taskId)` 拉取当前任务状态展示为单条记录，并在卡片头部常驻提示"完整历史记录功能即将上线"。后端落地历史 API 后此降级自动失效。
- **下载报告 / 保存到其他项目 API 降级**：spec 操作按钮区"下载报告(PDF/HTML)"与"保存到其他项目"对应：① 下载报告先按 `test_task_id` 查报告（`reportApi.getReports`），再调真实 `exportReportPDF/exportReportHTML`，任一环节失败均 `ElMessage.info('报告下载入口即将上线')`；② 保存到其他项目调真实 `POST /api/v1/projects/{targetId}/import-task/{taskId}`，接口不存在/失败时 `ElMessage.info('保存到其他项目入口即将上线')`。
- **Bug 创建路由降级**：缺陷清单"创建 Bug"按钮跳转 Bug 创建页路由 `/home/bug/create?case_id=xxx`，路由未落地时 `ElMessage.info('Bug 创建入口即将上线')`，不阻断渲染。
- 7 文件 126 用例 Vitest 全通过，`npm run typecheck` 0 错。

#### Scenario: 首页卡片一键启动
- **GIVEN** 用户已登录，在首页看到"快速测试"卡片
- **WHEN** 在输入框粘贴 `https://demo.playwright.dev/todomvc` 并点击"开始测试"
- **THEN** 调用 `POST /api/v1/quick-test/launch`，返回 task_id 与 websocket_channel
- **AND** 首页卡片原地切换为"进度视图"
- **AND** WebSocket 订阅 `quick_test:{task_id}`，4 阶段进度条实时刷新
- **AND** 全程页面不刷新

#### Scenario: 进度实时刷新
- **GIVEN** 任务运行中，执行阶段
- **WHEN** WebSocket 推送 `{stage:"execute", status:"running", cases:[{id:1, status:"passed"}, {id:2, status:"running"}]}`
- **THEN** 用例列表实时更新，用例1显示✓通过，用例2显示⏳进行中
- **AND** 失败用例红色高亮，可点"查看详情"

#### Scenario: 完成后展示结果
- **GIVEN** 任务执行完成
- **WHEN** WebSocket 推送 `{stage:"report", status:"done"}`
- **THEN** 自动切换到"结果视图"
- **AND** 顶部展示报告摘要卡片（通过率环形图、总数/通过/失败/耗时、缺陷严重度分布）
- **AND** 主体展示用例列表（含状态标签、步骤、预期vs实际、失败截图）
- **AND** 展示缺陷清单（P0 置顶）+ 生成资产 + 操作按钮区
- **AND** 用户可点"下载报告"导出 PDF/HTML，或"再次执行"重跑

#### Scenario: 失败降级提示
- **GIVEN** 站点探索阶段失败（网址无法访问）
- **WHEN** WebSocket 推送 `{stage:"explore", status:"failed", detail:"无法访问该网址"}`
- **THEN** 进度视图红色提示"无法访问该网址，请检查 URL 或网络"
- **AND** 展示"重试"和"换一个网址"两个按钮
- **AND** 不进入后续阶段

#### Scenario: 历史记录
- **GIVEN** 用户进入 `/quick-test` 侧边栏菜单页
- **WHEN** 页面加载
- **THEN** 除输入区外，下方展示"最近快速测试"列表（最近 10 次）
- **AND** 每条含网址、执行时间、通过率、用例数、状态
- **AND** 点击可重新查看结果视图，或"再次执行"

#### Scenario: 页面刷新恢复
- **GIVEN** 用户在进度视图刷新页面
- **WHEN** 页面重新加载
- **THEN** 从 Pinia store 恢复 task_id，重新订阅 WebSocket 拉取当前进度
- **AND** 恢复到刷新前的阶段状态

### 实现约束（Phase 7 端到端验证已落地，发现并修复 5 处 BUG，已确认接受）

端到端验证目标 URL：`https://demo.playwright.dev/todomvc`，验证结果 task_id=230（project_id=12739），完整跑通：建项 → 探索（1 page, 4 elements）→ 生成（5 cases, TC-12739-0001~0005）→ 编排（task_id=230）→ 执行（5 TestResult 持久化, all FAILED）→ 状态持久化（status=FAILED(3), start/end_time 已设置）。总耗时 ~38s（远低于 ≤5 分钟 SLA）。

**BUG 1：任务状态未持久化到数据库（Session 隔离）**
- **现象**：task 223/224/225 数据库 status=1 (RUNNING)、end_time=None，但日志显示"测试任务执行完成"
- **根因**：`TaskAssembler._start_task` 通过 `asyncio.create_task` 创建后台任务时复用了 request-scoped session。`get_db()` 在请求结束时关闭 session，后台任务的 commit 静默失败
- **对比证据**：`app/api/v1/endpoints/test_task.py` 原始 `start_test_task` 在请求内 `await executor.execute_test_task(...)`，session 保持活跃；`task_assembler` 的差异是使用 `asyncio.create_task` 后台执行，导致 session 被提前关闭
- **修复**：`_run_executor_safely` 从 `@staticmethod` 改为实例方法，内部通过 `PrimarySessionLocal()` 创建独立 session 供执行引擎使用；异常兜底将任务置 FAILED；`finally` 块确保 session 关闭
- **验证**：task 230 正确持久化 status=3 (FAILED), start_time/end_time 已设置, 5 TestResult 已持久化

**BUG 2：AI 返回空内容（max_tokens 不足）**
- **现象**：`AI 返回空内容，降级处理` → `AI 生成全部失败，降级为仅生成登录用例` → `降级后仍无用例可生成`
- **根因**：`AutoCaseGenerator._call_ai` 硬编码 `max_tokens=2048`。DeepSeek v4-flash 是推理模型，先消耗 `reasoning_tokens` 再产出 `content`，2048 不足以同时容纳推理与用例 JSON 输出
- **验证**：直接调用 DeepSeek API 确认可用，检查响应结构发现 `reasoning_content` 字段，证实推理模型特性
- **修复**：`max_tokens` 从硬编码 `2048` 改为 `settings.AI_MAX_TOKENS`（.env 配置为 4096）
- **验证**：task 230 成功生成 5 个用例（TC-12739-0001~0005）

**BUG 3：SiteMap 缓存命中空 SiteMap（缓存污染）**
- **现象**：`SiteMap 缓存命中，直接返回` + SiteMap 为空 → 0 用例生成
- **根因**：前一次失败的探索将空 SiteMap 存入 Redis 缓存（`sitemap:{sha256(url)}`），后续 launch 命中空缓存直接返回
- **修复**：清除 Redis `sitemap:*` 缓存后重新探索
- **运维约束**：每次重新运行端到端验证前需清除 Redis sitemap 缓存（脚本：`redis.from_url(...).delete('sitemap:...')`）

**BUG 4：Playwright 1.58 兼容性（上一轮修复）**
- **现象**：`page.accessibility.snapshot` API 已移除
- **根因**：Playwright 1.58 移除了 `page.accessibility.snapshot`，替代方案 `page.locator("body").aria_snapshot()` 返回 YAML 字符串（非 dict）
- **修复**：`_snapshot_mixin.py` 改用 `page.locator("body").aria_snapshot()` + 自研 YAML 解析器解析 `- role "name" [key=value]` 格式
- **验证**：235 单元测试全通过

**BUG 5：Windows 事件循环 + TestExecutionResult 属性（上一轮修复）**
- **现象**：Playwright 子进程在 Windows SelectorEventLoop 下报错；`TestExecutionResult.actual_result` 属性不存在
- **根因**：① Playwright 需要 ProactorEventLoop 支持 subprocess；② `TestExecutionResult` dataclass 有 `error_message` 属性而非 `actual_result`
- **修复**：① `app/main.py` 设置 `WindowsProactorEventLoopPolicy`；② 替换 `actual_result` 为 `error_message`

**BUG 6：WebSocket 403 Forbidden（端点缺失 + 鉴权方式不匹配 + 路径不匹配）**
- **现象**：前端连 `ws://127.0.0.1:3000/ws/quick-test/232`，后端返回 403，6 次重连全失败
- **根因**：① 后端只有 `/ws/execution/{execution_id}` 和 `/ws/pipeline/{run_id}`，无 `/ws/quick-test/{task_id}` 端点；② 后端鉴权用 `Query(..., token=...)` URL 查询参数，前端用子协议 `[token]` 传 token，鉴权方式不匹配；③ 后端 websocket router 注册在 `/api/v1` 前缀下实际路径 `/api/v1/ws/...`，vite proxy 无 rewrite 路径不匹配
- **修复**：3 处改动 ① `app/api/v1/endpoints/websocket.py` 新增 `/ws/quick-test/{task_id}` WebSocket 端点，订阅 `quick_test:{task_id}` 通道；② `src/utils/websocket.ts` `connectWebSocket` 改用 URL Query 参数 `?token=xxx` 传 token（与后端 Query 鉴权对齐）；③ `vite.config.ts` `/ws` proxy 新增 `rewrite: (path) => path.replace(/^\/ws/, '/api/v1/ws')` 补全前缀
- **验证**：后端日志 `WebSocket /api/v1/ws/quick-test/233?token=xxx [accepted]`，`connection open`

**BUG 7：已用时长显示 480 分 54 秒（naive UTC datetime 偏移）**
- **现象**：进度视图"已用时长"显示 480 分 54 秒（8 小时偏移）
- **根因**：后端 `task.start_time.isoformat()` 返回 naive UTC 字符串（无时区后缀），前端 `Date.parse` 按 CST 本地时区（+8）解析，导致 8 小时偏移（480 分 ≈ 8 小时）
- **修复**：`src/views/quick-test/components/QuickProgressView.vue` `startMs` computed 检测无时区后缀时追加 `'Z'` 按 UTC 解析（正则 `/[zZ]$|[+-]\d{2}:\d{2}$/`）
- **验证**：修复后已用时长显示 54 秒、3 分 25 秒（准确）

**BUG 8：进度推送时序问题（onOpen refreshStatus 仅拉取一次）**
- **现象**：launch API 返回后前端连上 WebSocket，但 4 阶段编排推送已在 launch 期间完成，前端收不到任何推送，进度卡在 0%
- **根因**：launch API 同步执行 4 阶段编排（site_exploring→case_generating→task_assembling→completed），每阶段推送进度到 `quick_test:{task_id}` 通道，但前端在 launch 返回后才连 WebSocket，错过所有编排阶段推送
- **修复**：`src/views/quick-test/useQuickTestFlow.ts` `connect()` 的 `onOpen` 回调中新增 `store.refreshStatus()` 调用，连上后立即拉取当前进度补齐
- **验证**：后端日志确认 `GET /api/v1/quick-test/233/status HTTP/1.1 200`，前端 currentStage/progress 与后端一致

**BUG 9：0 用例任务状态置 PENDING（前端状态机无法切出 running）**
- **现象**：AI 生成失败降级为 0 用例时，任务执行完成但前端永久显示"测试进行中"（phase 卡在 running）
- **根因**：`app/services/test_execution_engine/task_batch_executor_mixin/_executor.py` 在 0 用例分支设 `task.status = TaskStatus.PENDING`（"等待执行"），前端 `refreshStatus` 检查 `data.status === '执行完成'/'执行失败'/'已停止'`，"等待执行" 不匹配任何分支，phase 无法切换
- **修复**：0 用例分支改为 `task.status = TaskStatus.COMPLETED`（任务已走完执行流程，0 用例视为空完成），日志改为"没有关联的测试用例，标记为执行完成"
- **验证**：task 235（0 用例）后端日志 `测试任务 235 没有关联的测试用例，标记为执行完成`，DB status=2 (COMPLETED)，前端 phase='completed'

**BUG 10：异步执行完成未推送终态（前端永久卡在 running）**
- **现象**：launch 返回后前端连 WebSocket，onOpen 时 refreshStatus 拿到 RUNNING，之后任务完成变 COMPLETED/FAILED 但前端未再拉取，永久卡在 running/site_exploring
- **根因**：`TaskAssembler._run_executor_safely` 后台异步执行完成后，未向 `quick_test:{task_id}` 通道推送终态。前端只 onOpen 拉取一次，之后无推送无轮询
- **修复**：① `app/services/url_driven/task_assembler.py` 注入 `push_service`，`_run_executor_safely` 的 `finally` 块新增 `_push_final_status(task_id, session)` —— 查询任务最终状态，按 COMPLETED/FAILED 分别推送 `stage='completed',status='done',progress=100` 或 `stage='failed',status='error',progress=100`；② `app/services/url_driven/quick_launcher.py` 将 `push_service` 透传给 `TaskAssembler` 构造函数
- **验证**：task 235 前端 WebSocket 自动收到终态推送，phase 从 running 自动切到 completed（无需刷新页面），progress=100，结果视图正确显示

**TaskStatus 枚举值确认**（避免映射错误）：
```python
class TaskStatus:
    PENDING = 0       # 等待执行
    RUNNING = 1       # 执行中
    COMPLETED = 2     # 执行完成
    FAILED = 3        # 执行失败
    STOPPED = 4       # 已停止
```
注意 FAILED=3（非 2），COMPLETED=2（非 4），与通常假设相反。task 230 status=3 即 FAILED（执行失败），状态正确。

## MODIFIED Requirements

### Requirement: Project 模型新增 source 字段
原实现：Project 无来源标识
修改后：
- 新增 `source: str` 字段，默认 `"manual"`，url_quick_test 流程设为 `"url_quick_test"`
- Alembic 迁移脚本新增列

### Requirement: 项目列表区分来源
原实现：项目列表无来源标识
修改后：
- `src/views/project/ProjectList.vue` 项目卡片显示来源标签（url_quick_test → 蓝色"快速测试"标签）
- 支持按来源筛选

## REMOVED Requirements
（无删除项，本 spec 全部为新增与最小修改）
