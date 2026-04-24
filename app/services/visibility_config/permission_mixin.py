"""可见模式配置服务 - 权限校验逻辑"""
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.models.project import Project


class VisibilityConfigPermissionMixin:
    """可见模式配置权限校验Mixin"""

    def check_permission(
        self,
        db: Session,
        user_id: int,
        project_id: int,
        required_role: str = "member"
    ) -> bool:
        """检查用户是否有权限访问指定项目的可见模式配置。

        权限校验规则:
            1. 项目必须存在且状态正常（status=1）
            2. 用户必须是项目所有者（user_id匹配）
            3. required_role参数预留扩展，当前仅校验项目所有权

        Args:
            db: 数据库会话。
            user_id: 用户ID。
            project_id: 项目ID。
            required_role: 所需角色（预留扩展，当前未使用）。

        Returns:
            是否有权限。
        """
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id,
            Project.status == 1
        ).first()

        if not project:
            logger.warning(
                f"用户 {user_id} 无权访问项目 {project_id} 的可见模式配置: "
                f"项目不存在、用户非所有者或项目已归档"
            )
            return False

        return True
