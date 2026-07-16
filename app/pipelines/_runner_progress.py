"""Pipeline 进度推送辅助模块。

从 runner.py 拆分而来，负责通过 WebSocket 向前端推送 Pipeline 执行进度。
推送采用 fire-and-forget 策略，失败不影响业务流程。
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


def _push_pipeline_progress(
    run_id: int,
    step_name: str,
    status: str,
    progress: float,
    pipeline_status: str,
) -> None:
    """通过 WebSocket 推送 Pipeline 进度（fire-and-forget）。

    在 Step 状态变更时调用，将进度信息推送到前端 WebSocket 客户端。
    推送失败不影响业务流程，仅记录警告日志。

    Args:
        run_id: Pipeline 运行 ID。
        step_name: 步骤名称，Pipeline 级别事件传空字符串。
        status: 当前步骤或 Pipeline 的状态。
        progress: 进度百分比（0-100）。
        pipeline_status: Pipeline 整体状态。
    """
    try:
        from app.services.push_service import get_push_service
        push_service = get_push_service()
        data = {
            "type": "pipeline_progress",
            "run_id": run_id,
            "step_name": step_name,
            "status": status,
            "progress": progress,
            "pipeline_status": pipeline_status,
        }
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(push_service.push(f"pipeline:{run_id}", data))
    except RuntimeError:
        logger.debug("No running event loop, skipping pipeline progress push")
    except Exception as e:
        logger.warning("Pipeline progress push failed: %s", e)
