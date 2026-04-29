"""
需求链接CRUD操作模块

提供需求链接（RequirementLink）的增删改查数据库操作。需求链接管理外部需求来源
（如Jira、Confluence、墨刀等）的URL引用，支持认证配置、内容缓存、启用状态切换等。

核心函数概览：
    - create_requirement_link: 创建需求链接（支持多种认证类型）
    - get_requirement_link_by_id: 根据ID获取链接（可选项目隔离）
    - get_requirement_links_by_project: 获取项目链接列表（JOIN Project权限隔离+动态过滤）
    - get_requirement_links_count: 获取链接数量（用于分页计算）
    - get_requirement_links_by_types: 根据类型列表获取链接（IN查询）
    - update_requirement_link: 更新链接（保护字段不可修改）
    - delete_requirement_link: 删除链接（硬删除）
    - update_link_cache: 更新链接缓存内容和抓取状态
    - get_active_links_by_project: 获取项目的所有有效链接（用于AI用例生成）
    - toggle_link_active: 切换链接启用状态
    - check_link_exists: 检查链接URL是否已存在（防重复）

与Model/Schema的对应关系：
    - Model: app.models.requirement_link.RequirementLink
    - 关联Model: app.models.project.Project（JOIN查询用于用户权限过滤）

与其他CRUD模块的调用关系：
    - 链接内容缓存供AI分析使用，作为测试用例生成的输入源
    - 链接可关联UI原型（link_type=ui_mockup）

事务处理方式：
    - 所有写操作均自动commit

软删除/硬删除：
    - delete_requirement_link 为硬删除
    - toggle_link_active 提供软性启停控制（is_active字段）

链接类型枚举：
    - requirement: 需求文档链接
    - ui_mockup: UI原型图链接
    - api_doc: API文档链接
    - other: 其他链接

认证类型枚举：
    - none: 无需认证
    - basic: Basic认证
    - bearer: Bearer Token认证
    - api_key: API Key认证
    - cookie: Cookie认证
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.requirement_link import RequirementLink
from app.models.project import Project
from datetime import datetime
from app.utils.db_time import utcnow


def create_requirement_link(
    db: Session,
    project_id: int,
    link_name: str,
    link_type: str,
    link_url: str,
    created_by: Optional[int] = None,
    auth_type: str = "none",
    auth_config: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    cache_expire_minutes: int = 60
) -> RequirementLink:
    """
    创建需求链接

    创建一条外部需求来源的URL引用记录，支持多种认证类型和缓存配置。

    Args:
        db: 数据库会话
        project_id: 所属项目ID
        link_name: 链接名称，便于识别，如"PRD-v2.0"
        link_type: 链接类型: requirement/ui_mockup/api_doc/other
        link_url: 链接地址，完整URL
        created_by: 创建人用户ID（可选）
        auth_type: 认证类型: none/basic/bearer/api_key/cookie
        auth_config: 认证配置（可选），JSON格式，如{"username":"xxx","password":"xxx"}
        description: 链接描述（可选）
        cache_expire_minutes: 缓存过期时间（分钟），默认60分钟

    Returns:
        RequirementLink: 创建成功后的链接对象（已commit并refresh）

    Warning:
        auth_config中可能包含敏感信息（如密码、Token），应在存储前加密，
        日志中脱敏处理。
    """
    db_link = RequirementLink(
        project_id=project_id,
        link_name=link_name,
        link_type=link_type,
        link_url=link_url,
        created_by=created_by,
        auth_type=auth_type,
        auth_config=auth_config,
        description=description,
        cache_expire_minutes=cache_expire_minutes
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link


def get_requirement_link_by_id(
    db: Session,
    link_id: int,
    project_id: Optional[int] = None
) -> Optional[RequirementLink]:
    """
    根据ID获取需求链接

    支持可选的项目ID过滤，传入project_id时增加项目维度隔离校验。

    Args:
        db: 数据库会话
        link_id: 链接ID
        project_id: 项目ID（可选），用于隔离校验

    Returns:
        RequirementLink: 链接对象或None

    Note:
        project_id为可选参数，不传时仅按link_id查询，适用于内部调用；
        传入时增加项目维度校验，防止跨项目访问。
    """
    query = db.query(RequirementLink).filter(RequirementLink.id == link_id)
    if project_id:
        query = query.filter(RequirementLink.project_id == project_id)
    return query.first()


def get_requirement_links_by_project(
    db: Session,
    project_id: int,
    user_id: int,
    link_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100
) -> List[RequirementLink]:
    """
    获取项目的需求链接列表（多项目隔离）

    通过JOIN Project表实现用户权限隔离，支持按链接类型和启用状态动态过滤。
    按创建时间倒序排列。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project实现权限隔离
        link_type: 链接类型筛选（可选）
        is_active: 是否启用筛选（可选）
        skip: 跳过数量
        limit: 限制数量

    Returns:
        List[RequirementLink]: 需求链接列表，按创建时间倒序
    """
    # JOIN Project表：通过Project.user_id实现用户权限隔离
    query = db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id
    )

    # 动态追加过滤条件
    if link_type:
        query = query.filter(RequirementLink.link_type == link_type)

    if is_active is not None:
        query = query.filter(RequirementLink.is_active == is_active)

    return query.order_by(RequirementLink.create_time.desc()).offset(skip).limit(limit).all()


def get_requirement_links_count(
    db: Session,
    project_id: int,
    user_id: int,
    link_type: Optional[str] = None,
    is_active: Optional[bool] = None
) -> int:
    """
    获取需求链接数量

    用于分页计算总条数，查询条件与 get_requirement_links_by_project 一致。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        link_type: 链接类型筛选（可选）
        is_active: 是否启用筛选（可选）

    Returns:
        int: 链接数量
    """
    query = db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id
    )

    if link_type:
        query = query.filter(RequirementLink.link_type == link_type)

    if is_active is not None:
        query = query.filter(RequirementLink.is_active == is_active)

    return query.count()


def get_requirement_links_by_types(
    db: Session,
    project_id: int,
    user_id: int,
    link_types: List[str]
) -> List[RequirementLink]:
    """
    根据链接类型列表获取需求链接

    使用IN查询一次获取多种类型的链接，仅返回活跃状态的链接。
    常用于批量获取特定类型的链接供AI分析。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        link_types: 链接类型列表，如["requirement", "api_doc"]

    Returns:
        List[RequirementLink]: 符合类型的活跃链接列表

    Note:
        使用 link_type.in_() 实现IN查询，比多次单类型查询更高效。
    """
    return db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id,
        RequirementLink.link_type.in_(link_types),  # IN查询：一次获取多种类型
        RequirementLink.is_active == True  # 仅返回活跃链接
    ).all()


def update_requirement_link(
    db: Session,
    link_id: int,
    project_id: Optional[int] = None,
    **kwargs
) -> Optional[RequirementLink]:
    """
    更新需求链接

    通过kwargs动态更新链接字段，保护关键字段（id/project_id/created_by/create_time）
    不允许被修改。自动更新update_time。

    Args:
        db: 数据库会话
        link_id: 链接ID
        project_id: 项目ID（可选），用于隔离校验
        **kwargs: 需要更新的字段键值对

    Returns:
        RequirementLink: 更新后的链接对象或None

    Note:
        protected_fields 定义了不允许通过kwargs修改的字段，
        防止误操作修改关键字段导致数据不一致。
    """
    link = get_requirement_link_by_id(db, link_id, project_id)
    if not link:
        return None

    # 不允许直接修改的字段：防止误操作修改关键字段
    protected_fields = ['id', 'project_id', 'created_by', 'create_time']

    for key, value in kwargs.items():
        if key not in protected_fields and hasattr(link, key):
            setattr(link, key, value)

    # 自动更新修改时间为UTC当前时间
    link.update_time = utcnow()
    db.commit()
    db.refresh(link)
    return link


def delete_requirement_link(
    db: Session,
    link_id: int,
    project_id: Optional[int] = None
) -> bool:
    """
    删除需求链接（硬删除）

    物理删除链接记录，数据库中不再保留。

    Args:
        db: 数据库会话
        link_id: 链接ID
        project_id: 项目ID（可选），用于隔离校验

    Returns:
        bool: 删除成功返回True，链接不存在返回False
    """
    link = get_requirement_link_by_id(db, link_id, project_id)
    if not link:
        return False

    db.delete(link)  # 硬删除：物理移除数据库记录
    db.commit()
    return True


def update_link_cache(
    db: Session,
    link_id: int,
    cached_content: str,
    fetch_status: str = "success"
) -> Optional[RequirementLink]:
    """
    更新链接的缓存信息

    后台抓取链接内容后调用此函数更新缓存。记录缓存内容、抓取时间和状态。
    缓存内容供AI分析使用，避免重复抓取。

    Args:
        db: 数据库会话
        link_id: 链接ID
        cached_content: 缓存的内容（HTML/文本等）
        fetch_status: 获取状态: success/failed

    Returns:
        RequirementLink: 更新后的链接对象或None

    Note:
        - cached_content可能包含大量文本，建议在模型层使用TEXT类型存储
        - 使用 utcnow() 记录抓取时间，确保多时区一致性
    """
    link = db.query(RequirementLink).filter(RequirementLink.id == link_id).first()
    if not link:
        return None

    link.cached_content = cached_content
    link.last_fetch_time = utcnow()  # 记录最近抓取时间
    link.last_fetch_status = fetch_status
    link.update_time = utcnow()

    db.commit()
    db.refresh(link)
    return link


def get_active_links_by_project(
    db: Session,
    project_id: int,
    user_id: int
) -> List[RequirementLink]:
    """
    获取项目的所有有效链接（用于测试用例生成）

    查询项目下所有is_active=True的链接，按链接类型和创建时间排序。
    主要用于AI生成测试用例时获取需求来源。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project实现权限隔离

    Returns:
        List[RequirementLink]: 有效需求链接列表

    Note:
        排序策略：先按link_type分组（同类型链接聚合），再按创建时间倒序
        （同类型内最新链接优先）。
    """
    return db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id,
        RequirementLink.is_active == True  # 仅返回活跃链接
    ).order_by(RequirementLink.link_type, RequirementLink.create_time.desc()).all()


def toggle_link_active(
    db: Session,
    link_id: int,
    project_id: int,
    user_id: int
) -> Optional[RequirementLink]:
    """
    切换链接的启用状态

    将链接的is_active字段取反，实现启用/禁用切换。
    通过JOIN Project校验用户权限。

    Args:
        db: 数据库会话
        link_id: 链接ID
        project_id: 项目ID
        user_id: 用户ID

    Returns:
        RequirementLink: 更新后的链接对象或None

    Note:
        禁用链接后，该链接不会参与AI测试用例生成，
        但链接记录仍保留在数据库中，可随时重新启用。
    """
    # 三重过滤：链接ID + 项目ID + 用户ID，确保权限安全
    link = db.query(RequirementLink).join(Project).filter(
        RequirementLink.id == link_id,
        RequirementLink.project_id == project_id,
        Project.user_id == user_id
    ).first()

    if not link:
        return None

    link.is_active = not link.is_active  # 取反切换状态
    link.update_time = utcnow()
    db.commit()
    db.refresh(link)
    return link


def check_link_exists(
    db: Session,
    project_id: int,
    link_url: str
) -> bool:
    """
    检查链接是否已存在

    在项目维度下检查URL是否重复，防止添加重复的需求链接。

    Args:
        db: 数据库会话
        project_id: 项目ID
        link_url: 链接地址

    Returns:
        bool: 存在返回True，不存在返回False

    Note:
        校验范围限定在项目内（project_id + link_url），
        不同项目下允许存在相同URL的链接。
    """
    return db.query(RequirementLink).filter(
        RequirementLink.project_id == project_id,
        RequirementLink.link_url == link_url
    ).first() is not None
