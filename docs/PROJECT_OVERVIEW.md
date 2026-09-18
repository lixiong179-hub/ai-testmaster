# AI TestMaster 项目代码梳理与技术栈整理

## 一、项目定位

**AI TestMaster** 是一个 AI 驱动的全自动测试平台，集需求分析、测试用例生成、元素定位、测试执行、质量评估、报告生成于一体。前后端分离架构，前端 Vue3 SPA + 后端 FastAPI 微服务。

---

## 二、整体架构（分层）

```
┌─────────────────────────────────────────────────┐
│  前端 (Vue3 + Vite + Element Plus)              │
│  src/ → views/ components/ store/ api/ composables/
├─────────────────────────────────────────────────┤
│  API 网关层 (FastAPI + CORS + 限流)              │
│  app/main.py → app/api/v1/endpoints/            │
├─────────────────────────────────────────────────┤
│  业务服务层 (app/services/)                      │
│  AI生成 / Pipeline / 用例管理 / 执行 / 报告      │
├─────────────────────────────────────────────────┤
│  AI 层 (app/ai/)                                │
│  AIClient Protocol → OpenAIClient / Fallback     │
│  支持: DeepSeek / Kimi / 通义千问 / 智谱 / 豆包   │
├─────────────────────────────────────────────────┤
│  Pipeline 引擎 (app/pipelines/)                 │
│  Step Protocol → Runner → Context → Artifacts    │
├─────────────────────────────────────────────────┤
│  数据层 (app/db/ + app/models/ + app/crud/)     │
│  SQLAlchemy ORM → MySQL 主从 + Redis 缓存        │
├─────────────────────────────────────────────────┤
│  工具层 (app/utils/)                             │
│  浏览器控制 / ADB / OCR / WebSocket / 加密       │
└─────────────────────────────────────────────────┘
```

---

## 三、后端技术栈详解

### 3.1 核心框架
| 组件 | 版本 | 路径 | 说明 |
|------|------|------|------|
| FastAPI | 0.135.1 | `app/main.py` | Web框架，lifespan管理 |
| Uvicorn | 0.41.0 | ASGI服务器 | |
| Pydantic | 2.12.5 | `app/schemas/` | 请求/响应数据校验 |
| pydantic-settings | 2.13.1 | `app/core/config.py` | 多环境配置(dev/test/prod) |

### 3.2 数据库层
| 组件 | 版本 | 路径 | 说明 |
|------|------|------|------|
| SQLAlchemy | 2.0.48 | `app/db/database/` | ORM，主从分离 |
| PyMySQL | 1.1.2 | - | MySQL驱动 |
| Alembic | 1.18.4 | `alembic/` | 数据库迁移 |

**数据库连接**:
- 主库: `PrimarySessionLocal` (读写)
- 从库: `SecondarySessionLocal` (只读)
- Session注入: `app/db/database/_session.py` → `get_db()` / `get_read_db()`

### 3.3 认证与安全
| 组件 | 版本 | 路径 | 说明 |
|------|------|------|------|
| python-jose | 3.5.0 | `app/utils/jwt_utils.py` | JWT token |
| bcrypt | 4.1.2 | `app/utils/jwt_utils.py` | 密码哈希 |
| cryptography | 46.0.6 | `app/utils/crypto.py` | 数据加密 |

### 3.4 AI 集成
| 组件 | 版本 | 路径 | 说明 |
|------|------|------|------|
| openai | 2.33.0 | `app/ai/` | OpenAI兼容客户端 |

**AI模型支持** (通过`app/core/config.py`配置):
- **文本模型**: DeepSeek (deepseek-v4-flash) — 主力
- **视觉模型**: 通义千问(qwen) / Kimi / 智谱GLM / 文心一言 / 豆包 / MiMo
- **降级策略**: `FallbackAIClient` 主模型失败自动切换备选

**AI Client架构** (`app/ai/`):
- `client.py` — `AIClient` Protocol (接口)
- `openai_client.py` — OpenAI API实现
- `fallback_client.py` — 主备降级包装
- `mock_client.py` — 测试用Mock
- `error_codes.py` — AI错误码定义
- `call_log.py` — Token用量与成本记录

### 3.5 Pipeline 引擎
核心目录: `app/pipelines/`

**架构模式**: Step-based Pipeline (类似Airflow DAG)

- `base.py` — `PipelineStep` Protocol + `StepResult` 数据类
- `runner.py` — `PipelineRunner` 执行引擎 (缓存/重试/降级/暂停/WebSocket推送)
- `context.py` — `PipelineContext` 运行时上下文 (DB/AI/Config/Artifact注入)

**Step实现** (`app/pipelines/steps/`):
- `signal_gatherer.py` — 信号采集
- `forward_scan/` — 正向扫描
- `backward_scan/` — 反向扫描
- `case_generation.py` — 用例生成
- `quality_gate.py` — 质量门禁
- `persist.py` — 持久化
- `scoring.py` / `_signal_scoring.py` — 评分
- `dedup.py` — 去重
- `reconciliation/` — 调和
- `testpoint_alignment/` — 测试点对齐
- `history_fingerprint.py` — 历史指纹
- `reverse_infer/` — 反向推断
- `decision_dispatch/` — 决策分发
- `scenario_candidates.py` — 场景候选

**Pipeline状态机**: `pending → running → [waiting_for_user] → completed/failed/cancelled`

### 3.6 API 层 (78个endpoint文件)
路径: `app/api/v1/endpoints/`

**主要模块**:
| 模块 | 文件 | 说明 |
|------|------|------|
| 认证 | `auth.py`, `auth_deps.py`, `auth_endpoints.py` | 登录/Token/权限依赖 |
| 项目 | `project.py`, `project_core.py`, `project_config.py`, `project_grounding.py` | 项目CRUD+配置 |
| 测试用例 | `test_case.py`, `test_case_crud.py`, `test_case_ai*.py`, `test_case_export.py` | 用例管理+AI生成+导出 |
| 测试点 | `test_point.py`, `test_point_extract.py`, `test_point_import.py` | 测试点提取+导入 |
| 测试任务 | `test_task.py`, `test_task_exec.py` | 任务管理+执行 |
| 测试执行 | `execution.py`, `execution_core/`, `execution_management.py` | 执行引擎 |
| Pipeline | `pipeline.py`, `pipeline_*.py` | 流水线管理 |
| 迭代 | `iteration/` | 迭代管理 |
| 报告 | `report.py` | 报告生成 |
| UI原型 | `ui_prototype.py`, `ui_prototype/` | 原型解析+管理 |
| 文件 | `file.py`, `file_*.py` | 文件上传/导出 |
| AI调用 | `ai_invocation.py` | AI接口代理 |
| Bug管理 | `bug.py` | 缺陷跟踪 |
| 审计 | `audit_log.py` | 操作审计 |
| 质量规则 | `quality_rule.py` | 质量规则配置 |
| Feature Flag | `feature_flag.py` | 运行时开关 |

### 3.7 Models (42个模型文件)
路径: `app/models/`

**核心模型关系链**:
```
User → Project → [TestCase, TestPoint, TestTask, Iteration, TestReport]
TestCase → TestStep → [ElementLocator, TestData]
TestCase → TestCaseVersion (版本管理)
TestCase → TestCasePreconditionStep (前置条件)
TestTask → TestResult → TestCase
UIPrototypeScreen ↔ TestCase (多对多)
Iteration → [IterationInput, PipelineRun] → PipelineStep → Artifact
```

**关键枚举** (`app/models/enums.py`):
- `TestCaseLifecycleStatus`: draft → active → pending_review → needs_modify → locator_broken → deprecated → archived
- `PipelineRunStatus`: pending → running → waiting_for_user → completed/failed/cancelled
- `IterationPipelineStatus`: draft → in_pipeline → in_review → finalized → archived
- `LocatorStatus`: pending → recorded / failed
- `CapabilityStatus`: active → deprecated → archived

### 3.8 Services (89个服务)
路径: `app/services/`

**核心服务分组**:

| 分组 | 服务 | 说明 |
|------|------|------|
| AI生成 | `case_generation/`, `test_case_generation/` | 用例AI生成 |
| Pipeline | `pipeline_service/`, `pipeline_permission_service.py`, `pipeline_timeout_service.py` | 流水线管理 |
| 质量 | `case_quality/`, `case_quality_analyzer.py`, `quality/` | 用例质量分析 |
| 元素定位 | `element_locator_service.py`, `element_locator/`, `batch_locator/`, `batch_locator_service.py` | UI元素定位 |
| 浏览器 | `browser_controller*.py` (utils/) | 浏览器自动化 |
| 文件解析 | `file_parser.py`, `file_extractor/`, `file_content_extractor.py` | 文档解析 |
| XMind | `xmind_parser/`, `xmind_import_service.py`, `xmind_ai_parser/` | XMind导入 |
| UI原型 | `ui_spec_parser.py`, `ui_spec_parser/`, `ui_spec_ocr.py`, `ui_spec_parse_pipeline.py` | UI原型解析 |
| 测试数据 | `test_data_generator.py`, `test_data_parameterizer/`, `test_data/` | 测试数据生成 |
| 执行引擎 | `test_execution_engine_v2.py`, `test_execution_engine/`, `execution_replay/` | 测试执行 |
| Prompt | `prompt_builder/`, `prompt_registry.py` | 提示词管理 |
| 用例生命周期 | `lifecycle_service/` | 状态流转 |
| 迁移 | `case_migration/` | 用例迁移 |
| 保鲜 | `case_refresh_service.py` | 用例保鲜建议 |
| 前置条件 | `precondition_service.py`, `precondition/` | 前置条件解析 |
| 成本统计 | `cost_statistics_service.py`, `cost_statistics/` | AI调用成本 |
| 调度 | `scheduler_service.py` | APScheduler定时任务 |
| 通知推送 | `push_service.py` | WebSocket推送 |
| 自测 | `self_test_service.py` | 自动化自测 |

### 3.9 Utils (33个工具)
路径: `app/utils/`

| 工具 | 文件 | 说明 |
|------|------|------|
| AI客户端 | `ai_client.py`, `ai_client_core.py`, `ai_client_enhanced/`, `ai_client_parser/`, `ai_client_stream/`, `ai_client_prompt.py`, `ai_client_formatter.py`, `ai_client_test_case.py` | AI调用封装 |
| 浏览器 | `browser_controller.py`, `browser_controller_v2.py`, `browser_controller_base.py`, `browser_controller_actions.py`, `browser_controller_navigation.py` | Playwright浏览器控制 |
| ADB | `adb_controller/` | Android设备控制 |
| OCR | `ocr_extractor.py` | 图像文字识别 |
| MCP | `playwright_mcp_client.py`, `mcp_text_llm.py` | Playwright MCP集成 |
| 视觉模型 | `unified_vision/`, `unified_vision_model/` | 统一视觉模型接口 |
| 加密 | `crypto.py`, `jwt_utils.py` | 加解密+JWT |
| HTTP | `http_utils.py`, `websocket.py` | HTTP/WebSocket工具 |
| 文件 | `file_utils.py` | 文件类型/处理 |
| 数据库 | `db_time.py` | UTC时间工具 |
| 用例 | `test_case_helpers.py`, `case_classifier.py` | 用例辅助函数 |
| 权限 | `permission_utils.py` | 权限检查 |
| 文本 | `text_similarity.py` | 文本相似度 |
| 环境 | `web_env_parser.py` | Web环境解析 |

---

## 四、前端技术栈详解

### 4.1 核心框架
| 组件 | 版本 | 说明 |
|------|------|------|
| Vue | 3.4 | 前端框架 (Composition API) |
| Vite | 5.0 | 构建工具 |
| TypeScript | 5.2 | 类型系统 (严格模式) |
| Element Plus | 2.8 | UI组件库 (按需导入) |
| Pinia | 2.1 | 状态管理 |
| Vue Router | 4.2 | 路由 (动态+权限) |
| Axios | 1.6 | HTTP客户端 |
| ECharts | 5.4 | 图表 |
| Vue Flow | 1.48 | 流程图编辑器 |

### 4.2 开发工具
| 组件 | 说明 |
|------|------|
| ESLint + Prettier | 代码规范 |
| unplugin-vue-components | Element Plus按需注册 |
| unplugin-auto-import | 自动导入 |
| sass-embedded | SCSS预处理 |
| Vitest | 单元测试 |
| Playwright | E2E测试 |

### 4.3 前端结构
```
src/
├── api/            # 30个API模块，按业务拆分
├── components/     # 通用组件 (analysis/case/report/xmind/testData)
├── composables/    # 43个组合式函数 (Flow/用例/执行/需求/任务)
├── constants/      # 常量定义
├── directives/     # 自定义指令 (权限)
├── layouts/        # 布局 (MainLayout)
├── router/         # 路由定义 (动态路由+权限守卫)
├── store/          # Pinia状态 (project/case/task/flowSort等)
├── styles/         # 全局样式
├── types/          # TypeScript类型
├── utils/          # 工具函数 (request/websocket/debounce/download)
└── views/          # 13个业务模块页面
```

### 4.4 页面路由结构
```
/login                    — 登录
/home/
  ├── /project            — 项目中心 (列表+详情)
  ├── /requirement        — 资源中心 (管理/上传/UI原型)
  ├── /analysis           — 需求分析
  ├── /case/              — 测试资产
  │   ├── /               — 用例列表
  │   ├── /smart-generate — 智能生成
  │   ├── /migration      — 用例迁移
  │   ├── /test-point-*   — 测试点管理/提取
  │   ├── /case-refresh   — 保鲜建议
  │   ├── /detail/:id     — 用例详情
  │   └── /quality/:id    — 质量分析
  ├── /task/              — 执行中心
  │   ├── /               — 任务列表
  │   ├── /create/:pid    — 创建任务
  │   ├── /detail/:tid    — 任务详情
  │   └── /execution/:tid — 测试执行
  ├── /report             — 报告中心
  ├── /iteration/         — 迭代中心 (Pipeline进度/回归变更)
  ├── /admin/             — 管理后台 (Pipeline仪表盘/AI成本)
  └── /system/            — 系统管理 (用户/角色/能力/审计/质量规则/FeatureFlag)
```

### 4.5 API请求架构 (`src/utils/request.ts`)
- 动态超时: 普通30s / AI接口180s / XMind导入300s / 上传60s
- Token自动注入: `localStorage.getItem('token')`
- 401自动跳转登录
- FailureEnvelope结构化错误处理
- FormData自动去除Content-Type

---

## 五、测试体系

### 5.1 后端测试 (pytest)
配置: `pytest.ini`
- 测试目录: `tests/` (155个文件)
- 标记: `unit` / `integration` / `api` / `slow` / `real_browser` / `real_api` / `regression`
- Mock DB: `tests/conftest.py` 事务级隔离 (session.flush替代commit, rollback隔离)
- 忽略: `test_browser_*.py` / `test_element_locator_*.py` / `test_execution_engine_*.py`

**测试结构**:
```
tests/
├── api/           # API端点测试
├── crud/          # CRUD操作测试
├── models/        # 模型单元测试
├── schemas/       # Schema验证测试
├── services/      # 服务层测试
├── pipelines/     # Pipeline测试
├── ai/            # AI客户端测试
├── e2e/           # 端到端测试
├── integration/   # 集成测试
├── regression/    # 回归测试
├── store/         # 前端Store测试
├── tasks/         # 后台任务测试
├── mocks/         # Mock数据
└── data/          # 测试数据
```

### 5.2 前端测试
- **Vitest**: 单元测试 (`npm run test`)
- **Playwright**: E2E测试 (`npm run test:e2e`, 用例目录 `e2e-playwright/`)

### 5.3 脚本工具 (49个)
路径: `scripts/`

| 分类 | 脚本 | 说明 |
|------|------|------|
| 数据库 | `db_health_check.py`, `comprehensive_db_check.py`, `repair_alembic_history.py`, `add_missing_columns.py` | 健康检查/修复 |
| 数据迁移 | `migrate_artifacts.py`, `migrate_add_prior_score.py`, `migrate_add_posterior_score.py` | 数据迁移 |
| 数据清理 | `cleanup_all_business_data.py`, `cleanup_audit_logs.py`, `delete_project_cases.py` | 数据清理 |
| 质量验证 | `verify_case_quality.py`, `verify_data_pipeline.py`, `verify_e2e_quality.py` | 质量验证 |
| 回归测试 | `regression_t9_t10.py` | 自动化回归 |
| 调试 | `debug_auth*.py`, `debug_ai_response.py` | 调试工具 |
| 背填 | `backfill_case_summary.py`, `backfill_testpoint_capability.py` | 数据补全 |
| 基线 | `collect_quality_baseline.py`, `collect_ai_cost_baseline.py` | 质量/成本基线 |
| 其他 | `seed_prompt_templates.py`, `sync_test_db.py`, `prepare_test_data.py` | 辅助工具 |

---

## 六、配置体系

### 6.1 环境配置 (`app/core/config.py`)
- 基类: `Settings(BaseSettings)` — 170+配置项
- 环境子类: `DevSettings` / `TestSettings` / `ProdSettings` (`app/core/settings_profiles.py`)
- 密钥管理: `app/core/key_management.py` — 自动检测并生成缺失密钥
- 加载优先级: 环境变量 > .env文件 > 类属性默认值

### 6.2 关键配置分组
| 分组 | 配置项 | 说明 |
|------|--------|------|
| 数据库 | `DATABASE_URL`, `DATABASE_URL_SLAVE`, `DB_POOL_SIZE` | 主从分离 |
| AI | `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL_NAME` | AI模型 |
| 视觉 | `VISION_MODEL_DEFAULT`, `QWEN_API_KEY`, `KIMI_API_KEY`等 | 多视觉模型 |
| Pipeline | `AI_TOKEN_BUDGET_PER_RUN`, `PIPELINE_PAUSE_TIMEOUT_DAYS` | Pipeline控制 |
| 生命周期 | `LIFECYCLE_DEPRECATE_COOLDOWN_HOURS`, `ARCHIVE_RETENTION_DAYS` | 用例生命周期 |
| XMind | `XMIND_AI_TIMEOUT`, `XMIND_AI_MAX_WORKERS` | XMind处理 |
| Celery | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | 任务队列 |
| MCP | `PLAYWRIGHT_MCP_ENABLED`, `MCP_DIRECT_EXECUTION_ENABLED` | Playwright MCP |

### 6.3 中间件
- **CORS**: 环境感知 (dev允许*, prod指定域名)
- **限流**: `RateLimitMiddleware` (prod 1000/min, dev 5000/min)
- **异常处理**: 6层异常处理器 (BaseAPI → HTTP → SQLAlchemy → Pydantic → RequestValidation → General)

---

## 七、数据流核心链路

### 7.1 用例生成流程
```
用户上传需求文件 → 文件解析(file_parser) → AI提取测试点(test_point_extract)
→ AI生成用例(test_case_ai) → 质量评估(case_quality) → 用户确认
→ 持久化(test_case CRUD) → 版本管理(test_case_version)
```

### 7.2 Pipeline执行流程
```
迭代创建 → Pipeline启动(pipeline_service) → Runner执行(runner.py)
→ Step1: 信号采集 → Step2: 正向扫描 → Step3: 反向扫描
→ Step4: 用例生成 → Step5: 质量门禁 → Step6: 去重
→ Step7: 持久化 → WebSocket推送进度 → 完成/暂停/失败
```

### 7.3 测试执行流程
```
创建任务 → 选择用例 → 执行模式选择(execution_mode_selector)
→ 浏览器自动化(browser_controller) / ADB移动端(adb_controller)
→ 元素定位(element_locator) + AI自愈(ai_self_healing)
→ 结果记录(test_result) → 报告生成(report_service)
```

---

## 八、排查问题关键路径

### 8.1 日志体系
- 后端: `loguru` (`app/core/logging.py`)
- 日志文件: `*_err.log` / `*_out.log` (根目录大量)
- WebSocket日志: `app/utils/websocket.py`

### 8.2 调试工具
- API测试: `scripts/debug_auth*.py`
- AI调试: `scripts/debug_ai_response.py`
- 健康检查: `GET /health` (检查DB/Redis/AI状态)
- 自测: `app/services/self_test_service.py`

### 8.3 常见问题定位
| 问题 | 排查路径 |
|------|----------|
| AI调用失败 | `app/ai/error_codes.py` → `app/ai/call_log.py` → config中的API Key |
| Pipeline失败 | `app/pipelines/runner.py` → `PipelineRun.status` → `PipelineStep.error` |
| 用例生成异常 | `app/services/case_generation/` → `app/ai/client.py` |
| 元素定位失败 | `app/services/element_locator/` → `ElementLocator.status` |
| 数据库问题 | `scripts/db_health_check.py` → `app/db/database/` |
| 前端请求异常 | `src/utils/request.ts` → FailureEnvelope → 后端 `_handlers.py` |
| WebSocket断连 | `app/utils/websocket.py` → `app/services/push_service.py` |

---

## 九、代码规范

### 后端
- **Linter**: Ruff (`ruff.toml` — rules: F/E/W/C90/SIM/UP, max-complexity=10, line-length=120)
- **格式化**: Black (通过 Alembic hook)
- **类型**: Python 3.10+, Pydantic v2

### 前端
- **Linter**: ESLint + Prettier (Airbnb Vue规范)
- **类型**: TypeScript严格模式
- **组件**: Element Plus按需导入 (unplugin-vue-components)

---

## 十、技术亮点与设计模式

1. **Pipeline Step Protocol**: 基于Protocol的Step接口，支持缓存/重试/降级/暂停/恢复
2. **AI Fallback**: 主备模型自动切换，Token预算控制
3. **事务级测试隔离**: pytest中session.flush替代commit，rollback隔离
4. **FailureEnvelope**: 结构化错误传递 (前端 ↔ 后端)
5. **多环境配置**: pydantic-settings + 环境变量优先级
6. **主从分离**: SQLAlchemy双引擎 + scoped_session
7. **WebSocket实时推送**: Pipeline进度 + 测试执行状态
8. **Feature Flag**: 运行时功能开关
9. **审计日志**: 全链路操作追踪
10. **用例生命周期状态机**: 7状态流转，强制通过LifecycleService
