# 迭代 Pipeline 审查问题修复计划

## 背景

基于 `docs/iteration-pipeline-tasks.md` 中 M1-T11、M1-T12 相关任务，对当前迭代 Pipeline 实现进行代码审查后，发现部分实现与文档验收要求、API 契约、测试覆盖存在不一致。

本计划用于跟踪审查发现问题的修复任务。

## 总体目标

- 修复 Pipeline API 实际触发路径中的运行时风险。
- 统一接口文档、实际路由和返回字段。
- 补齐场景 2 无 UI 输入时的定位状态验收。
- 增强 API 层和场景验收测试覆盖。
- 消除场景版本定义不一致带来的维护风险。

## 问题清单

### P0-01 Pipeline API 缺失 `PipelineRun` 导入

- **优先级**: P0
- **状态**: 已修复
- **涉及文件**:
  - `app/api/v1/endpoints/pipeline.py`
- **问题描述**:
  - `run_pipeline()` 中使用了 `PipelineRun` 查询历史运行记录，但文件顶部未导入 `PipelineRun`。
  - 实际调用 `POST /api/v1/pipeline/iteration/{iteration_id}/run` 时可能触发 `NameError`。
- **已完成修复**:
  - 将导入从 `from app.models.pipeline import Artifact` 调整为 `from app.models.pipeline import Artifact, PipelineRun`。
- **验收标准**:
  - API 触发 Pipeline 不再因 `PipelineRun` 未定义失败。
  - 增加或通过 API 层测试覆盖该路径。
- **建议测试**:
  ```powershell
  pytest tests/pipelines/test_scenario_2.py -q
  ```

### P0-02 API 返回缺少文档要求的 `pipeline_run_id`

- **优先级**: P0
- **状态**: 已修复
- **涉及文件**:
  - `app/api/v1/endpoints/pipeline.py`
- **问题描述**:
  - 文档要求触发端点返回 `pipeline_run_id`。
  - 当前接口原本只返回 `run_id`。
- **已完成修复**:
  - 在 `run_pipeline()` 返回数据中增加 `pipeline_run_id`，与 `run_id` 保持相同值。
- **验收标准**:
  - 返回数据同时包含 `run_id` 和 `pipeline_run_id`。
  - 前端或调用方可继续使用 `run_id`，也可按文档使用 `pipeline_run_id`。
- **建议测试**:
  - 直接调用 API 或端点函数，断言 `data.run_id == data.pipeline_run_id`。

### P1-01 Pipeline 触发路由与文档描述不一致

- **优先级**: P1
- **状态**: 已修复
- **涉及文件**:
  - `docs/iteration-pipeline-tasks.md`
  - `app/api/v1/endpoints/pipeline.py`
  - 前端调用 Pipeline 的相关代码，如存在
- **问题描述**:
  - 文档 Deliverables 中写的是 `POST /api/v1/iteration/{id}/pipeline/run`。
  - 实际实现是 `POST /api/v1/pipeline/iteration/{iteration_id}/run`。
  - 文档 Notes ADR-8 又描述为 `/pipeline/iteration/{id}/run`，与实际实现更接近。
- **已完成修复**:
  - 保留现有路由 `POST /api/v1/pipeline/iteration/{iteration_id}/run`。
  - 新增兼容路由 `POST /api/v1/iteration/{iteration_id}/pipeline/run`，转发到同一运行逻辑。
- **验收标准**:
  - 文档、OpenAPI、前端调用路径保持一致。
  - 不再存在同一任务内两个不同触发路径的描述。

### P1-02 场景 2 `locator_status=pending` 验收未充分落地

- **优先级**: P1
- **状态**: 已修复
- **涉及文件**:
  - `app/pipelines/steps/case_generation.py`
  - `app/pipelines/steps/persist.py`
  - `app/models/test_case.py`
  - `tests/pipelines/test_scenario_2.py`
- **问题描述**:
  - M1-T12 要求无 UI 输入时：生成用例的 `step.has_locator=0`、`locator_status=pending`。
  - 当前 Pipeline 持久化主要写入 `TestCase.steps_json`，未确认是否创建 `TestStep` 记录。
  - 当前测试只检查用例 `lifecycle_status`，没有断言 `TestStep.has_locator` 或 `TestStep.locator_status`。
- **已完成修复**:
  - `Persist` Step 按 `case_data.steps` 同步创建 `TestStep`。
  - 无 UI 输入时设置 `has_locator=0`、`locator_status='pending'`。
  - 场景 2 测试已断言生成的 `TestStep` 定位状态。
- **验收标准**:
  - 场景 2 无 UI 输入时 Pipeline 可正常完成。
  - 生成用例关联的所有 `TestStep` 满足：
    - `has_locator == 0`
    - `locator_status == 'pending'`
  - 测试覆盖该断言。

### P2-01 场景 2 版本常量与注册表不一致

- **优先级**: P2
- **状态**: 已修复
- **涉及文件**:
  - `app/pipelines/scenarios/scenario_2.py`
  - `app/pipelines/scenarios/__init__.py`
  - `tests/pipelines/test_scenario_2.py`
- **问题描述**:
  - `app/pipelines/scenarios/__init__.py` 注册表中场景 2 版本为 `2.0`。
  - `app/pipelines/scenarios/scenario_2.py` 中 `SCENARIO_2_VERSION` 仍为 `1.0`。
  - 当前注册表没有直接使用该常量，因此不影响运行，但存在维护风险。
- **已完成修复**:
  - 已将 `app/pipelines/scenarios/scenario_2.py` 中的 `SCENARIO_2_VERSION` 调整为 `2.0`。
  - 已增加注册表版本断言。
- **验收标准**:
  - 场景 2 所有版本定义均为 `2.0`。
  - 注册表测试通过。

### P2-02 API 层测试覆盖不足

- **优先级**: P2
- **状态**: 已修复
- **涉及文件**:
  - `tests/pipelines/test_scenario_1.py`
  - `tests/pipelines/test_scenario_2.py`
  - 可新增 `tests/api/test_pipeline_api.py`
- **问题描述**:
  - 当前场景测试主要绕过 FastAPI 路由，直接调用 `PipelineRunner`。
  - 因此无法覆盖 API 依赖注入、权限校验、返回字段、真实路由路径等问题。
- **已完成修复**:
  - 在 `tests/api/test_pipeline_api.py` 新增端点函数级测试。
  - 使用 `MockAIClient` 并 monkeypatch `_create_ai_client`，避免真实外部 AI 请求。
  - 覆盖主 Pipeline 路由逻辑和文档兼容路由逻辑的返回字段。
- **验收标准**:
  - 覆盖 `POST /api/v1/pipeline/iteration/{iteration_id}/run`。
  - 断言响应包含：
    - `run_id`
    - `pipeline_run_id`
    - `iteration_id`
    - `status`
    - `scenario`
  - 覆盖无权限、迭代不存在、非法状态等至少一个异常路径。

## 建议执行顺序

1. **P0-01 / P0-02 验证收尾（已完成）**
   - 确认 `PipelineRun` 导入和 `pipeline_run_id` 返回字段已合入。
   - 补 API 层最小测试。

2. **P1-01 路由文档统一（已完成）**
   - 决定是否新增兼容路由。
   - 同步更新任务文档或接口文档。

3. **P1-02 场景 2 定位状态落库（已完成）**
   - 明确 `TestStep` 是否为技术视图必需实体。
   - 补实现和断言测试。

4. **P2-01 版本常量收尾（已完成）**
   - 将场景 2 常量统一为 `2.0`，或重构为注册表引用常量。

5. **P2-02 API 测试补齐（已完成）**
   - 新增独立 API 测试文件，避免后续端点问题被 Runner 测试遗漏。

## 推荐测试命令

```powershell
pytest tests/pipelines/test_scenario_1.py tests/pipelines/test_scenario_2.py -q
```

如新增 API 测试：

```powershell
pytest tests/api/test_pipeline_api.py -q
```

## 当前已知验证结果

已运行：

```powershell
python -m pytest tests/pipelines/test_scenario_2.py -q
```

结果：

```text
8 passed, 3 warnings
```

本轮修复后已运行：

```powershell
python -m pytest tests/pipelines/test_scenario_1.py tests/pipelines/test_scenario_2.py tests/api/test_pipeline_api.py -q
```

结果：

```text
50 passed, 8 warnings
```

## 完成定义

本修复计划全部完成需满足：

- Pipeline API 触发路径无运行时错误。
- API 返回字段与文档一致。
- 路由路径在文档、实现、前端调用中一致。
- 场景 2 无 UI 时定位状态验收有明确实现和测试覆盖。
- 场景版本定义无重复不一致。
- Pipeline API 层测试能覆盖触发、查询和主要异常路径。
