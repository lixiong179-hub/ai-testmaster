"""Phase 3 Task 9: 租户行级安全查询过滤器 — 自动注入 tenant_id 隔离条件。

基于 SQLAlchemy 2.0 的 do_orm_execute 事件 + with_loader_criteria 实现：
    - 查询过滤：所有 TenantAwareMixin 子类的 SELECT 自动追加 WHERE tenant_id = :current
    - 写入填充：before_flush 时为新建对象自动填充 tenant_id（未显式设置时）
    - 超级管理员：tenant_id=None 时跳过过滤，可访问全部数据
    - 幂等安装：install_tenant_query_filter 可重复调用，仅首次生效

事件注册目标：
    Session 类（非实例），对 sync Session 和 AsyncSession（内部包装 sync Session）均生效。

使用方式：
    # 应用启动时安装一次
    install_tenant_query_filter()

    # 测试隔离时卸载
    uninstall_tenant_query_filter()
"""
from loguru import logger
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.tenant_context import TenantAwareMixin, get_current_tenant_id

# 安装状态标志，防止重复注册事件
_installed: bool = False


def _make_tenant_criteria(tenant_id: int):
    """构造租户过滤条件工厂函数。

    每次调用生成新的闭包函数，避免 with_loader_criteria 缓存键冲突。

    Args:
        tenant_id: 当前租户 ID

    Returns:
        callable: 接收实体类、返回 SQL 条件表达式的函数
    """
    def criteria(cls):
        return cls.tenant_id == tenant_id
    return criteria


def _on_do_orm_execute(execute_state) -> None:
    """do_orm_execute 事件处理器 — 为 SELECT 自动追加 tenant_id 过滤。

    跳过场景：
        - 非 SELECT 语句（INSERT/UPDATE/DELETE）
        - column load（单列懒加载，无需过滤）
        - 系统级上下文（tenant_id=None，超级管理员）
    """
    # 仅对 SELECT 生效
    if not execute_state.is_select:
        return
    # 跳过单列懒加载（避免对 relationship 懒加载产生副作用）
    if execute_state.is_column_load:
        return
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return  # 系统级上下文，不应用过滤
    # 追加 tenant_id 过滤到所有租户感知模型
    # 使用延迟导入避免循环依赖
    from app.models import (
        Iteration,
        Project,
        ProjectFile,
        Requirement,
        TestCase,
        TestCapability,
        TestPoint,
        TestReport,
        TestResult,
        TestTask,
        User,
    )
    for model in (
        User, Project, ProjectFile,
        TestCase, TestTask, TestResult, TestReport,
        Iteration, TestPoint, TestCapability, Requirement,
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                model,
                _make_tenant_criteria(tenant_id),
                include_aliases=True,
            )
        )


def _on_before_flush(session, flush_context, instances) -> None:
    """before_flush 事件处理器 — 为新建对象自动填充 tenant_id。

    规则：
        - 仅处理 session.new 中的新对象
        - 仅处理 TenantAwareMixin 子类实例
        - 仅在 tenant_id 为 None 时填充（不覆盖显式设置）
        - 系统级上下文（tenant_id=None）时跳过
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return  # 系统级上下文，不自动填充
    for instance in session.new:
        if isinstance(instance, TenantAwareMixin) and instance.tenant_id is None:
            instance.tenant_id = tenant_id


def install_tenant_query_filter() -> None:
    """安装租户查询过滤器和自动填充钩子。

    应在应用启动时调用一次（main.py create_app 中）。
    重复调用安全：已安装时直接返回。
    """
    global _installed
    if _installed:
        return
    event.listen(Session, "do_orm_execute", _on_do_orm_execute)
    event.listen(Session, "before_flush", _on_before_flush)
    _installed = True
    logger.info("[TenantSecurity] 租户行级安全过滤器已安装")


def uninstall_tenant_query_filter() -> None:
    """卸载租户查询过滤器和自动填充钩子。

    用于测试隔离：确保测试间事件监听器不互相干扰。
    """
    global _installed
    if not _installed:
        return
    event.remove(Session, "do_orm_execute", _on_do_orm_execute)
    event.remove(Session, "before_flush", _on_before_flush)
    _installed = False
    logger.info("[TenantSecurity] 租户行级安全过滤器已卸载")


def is_tenant_filter_installed() -> bool:
    """查询过滤器是否已安装。"""
    return _installed


__all__ = [
    "install_tenant_query_filter",
    "uninstall_tenant_query_filter",
    "is_tenant_filter_installed",
]
