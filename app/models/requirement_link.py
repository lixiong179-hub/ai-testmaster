"""
需求链接模型模块

本模块定义了需求链接（RequirementLink）模型，用于管理需求文档链接、
UI原型图链接等外部资源链接，支持带认证的外部资源访问。

核心类概览：
    - RequirementLink : 需求链接模型，支持多种认证方式

表关系：
    Project → RequirementLink（一对多，级联删除）
    User → RequirementLink（一对多，创建者，SET NULL）

依赖关系：
    - app.utils.crypto.encrypt_password / decrypt_password : 认证配置加解密
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类

安全说明：
    认证配置（auth_config）通过加密存储，数据库中仅保留密文，
    防止凭据泄露。
"""
import json as _json
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.crypto import encrypt_password, decrypt_password


class RequirementLink(Base):
    """
    需求链接模型 - 存储需求文档链接、UI原型图链接等

    支持多种认证方式：Basic Auth、Bearer Token、API Key、无认证。
    认证配置加密存储，确保凭据安全。支持内容缓存，减少重复获取。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → User（创建者，SET NULL）

    使用场景：
        - 管理外部需求文档链接（如Confluence、语雀）
        - 管理UI原型链接（如摹客、蓝湖）
        - 自动获取链接内容用于AI分析
    """
    __tablename__ = "requirement_links"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                            # 链接主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID")  # 项目ID，级联删除

    # 链接基本信息
    link_name = Column(String(200), nullable=False, comment="链接名称，如：需求文档_v1.2、Axure原型")   # 链接显示名称
    link_type = Column(String(50), nullable=False, comment="链接类型: requirement/ui_mockup/api_doc/other")  # requirement=需求文档，ui_mockup=UI原型，api_doc=接口文档，other=其他
    link_url = Column(String(1000), nullable=False, comment="链接地址")                                # 外部资源URL

    # 认证配置（存储加密后的凭据）
    auth_type = Column(String(50), nullable=False, default="none", comment="认证类型: none/basic/bearer/api_key/cookie")  # none=无认证，basic=Basic Auth，bearer=Bearer Token，api_key=API密钥，cookie=Cookie认证
    auth_config_encrypted = Column("auth_config", JSON, nullable=True, comment="认证配置JSON(加密存储)")  # 数据库列名为auth_config，存储加密密文

    # 链接元数据
    description = Column(Text, nullable=True, comment="链接描述")                                      # 链接用途说明
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")                       # 软删除标记
    last_fetch_time = Column(DateTime, nullable=True, comment="最后获取时间")                           # 最近一次获取内容的时间
    last_fetch_status = Column(String(50), nullable=True, comment="最后获取状态: success/failed")       # success=获取成功，failed=获取失败

    # 缓存的内容（用于快速访问）
    cached_content = Column(Text, nullable=True, comment="缓存的内容摘要")                              # 缓存的内容摘要，避免频繁获取
    cache_expire_minutes = Column(Integer, nullable=False, default=60, comment="缓存过期时间（分钟）")   # 缓存过期时间，默认60分钟

    # 关联用户
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)          # 创建者ID，SET NULL保留链接
    create_time = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")                 # 创建时间，UTC时区
    update_time = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, comment="更新时间") # 更新时间

    @property
    def auth_config(self) -> dict:
        """
        获取认证配置的明文值。

        Returns:
            dict: 解密后的认证配置字典；未设置时返回空字典。

        安全说明：自动解密加密存储的认证配置，
        解密失败时返回原始数据（兼容未加密的旧数据）。
        """
        raw = self.auth_config_encrypted
        if not raw:
            return {}
        if isinstance(raw, dict):
            encrypted_str = raw.get("_encrypted")
            if encrypted_str:
                try:
                    return _json.loads(decrypt_password(encrypted_str))
                except Exception:
                    return raw
        return raw

    @auth_config.setter
    def auth_config(self, value: dict) -> None:
        """
        设置认证配置，自动加密后存储。

        Args:
            value: 认证配置字典，如 {"username": "xxx", "password": "xxx"}。
                   若为空则清除认证配置。

        安全说明：认证配置通过 app.utils.crypto 加密后存储到数据库，
        数据库中仅保留密文，防止凭据泄露。
        """
        if not value:
            self.auth_config_encrypted = None
        else:
            encrypted_str = encrypt_password(_json.dumps(value, ensure_ascii=False))
            self.auth_config_encrypted = {"_encrypted": encrypted_str}

    # 关联关系
    project = relationship("Project", back_populates="requirement_links")                             # 所属项目
    creator = relationship("User", foreign_keys=[created_by])                                         # 创建者


# 扩展Project模型，添加关联关系
from app.models.project import Project
Project.requirement_links = relationship("RequirementLink", back_populates="project", cascade="all, delete-orphan")  # 动态扩展Project模型，添加需求链接关联
