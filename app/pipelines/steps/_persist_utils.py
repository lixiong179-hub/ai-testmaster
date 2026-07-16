"""Persist Step 辅助工具函数。

提供 JSON 序列化、日期解析、评分映射构建与用例步骤持久化能力，
供 Persist Step 主流程复用。
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.pipelines.context import PipelineContext


def _serialize_json_field(value: Any) -> Optional[str]:
    """将列表或已序列化的字符串统一为 JSON 字符串。

    Args:
        value: 列表或已序列化的字符串。

    Returns:
        JSON 字符串或 None。
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return None


def _parse_datetime_field(value: Any) -> Optional[datetime]:
    """将 ISO 字符串或 datetime 对象统一为 datetime 对象。

    用于解析 case_data 中的 last_verified_at 字段（由 ExecutionValidation
    Step 写入）。支持 ISO 8601 字符串和 datetime 对象，非法值返回 None。

    Args:
        value: ISO 字符串、datetime 对象或 None。

    Returns:
        datetime 对象或 None。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("last_verified_at 非法 ISO 字符串: {}，已置为 None", value)
            return None
    logger.warning(
        "last_verified_at 非法类型: {}，已置为 None", type(value).__name__,
    )
    return None


def _build_score_map(scores_artifact: Optional[Dict[str, Any]]) -> Dict[str, Dict]:
    """构建 case_title -> score_info 映射（fallback 用）。

    主路径优先从 case_data 取 QualityGate 直接写入的分数，
    此函数仅在 case_data 缺少分数时作为 fallback。
    使用 case_title 而非 tp_id 作为键，避免同一测试点多用例覆盖。
    """
    if not scores_artifact:
        return {}
    result = {}
    for score in scores_artifact.get("scores", []):
        title = score.get("case_title", "")
        if title:
            result[title] = score
    return result


def _persist_case_steps(
    ctx: PipelineContext,
    case_id: int,
    steps_json: List[Dict[str, Any]],
    has_ui: bool,
) -> None:
    """将用例步骤批量写入 TestStep 表。

    Args:
        ctx: Pipeline 上下文，提供 db 会话。
        case_id: 关联的 TestCase.id。
        steps_json: 步骤数据列表。
        has_ui: 是否为 UI 用例（影响 locator 字段填充）。
    """
    from app.models.test_case import TestStep

    steps_to_add = []
    for index, step_data in enumerate(steps_json, start=1):
        action = (
            step_data.get("action")
            or step_data.get("step")
            or step_data.get("description")
            or ""
        )
        expected = (
            step_data.get("expected")
            or step_data.get("expected_result")
            or step_data.get("expect")
            or ""
        )
        has_locator = int(step_data.get("has_locator", 0)) if has_ui else 0
        locator_status = step_data.get("locator_status") if has_ui else "pending"
        steps_to_add.append(TestStep(
            test_case_id=case_id,
            step_number=index,
            action=str(action),
            expected_result=str(expected),
            has_locator=has_locator,
            locator_status=locator_status or "pending",
            action_type=step_data.get("action_type"),
            input_value=step_data.get("input_value"),
            target_element=step_data.get("target_element"),
        ))

    if steps_to_add:
        ctx.db.add_all(steps_to_add)
