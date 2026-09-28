"""项目级自愈配置服务模块。

存储于 Project.config['self_healing_config'] JSON 子键。enabled 取全局开关
(settings.AI_SELF_HEALING_ENABLED) AND 项目开关，全局关闭时项目强制关闭，
保证灰度发布安全。
"""
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import Project

DEFAULT_SELF_HEALING_CONFIG: dict[str, Any] = {
    "enabled": True,
    "strategies": ["mcp", "vision"],
    "token_limit": 2000,
}
ALLOWED_STRATEGIES: frozenset[str] = frozenset({"mcp", "vision", "stagehand"})
TOKEN_LIMIT_MIN: int = 1
TOKEN_LIMIT_MAX: int = 10000
CONFIG_KEY: str = "self_healing_config"


class SelfHealingConfigService:
    """项目级自愈配置服务，存储于 Project.config JSON 字段。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_project_config(self, project_id: int) -> dict:
        """获取项目自愈配置，合并默认值与全局开关。

        项目不存在时返回 enabled=False 的默认配置，避免执行链路抛异常。
        enabled = settings.AI_SELF_HEALING_ENABLED AND 项目开关。
        """
        project = self._db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return {**DEFAULT_SELF_HEALING_CONFIG, "enabled": False}

        raw = project.config if isinstance(project.config, dict) else {}
        stored = raw.get(CONFIG_KEY, {})
        stored = stored if isinstance(stored, dict) else {}
        merged = {**DEFAULT_SELF_HEALING_CONFIG, **stored}
        merged["enabled"] = bool(
            settings.AI_SELF_HEALING_ENABLED and merged.get("enabled", True)
        )
        return merged

    def set_project_config(self, project_id: int, config: dict) -> dict:
        """更新项目自愈配置，写入 Project.config['self_healing_config']。

        Raises:
            HTTPException: 项目不存在(404) 或字段校验失败(400)。
        """
        project = self._db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

        validated = self._validate_config(config)
        project_config = dict(project.config) if isinstance(project.config, dict) else {}
        project_config[CONFIG_KEY] = validated
        project.config = project_config
        self._db.commit()
        self._db.refresh(project)

        validated["enabled"] = bool(
            settings.AI_SELF_HEALING_ENABLED and validated["enabled"]
        )
        return validated

    def is_self_healing_enabled(self, project_id: int) -> bool:
        """快捷判断项目自愈是否启用（全局 AND 项目）。"""
        return bool(self.get_project_config(project_id).get("enabled", False))

    @staticmethod
    def _validate_config(config: dict) -> dict:
        """校验并归一化配置字段，返回含全部三字段的 dict。

        Raises:
            HTTPException: 字段类型或取值非法(400)。
        """
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="配置必须为字典对象")

        result = {**DEFAULT_SELF_HEALING_CONFIG}

        enabled = config.get("enabled", result["enabled"])
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=400, detail="enabled 必须为布尔值")
        result["enabled"] = enabled

        strategies = config.get("strategies", result["strategies"])
        if not isinstance(strategies, list) or not all(
            isinstance(s, str) for s in strategies
        ):
            raise HTTPException(status_code=400, detail="strategies 必须为字符串列表")
        invalid = [s for s in strategies if s not in ALLOWED_STRATEGIES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"strategies 含非法值: {invalid}, 仅允许 {sorted(ALLOWED_STRATEGIES)}",
            )
        result["strategies"] = strategies

        token_limit = config.get("token_limit", result["token_limit"])
        # bool 是 int 子类，需单独排除
        if not isinstance(token_limit, int) or isinstance(token_limit, bool):
            raise HTTPException(status_code=400, detail="token_limit 必须为整数")
        if not (TOKEN_LIMIT_MIN <= token_limit <= TOKEN_LIMIT_MAX):
            raise HTTPException(
                status_code=400,
                detail=f"token_limit 取值范围: [{TOKEN_LIMIT_MIN}, {TOKEN_LIMIT_MAX}]",
            )
        result["token_limit"] = token_limit

        return result
