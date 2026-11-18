"""端点共享依赖（R4-7：从 `endpoints/user.py` 下沉，打破路由聚合与子路由的循环导入）。

原状：`user.py` 在文件尾部导入 `_user_role_routes` / `_user_perm_routes` 的子 router，
而两个子路由又 `from app.api.v1.endpoints.user import _require_superuser`，
形成 `user → _user_*_routes → user` 的运行时环。依赖下沉后变为单向：

    _user_role_routes → _deps
    _user_perm_routes → _deps
    user → _deps / _user_*_routes
"""

from fastapi import HTTPException, status

from app.models.user import User


def require_superuser(current_user: User) -> User:
    """要求当前用户为超级管理员，否则 403。"""
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限",
        )
    return current_user


# 兼容既有私有名写法（`_require_superuser`），避免调用点大范围改名
_require_superuser = require_superuser
