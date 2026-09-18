# ADR-0018: MySQL 读写分离架构决策

- **状态**: 已接受 (Accepted)
- **日期**: 2026-07-29
- **作者**: AI TestMaster 团队
- **评审**: Phase 1 Task 2 读写分离实施
- **关联规则**: `.trae/rules/project_rules.md` 第三章"架构设计"、第五章"性能要求"
- **关联路线图**: `docs/architecture-competitive-analysis.md` 第六章 Phase 1

## 1. 背景 (Context)

AI TestMaster 后端 API 在 v1.1 阶段已实现 Agent/自愈/安全合规 Phase 1A，但可扩展性
仍是最大短板（架构对标差距 60%）。当前单库 MySQL 在测试任务并发执行、报告查询、
列表分页等读密集场景下，主库 QPS 成为瓶颈，制约水平扩展能力。

v2.0 路线图 Phase 1 要求 0-3 个月内完成 MySQL 读写分离，目标：
- 读流量路由至从库，主库写压力下降 ≥60%
- 读 QPS ≥3x
- 主从延迟 P95 ≤500ms
- 从库故障 30s 内降级主库，零 5xx

本 ADR 记录读写分离的四项核心架构决策：路由层抽象、延迟监控降级、写后读一致性、
灰度回退机制，作为 Phase 1 Task 2 验收基线。

## 2. 决策 (Decision)

### 2.1 路由层抽象（ReadWriteRouter）

**决策**：在 `app/db/router.py` 实现 `get_async_write_session` / `get_async_read_session`
双依赖注入函数，封装主从选择逻辑。复用已就位的 `_engine.py` 懒加载 secondary 引擎层。

**理由**：
- 业务端点仅需切换依赖名（`async_get_db` → `get_async_read_session`），无侵入式改造；
- 路由策略集中维护，便于后续扩展（多从库负载均衡、读写权重等）；
- 复用现有 `get_async_secondary_session_local`，零基础设施重复建设。

### 2.2 主从延迟监控与自动降级

**决策**：在 `app/db/replica_lag.py` 实现独立延迟监控模块，APScheduler 周期采样
`SHOW REPLICA STATUS` 的 `Seconds_Behind_Source`，缓存至进程内。
路由层根据延迟阈值自动降级：
- `> REPLICA_LAG_WARN_SECONDS (0.5s)`：告警但仍走从库；
- `> REPLICA_LAG_DEGRADE_SECONDS (2.0s)`：自动降级走主库，避免脏读。

**理由**：
- 单进程内缓存避免每次读请求都查询从库状态，零额外 DB 负载；
- 阈值化降级避免延迟抖动误判，0.5s/2.0s 双阈值平衡灵敏度与稳定性；
- 监控失败不抛异常，保留上一次有效值，符合"监控不影响主流程"原则。

### 2.3 写后读一致性窗口

**决策**：写操作完成后通过 `_mark_write_timestamp` 记录时间戳（Redis 优先，进程内 dict 兜底），
`get_async_read_session` 检查时间戳，若距上次写操作 < `READ_AFTER_WRITE_WINDOW_SECONDS (5s)`，
强制走主库。

**理由**：
- 主从复制即使半同步也存在毫秒级延迟，写后立即读从库可能脏读；
- 5s 窗口覆盖 95% 的"创建后立即查询列表"场景；
- Redis 跨实例共享时间戳，多 Pod 部署时窗口一致；
- 进程内 dict 兜底确保 Redis 故障时不丢失功能。

### 2.4 灰度回退总开关

**决策**：`READ_WRITE_SPLIT_ENABLED` 环境变量控制读写分离总开关。
- `True`（默认）：读请求按路由策略走主/从库；
- `False`：所有读请求走主库，行为等同 v1.1。

**理由**：
- 灰度发布期间可按环境变量逐步切量（dev → staging → prod）；
- 从库故障或回归问题时 1 分钟内可通过配置回退，无需代码变更；
- 与 Phase 1 Task 1 的 `STORAGE_BACKEND` 开关模式一致，运维心智模型统一。

## 3. 备选方案 (Alternatives Considered)

### 3.1 ProxySQL 中间件

**方案**：部署 ProxySQL 作为数据库代理，基于 SQL 语义自动路由。

**否决理由**：
- 引入新中间件，运维复杂度增加；
- SQL 语义识别有误判风险（如存储过程读写混合）；
- Phase 1 目标是 0-3 个月落地，ProxySQL 学习曲线不匹配。
- 留待 Phase 2 多从库负载均衡时评估。

### 3.2 @readonly 注解

**方案**：通过装饰器 `@readonly` 标记只读方法，AOP 拦截切换数据源。

**否决理由**：
- Python 无原生 AOP，需引入额外依赖（如 aspectlib）；
- 装饰器隐式行为增加调试难度；
- FastAPI 依赖注入已是显式路由机制，复用更自然。

### 3.3 多从库负载均衡

**方案**：Phase 1 即引入多从库加权轮询。

**否决理由**：
- Phase 1 单从库即可达成 ≥3x 读 QPS 目标；
- 多从库负载均衡属 Phase 2 范围，避免过度设计；
- 当前路由层抽象已为多从库扩展预留接口（factory 函数可替换为负载均衡器）。

## 4. 影响 (Consequences)

### 4.1 正面影响

- 主库写压力下降 ≥60%，支撑 ≥5 实例水平扩展；
- 读 QPS 提升 ≥3x，列表/报表端点 P95 延迟改善；
- 路由层抽象为后续 Phase 2 ProxySQL / 多从库演进铺平道路；
- 灰度回退机制保障切换风险可控。

### 4.2 负面影响

- 写后读窗口内仍走主库，5s 内读 QPS 提升受限（可接受）；
- 监控采样周期 15s，存在短时延迟抖动未感知窗口（由 2s 降级阈值兜底）；
- 端点改造工作量较大（82 个端点使用 async_get_db），需分批推进。

### 4.3 风险与缓释

| 风险 | 缓释方案 |
|------|----------|
| 主从延迟导致脏读 | 写后读窗口 + 2s 延迟降级双保险 |
| 从库故障 | 监控采样失败保留上次值，超阈值自动降级主库 |
| 端点误判为只读 | 评审清单 + 单元测试覆盖路由决策 |
| 复制中断 | GTID 模式 + Prometheus 监控 `Replica_IO_Running` |

## 4. 后续演进 (Future Work)

- **Phase 2**：多从库负载均衡（加权轮询/最少连接），引入 ProxySQL 评估；
- **Phase 2**：跨集群读流量分发（异地多活场景）；
- **Phase 3**：分库分表（基于 tenant_id 水平拆分）；
- **Phase 4**：PostgreSQL RLS 迁移后，路由层适配 RLS 策略。

## 5. 验收标准

- [x] 路由层 `app/db/router.py` 实现完成（< 130 行）
- [x] 延迟监控 `app/db/replica_lag.py` 实现完成
- [x] 配置项 `REPLICA_LAG_*` / `READ_AFTER_WRITE_WINDOW_SECONDS` / `READ_WRITE_SPLIT_ENABLED` 加入 Settings
- [x] `app/main.py` 启动时自动启动延迟监控
- [x] 示范只读端点 `pipeline_metrics.py` 改造完成
- [x] MySQL 主从 K8s 配置（StatefulSet + 复制初始化 Job + ServiceMonitor）
- [x] 单元测试 23/23 通过（路由决策/写后读窗口/延迟降级/URL 解析/require_master）
- [x] ADR 文档记录决策

## 6. 参考

- [MySQL 8.0 Replication Documentation](https://dev.mysql.com/doc/refman/8.0/en/replication.html)
- [SQLAlchemy 2.0 AsyncSession](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- `docs/phase1-implementation-plan.md` 第三章 P1-2 WBS
- `docs/architecture-competitive-analysis.md` 第六章 Phase 1
