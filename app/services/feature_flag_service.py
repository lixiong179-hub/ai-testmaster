"""
运行时特性开关服务

提供特性开关的 CRUD、启用/禁用切换以及灰度评估逻辑。
灰度评估规则：
    1. flag 不存在或 disabled → False
    2. target_type == "specific" 且 project_id 不在 target_project_ids 中 → False
    3. rollout_percentage == 100 → True
    4. rollout_percentage == 0 → False
    5. 否则按 hash(key + str(project_id or "")) % 100 < rollout_percentage 决定
"""
import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag


class FeatureFlagService:
    """运行时特性开关服务，封装 CRUD 与灰度评估逻辑"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def is_enabled(self, key: str, context: Optional[dict] = None) -> bool:
        """检查特性开关是否启用（简化入口，context 可传递 project_id / user_id）

        Args:
            key: 特性开关唯一标识
            context: 上下文字典，支持 project_id / user_id 键

        Returns:
            bool: 特性开关是否对当前上下文生效
        """
        ctx = context or {}
        return self.evaluate(
            key,
            project_id=ctx.get("project_id"),
            user_id=ctx.get("user_id"),
        )

    def evaluate(
        self,
        key: str,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        """评估特性开关值，按灰度规则判断是否生效

        Args:
            key: 特性开关唯一标识
            project_id: 项目ID，用于项目级定向与灰度分桶
            user_id: 用户ID（预留，当前未参与计算）

        Returns:
            bool: 特性开关是否对当前上下文生效
        """
        flag = self.get_flag(key)
        if flag is None or not flag.enabled:
            return False

        if flag.target_type == "specific":
            target_ids = flag.target_project_ids or []
            if project_id is None or project_id not in target_ids:
                return False

        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False

        bucket_key = f"{key}{project_id or ''}"
        bucket_value = int(hashlib.md5(bucket_key.encode()).hexdigest(), 16) % 100
        return bucket_value < flag.rollout_percentage

    def get_flag(self, key: str) -> Optional[FeatureFlag]:
        """根据 key 获取特性开关

        Args:
            key: 特性开关唯一标识

        Returns:
            FeatureFlag 实例，不存在时返回 None
        """
        return self.db.query(FeatureFlag).filter(FeatureFlag.key == key).first()

    def list_flags(self) -> list[FeatureFlag]:
        """获取所有特性开关列表

        Returns:
            FeatureFlag 实例列表
        """
        return self.db.query(FeatureFlag).order_by(FeatureFlag.key).all()

    def create_flag(
        self,
        key: str,
        name: str,
        description: Optional[str] = None,
        enabled: bool = True,
        rollout_percentage: int = 100,
        target_type: str = "all",
        target_project_ids: Optional[list[int]] = None,
    ) -> FeatureFlag:
        """创建特性开关

        Args:
            key: 特性开关唯一标识
            name: 显示名称
            description: 描述
            enabled: 是否启用
            rollout_percentage: 灰度比例(0-100)
            target_type: 投放类型 all/specific
            target_project_ids: 目标项目ID列表

        Returns:
            FeatureFlag: 已持久化的特性开关实例

        Raises:
            ValueError: key 已存在
        """
        existing = self.get_flag(key)
        if existing is not None:
            raise ValueError(f"特性开关已存在: {key}")

        flag = FeatureFlag(
            key=key,
            name=name,
            description=description,
            enabled=enabled,
            rollout_percentage=rollout_percentage,
            target_type=target_type,
            target_project_ids=target_project_ids,
        )
        self.db.add(flag)
        self.db.flush()
        self.db.refresh(flag)
        return flag

    def update_flag(self, key: str, **kwargs) -> FeatureFlag:
        """更新特性开关属性

        Args:
            key: 特性开关唯一标识
            **kwargs: 需要更新的字段（name/description/enabled/rollout_percentage/target_type/target_project_ids）

        Returns:
            FeatureFlag: 更新后的特性开关实例

        Raises:
            ValueError: key 不存在
        """
        flag = self.get_flag(key)
        if flag is None:
            raise ValueError(f"特性开关不存在: {key}")

        allowed_fields = {
            "name", "description", "enabled",
            "rollout_percentage", "target_type", "target_project_ids",
        }
        for field_name, value in kwargs.items():
            if field_name in allowed_fields and value is not None:
                setattr(flag, field_name, value)

        self.db.flush()
        self.db.refresh(flag)
        return flag

    def toggle_flag(self, key: str, enabled: bool) -> FeatureFlag:
        """切换特性开关启用/禁用状态

        Args:
            key: 特性开关唯一标识
            enabled: 目标启用状态

        Returns:
            FeatureFlag: 更新后的特性开关实例

        Raises:
            ValueError: key 不存在
        """
        flag = self.get_flag(key)
        if flag is None:
            raise ValueError(f"特性开关不存在: {key}")

        flag.enabled = enabled
        self.db.flush()
        self.db.refresh(flag)
        return flag

    def delete_flag(self, key: str) -> bool:
        """删除特性开关

        Args:
            key: 特性开关唯一标识

        Returns:
            bool: 是否成功删除（True=已删除，False=不存在）

        Raises:
            ValueError: key 不存在
        """
        flag = self.get_flag(key)
        if flag is None:
            raise ValueError(f"特性开关不存在: {key}")

        self.db.delete(flag)
        self.db.flush()
        return True
