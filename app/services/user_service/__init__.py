
"""用户服务模块 - 统一导出用户相关服务。

本模块作为用户服务的对外统一入口，将分散在不同模块中的用户管理、
角色管理、权限控制等服务的公开API集中导出，简化上层调用方的导入路径。

核心导出:
    - UserService: 用户CRUD与认证服务
    - RoleService: 角色CRUD服务
    - PermissionService: 权限校验服务
    - UserRoleService: 用户-角色关联服务
    - RBACService: 基于角色的访问控制服务
    - pwd_context: bcrypt密码加密上下文

依赖关系:
    - app.services.user_service.user_service: 用户核心业务逻辑
    - app.services.role_service.role_service: 角色核心业务逻辑
    - app.services.permission_service: 权限体系与RBAC实现

Note: PermissionService/RoleService are imported lazily to avoid circular import:
    permission_service -> user_service.user_service -> user_service.__init__ -> permission_service
"""
from app.services.user_service.user_service import UserService, pwd_context


def __getattr__(name):
    """Lazy import to break circular dependency with permission_service."""
    if name == 'RoleService':
        from app.services.role_service.role_service import RoleService
        return RoleService
    if name == 'PermissionService':
        from app.services.permission_service import PermissionService
        return PermissionService
    if name == 'UserRoleService':
        from app.services.permission_service import UserRoleService
        return UserRoleService
    if name == 'RBACService':
        from app.services.permission_service import RBACService
        return RBACService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'UserService',
    'RoleService',
    'PermissionService',
    'UserRoleService',
    'RBACService',
    'pwd_context',
]
