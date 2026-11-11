"""项目级视觉校验配置服务（R3-3）。

配置存储于 `Project.config['visual_validation_config']`，与自愈配置
`self_healing_config` 同构：

    enabled = settings.AI_VISUAL_VALIDATION_ENABLED AND 项目级 enabled

全局关闭时项目强制关闭，保证「默认关」策略不可被单项目绕过；
Q4 决策为「按项目配置、默认关」，因此缺省项目配置 enabled=True 但全局 False，
实际效果仍是关闭，需显式开启全局 + 项目双开关才生效。
"""
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import Project

DEFAULT_VISUAL_VALIDATION_CONFIG: dict[str, Any] = {
    "enabled": True,
    "diff_threshold": 5.0,
    "ignore_colors": False,
}
CONFIG_KEY: str = "visual_validation_config"
DIFF_THRESHOLD_MIN: float = 0.0
DIFF_THRESHOLD_MAX: float = 100.0


def resolve_enabled(project_config: Any) -> bool:
    """纯函数：计算视觉校验最终开关（全局 AND 项目）。

    Args:
        project_config: `Project.config` 原始值（可能为 None / 非 dict）。

    Returns:
        bool: 全局与项目开关同时为真时返回 True。
    """
    if not settings.AI_VISUAL_VALIDATION_ENABLED:
        return False
    raw = project_config if isinstance(project_config, dict) else {}
    stored = raw.get(CONFIG_KEY, {})
    stored = stored if isinstance(stored, dict) else {}
    project_enabled = stored.get("enabled", DEFAULT_VISUAL_VALIDATION_CONFIG["enabled"])
    return bool(settings.AI_VISUAL_VALIDATION_ENABLED and project_enabled)


class VisualValidationConfigService:
    """项目级视觉校验配置服务，存储于 Project.config JSON 字段。"""

    def __init__(self, db: Session) -> None:
        """注入数据库会话，禁止内部新建 Session。"""
        self._db = db

    def get_project_config(self, project_id: int) -> dict:
        """获取项目视觉校验配置，合并默认值与全局开关。

        项目不存在时返回 enabled=False 的默认配置，避免执行链路抛异常。
        """
        project = self._db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return {**DEFAULT_VISUAL_VALIDATION_CONFIG, "enabled": False}

        merged = {**DEFAULT_VISUAL_VALIDATION_CONFIG}
        raw = project.config if isinstance(project.config, dict) else {}
        stored = raw.get(CONFIG_KEY, {})
        if isinstance(stored, dict):
            merged.update(stored)
        merged["enabled"] = resolve_enabled(raw)
        return merged

    def set_project_config(self, project_id: int, config: dict) -> dict:
        """更新项目视觉校验配置，写入 Project.config['visual_validation_config']。

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

        validated["enabled"] = resolve_enabled(project_config)
        return validated

    def is_visual_validation_enabled(self, project_id: int) -> bool:
        """快捷判断项目视觉校验是否启用（全局 AND 项目）。"""
        return bool(self.get_project_config(project_id).get("enabled", False))

    @staticmethod
    def _validate_config(config: dict) -> dict:
        """校验并归一化配置字段。

        Raises:
            HTTPException: 字段类型或取值非法(400)。
        """
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="配置必须为字典对象")

        result = {**DEFAULT_VISUAL_VALIDATION_CONFIG}

        enabled = config.get("enabled", result["enabled"])
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=400, detail="enabled 必须为布尔值")
        result["enabled"] = enabled

        ignore_colors = config.get("ignore_colors", result["ignore_colors"])
        if not isinstance(ignore_colors, bool):
            raise HTTPException(status_code=400, detail="ignore_colors 必须为布尔值")
        result["ignore_colors"] = ignore_colors

        diff_threshold = config.get("diff_threshold", result["diff_threshold"])
        if isinstance(diff_threshold, bool) or not isinstance(diff_threshold, (int, float)):
            raise HTTPException(status_code=400, detail="diff_threshold 必须为数值")
        if not (DIFF_THRESHOLD_MIN <= float(diff_threshold) <= DIFF_THRESHOLD_MAX):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"diff_threshold 取值范围: "
                    f"[{DIFF_THRESHOLD_MIN}, {DIFF_THRESHOLD_MAX}]"
                ),
            )
        result["diff_threshold"] = float(diff_threshold)

        return result


__all__ = [
    "CONFIG_KEY",
    "DEFAULT_VISUAL_VALIDATION_CONFIG",
    "VisualValidationConfigService",
    "resolve_enabled",
]
