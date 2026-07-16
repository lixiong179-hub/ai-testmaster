"""Alembic 迁移回滚集成测试。

测试矩阵：
    test_all_migrations_have_downgrade
        静态扫描所有迁移文件，确保非 merge 迁移有非空 downgrade()。
        标记 integration，无需数据库，秒级。

    test_migrations_have_single_head
        静态扫描确保迁移链路仅 1 个 head（无分叉），需 merge 合并。
        标记 integration，无需数据库。

    test_latest_migration_round_trip
        动态往返：upgrade head → downgrade -1 → upgrade head。
        标记 integration，需 TEST_DATABASE_URL 指向的可访问测试库。

    test_full_round_trip
        动态往返：upgrade head → downgrade base → upgrade head（全链路）。
        标记 slow + integration，每日回归使用，PR 不跑。

设计要点：
- 复用 scripts/verify_migrations.py 的实现，避免重复逻辑。
- 单独 fixture 使用独立 alembic config，不复用 conftest.py 的 testEngine
  （后者通过 Base.metadata.create_all 建表，会干扰 alembic 的版本管理）。
- 通过 TEST_DATABASE_URL 决定测试库；未配置时动态用例自动跳过，
  静态用例仍可运行（不依赖数据库）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 将项目根加入 sys.path 以便导入 scripts.verify_migrations
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from alembic import command  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402

from scripts.verify_migrations import (  # noqa: E402 — sys.path 调整后再导入
    _build_alembic_config,
    _resolve_database_url,
    collect_migrations,
)


pytestmark = pytest.mark.integration


def _has_test_db() -> bool:
    """是否配置了可用的测试数据库 URL。"""
    return bool(os.getenv("TEST_DATABASE_URL"))


def _iter_down_revision_targets(migrations):
    """从 migrations 中提取所有 down_revision 引用的 revision id。"""
    targets: set[str] = set()
    for m in migrations:
        dr = m.down_revision
        if isinstance(dr, str):
            targets.add(dr)
        elif isinstance(dr, (tuple, list)):
            targets.update(v for v in dr if isinstance(v, str))
    return targets


# -----------------------------------------------------------------------
# 1. 静态扫描测试（无需数据库）
# -----------------------------------------------------------------------


def test_all_migrations_have_downgrade() -> None:
    """所有非 merge 迁移必须有非空 downgrade() 函数。"""
    migrations = collect_migrations()
    assert migrations, "未扫描到任何迁移文件，检查 alembic/versions/ 目录"

    offenders: list[str] = []
    for m in migrations:
        if m.is_merge:
            continue  # merge 迁移 downgrade()=pass 是惯例
        if not m.has_downgrade:
            offenders.append(f"{m.path.name}: 缺失 downgrade() 函数")
        elif m.downgrade_is_trivial:
            offenders.append(f"{m.path.name}: downgrade() 函数体仅含 pass/注释")
    assert not offenders, "以下迁移缺少有效的 downgrade():\n  " + "\n  ".join(offenders)


def test_migrations_have_single_head() -> None:
    """迁移链路应仅有 1 个 head（无分叉），多 head 时需新增 merge 迁移合并。"""
    migrations = collect_migrations()
    assert migrations, "未扫描到任何迁移文件"

    all_revisions: set[str] = {m.revision for m in migrations}
    child_targets: set[str] = _iter_down_revision_targets(migrations)
    heads: list[str] = sorted(all_revisions - child_targets)

    assert len(heads) == 1, (
        f"期望恰好 1 个 head，实际 {len(heads)}: {heads}。"
        "存在多 head 时需新增 merge 迁移合并。"
    )


# -----------------------------------------------------------------------
# 2. 动态往返测试（需 TEST_DATABASE_URL）
# -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def alembic_config():
    """构造 Alembic Config；未配置 TEST_DATABASE_URL 时跳过整个模块的动态测试。"""
    if not _has_test_db():
        pytest.skip("未配置 TEST_DATABASE_URL，跳过动态往返测试")
    url = _resolve_database_url(None)
    return _build_alembic_config(url)


def _current_revision(config) -> str:
    """获取当前 alembic_version 表中的版本号。"""
    from sqlalchemy import create_engine

    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            return ctx.get_current_revision()
    finally:
        engine.dispose()


def test_latest_migration_round_trip(alembic_config) -> None:
    """最新迁移往返：upgrade head → downgrade -1 → upgrade head。

    验证最新迁移的 downgrade 与 upgrade 互逆。
    """
    # 前置：确保在 head
    command.upgrade(alembic_config, "head")
    head_rev_before = _current_revision(alembic_config)
    assert head_rev_before is not None, "upgrade head 后应存在版本号"

    # 回滚一步
    command.downgrade(alembic_config, "-1")
    prev_rev = _current_revision(alembic_config)
    assert prev_rev != head_rev_before, "downgrade -1 后版本号应变化"

    # 重新升级到 head
    command.upgrade(alembic_config, "head")
    head_rev_after = _current_revision(alembic_config)
    assert head_rev_after == head_rev_before, (
        f"往返后版本号应恢复: 期望 {head_rev_before}, 实际 {head_rev_after}"
    )


@pytest.mark.slow
def test_full_round_trip(alembic_config) -> None:
    """全链路往返：upgrade head → downgrade base → upgrade head。

    标记 slow，仅每日回归执行。验证整条迁移链路的可回滚性。
    """
    command.upgrade(alembic_config, "head")
    head_rev = _current_revision(alembic_config)
    assert head_rev is not None

    command.downgrade(alembic_config, "base")
    base_rev = _current_revision(alembic_config)
    assert base_rev is None, f"downgrade base 后应无版本号，实际 {base_rev}"

    command.upgrade(alembic_config, "head")
    head_rev_after = _current_revision(alembic_config)
    assert head_rev_after == head_rev, (
        f"全链路往返后版本号应恢复: 期望 {head_rev}, 实际 {head_rev_after}"
    )

