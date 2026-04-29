# 迭代用例生成与维护流水线 — 任务追踪文档

> 配套规划文档：`iteration-pipeline-plan.md`。
> **每完成一个任务并自测通过后，更新本文档状态为 `✅ done` 再开始下一任务**。

---

## 文档信息

| 项 | 内容 |
|----|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-04-29 |
| 更新日期 | 2026-04-29 |
| 关联文档 | `iteration-pipeline-plan.md` |

---

## 状态图例

| 标记 | 含义 |
|:-:|---|
| ⬜ pending | 未开始 |
| 🔄 in_progress | 进行中 |
| ⏸️ blocked | 被阻塞（注明原因） |
| ✅ done | 已完成且自测通过 |
| ❌ skipped | 评估后决定不做（注明原因） |

---

## 总览

### M1 基础骨架（13 任务）

| ID | 标题 | 估时 | 依赖 | 状态 |
|:-:|---|:-:|:-:|:-:|
| M1-T01 | 创建文档目录与初始化 | 0.5d | — | ✅ done |
| M1-T02 | TestCapability 表与模型 | 0.5d | M1-T01 | ⬜ pending |
| M1-T03 | TestPoint 字段补齐 | 0.5d | M1-T02 | ⬜ pending |
| M1-T04 | TestCase 字段补齐 | 0.5d | M1-T02 | ⬜ pending |
| M1-T05 | LifecycleService 状态机 | 1d | M1-T04 | ⬜ pending |
| M1-T06 | Iteration / IterationInput 表 | 1d | M1-T01 | ⬜ pending |
| M1-T07 | PipelineRun / Artifact 表 | 1d | M1-T01 | ⬜ pending |
| M1-T08 | Pipeline 抽象层与 Runner | 2d | M1-T07 | ⬜ pending |
| M1-T09 | 历史用例 summary 回填命令 | 1d | M1-T04 | ⬜ pending |
| M1-T10 | 场景 1 流水线（PRD+测试点+UI） | 2d | M1-T05, M1-T08 | ⬜ pending |
| M1-T11 | 场景 2 流水线（PRD+测试点） | 1d | M1-T10 | ⬜ pending |
| M1-T12 | 用例列表前端：状态筛选+徽标 | 1d | M1-T05 | ⬜ pending |
| M1-T13 | M1 集成测试与文档收口 | 1d | 所有 M1 任务 | ⬜ pending |

### M2 双向扫描（12 任务）

| ID | 标题 | 估时 | 依赖 | 状态 |
|:-:|---|:-:|:-:|:-:|
| M2-T01 | IterationReview / ReviewDecision 表 | 1d | M1 完成 | ⬜ pending |
| M2-T02 | HistoryFingerprint Step | 1d | M1-T09 | ⬜ pending |
| M2-T03 | BackwardScan Prompt + Schema | 1d | M2-T02 | ⬜ pending |
| M2-T04 | BackwardScanService（批处理+重试） | 2d | M2-T03 | ⬜ pending |
| M2-T05 | ScenarioCandidateExtractor Step | 1d | M2-T02 | ⬜ pending |
| M2-T06 | ForwardScanService | 2d | M2-T05 | ⬜ pending |
| M2-T07 | ReconciliationService（合并矩阵） | 1d | M2-T04, M2-T06 | ⬜ pending |
| M2-T08 | 评审 Inbox 后端 API | 1d | M2-T01 | ⬜ pending |
| M2-T09 | 评审 Inbox 前端页 | 2d | M2-T08 | ⬜ pending |
| M2-T10 | 决策应用服务（落库+建版本） | 1.5d | M2-T07, M1-T05 | ⬜ pending |
| M2-T11 | 场景 4 端到端流水线 | 1.5d | M2-T07~T10 | ⬜ pending |
| M2-T12 | M2 集成测试与文档收口 | 1d | 所有 M2 任务 | ⬜ pending |

### M3 反推 + 补全（8 任务）

| ID | 标题 | 估时 | 依赖 | 状态 |
|:-:|---|:-:|:-:|:-:|
| M3-T01 | BusinessSummaryReverseInfer Service | 2d | M1 完成 | ⬜ pending |
| M3-T02 | 信号补全表单后端 | 1d | M3-T01 | ⬜ pending |
| M3-T03 | 信号补全表单前端 | 1.5d | M3-T02 | ⬜ pending |
| M3-T04 | 强制确认门槛 UI 框架 | 1.5d | M3-T03 | ⬜ pending |
| M3-T05 | TestPointAlignment Step | 1d | M3-T01 | ⬜ pending |
| M3-T06 | 场景 3 流水线 | 1.5d | M3-T04 | ⬜ pending |
| M3-T07 | 场景 5 流水线 | 1.5d | M3-T01, M2 完成 | ⬜ pending |
| M3-T08 | M3 集成测试与文档收口 | 1d | 所有 M3 任务 | ⬜ pending |

### M4 质量与运营（7 任务）

| ID | 标题 | 估时 | 依赖 | 状态 |
|:-:|---|:-:|:-:|:-:|
| M4-T01 | 先验质量分服务 | 1d | M1 完成 | ⬜ pending |
| M4-T02 | 后验质量分回填任务 | 1d | M2 完成 | ⬜ pending |
| M4-T03 | 用例血缘 API | 1d | M1-T04 | ⬜ pending |
| M4-T04 | 用例血缘前端可视化 | 1.5d | M4-T03 | ⬜ pending |
| M4-T05 | FMEA 监控埋点 | 1.5d | M3 完成 | ⬜ pending |
| M4-T06 | 成本/性能仪表盘 | 1.5d | M4-T05 | ⬜ pending |
| M4-T07 | M4 集成测试与文档收口 | 1d | 所有 M4 任务 | ⬜ pending |

**总计：40 个任务，约 50 人/日。**

---

# M1 基础骨架

## M1-T01: 创建文档目录与初始化

- **Status**: ✅ done
- **Estimate**: 0.5d
- **Depends on**: —
- **Description**: 落地规划与任务追踪文档。
- **Deliverables**:
  - `docs/iteration-pipeline-plan.md`
  - `docs/iteration-pipeline-tasks.md`（本文档）
- **Acceptance**:
  - [x] 两个 md 文档已创建并 review
  - [x] 任务列表完整覆盖 M1~M4
  - [x] 状态图例与流程已说明
- **Self-Test**:
  1. 文件存在且可正常打开。
  2. 任务编号无重复、依赖关系合理。
- **Notes**:
  - 后续每个任务完成都更新本文档状态。

---

## M1-T02: TestCapability 表与模型

- **Status**: ⬜ pending
- **Estimate**: 0.5d
- **Depends on**: M1-T01
- **Description**: 引入"业务能力"作为最稳定的层级实体。所有 TestPoint 必须挂在某个 Capability 下。

- **Deliverables**:
  - Alembic migration: `alembic/versions/xxxx_add_test_capability.py`
  - 模型: `app/models/test_capability.py`
  - 字段: `id, project_id (FK), key (unique within project), title, description, status, created_at, updated_at`
  - 索引: `(project_id, key)` unique；`(project_id, status)`
  - Pydantic schema: `app/schemas/test_capability.py`
  - 基础 CRUD service: `app/services/test_capability_service.py`

- **Acceptance**:
  - [ ] 迁移可正向 / 反向执行（`alembic upgrade head` / `alembic downgrade -1`）
  - [ ] 同 project_id 下 key 重复创建抛唯一约束错误
  - [ ] 单测覆盖：创建、查询、按 project 列表、按 status 过滤
  - [ ] 不引入 API 端点（M1 阶段仅服务层）

- **Self-Test**:
  ```powershell
  # 1. 迁移
  alembic upgrade head
  alembic downgrade -1
  alembic upgrade head
  
  # 2. 单测
  pytest tests/services/test_capability_service.py -v
  
  # 3. 验证
  python -c "from app.services.test_capability_service import create; print(create(...))"
  ```

- **Notes**:
  - `status` 枚举：`active`, `deprecated`, `archived`
  - `key` 用于跨迭代稳定标识，title 可演进

---

## M1-T03: TestPoint 字段补齐

- **Status**: ⬜ pending
- **Estimate**: 0.5d
- **Depends on**: M1-T02
- **Description**: 给现有 `test_point` 表加 capability 关联与版本/状态字段，保持向后兼容。

- **Deliverables**:
  - migration:
    - `ADD COLUMN capability_id INT FK NULL`
    - `ADD COLUMN version INT DEFAULT 1`
    - `ADD COLUMN status ENUM('draft','active','deprecated','archived') DEFAULT 'active'`
    - 索引 `(capability_id, status)`
  - 数据回填脚本：每个 project 创建一个 `default` capability，把所有现有 test_point 关联到它
  - 模型 `app/models/test_point.py` 字段更新
  - 单测：旧数据加载、新字段读写

- **Acceptance**:
  - [ ] 旧用例查询接口（list / detail）行为不变
  - [ ] 所有现有 test_point.capability_id 不为 NULL
  - [ ] 新建 test_point 默认 status=active, version=1
  - [ ] 单测覆盖回填脚本

- **Self-Test**:
  ```powershell
  alembic upgrade head
  python scripts/backfill_testpoint_capability.py --dry-run
  python scripts/backfill_testpoint_capability.py
  
  # 验证：
  python -c "
  from app.db import SessionLocal
  from app.models.test_point import TestPoint
  db = SessionLocal()
  cnt = db.query(TestPoint).filter(TestPoint.capability_id == None).count()
  assert cnt == 0, f'still {cnt} testpoints without capability'
  print('OK')
  "
  
  pytest tests/models/test_test_point.py -v
  ```

- **Notes**:
  - 回填脚本必须**幂等**：重复运行不重复创建 default capability
  - 数据量大时支持分批 commit（每 1000 条）

---

## M1-T04: TestCase 字段补齐

- **Status**: ⬜ pending
- **Estimate**: 0.5d
- **Depends on**: M1-T02
- **Description**: 给 `test_case` 表加生命周期状态、指纹、血缘字段。

- **Deliverables**:
  - migration:
    - `ADD COLUMN test_point_id INT FK NULL`（强制挂测试点，初期允许 null 兼容）
    - `ADD COLUMN lifecycle_status ENUM('draft','active','pending_review','needs_modify','locator_broken','deprecated','archived') DEFAULT 'active'`
    - `ADD COLUMN summary TEXT NULL`
    - `ADD COLUMN summary_version INT DEFAULT 0`
    - `ADD COLUMN summary_model_version VARCHAR(64) NULL`
    - `ADD COLUMN parent_case_id INT FK NULL`
    - `ADD COLUMN last_review_id INT FK NULL`
    - 索引 `(project_id, lifecycle_status)`、`(test_point_id)`、`(parent_case_id)`
  - 模型字段更新
  - 数据回填：所有 lifecycle_status 默认 active，summary_version=0

- **Acceptance**:
  - [ ] 现有用例查询接口行为不变
  - [ ] 状态枚举完整覆盖设计文档中的 7 个状态
  - [ ] 列表筛选支持 `lifecycle_status` 参数
  - [ ] 单测：每种状态的用例可正常 CRUD

- **Self-Test**:
  ```powershell
  alembic upgrade head
  
  # 验证字段存在
  python -c "
  from app.models.test_case import TestCase
  assert hasattr(TestCase, 'lifecycle_status')
  assert hasattr(TestCase, 'summary')
  assert hasattr(TestCase, 'parent_case_id')
  print('OK')
  "
  
  # 接口冒烟
  curl http://localhost:8000/api/v1/testCase/list?project_id=1
  ```

- **Notes**:
  - 不在本任务实现状态变更逻辑，留给 M1-T05
  - `summary_model_version` 用于跟踪 AI 模型升级触发的批量重算

---

## M1-T05: LifecycleService 状态机

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T04
- **Description**: 集中管理用例 lifecycle_status 迁移，所有变更必经此服务。

- **Deliverables**:
  - `app/services/lifecycle_service.py`，主接口：
    - `transition(case_id, to_status, *, review_id=None, reason=None, actor_id=None) -> TestCase`
    - `can_transition(from_status, to_status) -> bool`
  - 异常：`IllegalStateTransition`, `MissingReviewError`, `CooldownNotElapsedError`
  - 完整迁移规则表（在 service 模块顶部以常量声明）
  - 单测 `tests/services/test_lifecycle_service.py`，覆盖：
    - 所有合法迁移路径（每条至少一例）
    - 所有非法迁移（应抛错）
    - `active → needs_modify` 不带 review_id 抛错
    - `needs_modify → modified` 必须创建新 case 版本
    - `deprecated → archived` 24h 内拒绝
  - 在 `TestCase` 模型加 SQLAlchemy event hook，禁止直接 update lifecycle_status（必须通过 service）

- **Acceptance**:
  - [ ] 单测全绿，分支覆盖率 ≥ 95%
  - [ ] 直接 SQL UPDATE lifecycle_status 触发 event hook 警告/抛错
  - [ ] 所有迁移产生审计日志（debug log，M1 阶段先这样，M2 接到 review_decision）
  - [ ] 无现有功能回归

- **Self-Test**:
  ```powershell
  pytest tests/services/test_lifecycle_service.py -v --cov=app.services.lifecycle_service
  
  # 手动验证
  python -c "
  from app.services.lifecycle_service import transition, IllegalStateTransition
  try:
      transition(case_id=1, to_status='deprecated')  # 缺 review_id
      assert False
  except IllegalStateTransition:
      print('OK')
  "
  ```

- **Notes**:
  - 冷却时间从配置读：`settings.LIFECYCLE_DEPRECATE_COOLDOWN_HOURS`，默认 24
  - `modified` 是逻辑终态，实际数据库不存这个 status（旧 case 直接 → archived，新 case 进 active）
  - 实现细节决策记录在本任务 Notes 段

---

## M1-T06: Iteration / IterationInput 表

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T01
- **Description**: 引入"迭代"作为流水线运行的根上下文。

- **Deliverables**:
  - migration:
    - `iteration(id, project_id FK, name, base_iteration_id FK NULL, status, created_by, created_at, finalized_at NULL)`
    - `iteration_input(id, iteration_id FK, kind ENUM('prd','prototype','xmind','testpoint','supplement_form'), file_id FK NULL, payload JSON NULL, hash, uploaded_at)`
    - 索引 `(project_id, status)`、`(iteration_id, kind)`
  - 模型: `app/models/iteration.py`
  - Service: `app/services/iteration_service.py`
    - `create_iteration(project_id, name, base_iteration_id?)`
    - `add_input(iteration_id, kind, file_id?, payload?)`
    - `list_iterations(project_id)`
    - `finalize_iteration(iteration_id)`
  - API 端点（最小集合）:
    - `POST /api/v1/iteration` - 创建
    - `GET /api/v1/iteration/list?project_id=` - 列表
    - `GET /api/v1/iteration/{id}` - 详情（含 inputs）
    - `POST /api/v1/iteration/{id}/inputs` - 添加输入
  - Pydantic schema 完整

- **Acceptance**:
  - [ ] 同 project 下 iteration name 唯一约束
  - [ ] base_iteration_id 校验：必须属于同 project，且 status='finalized'
  - [ ] file_id 引用 `requirement_file` 或新统一附件表（按现有架构选择）
  - [ ] 端点 e2e 测试通过

- **Self-Test**:
  ```powershell
  alembic upgrade head
  pytest tests/api/test_iteration.py -v
  
  # 接口冒烟
  curl -X POST http://localhost:8000/api/v1/iteration \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"project_id": 1, "name": "v1.5"}'
  ```

- **Notes**:
  - `status` 枚举: `draft, in_pipeline, in_review, finalized, archived`
  - `payload` 字段用于存非文件型输入（如补充表单 JSON）
  - file_id 关联到现有 requirement_file 表（如已存在），否则新建统一附件表

---

## M1-T07: PipelineRun / PipelineStep / Artifact 表

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T01
- **Description**: 落地 Pipeline 运行与产物的持久化基础设施，确保幂等与可重放。

- **Deliverables**:
  - migration:
    - `pipeline_run(id, iteration_id FK, input_hash VARCHAR(64), pipeline_version VARCHAR(32), status, started_at, finished_at, error TEXT NULL)`
    - `pipeline_step(id, run_id FK, step_name, step_version, status, cache_key VARCHAR(64), input_artifact_ids JSON, output_artifact_ids JSON, started_at, finished_at, error TEXT, retried_count INT, degraded BOOL)`
    - `artifact(id, run_id FK, kind, schema_version VARCHAR(32), payload JSON, confidence FLOAT, provenance JSON, hash VARCHAR(64), created_at)`
    - 索引: `pipeline_step.cache_key`、`artifact.hash`、`pipeline_run.iteration_id`
  - 模型 + 基础 CRUD service
  - 工具函数：
    - `compute_input_hash(iteration_inputs) -> str`
    - `compute_cache_key(step_name, step_version, input_artifact_hashes) -> str`
    - `find_cached_step(cache_key) -> PipelineStep | None`

- **Acceptance**:
  - [ ] 相同输入 hash 创建 PipelineRun 时返回旧 run（不重新创建）
  - [ ] 同 cache_key 已有 done 状态 step → 返回缓存
  - [ ] artifact.hash 唯一约束防止重复落库
  - [ ] 单测覆盖缓存命中、缓存失效、并发写入

- **Self-Test**:
  ```powershell
  alembic upgrade head
  pytest tests/services/test_pipeline_storage.py -v
  
  # 模拟两次同输入运行，第二次应命中缓存
  python -m scripts.test_pipeline_idempotency
  ```

- **Notes**:
  - artifact.payload JSON 大小可能较大（指纹列表、verdicts），考虑用 LONGTEXT
  - pipeline_version 用于 Pipeline 整体升级时强制重跑
  - 暂不引入分布式锁（M1 单进程）

---

## M1-T08: Pipeline 抽象层与 Runner

- **Status**: ⬜ pending
- **Estimate**: 2d
- **Depends on**: M1-T07
- **Description**: 实现 Pipeline 框架本体（Step 接口 + Runner + 缓存 + 重试 + 失败兜底）。

- **Deliverables**:
  - `app/pipelines/__init__.py`
  - `app/pipelines/base.py`:
    ```python
    class PipelineStep(Protocol):
        name: ClassVar[str]
        version: ClassVar[str]
        requires: ClassVar[list[str]]
        produces: ClassVar[list[str]]
        
        def should_run(self, ctx: PipelineContext) -> bool: ...
        def cache_key(self, ctx: PipelineContext) -> str: ...
        def execute(self, ctx: PipelineContext) -> StepResult: ...
        def validate_output(self, output: Artifact) -> bool: ...
        def fallback(self, ctx, error) -> StepResult | None: ...
    ```
  - `app/pipelines/runner.py`:
    - `PipelineRunner.run(iteration_id, steps: list[PipelineStep], dry_run=False)`
    - 重试逻辑（3 次指数退避）
    - 缓存命中检查
    - 中断恢复（从最近完成 step 续跑）
    - dry_run 模式（只评估 should_run 与 cache 命中情况，不执行 AI）
  - `app/pipelines/context.py`:
    - `PipelineContext`：当前运行状态、产物访问、AI client、db session
  - 一个示例 dummy step `EchoStep` 用于测试框架本身
  - 单测：
    - 缓存命中跳过 execute
    - 失败重试 3 次后调用 fallback
    - 中断恢复正确性
    - dry_run 不写 db
    - degraded 状态传递

- **Acceptance**:
  - [ ] 单测分支覆盖率 ≥ 90%
  - [ ] EchoStep 跑两次第二次零 AI 调用
  - [ ] 一次 run 中间 kill 进程，重启后从断点续跑
  - [ ] dry_run 模式输出执行计划但不落库

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/ -v
  
  # 压测
  python -m scripts.test_pipeline_runner --steps 10 --runs 100
  ```

- **Notes**:
  - 暂不支持 step 并行（M1 串行就够）
  - PipelineContext 内部访问 db 用 session 传入，避免全局状态
  - `dry_run` 输出 JSON 计划，便于前端可视化
  - Step `version` 属性变更视为新 step（强制重跑）

---

## M1-T09: 历史用例 summary 回填命令

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T04
- **Description**: 一次性脚本，给现有所有用例提炼 summary 并回填。可按 project 增量执行。

- **Deliverables**:
  - `scripts/backfill_case_summary.py`
    - 参数：`--project-id`, `--limit`, `--dry-run`, `--force`(忽略已有 summary)
    - 批处理：每 20 条用例调一次 AI（同一 prompt）
    - 失败兜底：AI 失败的用例标 summary='[FALLBACK] {case_no}: {title}'
    - 写入 `summary` + `summary_version` + `summary_model_version`
    - 进度条 + 中断恢复（基于 summary_version=0 筛选）
  - 单测（mock AI client）
  - 文档：scripts/README.md 增加使用说明

- **Acceptance**:
  - [ ] dry-run 不写 db，只输出每条预生成的 summary
  - [ ] 中断后重跑只处理 summary IS NULL 或 summary_version < TARGET 的用例
  - [ ] 同一用例多次回填不重复消耗 AI（基于 model_version 判断）
  - [ ] 失败用例不阻塞其他用例

- **Self-Test**:
  ```powershell
  python scripts/backfill_case_summary.py --project-id 1 --dry-run
  python scripts/backfill_case_summary.py --project-id 1 --limit 50
  
  # 中断恢复
  python scripts/backfill_case_summary.py --project-id 1
  # Ctrl+C
  python scripts/backfill_case_summary.py --project-id 1  # 应继续
  
  # 验证
  python -c "
  from app.db import SessionLocal
  from app.models.test_case import TestCase
  db = SessionLocal()
  null_cnt = db.query(TestCase).filter(TestCase.project_id==1, TestCase.summary==None).count()
  print(f'remaining: {null_cnt}')
  "
  ```

- **Notes**:
  - summary 长度建议 ≤ 200 字（业务摘要 + 关键步骤动词）
  - 当前模型版本写入 `settings.AI_MODEL_VERSION`
  - 大项目（>5000 用例）建议先按 module 分批

---

## M1-T10: 场景 1 流水线（PRD + 测试点 + UI）

- **Status**: ⬜ pending
- **Estimate**: 2d
- **Depends on**: M1-T05, M1-T08
- **Description**: 把现有 AI 生成接口编排为 Pipeline Steps，跑通场景 1（新项目，输入齐全）。

- **Deliverables**:
  - `app/pipelines/steps/signal_gatherer.py` (S1)
  - `app/pipelines/steps/testpoint_alignment.py` (S5 简化版：只做用户测试点 vs UI 一致性提示)
  - `app/pipelines/steps/case_generation.py` (S11)
  - `app/pipelines/steps/quality_gate.py` (S12 简化版：只算先验质量分)
  - `app/pipelines/steps/persist.py` (S13)
  - `app/pipelines/scenarios/scenario_1.py`：组装 Pipeline = [S1, S5, S11, S12, S13]
  - API: `POST /api/v1/iteration/{id}/pipeline/run`，body `{scenario: 1, ...}`
  - 端点返回 `pipeline_run_id`，支持 polling `GET /api/v1/pipeline/{run_id}`

- **Acceptance**:
  - [ ] 上传 (PRD + 测试点 + UI) → 触发 → 用例落库 → lifecycle_status=draft
  - [ ] 单测：每个 Step 独立可测
  - [ ] e2e 测试：完整跑通一个迭代
  - [ ] 重复触发命中缓存（artifact 复用）
  - [ ] AI 失败时正确标 degraded 并继续

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_scenario_1.py -v
  
  # e2e
  python -m scripts.e2e_scenario_1 --project-id 1
  ```

- **Notes**:
  - 复用现有 AI 生成 service，封装为 Step（不重写）
  - Step 输出统一 Artifact 形态，便于后续 Step 串联
  - 用例生成时 `lifecycle_status='draft'`，需用户手动批准转 active（M1 暂时自动转 active，留 TODO）

---

## M1-T11: 场景 2 流水线（PRD + 测试点）

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T10
- **Description**: 在场景 1 基础上去掉 UI 输入，生成的用例 locator 字段标 pending。

- **Deliverables**:
  - `app/pipelines/scenarios/scenario_2.py`
  - 修改 `case_generation.py` 支持 `has_ui=False` 分支：业务视图完整、技术视图 locator_status=pending
  - API 同 M1-T10，body `{scenario: 2}`
  - 用例列表前端：`locator_status=pending` 用例展示提示徽标

- **Acceptance**:
  - [ ] 不传 UI 时不报错，正常生成
  - [ ] 生成用例的 step.has_locator=0，locator_status=pending
  - [ ] e2e 跑通

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_scenario_2.py -v
  python -m scripts.e2e_scenario_2 --project-id 1
  ```

- **Notes**:
  - 场景 2 与场景 1 共享 90% Step
  - UI 缺失检测在 SignalGatherer 完成

---

## M1-T12: 用例列表前端：状态筛选 + 徽标

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T05
- **Description**: 让用户在列表页能基于 lifecycle_status 筛选与可视化。

- **Deliverables**:
  - `src/views/case/TestCaseList.vue` 增加：
    - 筛选器：`lifecycle_status` 多选（active / needs_modify / locator_broken / deprecated）
    - 列表行徽标：
      - active → 绿色"可用"
      - needs_modify → 橙色"待修改"
      - locator_broken → 黄色"待重录"
      - deprecated → 灰色"已弃用"
      - pending_review → 蓝色"评审中"
  - `src/views/case/CaseDetail.vue`：
    - 显示当前 lifecycle_status
    - 显示历史变更（M1 阶段简单 timeline，数据来自 review_decision，M2 完整化）
  - 后端 list 接口 `?lifecycle_status=` 参数支持多值

- **Acceptance**:
  - [ ] 筛选器 UI 与现有筛选样式一致
  - [ ] 状态徽标颜色与设计稿一致
  - [ ] 默认筛选 `active`，避免 deprecated 干扰用户
  - [ ] 多选筛选支持

- **Self-Test**:
  - 浏览器打开列表页，切换筛选验证结果集
  - 详情页验证状态展示
  - 控制台无错误

- **Notes**:
  - 默认筛选 active 是产品决策，写入 Notes 备查
  - timeline 数据 M1 阶段可用 audit log；M2 接 review_decision

---

## M1-T13: M1 集成测试与文档收口

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: 所有 M1 任务
- **Description**: 端到端验证 M1 所有能力，更新文档。

- **Deliverables**:
  - `tests/integration/test_m1_e2e.py`：场景 1 + 场景 2 完整跑通
  - 更新 `iteration-pipeline-plan.md` 中的"实现进度"段（如有偏离设计）
  - 更新本文档 M1 所有任务状态为 done
  - ADR 记录：M1 期间任何重大设计偏离

- **Acceptance**:
  - [ ] 所有 M1 单测、集成测试绿
  - [ ] 一个真实小项目（10 用例）能完整跑场景 1 出 active 用例
  - [ ] M1 涉及的所有 API 在 Swagger 中可见且可调用

- **Self-Test**:
  ```powershell
  pytest tests/ -v --cov=app
  python -m scripts.smoke_test_m1
  ```

- **Notes**:
  - M1 的目标是"骨架可用"，不追求场景多样
  - 任何遗留问题写入"M1 已知问题"段，由后续里程碑接手

---

# M2 双向扫描

## M2-T01: IterationReview / ReviewDecision 表

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1 完成
- **Description**: 引入评审快照与不可变决策记录。

- **Deliverables**:
  - migration:
    - `iteration_review(id, iteration_id FK, kind ENUM('forward','backward','merged'), status ENUM('draft','in_progress','finalized','cancelled'), created_at, finalized_at NULL, finalized_by FK NULL)`
    - `review_decision(id, review_id FK, target_kind ENUM('case','testpoint','capability'), target_id, target_version, ai_verdict, ai_confidence, ai_reason, modification_hint TEXT, deprecate_reason TEXT, human_verdict NULL, human_user_id FK NULL, human_reason TEXT NULL, final_verdict, decided_at, conflict_marker BOOL DEFAULT 0, accepted_low_confidence BOOL DEFAULT 0)`
    - `review_lock(review_id FK, target_kind, target_id, locked_at, expires_at)` 评审期独占锁
  - 模型 + service `app/services/review_service.py`
  - **不可变性**：`review_decision` 表禁止 update（用 trigger 或 ORM 层 enforce）

- **Acceptance**:
  - [ ] 修改已 finalize 的 decision 抛错
  - [ ] 同一 (target_kind, target_id) 在不同 review 锁定期内不能同时被锁定
  - [ ] 锁过期自动失效（24h TTL）

- **Self-Test**:
  ```powershell
  alembic upgrade head
  pytest tests/services/test_review_service.py -v
  ```

- **Notes**: 见 plan §3.2 不可变 audit log。

---

## M2-T02: HistoryFingerprint Step

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T09
- **Description**: 把已有 summary 包装成 Pipeline Step 输入产物，按需增量更新。

- **Deliverables**:
  - `app/pipelines/steps/history_fingerprint.py`
  - 输出 Artifact: `kind=history_fingerprints`，payload 为列表
  - 支持按 module 过滤
  - 检测过期 summary（model_version mismatch）→ 触发增量重算（调用 M1-T09 脚本逻辑）

- **Acceptance**:
  - [ ] 全部 summary 已存在时 Step 0 AI 调用
  - [ ] 部分缺失时只跑缺失部分
  - [ ] payload 大小受控（>1000 用例时分页或仅传指定 module）

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_history_fingerprint.py -v
  ```

- **Notes**: —

---

## M2-T03: BackwardScan Prompt + Schema

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M2-T02
- **Description**: 设计反向扫描 prompt 与输出 JSON Schema，准备喂给 LLM。

- **Deliverables**:
  - `app/pipelines/prompts/backward_scan.py`：prompt 模板（见 plan §4.2）
  - `app/pipelines/schemas/backward_verdict.py`：Pydantic 输出 schema
  - 校验函数：`validate_backward_output(raw, expected_case_ids) -> ValidationResult`
  - 单测覆盖 5 种 verdict + 校验失败场景

- **Acceptance**:
  - [ ] Schema 字段完整（plan §4.2 列举）
  - [ ] 校验函数捕获：缺 case_id、verdict 越界、confidence 越界、缺 hint
  - [ ] confidence < 0.7 自动改 verdict=UNCERTAIN

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_backward_schema.py -v
  ```

- **Notes**: 模板支持模块切片占位符。

---

## M2-T04: BackwardScanService（批处理 + 重试）

- **Status**: ⬜ pending
- **Estimate**: 2d
- **Depends on**: M2-T03
- **Description**: 反向扫描的执行引擎，含批处理、重试、降级。

- **Deliverables**:
  - `app/pipelines/steps/backward_scan.py`：包装为 Step
  - 内部 service `BackwardScanService`：
    - 按模块切片
    - 50 用例/批
    - 每批：调 AI → 校验 → 失败重试（3 次 → 切半 → 单条 → 标 UNCERTAIN）
    - 输出聚合 verdicts
  - 输出 Artifact: `kind=backward_verdicts`
  - 单测（mock AI）+ 集成测试（真实 AI 小批量）
  - 性能测试：100 用例端到端 < 60s（视模型而定）

- **Acceptance**:
  - [ ] 无效 JSON 触发重试机制
  - [ ] 重试 3 次仍失败 → 该批切半重跑
  - [ ] 单条仍失败 → 标 UNCERTAIN + degraded
  - [ ] 缓存命中跳过 AI

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_backward_scan.py -v
  python -m scripts.bench_backward_scan --case-count 100
  ```

- **Notes**: 注意 token 总数监控，做日志埋点。

---

## M2-T05: ScenarioCandidateExtractor Step

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M2-T02
- **Description**: 从新 PRD/UI 抽出"候选场景列表"（短描述，未展开步骤）。

- **Deliverables**:
  - `app/pipelines/steps/scenario_candidates.py`
  - prompt: "看这些原型/PRD，输出候选测试场景（每条 ≤30字 + 模块归属）"
  - 输出 Artifact: `kind=scenario_candidates`
  - 单测

- **Acceptance**:
  - [ ] 输出 JSON 严格 schema
  - [ ] 候选数量 ≥ UI 关键控件数量的 30%（启发式校验）
  - [ ] 模块归属与现有 module 体系一致

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_scenario_candidates.py -v
  ```

- **Notes**: —

---

## M2-T06: ForwardScanService

- **Status**: ⬜ pending
- **Estimate**: 2d
- **Depends on**: M2-T05
- **Description**: 把候选场景与历史指纹做匹配，输出 EXISTING/MODIFY/NEW 标签。

- **Deliverables**:
  - `app/pipelines/steps/forward_scan.py`
  - 两段式：
    - 粗筛：embedding 余弦相似度（用本地 sentence-transformers 或现有 embedding 服务）
    - 精筛：LLM 对每个候选 + 召回的 top-5 历史指纹判定
  - 输出 Artifact: `kind=forward_verdicts`
  - 单测 + 集成测试

- **Acceptance**:
  - [ ] embedding 召回 top-5 准确率 ≥ 80%（用人工标注样本验证）
  - [ ] 精筛输出包含 matched_case_id + reason
  - [ ] 缓存粒度到候选场景级别（同一场景跨 run 不重算）

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_forward_scan.py -v
  python -m scripts.eval_forward_scan_recall
  ```

- **Notes**:
  - 是否引入向量库（chroma/pgvector）作为本任务 ADR
  - 简化版：先用 sklearn 内存余弦，规模上来再换

---

## M2-T07: ReconciliationService（合并矩阵）

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M2-T04, M2-T06
- **Description**: 实现双向扫描合并矩阵，输出最终标签。

- **Deliverables**:
  - `app/pipelines/steps/reconciliation.py`
  - 合并表常量（与 plan §6 一致）
  - 输出 Artifact: `kind=merged_verdicts`
  - 单测：每个矩阵格子至少 1 例，包含红色冲突路径

- **Acceptance**:
  - [ ] 矩阵覆盖完整（DEPRECATED × EXISTING/MODIFY 等冲突格强制 conflict_marker=true）
  - [ ] 单测覆盖率 100%
  - [ ] 输出包含 reason，便于审计

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_reconciliation.py -v
  ```

- **Notes**: 矩阵抽成纯函数，无副作用，便于单测。

---

## M2-T08: 评审 Inbox 后端 API

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M2-T01
- **Description**: 评审 Inbox 的 CRUD API。

- **Deliverables**:
  - `GET /api/v1/review/{id}/decisions` - 列表（支持按 verdict 过滤、按 confidence 排序）
  - `POST /api/v1/review/{id}/decisions/{decision_id}/decide` - 提交人工决策
  - `POST /api/v1/review/{id}/decisions/batch-decide` - 批量决策
  - `POST /api/v1/review/{id}/finalize` - 最终化评审（触发决策应用）
  - 锁机制：决策时 acquire lock，finalize 后 release

- **Acceptance**:
  - [ ] 决策提交后 review_decision 写入但 final_verdict 待 finalize 才算数
  - [ ] finalize 后无法再修改决策
  - [ ] 锁冲突返回 409
  - [ ] 批量决策原子性（部分失败回滚）

- **Self-Test**:
  ```powershell
  pytest tests/api/test_review_inbox.py -v
  ```

- **Notes**: —

---

## M2-T09: 评审 Inbox 前端页

- **Status**: ⬜ pending
- **Estimate**: 2d
- **Depends on**: M2-T08
- **Description**: 评审决策的批量操作 UI。

- **Deliverables**:
  - `src/views/iteration/ReviewInbox.vue`
  - 路由 `/iteration/:iterationId/review/:reviewId`
  - 功能：
    - 按 verdict 分组 tab（VALID / NEEDS_MODIFY / DEPRECATED / UNCERTAIN）
    - 每行显示：用例标题、AI verdict、confidence 进度条、reason、modification_hint（折叠）
    - 单条决策按钮：采纳 / 否决 / 修改后采纳 / 推迟
    - 批量操作：全选采纳 confidence ≥ 0.85 的
    - 红色冲突项置顶 + 红色边框
    - finalize 按钮（带二次确认）

- **Acceptance**:
  - [ ] 设计稿与现有 element-plus 风格一致
  - [ ] 单条决策耗时（中位）< 10s
  - [ ] 锁冲突 409 时友好提示
  - [ ] finalize 后跳转用例列表

- **Self-Test**:
  - 手动跑场景 4 evaluation，进入评审页操作
  - 浏览器无错误日志

- **Notes**: —

---

## M2-T10: 决策应用服务（落库 + 建版本）

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M2-T07, M1-T05
- **Description**: 评审 finalize 后，把 final_verdict 应用到用例（状态迁移、创建新版本）。

- **Deliverables**:
  - `app/services/decision_application_service.py`
    - `apply_review(review_id)`：遍历 finalized decisions，逐条应用
    - VALID → 不动
    - LOCATOR_ONLY → status='locator_broken'，加入批量录制队列
    - NEEDS_MODIFY → 创建新版本（parent_case_id 指向旧），新版本进 'pending_review'，旧版本 archived
    - DEPRECATED → 'deprecated'（24h 后可走 archived）
    - NEW → 触发 case_generation Step 增量生成
  - 全程通过 LifecycleService（M1-T05）
  - 集成测试覆盖每种路径

- **Acceptance**:
  - [ ] 应用结果与 review_decision 完全一致
  - [ ] 所有用例状态变更可在 review_decision 中追溯
  - [ ] 失败时回滚（事务）

- **Self-Test**:
  ```powershell
  pytest tests/services/test_decision_application.py -v
  ```

- **Notes**: —

---

## M2-T11: 场景 4 端到端流水线

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M2-T07~T10
- **Description**: 组装场景 4 完整 Pipeline 并跑通。

- **Deliverables**:
  - `app/pipelines/scenarios/scenario_4.py`：组装 [S1, S2, S5, S6, S7, S8, S9, S10预览, S11, S12, S13]
  - API 接口对接
  - e2e 测试

- **Acceptance**:
  - [ ] 一个有 50 历史用例的项目跑场景 4 → 输出 review → 评审 → 落库
  - [ ] 全程不超过 5 分钟（不算人工评审）
  - [ ] Pipeline 中断可恢复

- **Self-Test**:
  ```powershell
  python -m scripts.e2e_scenario_4 --project-id 1
  ```

- **Notes**: —

---

## M2-T12: M2 集成测试与文档收口

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: 所有 M2 任务
- **Description**: M2 端到端验证。

- **Deliverables**:
  - `tests/integration/test_m2_e2e.py`
  - 更新本文档 M2 状态
  - ADR 记录设计偏差

- **Acceptance**: 同 M1-T13 模式。

- **Self-Test**: 同 M1-T13 模式。

---

# M3 反推 + 补全

## M3-T01: BusinessSummaryReverseInfer Service

- **Status**: ⬜ pending
- **Estimate**: 2d
- **Depends on**: M1 完成
- **Description**: 从 UI 原型（+ 历史指纹，旧项目）反推业务摘要 / 业务变更摘要。

- **Deliverables**:
  - `app/pipelines/steps/reverse_infer.py`
  - prompt 模板：
    - 新项目场景 3：输出 `inferred_capabilities + uncertain_questions`
    - 旧项目场景 5：输出 `change_summary + uncertain_questions`
  - 输出 Artifact: `kind=inferred_business_summary`，含 `confidence`
  - confidence < 0.7 → 强制后续 HumanConfirmation Step

- **Acceptance**:
  - [ ] 单测覆盖两种模式
  - [ ] confidence 字段必填
  - [ ] uncertain_questions 至少 0 条最多 10 条

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_reverse_infer.py -v
  ```

- **Notes**: 测试集需准备真实原型图 + 已知答案。

---

## M3-T02: 信号补全表单后端

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M3-T01
- **Description**: 接受用户对反推结果的补充与确认。

- **Deliverables**:
  - `POST /api/v1/iteration/{id}/supplement`
    body: `{domain, target_users, core_flow_summary, edge_cases, custom_answers: [{question, answer}]}`
  - 写入 `iteration_input` 表（kind='supplement_form'）
  - 触发 Pipeline 增量重跑（仅依赖 supplement 的 Step）

- **Acceptance**:
  - [ ] supplement 提交后，反推 confidence 提升至 ≥ 0.7（合并用户输入）
  - [ ] 提交记录可重复（修改后再触发）

- **Self-Test**:
  ```powershell
  pytest tests/api/test_supplement.py -v
  ```

- **Notes**: —

---

## M3-T03: 信号补全表单前端

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M3-T02
- **Description**: 反推结果展示 + 引导用户填补充字段。

- **Deliverables**:
  - `src/views/iteration/SupplementForm.vue`
  - 展示 AI 反推的 capabilities / change_summary
  - 显示 uncertain_questions 列表，逐条引导回答
  - 必填项校验
  - 提交后弹框确认是否继续 Pipeline

- **Acceptance**:
  - [ ] 必填项校验工作
  - [ ] uncertain_questions 完成度可视化
  - [ ] 提交后跳转 Pipeline 进度页

- **Self-Test**: 浏览器手测。

- **Notes**: —

---

## M3-T04: 强制确认门槛 UI 框架

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M3-T03
- **Description**: 通用的"Pipeline 暂停 + 用户确认"框架，可被多个 Step 复用。

- **Deliverables**:
  - 后端：Pipeline runner 支持 `pause_for_confirmation(reason, payload)`，Step 可调用
  - 状态：pipeline_run.status='waiting_for_user'
  - API: `POST /api/v1/pipeline/{run_id}/resume`，body `{confirmation_payload}`
  - 前端：`PipelineProgress.vue`，检测 waiting_for_user 状态后弹确认框
  - 通用 `ConfirmationDialog.vue` 组件，支持自定义 schema 渲染

- **Acceptance**:
  - [ ] Pipeline 在反推后正确暂停
  - [ ] 用户提交后恢复执行
  - [ ] 暂停超 7 天自动取消（防泄漏）
  - [ ] `accepted_low_confidence=true` 标记记录到 artifact

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_pause_resume.py -v
  ```

- **Notes**: 关键基础设施，多个场景共用。

---

## M3-T05: TestPointAlignment Step

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M3-T01
- **Description**: 对齐用户测试点 vs UI 抽出的测试点（场景 1/4）或反推测试点（场景 3）。

- **Deliverables**:
  - `app/pipelines/steps/testpoint_alignment.py`
  - 输出：aligned_testpoints + conflicts[]
  - 冲突触发 HumanConfirmation

- **Acceptance**:
  - [ ] 冲突识别准确率 ≥ 70%（人工标注样本验证）
  - [ ] 无冲突时不触发暂停

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_testpoint_alignment.py -v
  ```

- **Notes**: —

---

## M3-T06: 场景 3 流水线

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M3-T04
- **Description**: 仅 UI 输入的新项目场景。

- **Deliverables**:
  - `app/pipelines/scenarios/scenario_3.py`：[S1, S3反推, S4确认门槛, S2候选, S5对齐, S10预览, S11生成, S12, S13]
  - e2e 测试

- **Acceptance**:
  - [ ] 仅传 UI 不报错
  - [ ] 反推 confidence < 0.7 时强制弹补充表单
  - [ ] 用例落库后质量分 ≥ B+（视输入完整度）

- **Self-Test**:
  ```powershell
  python -m scripts.e2e_scenario_3 --prototype-dir ./samples/proto1
  ```

- **Notes**: —

---

## M3-T07: 场景 5 流水线

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M3-T01, M2 完成
- **Description**: 旧项目无新 PRD 场景。

- **Deliverables**:
  - `app/pipelines/scenarios/scenario_5.py`：场景 4 + 反推 + 强制确认
  - e2e 测试

- **Acceptance**:
  - [ ] 反推变更摘要 + 用户确认后跑通双向扫描
  - [ ] 反推 confidence 低时阻断

- **Self-Test**:
  ```powershell
  python -m scripts.e2e_scenario_5 --project-id 1 --prototype-dir ./samples/proto2
  ```

- **Notes**: —

---

## M3-T08: M3 集成测试与文档收口

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: 所有 M3 任务

同 M1-T13 模式。

---

# M4 质量与运营

## M4-T01: 先验质量分服务

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1 完成
- **Description**: 实现 plan §7.1 的先验质量分公式。

- **Deliverables**:
  - `app/services/quality_score_service.py`
  - 函数 `compute_prior_score(iteration_id, case_id) -> {score, grade, breakdown}`
  - 在 case_generation Step 后自动调用并写入 case 字段（新增 `prior_quality_score`, `prior_quality_grade`）
  - migration 增加字段
  - 单测覆盖各信号组合

- **Acceptance**:
  - [ ] 公式与 plan §7.1 一致
  - [ ] D 级用例自动标 `lifecycle_status=pending_review`，禁止自动 active
  - [ ] breakdown 字段记录每项加分明细

- **Self-Test**:
  ```powershell
  pytest tests/services/test_quality_score.py -v
  ```

- **Notes**: —

---

## M4-T02: 后验质量分回填任务

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M2 完成
- **Description**: 评审完成 + 自动化执行后回填后验分。

- **Deliverables**:
  - 定时任务：每天聚合上周用例的 review_pass_rate / execution_pass_rate / modification_rate
  - 写入 case 表新增 `posterior_quality_score`
  - 仪表盘数据来源（M4-T06 用）

- **Acceptance**:
  - [ ] 计算公式与 plan §7.2 一致
  - [ ] 仅有足够数据（执行次数 ≥ 3）的用例计算后验分

- **Self-Test**:
  ```powershell
  python -m scripts.compute_posterior_score --project-id 1
  ```

- **Notes**: —

---

## M4-T03: 用例血缘 API

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: M1-T04
- **Description**: 暴露用例血缘树（基于 parent_case_id）。

- **Deliverables**:
  - `GET /api/v1/case/{id}/lineage` - 返回血缘树（祖先 + 后代）
  - 包含每个节点的 lifecycle_status / iteration_id / created_at

- **Acceptance**:
  - [ ] 链长度 ≥ 3 触发警告字段（plan §7.3）

- **Self-Test**:
  ```powershell
  pytest tests/api/test_case_lineage.py -v
  ```

- **Notes**: —

---

## M4-T04: 用例血缘前端可视化

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M4-T03
- **Description**: 详情页加血缘树视图。

- **Deliverables**:
  - `src/components/case/LineageTree.vue`：树形展开 + 节点状态徽标 + 跳转链接
  - CaseDetail.vue 集成

- **Acceptance**:
  - [ ] 链长度 ≥ 3 显示警告
  - [ ] 可视化清晰（vue-tree 或自定义）

- **Self-Test**: 浏览器手测。

- **Notes**: —

---

## M4-T05: FMEA 监控埋点

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M3 完成
- **Description**: 落地 plan §8 FMEA 表中各失败模式的检测点。

- **Deliverables**:
  - F1: artifact.confidence < 0.7 + Pipeline pause 计数指标
  - F2: JSON 校验失败次数指标
  - F3: 红色冲突计数
  - F5: `confirmed_with_zero_edit` 用例计数
  - F9: Pipeline 中断恢复次数
  - 接入 Prometheus 或简单的内置 metrics 表

- **Acceptance**:
  - [ ] 每个 FMEA 项至少 1 个监控指标
  - [ ] 指标可在仪表盘看到

- **Self-Test**:
  ```powershell
  curl http://localhost:8000/metrics
  ```

- **Notes**: 暂用本地 metrics 表，不引入 Prometheus 部署成本。

---

## M4-T06: 成本/性能仪表盘

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: M4-T05
- **Description**: 可视化 Pipeline 运行成本与性能。

- **Deliverables**:
  - `src/views/admin/PipelineDashboard.vue`
  - 后端聚合 API：每日 AI token 消耗、平均运行时长、缓存命中率、各 Step 耗时分布
  - FMEA 监控指标可视化

- **Acceptance**:
  - [ ] 数据 24h 内更新
  - [ ] 缓存命中率 ≥ 50%（基线，正常迭代多次跑同输入）

- **Self-Test**: 浏览器手测。

- **Notes**: —

---

## M4-T07: M4 集成测试与文档收口

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: 所有 M4 任务

同 M1-T13 模式。

---

# 任务执行守则

> **每个开发者必读，违反即拒收 PR**。

1. **状态变更**：开始任务时改 `🔄 in_progress`，完成自测后改 `✅ done`。
2. **依赖检查**：开始前确认所有 Depends on 已 done。
3. **Acceptance 全部勾选**：未勾选不算 done。
4. **Self-Test 必须执行并截图/日志附在 Notes**：不允许"看起来对就提交"。
5. **遗留问题写入 Notes**：哪怕 1 行小坑也要记。
6. **设计偏离写 ADR**：在本文档 task Notes 段记录"为什么偏离 plan 文档"。
7. **不允许跳过任务**：跳过必须 ❌ skipped 并注明原因（产品决策 / 已废弃 / 优先级降低）。
8. **每周更新本文档**：哪怕没做完也写"本周进展 + 阻塞"。

---

# 变更日志

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-04-29 | v1.0 | 初版，覆盖 M1-M4 共 40 任务 |
