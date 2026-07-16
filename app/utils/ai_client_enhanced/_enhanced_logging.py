from typing import Dict, Any, Optional
from loguru import logger


def _record_enhanced_call(
    metadata: Optional[Dict[str, Any]],
    model_name: str,
    response: Any,
    latency_ms: int,
) -> None:
    """记录增强版 AI 调用日志

    从 metadata 提取审计增强字段，从 response 提取 Token 用量，
    统一写入 AICallLog。

    Args:
        metadata: 元数据字典（含 db, generation_batch_id, scenario_type 等）
        model_name: 模型名称
        response: OpenAI API 响应对象
        latency_ms: 调用耗时（毫秒）
    """
    try:
        from app.ai.call_log import record_call
        db = metadata.get("db") if metadata else None
        usage_data = response.usage
        prompt_tokens = usage_data.prompt_tokens if usage_data else 0
        completion_tokens = usage_data.completion_tokens if usage_data else 0
        cost_usd = (
            prompt_tokens / 1000 * 0.0014
            + completion_tokens / 1000 * 0.0028
        )
        record_call(
            db,
            model=response.model or model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost_usd, 6),
            latency_ms=latency_ms,
            step_name=metadata.get("step_name") if metadata else None,
            run_id=metadata.get("run_id") if metadata else None,
            generation_batch_id=metadata.get("generation_batch_id") if metadata else None,
            scenario_type=metadata.get("scenario_type") if metadata else None,
            generation_strategy=metadata.get("generation_strategy") if metadata else None,
            prompt_key=metadata.get("prompt_key") if metadata else None,
            prompt_version=metadata.get("prompt_version") if metadata else None,
            prompt_hash=metadata.get("prompt_hash") if metadata else None,
        )
    except Exception as log_err:
        logger.warning(f"Failed to record enhanced AI call log: {log_err}")
