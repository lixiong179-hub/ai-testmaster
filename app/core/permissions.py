"""
权限控制模块

本模块实现了基于RBAC（基于角色的访问控制）模型的权限验证体系，
为FastAPI端点提供声明式的角色权限校验能力。

核心设计思路：
    - 超级管理员(is_superuser=True)自动绕过所有角色检查，拥有全部权限
    - 普通用户通过roles关联表匹配允许的角色列表，满足任一角色即通过
    - 通过FastAPI的Depends机制将权限校验注入路由，实现声明式权限控制

核心组件概览：
    - PermissionDenied: 权限不足异常，返回HTTP 403
    - check_role(): 角色匹配核心逻辑，超级管理员优先判断
    - require_roles(): FastAPI依赖项工厂，生成角色校验函数
    - require_technical_view / require_admin / require_test_engineer: 预定义权限组合
    - ViewPermissions: 视图权限常量类，定义各业务场景的角色白名单
    - can_view_technical() / can_edit_locator(): 便捷权限检查函数

依赖关系：
    - app.db.database.get_db: 获取数据库会话
    - app.api.v1.endpoints.auth.get_current_user: 获取当前登录用户
    - app.models.user.User: 用户模型（含is_superuser字段和roles关联）
"""
from typing import List, Optional, Callable, Any
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User


class PermissionDenied(HTTPException):
    """
    权限不足异常

    当用户角色不满足接口要求时抛出，继承自HTTPException，
    自动返回HTTP 403 Forbidden状态码。

    使用场景：
        - require_roles()校验失败时自动抛出
        - 业务代码中手动进行权限检查时抛出

    Attributes:
        status_code: 固定为403，表示服务器理解请求但拒绝执行
        detail: 错误详情，默认"权限不足"，可自定义描述具体缺少的角色
    """

    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


def check_role(user: User, allowed_roles: List[str]) -> bool:
    """
    检查用户是否拥有指定角色列表中的任一角色（RBAC核心校验逻辑）

    校验策略：
        1. 超级管理员(is_superuser=True)直接返回True，跳过角色匹配
        2. 普通用户从user.roles关联中提取角色名称列表
        3. 用户角色与允许角色取交集，有任意匹配即通过

    Args:
        user: 当前用户对象，需包含is_superuser属性和roles关联关系
        allowed_roles: 允许访问的角色名称列表，如['admin', 'test_engineer']

    Returns:
        bool: True表示有权限，False表示无权限

    Note:
        - 使用getattr安全访问属性，防止User模型缺少is_superuser或roles字段时崩溃
        - roles提取使用try/except兜底，确保关联查询异常时不影响系统可用性
    """
    # 超级管理员拥有所有权限，直接放行，无需逐一匹配角色
    if getattr(user, 'is_superuser', False):
        return True

    # 检查用户角色（通过roles关联查询）
    # 使用getattr避免User对象无roles属性时抛出AttributeError
    user_roles = []
    try:
        user_roles = [role.name for role in getattr(user, 'roles', [])]
    except Exception:
        # roles关联查询可能因数据库异常等原因失败，此时视为无角色
        pass

    # 如果用户有任意一个允许的角色，则返回True（OR语义，非AND）
    return any(role in allowed_roles for role in user_roles)


def require_roles(roles: List[str]) -> Callable[..., Any]:
    """
    角色权限依赖项工厂函数

    生成FastAPI兼容的Depends依赖项函数，用于路由级别的声明式权限控制。
    该函数返回的role_checker会被FastAPI在请求处理前自动调用，
    完成用户身份获取和角色校验。

    使用方式：
        @router.get("/data", dependencies=[Depends(require_roles(['admin']))])
        或在路径操作函数参数中声明：
        def endpoint(user: User = Depends(require_roles(['admin']))):

    Args:
        roles: 允许访问的角色名称列表，如['admin', 'test_engineer']

    Returns:
        role_checker: FastAPI依赖项函数，接收当前用户和数据库会话，
                      校验通过后返回用户对象，校验失败抛出PermissionDenied

    Raises:
        PermissionDenied: 当用户角色不在允许列表中时抛出，detail中包含所需角色信息
    """

    def role_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        # 调用核心校验逻辑，不通过则抛出权限异常
        if not check_role(current_user, roles):
            raise PermissionDenied(
                detail=f"需要以下角色之一: {', '.join(roles)}"
            )
        return current_user

    return role_checker


# ============================================================================
# 预定义权限组合
# 将常用的角色组合实例化为FastAPI依赖项，避免在各路由中重复声明角色列表
# ============================================================================

require_technical_view = require_roles(['test_engineer', 'admin', 'developer'])
"""技术视图权限：允许测试工程师、管理员、开发者访问技术细节（如元素定位、执行日志）"""

require_admin = require_roles(['admin'])
"""管理员权限：仅允许管理员角色，用于系统配置、用户管理等敏感操作"""

require_test_engineer = require_roles(['test_engineer', 'admin'])
"""测试工程师权限：允许测试工程师和管理员，用于测试用例的创建、编辑、执行"""


class ViewPermissions:
    """
    视图权限常量类

    集中定义各业务场景的角色白名单，与require_roles()配合使用。
    按数据敏感程度从低到高分为四个层级，每个层级对应不同的角色集合。

    权限层级说明（由宽到严）：
        - BUSINESS_VIEW: 业务视图，所有角色可见，展示业务概览、统计数据等非敏感信息
        - TECHNICAL_VIEW: 技术视图，仅技术人员可见，展示元素定位、执行日志、错误堆栈等
        - EDIT: 编辑权限，允许修改测试用例、定位信息等核心数据
        - ADMIN: 管理权限，仅管理员可执行系统级操作（用户管理、全局配置等）

    使用场景：
        - 在业务代码中调用check_role(user, ViewPermissions.TECHNICAL_VIEW)
        - 作为require_roles()的参数：require_roles(ViewPermissions.EDIT)

    Attributes:
        BUSINESS_VIEW: 业务视图角色列表，包含viewer等只读角色
        TECHNICAL_VIEW: 技术视图角色列表，排除viewer和product_manager
        EDIT: 编辑角色列表，仅测试工程师和管理员
        ADMIN: 管理角色列表，仅管理员
    """

    # 业务视图 - 所有用户可见
    # viewer: 只读观察者，可查看业务数据但无技术细节
    # product_manager: 产品经理，关注业务指标和测试报告
    BUSINESS_VIEW = ['viewer', 'test_engineer', 'admin', 'developer', 'product_manager']

    # 技术视图 - 技术人员可见
    # 排除viewer和product_manager，因为技术细节（如元素定位器、错误堆栈）对非技术角色无意义
    TECHNICAL_VIEW = ['test_engineer', 'admin', 'developer']

    # 编辑权限 - 测试工程师和管理员
    # 涉及测试用例和定位信息的修改，需要专业角色
    EDIT = ['test_engineer', 'admin']

    # 管理权限 - 仅管理员
    # 涉及系统级操作，如用户管理、全局配置、数据清理
    ADMIN = ['admin']


def can_view_technical(user: Optional[User]) -> bool:
    """
    检查用户是否可以查看技术视图（便捷函数）

    封装check_role()和空值判断，适用于模板渲染、条件展示等场景，
    无需手动处理user为None的情况。

    Args:
        user: 用户对象，可能为None（未登录场景）

    Returns:
        bool: True表示可查看技术视图，False表示不可查看（含user为None的情况）

    使用示例：
        {% if can_view_technical(current_user) %}
            <div>技术详情...</div>
        {% endif %}
    """
    # 未登录用户（user为None）默认无技术视图权限
    if not user:
        return False
    return check_role(user, ViewPermissions.TECHNICAL_VIEW)


def can_edit_locator(user: Optional[User]) -> bool:
    """
    检查用户是否可以编辑定位信息（便捷函数）

    定位信息（Locator）是自动化测试的核心资产，修改权限需严格控制。
    仅测试工程师和管理员可编辑，防止误操作导致测试用例失效。

    Args:
        user: 用户对象，可能为None（未登录场景）

    Returns:
        bool: True表示可编辑定位信息，False表示不可编辑（含user为None的情况）

    使用示例：
        if can_edit_locator(current_user):
            locator.update(new_value)
    """
    # 未登录用户（user为None）默认无编辑权限
    if not user:
        return False
    return check_role(user, ViewPermissions.EDIT)
