# app/tasks/_frozen — Celery 分布式执行基础设施（已冻结）

**冻结日期**：2026-09-18
**冻结依据**：《架构优化与简化分析》§1.1 / §4 R0-2；《架构优化执行计划清单》R0-2

## 为什么冻结

这套 Celery 基础设施属于「已建成、未接线」状态，生产路径从未使用它：

| 事实 | 证据 |
| --- | --- |
| 配置默认关闭 | `app/core/config.py` 的 `CELERY_ENABLED: bool = False` |
| 全代码库无任务投递 | 无任何 `.delay()` / `.apply_async()` / `send_task()` 真实调用（唯一命中为 `celery_app.py` 内的 docstring 注释） |
| 生产执行路径不经过 Celery | `app/api/v1/endpoints/test_task_exec.py::run_test_task` 在请求进程内创建 `PrimarySessionLocal()`，经 `run_async_coro_in_thread` 线程桥接执行 |
| 部署面从未接线 | `Dockerfile`、`docker-compose*.yml`、`start_all.py`、`start_prod.py`、`gunicorn.conf.py`、CI workflow 中零 celery 引用 |

两套调度方案并存（进程内执行 vs. Celery）会让每次改动执行链路都要考虑双路径兼容，
因此先冻结而非删除，保留设计资料备查。

## 冻结内容

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `celery_app.py` | 99 | Celery 应用工厂（含 broker / backend URL 解析） |
| `base.py` | 98 | 任务基类、状态回调、重试退避 |
| `worker.py` | 83 | Worker / Beat 启动入口（CLI） |
| `scheduler.py` | 72 | Celery Beat 调度任务（APScheduler 迁移） |
| `_async_bridge.py` | 51 | 异步任务桥接装饰器 |
| `test_execution.py` | 188 | 流水线执行任务 |
| **合计** | **591** | |

**未冻结（仍在 `app/tasks/` 正常工作）**：`self_test_scheduler.py`（190 行）、
`_self_test_executor_mixin.py`（323 行）——自测（缺陷发现）定时调度，属活跃功能，
被 `app/api/v1/endpoints/project_core.py:325` 与 3 个测试文件引用。

对应单元测试 `test_celery_app.py` 一并移入 `tests/tasks/_frozen/`；由于
`tests/conftest.py` 已配置 `collect_ignore_glob = ["tasks/_frozen/*"]`，pytest 不会收集它
（若被收集，本目录文件的顶层 `import celery` 会抛 ImportError 而中断全量测试）。

## 恢复方法

若将来确需分布式执行（例如执行引擎进程隔离后需要消息队列），按以下步骤恢复：

1. 将本目录下 6 个 `.py` 文件**整体**移回 `app/tasks/`——它们之间使用
   `from app.tasks.xxx import ...` 绝对导入，分散移动会导致 ImportError；
2. 恢复 `app/tasks/__init__.py` 的导出语句（原始导出列表见该文件 docstring）；
3. 在 `requirements.txt` 的 `Task Queue` 区恢复 `celery[redis]==5.4.0`；
4. 将 `tests/tasks/_frozen/test_celery_app.py` 移回 `tests/tasks/`，并从
   `tests/conftest.py` 的 `collect_ignore_glob` 中移除对应规则；
5. **补上任务投递点**——原方案缺失的一环：`app/api/v1/endpoints/agents.py` 与
   `test_task_exec.py` 当前均为请求进程内执行，从未有代码调用 `.delay()`。

> 建议：恢复前先重新评估。本目录冻结时（2026-09-18）「执行引擎与 API 同进程」是
> 已知痛点，但更合适的演进方向是先做执行引擎进程隔离（见《架构优化与简化分析》
> §4 R5-1），再基于隔离后的真实需求选型消息队列——届时未必仍是 Celery。
