"""Celery 任务基类（Phase 1 Task 3：分布式测试执行引擎）

业务用途：统一日志、异常处理、状态回写、失败重试策略。
设计原则：
1. 任务执行前后回写状态至 DB + Redis（双写，Redis 失败仅告警）；
2. 失败重试采用指数退避（1s → 2s → 4s），最多 CELERY_TASK_MAX_RETRIES 次；
3. 任务异常分类：可重试（网络/超时）vs 不可重试（数据校验/权限）。

依赖：celery.Task、app.db.database、app.core.config
"""
import logging
import time
from typing import Any, Optional

from celery import Task

from app.core.config import settings

logger = logging.getLogger(__name__)


# 任务状态枚举（与 pipeline_runs.status / test_tasks.status 字段对齐）
TASK_STATE_PENDING = "pending"
TASK_STATE_STARTED = "started"
TASK_STATE_SUCCESS = "success"
TASK_STATE_FAILURE = "failure"
TASK_STATE_RETRY = "retry"


def task_state_callback(task_id: str, state: str, result: Optional[Any] = None) -> None:
    """任务状态变更回调（DB + Redis 双写）。

    业务用途：进度查询端点优先读 Redis，回退读 DB。
    边界场景：Redis 故障时仅写 DB，不影响主流程；DB 故障时仅写 Redis，告警。
    """
    # Redis 进度缓存（TTL 1h）
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
        r.hset(
            f"task:{task_id}:state",
            mapping={
                "state": state,
                "updated_at": time.time(),
                "result": str(result) if result is not None else "",
            },
        )
        r.expire(f"task:{task_id}:state", 3600)
        r.close()
    except Exception as e:
        logger.warning(f"Redis 任务状态写入失败（非致命）: {e}")

    # DB 状态回写由具体任务的 _persist_state 实现（避免基类耦合具体模型）
    logger.info(f"任务状态变更: task_id={task_id}, state={state}")


class BaseTask(Task):
    """Celery 任务基类，统一状态回写与异常处理。

    用法：
        @celery_app.task(bind=True, base=BaseTask)
        def my_task(self, *args, **kwargs):
            ...
    """

    abstract = True

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功回调：回写 success 状态。"""
        task_state_callback(task_id, TASK_STATE_SUCCESS, retval)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调：回写 failure 状态，记录详细错误。"""
        task_state_callback(task_id, TASK_STATE_FAILURE, str(exc))
        logger.error(
            f"任务失败: task_id={task_id}, args={args}, kwargs={kwargs}, "
            f"exception={exc}, traceback={einfo}"
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试回调：回写 retry 状态。"""
        task_state_callback(task_id, TASK_STATE_RETRY, str(exc))
        logger.warning(
            f"任务重试: task_id={task_id}, retry_count={self.request.retries}, "
            f"exception={exc}"
        )

    def on_start(self, task_id, args, kwargs):
        """任务启动回调：回写 started 状态。"""
        task_state_callback(task_id, TASK_STATE_STARTED)


def calculate_retry_backoff(retry_count: int) -> float:
    """指数退避计算：1s → 2s → 4s → 8s（上限 60s）。

    业务用途：避免瞬时故障下任务密集重试压垮下游服务。
    """
    return min(2 ** retry_count, 60)
