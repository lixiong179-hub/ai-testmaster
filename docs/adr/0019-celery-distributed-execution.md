# ADR-0019: Celery 分布式执行引擎架构决策

- **状态**: 已接受 (Accepted)
- **日期**: 2026-07-29
- **作者**: AI TestMaster 团队
- **评审**: Phase 1 Task 3 分布式执行引擎实施
- **关联规则**: `.trae/rules/project_rules.md` 第三章"架构设计"、第五章"性能要求"
- **关联路线图**: `docs/架构对标分析与优化路线图.md` 第六章 Phase 1

## 1. 背景 (Context)

AI TestMaster 后端测试任务执行在 v1.1 阶段通过 `test_execution_engine_v2.py` 实现，
但执行调度依赖 APScheduler 单机调度，且 Pipeline 执行在端点同步阻塞调用，存在：
1. 单机瓶颈：测试任务并发受限于 API Worker 数量，无法水平扩展；
2. 资源争抢：长任务阻塞 API 响应，影响其他端点 P99 延迟；
3. 状态丢失：APScheduler 单机部署，Pod 重启时在途任务丢失；
4. 扩展受限：无法支撑 ≥50 并发的水平扩展目标。

v2.0 路线图 Phase 1 要求 0-6 个月内完成分布式执行引擎，目标：
- 测试任务经 Celery + Redis 分布式调度，≥50 并发稳定；
- Worker 水平扩展，任务投递到启动 ≤2s；
- Worker 崩溃后任务自动重投（task_acks_late + task_reject_on_worker_lost）；
- APScheduler 任务 100% 迁移至 Celery Beat。

本 ADR 记录 Celery 集成的五项核心架构决策：应用工厂模式、任务基类抽象、
异步桥接策略、状态回写双写、灰度回退机制，作为 Phase 1 Task 3 验收基线。

## 2. 决策 (Decision)

### 2.1 应用工厂模式（create_celery_app）

**决策**：在 `app/tasks/celery_app.py` 实现应用工厂函数 `create_celery_app()`，
通过 `get_celery_app()` 单例缓存，配置包括 broker/backend URL、任务序列化、
超时限制、队列路由等。

**理由**：
- 工厂模式便于测试与多环境部署（dev/staging/prod 配置隔离）；
- 单例缓存避免重复创建 Celery 应用，减少 Redis 连接；
- broker URL 自动从 `REDIS_URL` 派生（DB 0=broker, DB 2=backend），零额外配置。

### 2.2 任务基类抽象（BaseTask）

**决策**：在 `app/tasks/base.py` 实现 `BaseTask(celery.Task)` 抽象基类，
统一 `on_success` / `on_failure` / `on_retry` / `on_start` 生命周期回调，
通过 `task_state_callback` 实现 DB + Redis 双写状态回写。

**理由**：
- 任务状态变更统一埋点，避免每个任务重复实现状态回写；
- Redis 故障时仅告警不影响主流程（任务执行优先）；
- 指数退避 `calculate_retry_backoff` 工具函数统一重试策略。

### 2.3 异步桥接策略（async_task）

**决策**：在 `app/tasks/_async_bridge.py` 实现 `async_task` 装饰器，
将 `async def` 任务函数桥接为 Celery 同步任务，单 Worker 内 `asyncio.run` 串行执行。

**理由**：
- Celery Worker 是同步进程，需桥接调用现有 async service 层；
- 单 Worker 内串行 `asyncio.run` 避免嵌套事件循环死锁；
- 嵌套场景检测到运行中事件循环时创建新循环兜底。

### 2.4 状态回写双写（DB + Redis）

**决策**：任务状态通过 `task_state_callback` 同时写入 DB（pipeline_runs.status）
与 Redis（`task:{task_id}:state` hash，TTL 1h），进度查询端点优先读 Redis，
回退读 DB。

**理由**：
- Redis 缓存提供 ≤200ms 进度查询延迟（设计文档 P1-3 验收要求）；
- DB 持久化保证任务状态不丢，Redis 故障后仍可查询；
- 双写失败不影响任务执行主流程，符合"监控不影响主流程"原则。

### 2.5 灰度回退机制（CELERY_ENABLED）

**决策**：`CELERY_ENABLED` 环境变量控制 Celery 启用开关。
- `True`：端点投递任务至 Celery Worker 异步执行；
- `False`（默认）：端点保持 v1.1 同步执行路径，零行为变更。

**理由**：
- 灰度发布期间可按环境变量逐步切量（dev → staging → prod）；
- Redis/Celery 故障时 1 分钟内可通过配置回退，无需代码变更；
- 默认 False 保障现有测试与生产环境稳定性，避免激进切换风险。

## 3. 备选方案 (Alternatives Considered)

### 3.1 RQ (Redis Queue)

**方案**：使用 RQ 替代 Celery，更轻量。

**否决理由**：
- RQ 不支持 Beat 周期任务调度，需保留 APScheduler；
- RQ 任务基类抽象能力弱，难以统一状态回写与重试策略；
- Celery 生态成熟，Worker 池选择丰富（prefork/gevent/eventlet）。

### 3.2 Dramatiq

**方案**：使用 Dramatiq 替代 Celery，性能更优。

**否决理由**：
- Dramatiq 生态较新，社区资源与文档不及 Celery；
- 现有 APScheduler 迁移至 Dramatiq 需额外学习成本；
- 团队对 Celery 熟悉度更高，降低实施风险。

### 3.3 端点直接 async 执行

**方案**：不引入任务队列，端点 `async def` 内 `asyncio.create_task` 异步执行。

**否决理由**：
- 任务状态随 Pod 重启丢失，无法满足"崩溃任务重投"要求；
- 无法水平扩展 Worker，并发受限于 API Worker 数量；
- 任务进度查询需额外实现，重复造轮子。

## 4. 影响 (Consequences)

### 4.1 正面影响

- 测试任务分布式调度，≥50 并发稳定，Worker 水平扩展；
- 任务投递到启动 ≤2s，长任务不阻塞 API 响应；
- Worker 崩溃任务自动重投，零任务丢失；
- APScheduler 迁移至 Celery Beat，调度器无状态化；
- 为 Phase 2 跨集群 Worker 与任务优先级队列铺平道路。

### 4.2 负面影响

- 引入 Celery 依赖，运维复杂度增加（Worker + Beat 部署）；
- 异步桥接存在少量性能开销（asyncio.run 创建事件循环）；
- 端点改造工作量较大（82 个端点），需分批推进；
- Redis 单点故障影响任务投递（Phase 2 升级 Sentinel/Cluster）。

### 4.3 风险与缓释

| 风险 | 缓释方案 |
|------|----------|
| Worker 内 async 桥接死锁 | 单 Worker 内 asyncio.run 串行，禁止嵌套事件循环 |
| Playwright 进程残留 | 任务结束 browser.close() + 定期 pkill 兜底 |
| Redis broker 单点 | Phase 1 单 Redis，Phase 2 升级 Sentinel/Cluster |
| 任务重复执行 | task_acks_late=True + 幂等设计（pipeline_run_id 去重） |
| 长任务超时 | task_time_limit=3600s，超时强制终止 + 告警 |

## 5. 后续演进 (Future Work)

- **Phase 2**：跨集群 Worker 部署，支持异地多活；
- **Phase 2**：任务优先级队列（high/normal/low），关键任务优先执行；
- **Phase 2**：执行结果流式回传（WebSocket），替代轮询查询；
- **Phase 3**：智能调度 v2（基于历史失败率 + 优先级排序）；
- **Phase 4**：Agent 自治执行（三级自治：建议→审批→自动）。

## 6. 验收标准

- [x] Celery 应用工厂 `app/tasks/celery_app.py` 实现完成（< 100 行）
- [x] 任务基类 `app/tasks/base.py` 实现完成（统一状态回写 + 重试策略）
- [x] 异步桥接 `app/tasks/_async_bridge.py` 实现完成（< 50 行）
- [x] 测试执行任务 `app/tasks/test_execution.py` 实现 `execute_pipeline_task`
- [x] Beat 调度任务 `app/tasks/scheduler.py` 迁移 `pipeline_timeout_check`
- [x] Worker 启动入口 `app/tasks/worker.py` 实现 `start_worker` / `start_beat`
- [x] 配置项 `CELERY_*` 加入 Settings
- [x] Worker K8s 部署配置（Deployment + HPA + Beat + PDB）
- [x] 单元测试 28/28 通过（应用工厂/桥接器/基类/调度/任务注册）
- [x] 回归测试 104/111 通过（7 skipped 为 S3 凭据缺失）
- [x] ADR 文档记录决策

## 7. 参考

- [Celery 5.4 Documentation](https://docs.celeryq.dev/en/stable/)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices)
- `docs/一期（0-3月）落地计划.md` 第四章 P1-3 WBS
- `docs/架构对标分析与优化路线图.md` 第六章 Phase 1
