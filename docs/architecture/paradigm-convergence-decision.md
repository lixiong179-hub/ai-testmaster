# 会话层范式收敛决策记录（R2-1 阶段一 / Q1）

- **决策日期**：2026-11-10
- **关联任务**：R2-1（会话层归一为单范式，XL，4 阶段）、R2-2（读写分离降级为配置预留）
- **关联决策项**：Q1（范式选择 + `async def` 端点处置）、Q2（`require_master` 去留）
- **决策依据**：`docs/架构优化执行计划清单.md` §10 推荐默认值（超时按默认执行规则）

---

## 一、决策结论

| 项 | 决策 | 说明 |
| --- | --- | --- |
| **Q1 范式** | **全 sync + `asyncio.to_thread`（方案 a）** | 端点**保留 `async def`**，数据库调用改为 `await asyncio.to_thread(sync_fn, ...)`；不采用「388 端点全改 `def`」（方案 b）——那会丢失 `await` 能力，WebSocket / 流式端点不可用 |
| **Q2 `require_master`** | **删除** | 全仓**零业务使用点**，且路由层从未读取其写入的 `request.state.force_master`（属死代码）；写后读一致性由 `READ_AFTER_WRITE_WINDOW_SECONDS` 窗口承担 |
| **Q5 import 路径** | **分阶段** | 先出六域映射表（R4-1 阶段一），再按域分 6 批移动 + 保留 re-export shim 一个迭代 |
| **Q10 审计哈希链** | **补全** | 见 §五，G-1 已落地 |
| **Q12 依赖解析** | **实现为可选能力** | `tests/services/test_dependency_resolution.py` 已 69 passed，无需降级 skip（G-3 结项） |
| **Q13 legacy 套件** | **按当前实现重写为契约测试** | 根级三套件已删除；`test_smoke_api` 转为 11 skipped（依赖真实后端），契约化重写登记为 R4-7 候选 |

---

## 二、现状实测（2026-11-10）

| 指标 | 实测值 | 采集命令 |
| --- | --- | --- |
| 使用 `async_get_db` / `async_get_db_context` 的 endpoint 文件 | **88 个** | `Select-String -Path app/api/v1/endpoints -Recurse -Pattern "async_get_db" -List` |
| 该模式引用总处数 | **409 处** | 同上 `-AllMatches` 求和 |
| `async def` 端点数 | **387 个** | `Select-String -Pattern "^\s*async def "` |
| 引擎 / 会话工厂构造点（`_engine.py`） | **6 处**（`create_engine` ×2、`create_async_engine` ×1、`sessionmaker` ×2、`async_sessionmaker` ×1） | 见 `_engine.py` |
| 会话入口（`_session.py`） | **8 个**（4 同步 + 4 异步） | `get_db` / `get_read_db` / `get_db_context` / `get_read_db_context` + 对应 `async_*` |
| 测试侧桥接类 | `_SyncBackedAsyncSession`（`tests/conftest.py`） | — |

> 与 2026-09-22 快照的差异（410→409 处、388→387 个 `async def`）来自同期 O-22 修复中的少量删改，量级不变。

---

## 三、目标形态

```
引擎层（_engine.py）：  primary_engine + secondary_engine（懒加载，未配置 slave 即退化为 primary）
会话工厂：              PrimarySessionLocal + get_secondary_session_local()
会话入口（_session.py）：get_db / get_read_db / get_db_context / get_read_db_context
端点：                 async def 保留，DB 调用 await asyncio.to_thread(...)
```

**关键约束**：阶段二的「4 引擎 → 2、4 工厂 → 2」**不能先于阶段三**物理删除。原因：88 个文件仍 `await db.execute(...)`，若把 `AsyncPrimarySessionLocal` 直接改成同步 `sessionmaker` 的别名，全部异步端点会在 `await` 处立即崩。因此阶段二只做「**冻结新增 + 标注 deprecated**」，物理删除留到阶段四。

---

## 四、阶段划分与判据

| 阶段 | 内容 | 判据 | 状态 |
| --- | --- | --- | --- |
| **一 · 决策** | 本文件（Q1/Q2 决策 + 批次表） | 决策记录存在且含批次划分 | ✅ 2026-11-10 |
| **二 · 引擎/会话层收敛（部分）** | `_session.py` 的 4 个 `async_*` 入口与 `_engine.py` 的异步引擎/工厂**标注 deprecated**（docstring + 注释），禁止新增调用；不删除实现 | 新增调用数 = 0（CI 可用 grep 门禁）；`import app.main` 成功 | 🔄 已标注，未删除 |
| **三 · 端点迁移（6 批）** | 409 处引用 → `await asyncio.to_thread(sync_fn, ...)` | `grep -rc "async_get_db" app/api/v1/endpoints` → **0** | 🔄 2026-11-16：W2-1a 405/76 → **377/74**（`test_data` 8 + `user` 20；5 个 `*_async_mixin` 改 `to_thread`，测试侧 `async_db` 改同步 Session + 壳）；W2-1b → **369/73**（`audit_log` 2 + `feature_flag` 7，`FeatureFlagService` 反向收敛为同步）。`agents`/`visual_ai` 19 处因 async storage 与 AgentRuntime/MCP 共用 AsyncSession 阻塞，转 **B-14**。W2-2a（2026-11-17）→ **352/71**（`execution_vis_video_replay` 14 + `test_task_exec` 3；删除手写独立 sync 会话）；W2-2b → **332/67**（`execution_vis_config` 6 + `execution_management` 4 + `test_task` 6 + `access_deps` 4；`require_task_access` 改同步 def 依赖）；W2-2c → **323/66**（`execution_core/__init__.py` 9 处 + 22 处 `await db.*`；新增 `is_visual_validation_enabled_sync`，执行域清单清零）；W2-3 → **284/62**（用例域 4 文件 39 处：`test_point` 12 / `test_case_workflow` 9 / `test_case_ai_generate` 9 / `case_quality_report` 9；权限与批量 CRUD 改同步版、`TestCaseViewService` 6 个 `*_async` 改调 sync + `to_thread`、70 处 `await db.*` 包装，用例域清单清零）；W2-4 → **241/54**（评审/迭代域 8 文件 43 处：`review_inbox` 10 / `iteration` 9 / `pipeline*` 24；`iteration_async_mixin` 改造为 sync 薄壳、`metrics_service` 新增 `*_sync` 三函数、`await db.run_sync` → `to_thread`，评审/迭代域清单清零）；W2-5 → **172/38**（其余端点域 16 文件 69 处；校验辅助改 sync + `to_thread`、四文件统一 `_execute(db, stmt)` 线程池辅助、`quality_rule`/`ai_invocation` async 试点回退为同步；`case_refresh`/`mfa_endpoints`/`agents`/`visual_ai` 转 W2-6 与 B-14）；W2-5b → **120/29**（续批 9 文件 52 处；`_execute` 辅助推广、同文件 async 辅助保留签名仅改注解、`conftest._safe_rollback` 增加跨线程 rollback 兜底）；W2-5c → **90/20**（续批二 9 文件 30 处；`auth_deps` 权限链路切同步打通 TestClient 真实 DB 路径，18 个 xmind 用例由 skip 转 passed，全量 1060 passed / 21 skipped）；W2-5d → **69/16**（续批三 4 文件 21 处：成员域 `ProjectAccessService` 改 sync、`CaseNumberService.generate` 替代 `generate_async`、`async with db.begin_nested()` → 同步 `with`、helpers 的 `db.run_sync` → `to_thread`）；W2-5e → **54/12**（续批四 4 文件 15 处：新增 `db_async_compat` 双兼容执行辅助，`case_refresh` 服务/`_apply` 11 处 DB 调用改走兼容层、`prompt_template` 改用 `PromptRegistry` sync Mixin；剩余仅引擎定义 9 + B-14 35 + `mfa`/`oidc`/`saml` 10） |
| **四 · 测试侧收口** | 移除 `_SyncBackedAsyncSession`，删除 deprecated 别名与异步引擎 | `grep -rn "_SyncBackedAsyncSession" tests/` → **0**；`pytest tests -q` 无新增失败 | ⬜ 未开始 |

### 阶段三批次表（按子目录，逐批独立提交 + 跑该子域测试）

| 批 | 范围 | 说明 |
| --- | --- | --- |
| ① | 顶层 `_*.py` 私有文件（17 个） | 先动私有拆分文件，影响面最小 |
| ② | `test_case*` / `test_point*` | 用例与测试点主链路 |
| ③ | `execution*` / `test_task*` | 执行链路（含 WebSocket 相关，注意 `async` 语义） |
| ④ | `pipeline*` / `report*` | 流水线与报表 |
| ⑤ | `ui_prototype*` / `file*` | 文件上传（注意流式读取保持 `async`） |
| ⑥ | 其余（含子目录 23 个 `_*.py`） | 收尾，合计 40 个私有文件 |

---

## 五、G-1 审计哈希链落地记录（Q10 已执行）

- `AuditLog.compute_hash(prev_hash)`：canonical JSON（`sort_keys=True`, `ensure_ascii=False`）+ SHA256，载荷含 action / actor_id / target_kind / target_id / detail / run_id / iteration_id / created_at / prev_hash。
- **精度陷阱（已修，含二次修正）**：MySQL `DATETIME(0)` 不仅不保留微秒，写入时对微秒做**四舍五入（half-up）而非截断**。若按「截断」归整，只要微秒 ≥ 500000 就整体偏移 1 秒 → 回读后重算不一致（假断裂）。最终实现：① `log_action` 写入时直接 `utcnow().replace(microsecond=0)`；② `compute_hash` 作为防御按 `+500ms` 后归零，对齐 MySQL 语义。
  - 该缺陷**只在跨测试上下文偶发**（是否触发取决于写入时刻的微秒值），全量跑第 2 批时表现为 `test_hash_survives_db_round_trip` 单点失败，已由「`tests/models/test_video_record.py` + 该用例」组合稳定复现并修复。
- `AuditChainService.compute_record_hash(record, prev_hash)`：静态工具方法补齐（模块 docstring 早已承诺）。
- `audit_service.log_action`：写入时取 `get_last_hash()` 作为 `prev_hash` 并计算 `hash`，**哈希链自此在生产写入路径生效**（此前 `hash` 恒为 NULL）。
- **历史数据不可回溯**：启用前的存量记录 `hash` 为 NULL，全链校验会在历史段断裂。校验请用 `verify_chain_integrity(start_id=<启用后首条 id>)`。
- 验证：`tests/services/test_audit_chain_service.py` **16 passed**；`tests/services/test_audit_service.py` **22 passed**（含 4 项新增写入链路用例）；`tests/api/test_audit_log_api.py` **2 passed**。

## 六、R2-2 落地记录（Q2 已执行）

- 删除 `app/db/router.py::require_master`（含 `Depends` 导入与 docstring 引用）与 `tests/db/test_read_write_router.py::TestRequireMaster`。
- `grep -rn "require_master" app/ tests/` → **0**。
- 新增 `tests/db/test_replica_lag_disabled.py`（4 项）：未配置 `DATABASE_URL_SLAVE` 时 `start_lag_monitor()` 不构造 APScheduler、不新增线程；`probe_replica_lag()` 不建连；`get_current_lag()` 只读内存态。
- `start_lag_monitor()` 已接入生命周期（`app/core/lifecycle.py::startup_lag_monitor`），未配置从库时零开销提前返回。
- 验证：`pytest tests/db -q` = **26 passed / 0 failed**；`pytest tests/api -q` = 998 passed / 0 failed（R4-2 时点）。

---

## 七、风险与回滚

| 风险 | 控制 |
| --- | --- |
| 阶段三迁移引入异步语义错误（阻塞事件循环） | 每批只动一批文件；每批后跑该子域 `tests/api` 子集；`to_thread` 包裹后仍是真异步 |
| 阶段二误删异步引擎导致全站 500 | **本轮不删除**，仅标注 deprecated；删除动作归入阶段四并附带全量回归 |
| WebSocket / 流式端点被改坏 | 批次 ③⑤ 单独列出，`await` 语义逐端点确认；不使用方案 b |
| 哈希链历史断裂被判为「系统被篡改」 | 校验约定 `start_id`；监控告警需区分「历史段」与「启用后段」 |
