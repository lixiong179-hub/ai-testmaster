"""
Pipeline 配置管理服务模块

本模块提供配置项的读写功能，启动时从 DB 加载到内存缓存，
set_config 时刷新缓存并写入 audit_log。

核心函数概览：
    - get_config : 读取配置项（优先内存缓存 → DB → default）
    - set_config : 修改配置项（写入 DB + 刷新缓存 + 写入 audit_log）
    - init_default_configs : 初始化默认配置项（幂等）

依赖关系：
    - app.models.pipeline_config : PipelineConfig
    - app.services.audit_service : 审计日志
"""
import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session
from app.models.pipeline_config import PipelineConfig

logger = logging.getLogger(__name__)

_cache: dict[str, Any] = {}

DEFAULT_CONFIGS: dict[str, dict] = {
    "LIFECYCLE_DEPRECATE_COOLDOWN_HOURS": {
        "value": "24", "value_type": "int",
        "description": "deprecated → archived 冷却时间（小时）",
    },
    "AI_TOKEN_BUDGET_PER_RUN": {
        "value": "500000", "value_type": "int",
        "description": "单次 PipelineRun token 上限",
    },
    "CONFIDENCE_THRESHOLD": {
        "value": "0.7", "value_type": "float",
        "description": "低于此值强制人工确认",
    },
    "REVIEW_LOCK_TTL_HOURS": {
        "value": "24", "value_type": "int",
        "description": "评审锁过期时间（小时）",
    },
    "PIPELINE_PAUSE_TIMEOUT_DAYS": {
        "value": "7", "value_type": "int",
        "description": "Pipeline 暂停超时自动取消（天）",
    },
    "BATCH_SIZE_BACKWARD_SCAN": {
        "value": "50", "value_type": "int",
        "description": "反向扫描每批用例数",
    },
    "BATCH_SIZE_SUMMARY_BACKFILL": {
        "value": "20", "value_type": "int",
        "description": "summary 回填每批用例数",
    },
    "REVIEW_UNDO_WINDOW_MINUTES": {
        "value": "60", "value_type": "int",
        "description": "finalize 后允许回滚的时间窗口（分钟）",
    },
    "AUTO_APPROVE_MIN_GRADE": {
        "value": "A", "value_type": "str",
        "description": "自动通过最低先验等级（A/B/C/NONE）",
    },
    "PIPELINE_VERSION": {
        "value": "1.0", "value_type": "str",
        "description": "Pipeline 逻辑版本，变更时强制重跑",
    },
    "SUMMARY_MAX_LENGTH": {
        "value": "200", "value_type": "int",
        "description": "summary 最大字数",
    },
    "LINEAGE_CHAIN_WARNING_LENGTH": {
        "value": "3", "value_type": "int",
        "description": "血缘链长度警告阈值",
    },
    "PRIOR_QUALITY_D_THRESHOLD": {
        "value": "45", "value_type": "int",
        "description": "先验质量 D 级阈值",
    },
    "POSTERIOR_MIN_EXECUTIONS": {
        "value": "3", "value_type": "int",
        "description": "后验分最少执行次数",
    },
}


def _cast_value(raw: str, value_type: str) -> Any:
    """将文本值转换为指定类型。

    Args:
        raw: 文本值。
        value_type: 目标类型。

    Returns:
        转换后的值。

    Raises:
        ValueError: 类型转换失败。
    """
    try:
        if value_type == "int":
            return int(raw)
        if value_type == "float":
            return float(raw)
        if value_type == "bool":
            return raw.lower() in ("true", "1", "yes")
        if value_type == "json":
            return json.loads(raw)
        return raw
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Cannot cast '{raw}' to {value_type}: {e}") from e


def get_config(db: Session, key: str, default: Any = None) -> Any:
    """读取配置项。

    优先级：内存缓存 → DB → default。

    Args:
        db: 数据库会话。
        key: 配置项键名。
        default: 默认值（DB 中不存在时返回）。

    Returns:
        配置项值（已类型转换）。
    """
    if key in _cache:
        return _cache[key]

    row = db.query(PipelineConfig).filter(PipelineConfig.key == key).first()
    if row is None:
        return default

    value = _cast_value(row.value, row.value_type)
    _cache[key] = value
    return value


def set_config(
    db: Session,
    key: str,
    value: Any,
    actor_id: Optional[int] = None,
) -> PipelineConfig:
    """修改配置项。

    写入 DB + 刷新内存缓存 + 写入 audit_log。

    Args:
        db: 数据库会话。
        key: 配置项键名。
        value: 新值。
        actor_id: 操作人 ID。

    Returns:
        更新后的 PipelineConfig 实例。

    Raises:
        ValueError: key 不存在且不在 DEFAULT_CONFIGS 中。
    """
    row = db.query(PipelineConfig).filter(PipelineConfig.key == key).first()

    if row is None:
        if key not in DEFAULT_CONFIGS:
            raise ValueError(f"Unknown config key: '{key}'")
        meta = DEFAULT_CONFIGS[key]
        row = PipelineConfig(
            key=key,
            value=str(value),
            value_type=meta["value_type"],
            description=meta.get("description"),
            updated_by=actor_id,
        )
        db.add(row)
        old_value = None
    else:
        old_value = row.value
        row.value = str(value)
        row.updated_by = actor_id

    db.flush()

    _cache[key] = _cast_value(row.value, row.value_type)

    try:
        from app.services.audit_service import log_action
        log_action(
            db=db,
            action="config_change",
            actor_id=actor_id,
            target_kind="pipeline_config",
            target_id=row.id,
            detail={"key": key, "old_value": old_value, "new_value": str(value)},
        )
    except Exception as e:
        logger.error("Failed to write audit log for config_change: key=%s, error=%s", key, e)

    return row


def init_default_configs(db: Session) -> None:
    """初始化默认配置项（幂等：已存在的 key 不覆盖）。

    Args:
        db: 数据库会话。
    """
    for key, meta in DEFAULT_CONFIGS.items():
        existing = db.query(PipelineConfig).filter(PipelineConfig.key == key).first()
        if existing is None:
            row = PipelineConfig(
                key=key,
                value=meta["value"],
                value_type=meta["value_type"],
                description=meta.get("description"),
            )
            db.add(row)
    db.flush()

    _load_cache(db)


def _load_cache(db: Session) -> None:
    """从 DB 加载所有配置项到内存缓存。"""
    rows = db.query(PipelineConfig).all()
    for row in rows:
        _cache[row.key] = _cast_value(row.value, row.value_type)


def clear_cache() -> None:
    """清空内存缓存（仅用于测试）。"""
    _cache.clear()
