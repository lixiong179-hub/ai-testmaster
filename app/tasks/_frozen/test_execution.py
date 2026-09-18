"""测试执行任务模块（Phase 1 Task 3：分布式测试执行引擎）

业务用途：测试任务经 Celery 投递，Worker 异步执行 PipelineRunner。
设计原则：
1. 任务接收 pipeline_run_id 与执行参数，Worker 内重建上下文；
2. 通过 async_task 桥接器将 async 入口转为同步任务；
3. 失败重试采用指数退避，幂等设计基于 pipeline_run_id 去重；
4. 任务状态回写至 pipeline_runs.status + Redis 进度缓存。

依赖：app.tasks.celery_app、app.tasks.base、app.pipelines.runner
"""
import logging
from typing import Any, Dict, Optional

from app.tasks._async_bridge import async_task
from app.tasks.base import (
    BaseTask,
    calculate_retry_backoff,
    TASK_STATE_STARTED,
)
from app.tasks.celery_app import get_celery_app

logger = logging.getLogger(__name__)

celery_app = get_celery_app()


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.test_execution.execute_pipeline",
    queue="test_execution",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=1,
    retry_backoff_max=60,
    retry_jitter=False,
    max_retries=3,
)
def execute_pipeline_task(
    self,
    pipeline_run_id: int,
    iteration_id: int,
    user_id: int,
    scenario: str = "default",
    dry_run: bool = False,
    ai_model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """执行 Pipeline 任务（Celery Worker 入口）。

    业务用途：将端点同步执行改为异步分布式执行，支持 ≥50 并发。
    边界场景：
    1. pipeline_run_id 不存在 → 抛 ValueError，不重试（数据错误）；
    2. AI 客户端连接失败 → 抛 ConnectionError，指数退避重试 3 次；
    3. 任务超时 → SoftTimeLimitExceeded，回写 failure 状态。

    幂等设计：基于 pipeline_run_id 去重，重复投递不重复执行（由 PipelineRunner 内部状态机保证）。

    Args:
        pipeline_run_id: Pipeline 运行记录 ID
        iteration_id: 迭代 ID
        user_id: 触发用户 ID
        scenario: 场景名称（默认 default）
        dry_run: 是否干跑（不真正执行步骤）
        ai_model: AI 模型配置（provider/api_key/model 等）

    Returns:
        任务执行结果，包含 run_id/status/iteration_id
    """
    self.on_start(self.request.id, args=(pipeline_run_id,), kwargs={})
    logger.info(
        f"开始执行 Pipeline: task_id={self.request.id}, "
        f"pipeline_run_id={pipeline_run_id}, iteration_id={iteration_id}, "
        f"scenario={scenario}, dry_run={dry_run}"
    )

    try:
        result = _run_pipeline_sync(
            pipeline_run_id=pipeline_run_id,
            iteration_id=iteration_id,
            user_id=user_id,
            scenario=scenario,
            dry_run=dry_run,
            ai_model=ai_model,
        )
        return result
    except (ConnectionError, TimeoutError) as e:
        # 可重试异常：指数退避
        retry_count = self.request.retries
        backoff = calculate_retry_backoff(retry_count)
        logger.warning(
            f"Pipeline 任务可重试异常: pipeline_run_id={pipeline_run_id}, "
            f"retry={retry_count}, backoff={backoff}s, error={e}"
        )
        raise self.retry(exc=e, countdown=backoff)
    except (ValueError, PermissionError) as e:
        # 不可重试异常：数据/权限错误
        logger.error(
            f"Pipeline 任务不可重试异常: pipeline_run_id={pipeline_run_id}, "
            f"error={e}"
        )
        raise
    except Exception as e:
        # 未知异常：尝试重试一次
        if self.request.retries < 3:
            logger.warning(f"Pipeline 任务未知异常，将重试: {e}")
            raise self.retry(exc=e, countdown=calculate_retry_backoff(self.request.retries))
        raise


def _run_pipeline_sync(
    pipeline_run_id: int,
    iteration_id: int,
    user_id: int,
    scenario: str,
    dry_run: bool,
    ai_model: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """同步执行 Pipeline（在 Celery Worker 进程内调用）。

    实现：从 DB 加载 PipelineRun 记录，重建 PipelineContext，调用 PipelineRunner.run()。
    与端点 run_pipeline 内的 _run 函数共享逻辑，但独立创建 DB 会话避免跨进程共享。
    """
    from app.db.database import PrimarySessionLocal
    from app.models.iteration import Iteration
    from app.models.pipeline import PipelineRun
    from app.pipelines.context import PipelineContext
    from app.pipelines.runner import PipelineRunner
    from app.pipelines.scenarios import get_scenario
    from app.services.iteration_service import transition_iteration_status

    db = PrimarySessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
        if not run:
            raise ValueError(f"PipelineRun 不存在: id={pipeline_run_id}")

        iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
        if not iteration:
            raise ValueError(f"Iteration 不存在: id={iteration_id}")

        scenario_config = get_scenario(scenario)
        if not scenario_config:
            raise ValueError(f"场景不存在: {scenario}")

        if iteration.status == "draft":
            transition_iteration_status(db, iteration_id, "in_pipeline")

        ai_client = _create_ai_client_from_config(ai_model)

        ctx = PipelineContext(
            db=db,
            ai_client=ai_client,
            run=run,
            iteration_id=iteration_id,
            user_id=user_id,
            config={"dry_run": dry_run, "scenario": scenario},
        )

        runner = PipelineRunner(scenario_config["name"], scenario_config["steps"])
        runner.run(ctx)

        db.commit()
        db.refresh(run)

        return {
            "run_id": run.id,
            "pipeline_run_id": run.id,
            "iteration_id": iteration_id,
            "status": run.status,
            "scenario": scenario,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _create_ai_client_from_config(ai_model: Optional[Dict[str, Any]]):
    """根据传入的 AI 模型配置创建 AI 客户端。

    边界场景：ai_model=None 时返回 None（场景无 AI 调用）。
    """
    if not ai_model:
        return None
    # 复用端点 _create_ai_client 逻辑，避免重复实现
    from app.api.v1.endpoints.pipeline import _create_ai_client
    return _create_ai_client(ai_model)
