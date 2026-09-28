"""Phase 3 Task 9: 租户上下文管理 — 请求级行级安全基础。

核心概念：
    - 基于 ContextVar 存储当前请求的 tenant_id，线程安全且异步友好
    - tenant_id 为 None 表示系统级上下文（超级管理员 / 迁移脚本），不应用过滤
    - 查询过滤器和 before_flush hook 从上下文读取 tenant_id

使用方式：
    # 中间件中设置（从 JWT claim 提取）
    set_current_tenant_id(user.tenant_id)

    # 业务代码读取
    tid = get_current_tenant_id()

    # 测试中临时切换
    with tenant_scope(tenant_id=1):
        ...

设计要点：
    - TenantAwareMixin 作为所有支持租户隔离模型的标记基类，
      with_loader_criteria 据此自动注入 WHERE tenant_id = :current 条件
    - 模型继承 TenantAwareMixin 后无需额外注册，查询过滤自动生效
"""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional


class TenantAwareMixin:
    """租户感知标记基类。

    所有拥有 tenant_id 列的业务模型应继承此 Mixin，
    以便 with_loader_criteria 自动应用行级过滤。
    Mixin 本身不定义列，列由各模型自行声明。
    """


# 当前请求的租户 ID（None = 系统级上下文，不应用过滤）
_current_tenant_id: ContextVar[Optional[int]] = ContextVar("current_tenant_id", default=None)


def get_current_tenant_id() -> Optional[int]:
    """获取当前请求的租户 ID。

    Returns:
        Optional[int]: 当前租户 ID；None 表示系统级上下文（超级管理员 / 后台任务），
        此时查询过滤器不追加 tenant_id 条件，可访问全部数据。
    """
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: Optional[int]) -> None:
    """设置当前请求的租户 ID。

    Args:
        tenant_id: 租户 ID；None 表示系统级上下文（超级管理员）。
    """
    _current_tenant_id.set(tenant_id)


def clear_current_tenant_id() -> None:
    """清除当前租户上下文，恢复为系统级（不应用过滤）。"""
    _current_tenant_id.set(None)


@contextmanager
def tenant_scope(tenant_id: Optional[int]):
    """临时切换租户上下文的作用域管理器。

    用于测试场景或系统级操作时临时切换租户视角，
    退出作用域后自动恢复原上下文。

    Args:
        tenant_id: 要切换到的租户 ID；None 切换到系统级上下文。

    Example:
        with tenant_scope(tenant_id=1):
            # 此范围内的查询自动过滤 tenant_id=1
            cases = db.query(TestCase).all()
    """
    token = _current_tenant_id.set(tenant_id)
    try:
        yield
    finally:
        _current_tenant_id.reset(token)


__all__ = [
    "TenantAwareMixin",
    "get_current_tenant_id",
    "set_current_tenant_id",
    "clear_current_tenant_id",
    "tenant_scope",
]
