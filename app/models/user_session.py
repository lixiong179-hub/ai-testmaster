"""
用户会话模型模块

本模块定义 UserSession 模型，记录每次登录后的会话元数据，支撑
会话治理端点（logout / logout-all / sessions / DELETE）与
deprovisioning 级联撤销（SCIM deprovisioning 时撤销所有会话）。

核心类概览：
    - UserSession : 用户会话模型

表关系：
    - User → UserSession（一对多，user_id 关联 users.id，ondelete=CASCADE）

字段语义：
    - refresh_jti   : refresh_token 的 jti 声明（唯一标识），用于黑名单匹配
    - user_agent    : 客户端 User-Agent（用于设备识别）
    - ip_address    : 登录时客户端 IP（用于安全审计）
    - last_active_at: 最后活跃时间（每次刷新 access_token 时更新）
    - expires_at    : 会话过期时间（与 refresh_token 的 exp 对齐）
    - revoked_at    : 会话撤销时间（NULL 表示有效，logout 时写入）
"""
from typing import Any, Dict

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)

from app.db.database import Base
from app.utils.db_time import utcnow


class UserSession(Base):
    """
    用户会话模型

    每条记录描述一次登录会话：用户 ID、refresh_token 的 jti、客户端信息、
    创建/最后活跃/过期/撤销时间。logout 端点通过写入 revoked_at 撤销会话，
    logout-all 撤销该用户所有有效会话。

    表关系：
        - 外键关联 → User（user_id，ondelete=CASCADE，
                                  用户删除时会话级联清除）

    使用场景：
        - 登录时创建会话记录
        - logout/logout-all 端点撤销会话
        - sessions 端点查询用户的有效会话列表
        - SCIM deprovisioning 时级联撤销所有会话
    """
    __tablename__ = "user_sessions"
    __table_args__ = (
        # 复合索引：覆盖按用户+有效状态维度检索会话的高频查询（sessions 端点）
        Index("idx_user_active", "user_id", "revoked_at"),
        # 单列索引：按 refresh_jti 检索会话（refresh 端点校验 jti 黑名单）
        Index("idx_jti", "refresh_jti"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="会话主键ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    refresh_jti = Column(String(128), nullable=False, unique=True, comment="refresh_token 的 jti 声明（唯一标识）")

    user_agent = Column(String(512), nullable=True, comment="客户端 User-Agent（用于设备识别）")
    ip_address = Column(String(64), nullable=True, comment="登录时客户端 IP（用于安全审计）")

    created_at = Column(DateTime, default=utcnow, nullable=False, comment="会话创建时间（UTC）")
    last_active_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False, comment="最后活跃时间（UTC）")
    expires_at = Column(DateTime, nullable=False, comment="会话过期时间（与 refresh_token exp 对齐）")
    revoked_at = Column(DateTime, nullable=True, comment="会话撤销时间（NULL 表示有效）")

    def __repr__(self) -> str:
        return (
            f"<UserSession(id={self.id}, user_id={self.user_id}, "
            f"jti={self.refresh_jti[:8]}..., revoked={self.revoked_at is not None})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回会话核心字段字典，供 API 响应使用。"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "refresh_jti": self.refresh_jti,
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "is_active": self.revoked_at is None,
        }

    @property
    def is_active(self) -> bool:
        """会话是否有效（未撤销且未过期）。"""
        if self.revoked_at is not None:
            return False
        # expires_at 与 revoked_at 均为 UTC naive datetime
        return self.expires_at > utcnow() if self.expires_at else False
