# 前端菜单与流程入口优化实施计划

> 目标：从整个项目维度重整左侧菜单和页面内流程入口，让菜单只承载稳定、高频、可独立进入的业务域，把依赖项目、资源、用例、任务上下文的流程动作放回对应页面内触发。

## 文档信息

| 项 | 内容 |
|----|------|
| 文档版本 | v2.4 |
| 创建日期 | 2026-05-25 |
| 最后更新 | 2026-05-26 |
| 适用范围 | 全项目左侧菜单、路由入口、页面内操作入口、面包屑、回归验证 |
| 关联文件 | `src/layouts/MainLayout.vue`、`src/layouts/useMainLayout.ts`、`src/router/routes.ts` |
| 关联业务域 | 项目、资源、需求分析、测试点、测试用例、任务执行、报告、迭代、系统管理 |
| 强制遵守规则 | `.trae/rules/project_rules.md` |

## 实施纪律

本计划实施过程中必须全程遵守项目开发规则：

`D:\PythonFile\ai-testmaster\.trae\rules\project_rules.md`

核心要求摘录：

| 类别 | 必须遵守 |
|------|----------|
| 核心原则 | 真实环境测试、禁止 Mock、覆盖率 ≥ 95%；最小改动、外科手术式修改、杜绝冗余 |
| 代码风格 | 变量函数 lowerCamelCase，类 UpperCamelCase，常量 UPPER_SNAKE_CASE；4 空格缩进，行宽 ≤ 120 |
| TypeScript | 禁用 `any`，强制空值处理，异步统一 `async/await` |
| 架构 | 单文件 ≤ 350 行；新增模块遵循现有结构；避免无意义抽象 |
| 安全 | 禁止硬编码密钥；外部输入必须校验；日志脱敏敏感字段 |
| 性能 | 高频查询优先 Set/Map；避免低效重复计算 |
| 测试 | 核心分支覆盖率 ≥ 95%；覆盖正常、空值、异常、边界用例 |
| AI 生成约束 | 禁止 TODO/FIXME/空占位；IO、网络、解析强制异常捕获；深层属性空安全兜底 |
| 修复与合并 | Bug 修复定位根因，只改必要代码并补验证；合并前类型检查和构建必须通过 |

每个代办任务开始前必须：

- [ ] 读取本计划对应任务说明
- [ ] 读取 `.trae/rules/project_rules.md`
- [ ] 确认当前工作树差异，避免覆盖他人改动
- [ ] 明确本任务涉及文件、入口、路由和验收标准

每个代办任务完成前必须：

- [ ] 无 TODO/FIXME/空占位
- [ ] 无新增 `any`
- [ ] 深层属性访问有空值兜底
- [ ] 文件行数未明显膨胀，必要时拆分
- [ ] 类型检查通过
- [ ] 构建通过或记录无法运行原因
- [ ] 人工/自动回归记录已补充
- [ ] 本文档代办状态和完成证据已同步

## 一、现状问题

当前菜单同时承载“业务域入口”和“流程动作入口”，导致导航层级偏重、入口重复、上下文缺失。

| 区域 | 当前问题 | 影响 |
|------|----------|------|
| 项目列表 | 菜单名偏列表页，实际承担项目工作台入口 | 用户进入后还要再找任务、测试点、资源等项目相关动作 |
| 资源管理 | `资源列表`、`上传需求`、历史 `UI原型管理` 能力边界重叠 | 上传、解析、截图、页面流转分析入口不够统一 |
| 需求分析 | 路由存在但左侧菜单未显式归属 | 入口语义不清，容易被忽略 |
| 测试用例管理 | 混入 `测试点提取`、`AI生成用例`、`用例质量分析`、`回归生成` 等流程动作 | 菜单过长，且多个入口需要项目/资源/用例上下文 |
| 测试任务管理 | `任务列表` 默认路由重定向到项目列表 | 从菜单进入任务域时不直观 |
| 测试报告 | 单菜单入口合理，但报告详情依赖任务/执行上下文 | 需要保持列表入口，详情从报告列表进入 |
| 迭代管理 | 只有 Pipeline 仪表盘，回归生成却挂在测试用例管理下 | 迭代/变更类能力分散 |
| 系统管理 | 用户、角色、审计日志、测试能力均展示在菜单 | 后续需要结合权限动态展示 |
| 评审 Inbox | 前端曾存在隐藏评审路由 | 当前无菜单承载，易残留过期入口 |

## 二、优化原则

1. 菜单只放“业务域入口”，不放一次性流程步骤。
2. 依赖具体 ID 的页面不进入菜单，例如用例详情、质量分析、任务详情、报告详情。
3. 依赖上下文的动作放在页面内，例如“从资源提取测试点”“生成用例”“创建任务”“质量分析”。
4. 项目是主上下文。能围绕项目展开的操作，优先从项目详情或项目工作台进入。
5. 资源是需求、UI 原型、截图、流转分析的统一入口，不再拆多个重复菜单。
6. 迭代/变更/Pipeline 统一归入迭代管理，不挂在测试用例管理下。
7. 第一阶段以“隐藏菜单、保留路由或兼容重定向”为主，降低历史链接和自动化脚本失效风险。
8. 已确认无入口价值且无菜单承载的过期页面，可以移除前端路由，但必须先登记在路由下线清单中。
9. 第二阶段再补重定向、页面内按钮和权限动态菜单。

## 三、目标业务流程

推荐主流程：

```text
项目中心
  -> 资源中心：上传需求 / UI截图 / 原型资料
  -> 资源解析：文档解析 / UI解析 / 页面流转分析
  -> 测试点管理：确认、维护、去重、关联资源
  -> 用例列表：AI生成、人工维护、质量分析
  -> 测试任务：选择用例、创建执行任务
  -> 执行监控：查看执行过程、失败分析、截图视频
  -> 测试报告：汇总执行结果和质量趋势
  -> 迭代管理：变更分析、回归生成、Pipeline监控
```

关键入口归属：

| 能力 | 推荐入口 | 不推荐入口 |
|------|----------|------------|
| 上传需求/原型/截图 | 资源列表或项目详情资源区 | 单独散落多个菜单 |
| UI 解析和页面流转分析 | 资源列表的资源详情/行操作 | `UI原型管理` 独立菜单 |
| 测试点提取 | 资源解析完成页、资源列表行操作 | 左侧常驻菜单 |
| AI 生成用例 | 测试点管理选中测试点后、资源解析完成下一步 | 左侧常驻菜单 |
| 用例质量分析 | 用例列表行操作、用例详情页 | `/quality/0` 菜单 |
| 创建测试任务 | 用例列表批量选择后、项目详情任务区 | 空上下文任务菜单 |
| 执行任务 | 任务详情页 | 左侧单独执行菜单 |
| 报告详情 | 报告列表行操作、任务执行完成页 | 左侧菜单 |
| 回归生成 | 迭代管理、资源/UI变更页 | 测试用例管理 |
| Pipeline 进度 | Pipeline 仪表盘、回归生成启动后跳转 | 测试用例管理 |
| XMind 导入 | 测试点管理页内动作 | 左侧菜单 |
| 元素定位/批量定位 | 用例详情、用例列表批量操作、任务执行前检查 | 左侧菜单 |
| 执行截图/视频回放 | 执行页、任务详情结果面板 | 左侧菜单 |

## 四、目标菜单结构

### 最终菜单决策表

| 当前菜单/入口 | 目标名称 | 菜单形态 | 处理 | 状态 |
|---------------|----------|----------|------|------|
| 项目列表 | 项目中心 | 单菜单项 | 改名，保留 `/home/project` | ✅ done |
| 资源管理 / 资源列表 | 资源中心 | 单菜单项 | 改名，保留 `/home/requirement` | ✅ done |
| 资源管理 / 上传需求 | - | 页面内动作 | 从菜单隐藏，合并为资源中心上传按钮 | ✅ done |
| 资源管理 / UI原型管理 | - | 页面内动作 | 已从菜单隐藏，资源中心行操作进入 | ✅ done |
| 测试用例管理 | 测试资产 | 二级菜单 | 改名 | ✅ done |
| 测试用例管理 / 用例列表 | 用例列表 | 二级菜单项 | 保留 | ✅ done |
| 测试用例管理 / 测试点管理 | 测试点管理 | 二级菜单项 | 保留 | ✅ done |
| 测试用例管理 / 测试点提取 | - | 页面内动作 | 从菜单隐藏，资源/测试点上下文进入 | ✅ done |
| 测试用例管理 / AI生成用例 | - | 页面内动作 | 从菜单隐藏，测试点上下文进入 | ✅ done |
| 测试用例管理 / 用例质量分析 | - | 行操作 | 从菜单隐藏，具体用例进入 | ✅ done |
| 测试用例管理 / 回归生成 | 回归生成 | 迭代中心二级菜单或页面动作 | 从测试资产移出 | ✅ done |
| 测试任务管理 / 任务列表 | 执行中心 | 单菜单项 | 改名并建设任务总览 | ✅ done |
| 测试报告 | 报告中心 | 单菜单项 | 改名，保留 `/home/report` | ✅ done |
| 迭代管理 / Pipeline仪表盘 | 迭代中心 / Pipeline仪表盘 | 二级菜单项 | 保留 | ✅ done |
| 系统管理 / 用户管理 | 用户管理 | 二级菜单项 | 按权限展示 | ✅ done |
| 系统管理 / 角色管理 | 角色管理 | 二级菜单项 | 按权限展示 | ✅ done |
| 系统管理 / 审计日志 | 审计日志 | 二级菜单项 | 按权限展示 | ✅ done |
| 系统管理 / 测试能力 | 测试能力 | 二级菜单项 | 按权限展示 | ✅ done |
| 个人中心 | 个人中心 | 头像下拉 | 不进左侧菜单 | ✅ done |
| ReviewInbox | - | 不暴露 | 已移除前端路由 | ✅ done |

### 推荐左侧菜单

| 一级菜单 | 二级菜单 | 说明 |
|----------|----------|------|
| 项目中心 | - | 原 `项目列表`，作为项目工作台入口 |
| 资源中心 | - | 原 `资源列表`，覆盖需求文档、UI原型、截图、解析、流转分析 |
| 测试资产 | 测试点管理 | 管理从资源提取出的测试点 |
| 测试资产 | 用例列表 | 管理生成和人工维护的测试用例 |
| 执行中心 | - | 任务总览、任务详情、执行入口 |
| 报告中心 | - | 报告列表和报告详情 |
| 迭代中心 | Pipeline 仪表盘 | 流水线运行监控 |
| 迭代中心 | 回归生成 | 变更分析、旧项目回归生成 |
| 系统管理 | 用户管理 | 按权限展示 |
| 系统管理 | 角色管理 | 按权限展示 |
| 系统管理 | 审计日志 | 按权限展示 |
| 系统管理 | 测试能力 | 按权限展示 |

### 可选更保守版本

若本轮不做菜单改名，只做瘦身：

| 当前一级菜单 | 保留二级菜单 | 移除/隐藏 |
|--------------|--------------|-----------|
| 项目列表 | - | 暂不改名 |
| 资源管理 | 资源列表 | 上传需求、UI原型管理 |
| 测试用例管理 | 用例列表、测试点管理 | 测试点提取、AI生成用例、用例质量分析、回归生成 |
| 测试任务管理 | 任务列表 | 任务详情、执行页不进菜单 |
| 测试报告 | - | 报告详情不进菜单 |
| 迭代管理 | Pipeline仪表盘、回归生成 | 评审 Inbox |
| 系统管理 | 用户、角色、审计日志、测试能力 | 按权限动态展示 |

## 五、全项目菜单评估

### 1. 项目中心

| 页面/能力 | 是否放菜单 | 处理建议 |
|-----------|------------|----------|
| 项目列表 | 是 | 保留，建议改名为 `项目中心` |
| 项目详情 | 否 | 从项目列表进入 |
| 项目资源概览 | 否 | 放在项目详情内 |
| 项目任务概览 | 否 | 放在项目详情内 |
| 项目测试点入口 | 否 | 项目详情按钮跳转到测试点管理并带 `projectId` |

实施要点：

- 项目列表是全系统起点，应承担“进入项目工作台”的职责。
- 项目详情建议增加快捷动作：上传资源、查看资源、测试点管理、用例列表、创建任务、查看报告。

### 2. 资源中心

| 页面/能力 | 是否放菜单 | 处理建议 |
|-----------|------------|----------|
| 资源列表 | 是 | 保留为主入口 |
| 上传需求 | 否 | 合并为资源列表内“上传资源/上传需求”按钮 |
| UI原型管理 | 否 | 已从菜单移除，能力合并到资源列表 |
| 资源解析 | 否 | 行操作或资源详情触发 |
| UI截图预览 | 否 | 资源详情触发 |
| 页面流转分析 | 否 | UI资源详情内触发 |
| 需求分析 | 否 | 归入资源详情或项目详情动作，不进左侧菜单 |

实施要点：

- 资源列表必须覆盖上传、解析、查看、删除、预览、UI解析、页面流转分析。
- `上传需求` 作为资源列表内按钮，不再作为二级菜单。
- `analysis` 路由归属资源/项目上下文，从资源详情或项目详情进入，不单独放菜单。

### 3. 测试资产

| 页面/能力 | 是否放菜单 | 处理建议 |
|-----------|------------|----------|
| 测试点管理 | 是 | 保留 |
| 测试点提取 | 否 | 从资源解析结果进入 |
| 用例列表 | 是 | 保留 |
| AI生成用例 | 否 | 从测试点管理或资源解析完成页进入 |
| 用例详情 | 否 | 从用例列表进入 |
| 用例质量分析 | 否 | 从用例列表行操作或用例详情进入 |
| 批量定位/修复 | 否 | 从用例列表或测试点管理动作进入 |

实施要点：

- `测试点管理` 与 `用例列表` 是稳定资产入口，适合放菜单。
- `测试点提取`、`AI生成用例` 是流程动作，不应常驻。
- 删除 `/home/case/quality/0` 菜单入口，避免无效参数。

### 4. 执行中心

| 页面/能力 | 是否放菜单 | 处理建议 |
|-----------|------------|----------|
| 任务列表 | 是 | 保留，但默认页不应重定向到项目列表 |
| 创建任务 | 否 | 从用例列表批量选择、项目详情进入 |
| 任务详情 | 否 | 从任务列表进入 |
| 测试执行 | 否 | 从任务详情进入 |
| 失败分析 | 否 | 从执行结果进入 |
| 截图/视频回放 | 否 | 从执行结果详情进入 |

实施要点：

- 当前 `/home/task` 默认重定向项目列表，建议改成真正的任务列表总览。
- 如果任务必须绑定项目，可以在任务列表提供项目筛选，而不是把菜单入口重定向走。

### 5. 报告中心

| 页面/能力 | 是否放菜单 | 处理建议 |
|-----------|------------|----------|
| 报告列表 | 是 | 保留 |
| 报告详情 | 否 | 从报告列表或任务完成页进入 |
| 报告导出 | 否 | 报告列表/详情页按钮 |
| 统计概览 | 可选 | 后续可与报告列表合并为报告中心首页 |

实施要点：

- 报告列表适合作为菜单入口。
- 报告详情、导出、回放、失败详情都应从报告上下文进入。

### 6. 迭代中心

| 页面/能力 | 是否放菜单 | 处理建议 |
|-----------|------------|----------|
| Pipeline 仪表盘 | 是 | 保留 |
| 回归生成 | 是或页面动作 | 建议迁移到迭代管理 |
| Pipeline 进度 | 否 | 从仪表盘或启动页进入 |
| 评审 Inbox | 否 | 当前不暴露 |
| 变更分析 | 是或页面动作 | 可与回归生成合并 |

实施要点：

- 回归生成不应挂在测试用例管理下。
- 若回归生成使用频率高，可作为迭代管理二级菜单；若必须先选择资源/UI版本，则作为资源变更页动作更合理。

### 7. 系统管理

| 页面/能力 | 是否放菜单 | 处理建议 |
|-----------|------------|----------|
| 用户管理 | 是 | 按权限展示 |
| 角色管理 | 是 | 按权限展示 |
| 审计日志 | 是 | 管理员或审计角色展示 |
| 测试能力 | 是或配置入口 | 管理员/QA Lead 展示 |
| 个人中心 | 否 | 用户头像下拉进入 |

实施要点：

- 系统管理菜单应接入权限动态过滤。
- 个人中心不应作为系统管理二级菜单，当前从头像下拉进入是合理的。

### 8. 专项能力入口

以下能力在项目中已经存在，但不适合作为左侧菜单，应明确归属到具体业务页面。

| 能力 | 当前承载 | 目标入口 | 处理建议 |
|------|----------|----------|----------|
| XMind 导入 | `XmindImportDialog`、测试点管理按钮 | 测试点管理 | 保留为测试点管理页内动作，支持预览和 AI 增强导入 |
| 元素定位维护 | 用例详情技术视图 | 用例详情 | 保留在用例详情，作为单步定位维护入口 |
| 批量元素定位 | `BatchLocatorDialog` | 用例列表批量操作、任务执行前检查 | 不进菜单，作为执行准备动作 |
| 定位覆盖率 | 用例详情技术视图 | 用例详情、用例列表列字段 | 可在用例列表增加覆盖率提示 |
| 执行配置 | 执行页侧栏 | 任务详情、执行页 | 执行前可配置 headless、录屏、分辨率、fps |
| 执行截图 | 执行页、任务结果面板 | 执行页、任务详情 | 作为结果查看动作 |
| 执行视频回放 | 执行页侧栏 | 执行页、任务详情 | 作为执行过程回放能力 |
| 失败分析 | 执行页分析面板 | 执行页、任务结果详情 | 不进菜单，随执行结果展示 |
| 资源 AI 分析 | 资源列表行操作 | 资源列表 | 应保持带项目/文件/UI原型上下文跳转 |

## 六、现有路由与入口迁移表

| 当前路由 | 当前用途 | 目标入口 | 路由策略 | 备注 |
|----------|----------|----------|----------|------|
| `/home/project` | 项目列表 | 项目中心 | 保留，可改菜单名 | 全系统起点 |
| `/home/project/detail` | 项目详情 | 项目列表行操作 | 保留隐藏 | 建议项目详情补快捷入口 |
| `/home/requirement` | 资源列表 | 资源中心 | 保留 | 资源主入口 |
| `/home/requirement/upload` | 上传需求 | 资源列表上传按钮或快捷入口 | 保留或后续合并 | 若保留，定位为快捷上传 |
| `/home/requirement/ui-prototype` | UI原型详情/流转分析 | 资源列表 UI 资源行操作 | 保留隐藏 | 当前资源操作仍跳转该路由 |
| `/home/analysis` | 需求分析 | 资源详情或项目详情动作 | 保留隐藏或归入资源中心 | 必须明确最终入口 |
| `/home/case` | 用例列表 | 测试资产 / 用例列表 | 保留 | 可支持项目筛选 |
| `/home/case/test-point-management` | 测试点管理 | 测试资产 / 测试点管理 | 保留 | 承接提取、XMind、生成用例 |
| `/home/case/test-point-extract` | 测试点提取向导 | 资源解析完成页、测试点管理动作 | 保留隐藏 | 需要携带 project/file 参数 |
| `/home/case/ai-generate` | AI生成用例 | 测试点管理、资源解析完成页 | 保留隐藏 | 需要携带项目、资源、测试点上下文 |
| `/home/case/detail/:caseId` | 用例详情 | 用例列表行操作 | 保留隐藏 | 不进菜单 |
| `/home/case/quality/:caseId` | 用例质量分析 | 用例列表/详情页操作 | 保留隐藏 | `caseId=0` 应重定向或提示 |
| `/home/case/pipeline/:runId` | Pipeline进度 | Pipeline仪表盘、回归生成完成页 | 保留隐藏，后续可迁移 | 当前挂在 case 下但语义属迭代 |
| `/home/case/iteration/regression-generate` | 回归生成 | 迭代中心或资源/UI变更页 | 保留兼容，新增目标入口 | 旧路径需兼容 |
| `/home/task` | 任务默认入口 | 执行中心 / 任务总览 | 需改造 | 当前重定向项目列表，不合理 |
| `/home/task/list/:projectId` | 项目任务列表 | 任务总览或项目详情任务区 | 保留 | 可新增无项目任务总览 |
| `/home/task/create/:projectId` | 创建任务 | 用例列表批量操作、项目详情 | 保留隐藏 | 需要项目上下文 |
| `/home/task/detail/:taskId` | 任务详情 | 任务列表行操作 | 保留隐藏 | 执行、结果、报告入口 |
| `/home/task/execution/:taskId` | 测试执行 | 任务详情 | 保留隐藏 | 截图、视频、失败分析 |
| `/home/report` | 报告列表 | 报告中心 | 保留 | 报告主入口 |
| `/home/report/detail` | 报告详情 | 报告列表行操作 | 保留隐藏 | 建议后续改为 `detail/:reportId` |
| `/home/pipeline-dashboard` | Pipeline仪表盘 | 迭代中心 | 保留 | Pipeline主入口 |
| `/home/system/*` | 系统管理 | 系统管理 | 按权限展示 | 复用路由 meta.permission |

## 七、路由兼容与下线规则

### 保留隐藏路由

以下路由不在菜单展示，但必须继续可访问：

| 路由 | 保留原因 |
|------|----------|
| `/home/requirement/ui-prototype` | 资源列表 UI 原型资源仍跳转该页面 |
| `/home/case/test-point-extract` | 资源解析流程需要进入 |
| `/home/case/ai-generate` | 测试点管理和资源流程需要进入 |
| `/home/case/detail/:caseId` | 报告、失败分析、用例列表会跳转 |
| `/home/case/quality/:caseId` | 用例质量分析需要具体用例上下文 |
| `/home/task/create/:projectId` | 创建任务需要项目上下文 |
| `/home/task/detail/:taskId` | 任务列表需要进入 |
| `/home/task/execution/:taskId` | 任务详情需要进入 |
| `/home/report/detail` | 报告列表需要进入 |

### 需要重定向或迁移的路由

| 路由 | 问题 | 建议 |
|------|------|------|
| `/home/case/quality/0` | 无效用例 ID | 重定向 `/home/case` 并提示选择具体用例 |
| `/home/task` | 当前重定向项目列表 | 改为任务总览，或显示项目选择和任务筛选 |
| `/home/case/pipeline/:runId` | 语义属于迭代 | 保留旧路由，新增 `/home/iteration/pipeline/:runId` 后重定向 |
| `/home/case/iteration/regression-generate` | 语义属于迭代 | 保留旧路由，新增迭代中心入口 |

### 入口参数契约

| 路由 | 必填参数 | 可选参数 | 缺参行为 | 来源页面 |
|------|----------|----------|----------|----------|
| `/home/project/detail` | `id` | - | 缺少 `id` 返回项目中心并提示选择项目 | 项目中心 |
| `/home/requirement/ui-prototype` | `project_id`、`prototype_project_id` | `name`、`iteration_id`、`iteration_name` | 缺少项目或原型 ID 返回资源中心 | 资源列表 UI 原型行操作 |
| `/home/analysis` | `project_id` | `file_id`、`prototype_project_id`、`iteration_id` | 缺少项目 ID 返回资源中心 | 资源详情、项目详情 |
| `/home/case/test-point-management` | `projectId` | `openExtract`、`file_id`、`filename` | 无项目时显示项目选择态 | 项目详情、资源列表、任务详情 |
| `/home/case/test-point-extract` | `project_id` | `file_id`、`prototype_project_id`、`iteration_id` | 缺少项目 ID 返回测试点管理 | 资源解析结果 |
| `/home/case/ai-generate` | `project_id` | `requirement_file_ids`、`file_id`、`test_point_ids` | 缺少项目 ID 显示项目选择态 | 测试点管理、资源解析结果 |
| `/home/case/detail/:caseId` | `caseId` | `project_id` | 非法 `caseId` 返回用例列表 | 用例列表、报告、失败分析 |
| `/home/case/quality/:caseId` | `caseId` | - | `caseId=0` 或非法时返回用例列表 | 用例列表、用例详情 |
| `/home/task/list/:projectId` | `projectId` | `status`、`keyword` | 无项目时进入 `/home/task` 总览 | 项目详情、项目中心 |
| `/home/task/create/:projectId` | `projectId` | `case_ids` | 无项目时返回用例列表并提示 | 用例列表、项目详情 |
| `/home/task/detail/:taskId` | `taskId` | `project_id` | 非法任务 ID 返回执行中心 | 任务列表 |
| `/home/task/execution/:taskId` | `taskId` | `project_id` | 非法任务 ID 返回任务详情或执行中心 | 任务详情 |
| `/home/report/detail` | `id` 或 `report_id` | `task_id` | 缺少报告 ID 返回报告中心 | 报告列表、任务详情 |
| `/home/iteration/pipeline/:runId` | `runId` | `project_id`、`iteration_id` | 非法运行 ID 返回 Pipeline 仪表盘 | Pipeline 仪表盘、回归生成 |
| `/home/iteration/regression-generate` | `project_id` | `ui_project_id`、`name`、`iteration_id` | 缺少项目 ID 返回迭代中心 | UI 原型详情、Pipeline 仪表盘 |

### 页面动作落点表

| 页面 | 动作 | 按钮/入口文案 | 目标 | 必须携带 |
|------|------|---------------|------|----------|
| 项目中心 | 进入项目详情 | 详情 | `/home/project/detail` | `id` |
| 项目详情 | 上传资源 | 上传资源 | 资源上传弹窗或 `/home/requirement` | `project_id` |
| 项目详情 | 查看测试点 | 测试点管理 | `/home/case/test-point-management` | `projectId` |
| 项目详情 | 查看用例 | 用例列表 | `/home/case` | `projectId` |
| 项目详情 | 查看任务 | 任务列表 | `/home/task/list/:projectId` | `projectId` |
| 资源中心 | 上传资源 | 上传资源 | 上传弹窗或上传页 | `project_id` |
| 资源中心 | 资源解析 | AI分析/提取测试点 | `/home/case/test-point-management` | `projectId`、`file_id` 或 `prototype_project_id` |
| 资源中心 | UI 原型详情 | 查看原型/流转分析 | `/home/requirement/ui-prototype` | `project_id`、`prototype_project_id` |
| 资源中心 | 需求分析 | 需求分析 | `/home/analysis` | `project_id` |
| 测试点管理 | 从资源提取 | 从资源提取 | 提取弹窗或 `/home/case/test-point-extract` | `project_id` |
| 测试点管理 | XMind 导入 | 导入 XMind | `XmindImportDialog` | `projectId` |
| 测试点管理 | 生成用例 | 生成用例 | `/home/case/ai-generate` | `project_id`、`test_point_ids` |
| 用例列表 | 查看详情 | 查看 | `/home/case/detail/:caseId` | `caseId` |
| 用例列表 | 质量分析 | 质量分析 | `/home/case/quality/:caseId` | `caseId` |
| 用例列表 | 创建任务 | 创建任务 | `/home/task/create/:projectId` | `projectId`、`case_ids` |
| 用例列表 | 批量定位 | 批量元素定位 | `BatchLocatorDialog` | `projectId`、`case_ids` |
| 用例详情 | 单步定位 | 添加定位 | 定位弹窗/API | `stepId` |
| 任务列表 | 查看任务 | 详情 | `/home/task/detail/:taskId` | `taskId` |
| 任务详情 | 执行任务 | 开始执行 | `/home/task/execution/:taskId` | `taskId` |
| 任务详情 | 查看报告 | 查看报告 | `/home/report/detail` | `report_id` 或 `task_id` |
| 执行页 | 查看截图 | 截图 | 当前页弹窗 | `taskId`、`caseId`、`stepNumber` |
| 执行页 | 视频回放 | 执行视频 | 当前页侧栏 | `taskId`、`caseId` |
| Pipeline 仪表盘 | 查看进度 | 查看进度 | `/home/iteration/pipeline/:runId` | `runId` |
| Pipeline 仪表盘 | 回归生成 | 回归生成 | `/home/iteration/regression-generate` | `project_id` |

### 路由下线前置检查

删除任何路由前必须完成：

- [ ] `rg` 扫描所有 `router.push`、`<router-link>`、`path` 引用
- [ ] 检查 Cypress/E2E 测试是否直接访问该路由
- [ ] 检查后端响应是否返回前端路径
- [ ] 检查文档和操作手册是否引用该路由
- [ ] 若存在历史风险，先保留 1 个版本并加重定向

## 八、权限矩阵

当前路由已使用 `meta.permission` 做部分权限控制，菜单动态过滤应复用相同字段。

| 菜单 | 路由 | 权限建议 | 当前状态 |
|------|------|----------|----------|
| 项目中心 | `/home/project` | 登录用户 | 无显式 permission |
| 资源中心 | `/home/requirement` | 登录用户或项目成员 | 无显式 permission |
| 测试资产 / 测试点管理 | `/home/case/test-point-management` | QA、项目成员 | 无显式 permission |
| 测试资产 / 用例列表 | `/home/case` | QA、项目成员 | 无显式 permission |
| 执行中心 | `/home/task` | QA、执行人、项目成员 | 无显式 permission |
| 报告中心 | `/home/report` | QA、项目成员、只读角色 | 无显式 permission |
| 迭代中心 / Pipeline | `/home/pipeline-dashboard` | QA Lead、管理员、项目负责人 | 当前只 requireAuth |
| 系统管理 / 用户管理 | `/home/system/user` | `user:list` | 已配置 |
| 系统管理 / 角色管理 | `/home/system/role` | `role:list` | 已配置 |
| 系统管理 / 审计日志 | `/home/system/audit-log` | `system:manage` | 已配置 |
| 系统管理 / 测试能力 | `/home/system/test-capability` | `system:manage` 或 QA Lead | 已配置 `system:manage` |

实施建议：

- 第一阶段只对系统管理做菜单权限过滤。
- 第二阶段再补项目级权限，如项目成员、执行人、只读角色。
- 菜单隐藏不能代替权限校验，路由守卫仍必须保留。

## 九、专项功能验收清单

| 功能 | 验收标准 |
|------|----------|
| XMind 导入 | 测试点管理可打开导入弹窗，支持预览、导入、AI增强导入，导入后刷新测试点 |
| 资源 AI 分析 | 资源列表行操作可带 `projectId`、`file_id` 或 `prototype_project_id` 进入提取流程 |
| UI 原型详情 | 资源列表 UI 原型资源可进入截图预览和页面流转分析 |
| 测试点提取 | 从资源上下文进入时自动带项目和资源参数 |
| AI 生成用例 | 从测试点管理进入时自动带项目和选中的测试点 |
| 用例质量分析 | 只能从具体用例进入，不允许 `caseId=0` |
| 批量元素定位 | 可从用例列表/详情选择用例启动定位，支持进度、取消、报告 |
| 执行前检查 | 任务详情能提示是否需要补充定位信息 |
| 执行截图 | 执行页和任务结果可查看失败截图 |
| 执行视频 | 执行页可查看视频回放和控制播放速度 |
| 失败分析 | 执行页能展示 AI 分析结果和问题类型切换 |

## 十、测试映射表

| 验证项 | 覆盖任务 | 验证方式 | 通过标准 |
|--------|----------|----------|----------|
| TypeScript 类型检查 | 全部前端任务 | `F:\nodejs\23.4.0\node.exe node_modules\vue-tsc\bin\vue-tsc.js --noEmit` | 0 error |
| 生产构建 | 全部前端任务 | `F:\nodejs\23.4.0\node.exe node_modules\vite\bin\vite.js build` | build success，无阻断错误 |
| 菜单结构 smoke | NAV-03、NAV-04、NAV-05、NAV-06 | 人工或 Cypress | 左侧菜单符合最终菜单决策表 |
| 路由兼容 smoke | ROUTE-01 到 ROUTE-06 | 人工或 Cypress | 旧链接可访问/重定向，新链接可访问 |
| 项目快捷入口 | PROJECT-01 | 人工或 Cypress | 项目详情能进入资源、测试点、用例、任务、报告 |
| 资源中心流程 | RESOURCE-01 到 RESOURCE-04 | 人工或 Cypress | 上传、解析、UI 原型详情、需求分析入口可达 |
| 测试点流程 | ASSET-01 到 ASSET-03 | 人工或 Cypress | 提取、XMind 导入、生成用例入口可达 |
| 用例流程 | CASE-01 到 CASE-04 | 人工或 Cypress | 详情、质量分析、创建任务、定位入口可达 |
| 任务流程 | TASK-01 到 TASK-03 | 人工或 Cypress | 任务总览、筛选、详情、执行前检查正常 |
| 执行流程 | EXEC-01 到 EXEC-03 | 人工或 Cypress | 截图、视频、失败分析正常 |
| 报告流程 | REPORT-01 | 人工或 Cypress | 报告列表到详情可达，旧 query 方式兼容 |
| 权限菜单 | PERM-01、PERM-02 | 人工切换角色或单测 | 无权限系统子菜单不展示，有权限可展示 |
| 文档状态同步 | DOC-01 | 文档审查 | 完成项状态、证据、验证记录已更新 |


## 十一、实施范围

### 前端文件

| 文件 | 改动点 |
|------|--------|
| `src/layouts/MainLayout.vue` | 重整左侧菜单和二级菜单 |
| `src/layouts/useMainLayout.ts` | 更新菜单高亮、面包屑、隐藏路由映射 |
| `src/router/routes.ts` | 保留必要隐藏路由，移除过期路由，补充重定向 |
| `src/views/project/ProjectList.vue` | 强化项目中心入口和项目快捷动作 |
| `src/views/project/detail.vue` | 增加资源、测试点、用例、任务、报告快捷入口 |
| `src/views/requirement/resource-manage.vue` | 承接资源上传、解析、UI截图、页面流转分析 |
| `src/views/case/test-point-management/index.vue` | 承接测试点提取和生成用例动作 |
| `src/components/xmind/XmindImportDialog.vue` | 测试点管理内的 XMind 导入流程 |
| `src/views/case/TestCaseList.vue` | 承接用例质量分析、创建任务、导出等动作 |
| `src/views/case/BatchLocatorDialog.vue` | 用例批量元素定位入口 |
| `src/views/case/components/CaseTechnicalView.vue` | 用例详情内元素定位维护入口 |
| `src/views/task/TaskList.vue` | 改为真正任务总览，支持项目筛选 |
| `src/views/task/TaskDetail.vue` | 执行前检查、执行入口、结果面板入口 |
| `src/views/execution/TestExecution.vue` | 执行监控、截图、视频回放、失败分析入口 |
| `src/views/iteration/RegressionGenerate.vue` | 迁移到迭代中心或资源变更流程 |
| `src/views/admin/PipelineDashboard.vue` | 作为 Pipeline 统一入口 |

### 暂不处理

| 项 | 原因 |
|----|------|
| 后端 API 删除 | 本计划先调整前端信息架构 |
| 数据库迁移 | 菜单优化不涉及模型变更 |
| 大规模权限系统重做 | 动态菜单可作为后续独立任务 |
| 删除隐藏路由对应页面文件 | 先保留，避免回滚困难 |

## 十二、分阶段实施计划

### 状态更新规则

每个任务必须按以下规则维护状态，避免开发过程中遗漏代码或遗留技术债。

| 状态 | 含义 | 更新要求 |
|------|------|----------|
| ⬜ pending | 未开始 | 默认状态 |
| 🔄 in_progress | 开发中 | 开始改代码前更新，最多同时 2 个进行中 |
| ✅ done | 已完成 | 代码、验证、文档状态同步完成后更新 |
| ⏸️ blocked | 阻塞 | 写明阻塞原因和解除条件 |
| ❌ dropped | 不做 | 必须写明取消原因和替代方案 |

任务标记 `✅ done` 前必须补齐：

- [ ] 已按 `.trae/rules/project_rules.md` 完成自检
- [ ] 代码改动文件列表
- [ ] 入口可达性说明
- [ ] 路由兼容/重定向说明
- [ ] `vue-tsc --noEmit` 结果
- [ ] `vite build` 结果
- [ ] 人工回归记录

### 代办总表

| ID | 状态 | 任务 | 主要文件 | 验收标准 | 完成证据 |
|----|------|------|----------|----------|----------|
| NAV-01 | ✅ done | 隐藏 `资源管理 / UI原型管理` 菜单 | `MainLayout.vue` | 左侧资源管理不再展示 UI 原型管理 | 已从菜单移除 |
| NAV-02 | ✅ done | 移除 `ReviewInbox` 前端暴露入口 | `routes.ts` | 前端路由不再暴露评审 Inbox | 已移除路由 |
| NAV-03 | ✅ done | 菜单改名为业务域：项目中心、资源中心、测试资产、执行中心、报告中心、迭代中心 | `MainLayout.vue`、`useMainLayout.ts` | 菜单文案和面包屑一致 | MENU_CONFIG 全部使用新名称 |
| NAV-04 | ✅ done | 隐藏 `资源管理 / 上传需求` 菜单 | `MainLayout.vue` | 上传需求改为资源中心按钮 | MENU_CONFIG 资源中心无子菜单 |
| NAV-05 | ✅ done | 隐藏测试资产下流程动作菜单 | `MainLayout.vue` | 测试资产仅保留用例列表、测试点管理 | MENU_CONFIG 测试资产仅2个子项 |
| NAV-06 | ✅ done | 将回归生成迁移到迭代中心 | `MainLayout.vue`、`routes.ts`、`useMainLayout.ts` | 迭代中心可进入回归生成，旧路径兼容 | 新路由+旧路由redirect |
| ROUTE-01 | ✅ done | 新增 `/home/iteration/pipeline/:runId` 目标路由 | `routes.ts` | Pipeline 进度语义归入迭代 | routes.ts:L125 |
| ROUTE-02 | ✅ done | 新增 `/home/iteration/regression-generate` 目标路由 | `routes.ts` | 回归生成语义归入迭代 | routes.ts:L126 |
| ROUTE-03 | ✅ done | 旧 Pipeline/回归生成路由兼容重定向 | `routes.ts` | 旧链接可访问且跳转新路由 | routes.ts:L101-L102 |
| ROUTE-04 | ✅ done | `/home/case/quality/0` 无效路由处理 | `routes.ts` 或 `CaseQualityAnalysis.vue` | 返回用例列表并提示选择具体用例 | routes.ts:L94-L99 beforeEnter守卫 |
| ROUTE-05 | ✅ done | 统一隐藏路由 activeMenu 映射 | `useMainLayout.ts` | 隐藏页面高亮正确父菜单 | 13条activeMenu映射 |
| ROUTE-06 | ✅ done | 统一面包屑业务域文案 | `useMainLayout.ts` | 面包屑不出现已隐藏菜单 | breadcrumbMap已使用新名称 |
| PROJECT-01 | ✅ done | 项目详情增加资源、测试点、用例、任务、报告快捷入口 | `project/detail.vue`、`useProjectDetail.ts` | 项目上下文内可进入核心业务 | 5个快捷按钮+useProjectDetail跳转 |
| RESOURCE-01 | ✅ done | 资源中心增加上传资源入口 | `resource-manage.vue` | 替代上传需求菜单 | ResourceTable上传文件按钮 |
| RESOURCE-02 | ✅ done | 资源中心确认 UI 原型详情入口参数 | `useResourceOperations.ts` | 跳转带 `project_id`、`prototype_project_id` | handleEditNavigation携带参数 |
| RESOURCE-03 | ✅ done | 资源中心确认资源 AI 分析/提取入口 | `useResourceOperations.ts` | 跳转带项目和资源参数 | handleAnalyze携带project/file参数 |
| RESOURCE-04 | ✅ done | 需求分析入口归入资源/项目动作 | `resource-manage.vue`、`project/detail.vue`、`routes.ts` | `/home/analysis` 不进左侧菜单但可达 | activeMenu映射到资源中心 |
| ASSET-01 | ✅ done | 测试点管理保留从资源提取入口 | `test-point-management/index.vue` | 可打开提取流程并带项目上下文 | "从需求提取"按钮+TestPointExtractDialog |
| ASSET-02 | ✅ done | 测试点管理强化 XMind 导入验收 | `XmindImportDialog.vue`、`useXmindImport.ts` | 支持预览、导入、AI增强导入、刷新列表 | "导入XMind"按钮+XmindImportDialog |
| ASSET-03 | ✅ done | 测试点管理生成用例入口参数校验 | `useTestPointActions.ts` | 跳转 AI 生成时带项目和测试点 | startGenerate带project_id+test_point_ids |
| CASE-01 | ✅ done | 用例列表增加质量分析行操作 | `TestCaseList.vue` | 仅具体用例可进入质量分析 | "质量分析"行按钮+caseId校验 |
| CASE-02 | ✅ done | 用例列表增加创建任务批量操作 | `TestCaseList.vue` | 选中用例后可创建任务 | "创建任务"批量按钮+case_ids |
| CASE-03 | ✅ done | 用例列表/详情强化批量元素定位入口 | `TestCaseList.vue`、`BatchLocatorDialog.vue`、`CaseDetail.vue` | 可启动、取消、查看定位报告 | BatchLocatorDialog.open/defineExpose |
| CASE-04 | ✅ done | 用例详情单步定位入口校验 | `CaseTechnicalView.vue`、`useCaseDetail.ts` | 可添加/编辑单步定位 | 定位覆盖率+locator_status+双击编辑xpath |
| TASK-01 | ✅ done | `/home/task` 改为任务总览 | `routes.ts`、`TaskList.vue`、相关 API | 不再重定向项目列表 | TaskOverview独立路由 |
| TASK-02 | ✅ done | 任务总览支持项目、状态、关键词筛选 | `TaskList.vue`、`useTaskList.ts` | 可跨项目或按项目查看任务 | 项目筛选+状态筛选 |
| TASK-03 | ✅ done | 任务详情执行前检查入口 | `TaskDetail.vue` | 明确提示是否需要补充定位 | 执行模式选择器+preprocess提示 |
| EXEC-01 | ✅ done | 执行页截图入口回归 | `TestExecution.vue`、`useTestExecution.ts` | 可切换 before/after 截图并预览 | before/after切换+全屏预览 |
| EXEC-02 | ✅ done | 执行页视频回放入口回归 | `ExecutionSidePanel.vue`、`useVideoReplay.ts` | 可播放、暂停、调整进度/速度 | 视频播放+seek±10s+0.5x~2x速度+回放控制 |
| EXEC-03 | ✅ done | 执行页失败分析入口回归 | `TestExecution.vue` | 可查看 AI 分析并切换问题类型 | 失败分析面板+问题类型切换 |
| REPORT-01 | ✅ done | 报告详情路由兼容策略确认 | `routes.ts`、`ReportList.vue`、`ReportDetail.vue` | `/home/report/detail` 旧方式可用 | ReportList.push → /home/report/detail |
| PERM-01 | ✅ done | 抽取菜单配置表 | `MainLayout.vue`、新建菜单配置文件 | 菜单不再硬编码分散 | MENU_CONFIG独立数组 |
| PERM-02 | ✅ done | 系统管理菜单按 `meta.permission` 过滤 | `MainLayout.vue`、`useMainLayout.ts` | 无权限用户不显示系统子菜单 | filterMenuByPermission递归过滤 |
| TEST-01 | ✅ done | 类型检查 | - | `vue-tsc --noEmit` 通过 | exit code 0, 0 error |
| TEST-02 | ✅ done | 生产构建 | - | `vite build` 通过 | exit code 0, build success (18.41s) |
| TEST-03 | ⬜ pending | 导航 smoke 回归 | Cypress 或人工记录 | 菜单和关键入口可达 | 待补 |
| DOC-01 | ✅ done | 开发完成后同步本文档状态 | 本文档 | 完成项更新为 ✅ done 并补证据 | 本表已全量同步 |

### Phase 1：菜单瘦身

目标：先消除明显重复和无效菜单。

| ID | 任务 | 文件 | 验收 |
|----|------|------|------|
| P1-01 | 移除 `资源管理 / UI原型管理` | `MainLayout.vue` | 资源中心只保留资源列表/上传入口 |
| P1-02 | 移除 `测试用例管理 / 测试点提取` | `MainLayout.vue` | 流程入口改由资源页触发 |
| P1-03 | 移除 `测试用例管理 / AI生成用例` | `MainLayout.vue` | 入口改由测试点/资源页触发 |
| P1-04 | 移除 `测试用例管理 / 用例质量分析` | `MainLayout.vue` | 不再出现 `/quality/0` |
| P1-05 | 将 `回归生成` 从测试用例管理移出 | `MainLayout.vue` | 迁移到迭代管理或隐藏 |
| P1-06 | 移除 `ReviewInbox` 前端暴露入口 | `routes.ts` | 无过期评审入口 |

### Phase 2：全项目菜单重命名与归组

目标：让菜单名称表达业务域，而不是页面类型。

| ID | 任务 | 建议 |
|----|------|------|
| P2-01 | `项目列表` 改为 `项目中心` | 作为全流程起点 |
| P2-02 | `资源管理` 改为 `资源中心` | 承载文档、UI、截图、解析 |
| P2-03 | `测试用例管理` 改为 `测试资产` | 下挂测试点管理、用例列表 |
| P2-04 | `测试任务管理` 改为 `执行中心` | 下挂任务列表 |
| P2-05 | `测试报告` 改为 `报告中心` | 单入口或后续扩展统计 |
| P2-06 | `迭代管理` 改为 `迭代中心` | 下挂 Pipeline 和回归生成 |

### Phase 3：页面内入口补齐

目标：隐藏菜单后，功能仍能从正确上下文进入。

| ID | 任务 | 入口位置 |
|----|------|----------|
| P3-01 | 项目详情增加资源/测试点/用例/任务/报告快捷入口 | 项目详情 |
| P3-02 | 资源列表增加 UI 解析和页面流转分析入口 | 资源列表行操作 |
| P3-03 | 资源解析完成后增加“提取测试点”入口 | 资源详情/解析结果 |
| P3-04 | 测试点管理增加“从资源提取”入口 | 测试点管理 |
| P3-05 | 测试点管理增加“生成用例”入口 | 测试点管理 |
| P3-06 | 测试点管理保留并强化 XMind 导入入口 | 测试点管理 |
| P3-07 | 用例列表增加“质量分析”行操作 | 用例列表 |
| P3-08 | 用例列表增加“创建任务”批量操作 | 用例列表 |
| P3-09 | 用例列表或详情增加“批量元素定位”入口 | 用例列表/用例详情 |
| P3-10 | 任务列表支持项目筛选和状态筛选 | 任务列表 |
| P3-11 | 任务详情增加执行/报告入口和执行前检查 | 任务详情 |
| P3-12 | 执行页强化截图、视频回放、失败分析入口 | 执行页 |
| P3-13 | Pipeline 仪表盘增加查看进度和回归生成入口 | Pipeline 仪表盘 |

### Phase 4：路由兼容与面包屑

目标：直接访问隐藏页面时体验合理，菜单高亮稳定。

| ID | 任务 | 说明 |
|----|------|------|
| P4-01 | 隐藏路由保留兼容访问 | 如 `ai-generate`、`test-point-extract` |
| P4-02 | 无效路由重定向 | 如 `quality/0` 跳回用例列表 |
| P4-03 | 更新 `activeMenu` 映射 | 隐藏页面高亮父级业务域 |
| P4-04 | 更新 `breadcrumbMap` | 面包屑显示业务路径而非过期菜单 |
| P4-05 | 清理过期菜单常量或注释 | 避免后续误恢复 |
| P4-06 | 建立路由下线清单 | 移除路由前记录依赖扫描结论 |

### Phase 5：权限动态菜单

目标：避免用户看到没有权限或不相关的系统能力。

| ID | 任务 | 说明 |
|----|------|------|
| P5-01 | 定义菜单配置表 | 从模板中抽离硬编码菜单 |
| P5-02 | 按 `meta.permission` 过滤菜单 | 与路由权限保持一致 |
| P5-03 | 隐藏无权限系统菜单 | 用户、角色、审计、测试能力 |
| P5-04 | 保留管理员完整菜单 | 管理员可见全部系统入口 |

### Phase 6：验证与回归

验证命令：

```powershell
F:\nodejs\23.4.0\node.exe node_modules\vue-tsc\bin\vue-tsc.js --noEmit
F:\nodejs\23.4.0\node.exe node_modules\vite\bin\vite.js build
```

人工回归清单：

| 场景 | 验证点 |
|------|--------|
| 登录进入首页 | 菜单结构符合目标 |
| 项目中心 | 可进入项目详情和各业务快捷入口 |
| 资源中心 | 可上传、解析、预览、查看 UI 流转 |
| 测试资产 | 可维护测试点和用例 |
| 测试点提取 | 可从资源上下文进入 |
| AI生成用例 | 可从测试点上下文进入 |
| 用例质量分析 | 只能对具体用例进入 |
| 执行中心 | 可查看任务、进入详情、启动执行 |
| 报告中心 | 可查看报告列表和详情 |
| 迭代中心 | 可查看 Pipeline、进入回归生成 |
| 系统管理 | 权限符合预期 |
| 旧链接访问 | 可展示、重定向或给出合理提示 |

## 十三、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 菜单隐藏后用户找不到功能 | 操作效率下降 | 在业务页面补足明确按钮和空状态引导 |
| 路由删除过早 | 历史链接、自动化测试失败 | 第一阶段只隐藏菜单，确认无依赖后再删 |
| 回归生成迁移后参数缺失 | 无法启动分析 | 入口统一校验 `project_id`、`ui_project_id` |
| 任务菜单仍重定向项目列表 | 执行中心体验不完整 | 建设任务总览页或项目筛选 |
| 权限动态菜单与路由守卫不一致 | 用户看到入口但进不去 | 菜单配置复用路由 `meta.permission` |
| 面包屑仍显示旧业务名 | 用户路径认知混乱 | 同步更新 `breadcrumbMap` |

## 十四、总体验收清单

- [x] 左侧菜单只保留业务域入口和高频总览入口
- [x] 资源中心覆盖需求文档、UI截图、解析、页面流转分析
- [x] 测试资产只保留测试点管理和用例列表
- [x] 测试点提取从资源上下文进入
- [x] AI生成用例从测试点或资源上下文进入
- [x] 用例质量分析从具体用例进入
- [x] 执行中心不再把任务菜单重定向到项目列表
- [x] 回归生成归入迭代中心或资源变更流程
- [x] 报告详情、任务详情、用例详情不出现在菜单
- [x] 系统管理支持后续权限动态过滤
- [x] 面包屑和菜单高亮符合新结构
- [x] `vue-tsc --noEmit` 通过
- [x] `vite build` 通过

## 十五、建议排期

| 阶段 | 工作量 | 说明 |
|------|--------|------|
| Phase 1 菜单瘦身 | 0.5d | 快速去掉重复和无效入口 |
| Phase 2 菜单重命名与归组 | 0.5d | 统一业务域命名 |
| Phase 3 页面内入口补齐 | 2d | 关键工作，确保功能可达 |
| Phase 4 路由兼容与面包屑 | 0.5d | 降低历史链接风险 |
| Phase 5 权限动态菜单 | 1d | 可独立排期 |
| Phase 6 验证与回归 | 0.5d | 类型检查、构建、人工验证 |
| 合计 | 5d | 建议拆为 2 到 3 个 PR |

## 十六、当前已完成项

| 项 | 状态 | 说明 |
|----|------|------|
| 移除 `资源管理 / UI原型管理` 菜单 | ✅ done | 功能入口统一回到资源列表 |
| 移除 `ReviewInbox` 前端路由 | ✅ done | 当前不再暴露过期评审页面 |
| 全局布局基础优化 | ✅ done | 修复全局样式、内容滚动和侧栏折叠 |
| Phase 1 菜单瘦身（全量） | ✅ done | 导航 NAV-01~NAV-06 全部完成 |
| Phase 2 菜单重命名与归组 | ✅ done | 项目中心/资源中心/测试资产/执行中心/报告中心/迭代中心 |
| Phase 3 页面内入口补齐（全量） | ✅ done | PROJECT-01~EXEC-03 全部完成，功能可达 |
| Phase 4 路由兼容与面包屑 | ✅ done | ROUTE-01~ROUTE-06 + REPORT-01 全部完成 |
| Phase 5 权限动态菜单 | ✅ done | PERM-01 MENU_CONFIG + PERM-02 filterMenuByPermission |
| TEST-01 类型检查 | ✅ done | `vue-tsc --noEmit` → exit code 0, 0 error |
| TEST-02 生产构建 | ✅ done | `vite build` → exit code 0, build success (18.41s) |
| DOC-01 文档状态同步 | ✅ done | 2026-05-26 全量同步完成，仅 TEST-03 待人工回归 |

## 十七、后续决策点

1. ✅ 菜单重命名已完成：项目中心、资源中心、测试资产、执行中心、报告中心、迭代中心。
2. ✅ `上传需求` 已从菜单隐藏，保留为资源列表内上传按钮。
3. ✅ `回归生成` 已作为迭代中心二级菜单，旧路径兼容重定向。
4. ✅ `/home/task` 已建设任务总览页，支持项目筛选和状态筛选。
5. ✅ 隐藏路由已保留兼容访问 + 旧路由重定向，后续版本可评估下线。
6. ✅ 权限动态菜单已实现，菜单配置复用 `meta.permission` 进行过滤。
