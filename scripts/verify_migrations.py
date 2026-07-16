"""Alembic 迁移回滚验证 CLI。

提供三种验证模式，形成"开发本地 → PR → 每日回归"的二级防线：

    # 静态扫描：所有非 merge 迁移必须有非空 downgrade()，秒级
    python scripts/verify_migrations.py --check-downgrade

    # 最新迁移往返：upgrade head → downgrade -1 → upgrade head
    python scripts/verify_migrations.py --last

    # 全链路往返：upgrade head → downgrade base → upgrade head
    python scripts/verify_migrations.py --full

退出码：0 成功，1 失败（CI 友好）。

设计要点：
- 使用 alembic.config.Config + command.upgrade/downgrade 编程式调用，
  避免 subprocess 开销与 stdout 解析。
- 静态扫描用 ast 解析识别 merge 迁移（down_revision 为 tuple/list），
  豁免其 downgrade()=pass 的惯例。
- 不修改业务数据库：要求使用 TEST_DATABASE_URL 或通过 --database-url 显式指定。
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 项目根目录加入 sys.path，便于复用 app.core.config
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.config import settings


_SCRIPTS_LOCATION = _PROJECT_ROOT / "alembic"
_VERSIONS_DIR = _SCRIPTS_LOCATION / "versions"


@dataclass(frozen=True)
class MigrationFile:
    """单个迁移文件的静态解析结果。"""

    path: Path
    revision: str
    down_revision: object  # str | tuple[str, ...] | None
    is_merge: bool
    has_downgrade: bool
    downgrade_is_trivial: bool  # True 表示函数体仅含 pass/注释/docstring


def _extract_value(node: ast.AST) -> object:
    """从 AST 节点还原字面量（用于 revision/down_revision 赋值）。"""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def _is_trivial_body(func_node: ast.FunctionDef) -> bool:
    """判断函数体是否仅含 pass/文档字符串/注释。

    merge 迁移的 downgrade() 惯例为空体，需豁免；非 merge 迁移的空体视为缺陷。
    """
    meaningful: list[ast.stmt] = []
    for stmt in func_node.body:
        # 跳过文档字符串
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        # 跳过 pass
        if isinstance(stmt, ast.Pass):
            continue
        meaningful.append(stmt)
    return len(meaningful) == 0


def parse_migration_file(path: Path) -> Optional[MigrationFile]:
    """解析单个迁移文件，返回 MigrationFile 或 None（解析失败时）。"""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, OSError):
        return None

    revision: str = ""
    down_revision: object = None
    has_downgrade: bool = False
    downgrade_trivial: bool = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "revision":
                    value = _extract_value(node.value)
                    if isinstance(value, str):
                        revision = value
                elif isinstance(target, ast.Name) and target.id == "down_revision":
                    down_revision = _extract_value(node.value)
        elif isinstance(node, ast.AnnAssign):
            # 处理 revision: str = "..." / down_revision: str = "..." 形式
            if isinstance(node.target, ast.Name) and node.value is not None:
                if node.target.id == "revision":
                    value = _extract_value(node.value)
                    if isinstance(value, str):
                        revision = value
                elif node.target.id == "down_revision":
                    down_revision = _extract_value(node.value)
        elif isinstance(node, ast.FunctionDef) and node.name == "downgrade":
            has_downgrade = True
            downgrade_trivial = _is_trivial_body(node)

    if not revision:
        return None

    is_merge = isinstance(down_revision, (tuple, list))
    return MigrationFile(
        path=path,
        revision=revision,
        down_revision=down_revision,
        is_merge=is_merge,
        has_downgrade=has_downgrade,
        downgrade_is_trivial=downgrade_trivial,
    )


def collect_migrations() -> list[MigrationFile]:
    """收集 alembic/versions/ 下所有迁移文件。"""
    files: list[MigrationFile] = []
    for py_path in sorted(_VERSIONS_DIR.glob("*.py")):
        if py_path.name.startswith("__"):
            continue
        parsed = parse_migration_file(py_path)
        if parsed is not None:
            files.append(parsed)
    return files


def check_downgrade() -> int:
    """静态扫描：所有非 merge 迁移必须有非空 downgrade()。"""
    migrations = collect_migrations()
    if not migrations:
        print(f"[FAIL] 未在 {_VERSIONS_DIR} 找到任何迁移文件", file=sys.stderr)
        return 1

    offenders: list[str] = []
    merge_count: int = 0
    healthy_count: int = 0

    for m in migrations:
        if m.is_merge:
            merge_count += 1
            continue
        if not m.has_downgrade:
            offenders.append(f"{m.path.name}: 缺失 downgrade() 函数")
        elif m.downgrade_is_trivial:
            offenders.append(f"{m.path.name}: downgrade() 函数体仅含 pass/注释")
        else:
            healthy_count += 1

    print(f"[INFO] 扫描 {len(migrations)} 个迁移文件")
    print(f"[INFO] merge 迁移（豁免）: {merge_count}")
    print(f"[INFO] 健康迁移（非空 downgrade）: {healthy_count}")
    print(f"[INFO] 问题迁移: {len(offenders)}")

    if offenders:
        print("\n[FAIL] 以下迁移缺少有效的 downgrade():", file=sys.stderr)
        for line in offenders:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print("[OK] 所有非 merge 迁移均有非空 downgrade()")
    return 0


def _build_alembic_config(database_url: str) -> AlembicConfig:
    """构造 Alembic Config，注入 script_location 与 sqlalchemy.url。"""
    config = AlembicConfig()
    config.set_main_option("script_location", str(_SCRIPTS_LOCATION))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _resolve_database_url(cli_url: Optional[str]) -> str:
    """决定使用哪个数据库 URL：CLI 参数 > TEST_DATABASE_URL > settings.DATABASE_URL。"""
    if cli_url:
        return cli_url
    test_url = os.getenv("TEST_DATABASE_URL")
    if test_url:
        return test_url
    return settings.DATABASE_URL


def _run_round_trip(database_url: str, target: str) -> int:
    """执行 upgrade head → downgrade target → upgrade head 往返。

    target 取值：
    - "-1"：仅回滚最新一个迁移
    - "base"：回滚到初始状态（全链路）
    """
    config = _build_alembic_config(database_url)
    print(f"[INFO] 使用数据库: {database_url}")
    print(f"[INFO] 往返目标: downgrade {target}")

    try:
        print("[STEP 1] alembic upgrade head ...")
        command.upgrade(config, "head")

        print(f"[STEP 2] alembic downgrade {target} ...")
        command.downgrade(config, target)

        print("[STEP 3] alembic upgrade head ...")
        command.upgrade(config, "head")
    except Exception as exc:  # noqa: BLE001 — CLI 顶层需捕获所有异常返回非零退出码
        print(f"\n[FAIL] 往返验证失败: [{type(exc).__name__}] {exc}", file=sys.stderr)
        return 1

    print("[OK] 往返验证成功：upgrade → downgrade → upgrade 全部通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Alembic 迁移回滚验证 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例：
    # 静态扫描（秒级，无需数据库）
    python scripts/verify_migrations.py --check-downgrade

    # 最新迁移往返（PR 用，需可访问的测试库）
    python scripts/verify_migrations.py --last

    # 全链路往返（每日回归用，耗时较长）
    python scripts/verify_migrations.py --full
""",
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--check-downgrade",
        action="store_true",
        help="静态扫描所有迁移文件，确保非 merge 迁移有非空 downgrade()",
    )
    mode_group.add_argument(
        "--last",
        action="store_true",
        help="动态往返：upgrade head → downgrade -1 → upgrade head",
    )
    mode_group.add_argument(
        "--full",
        action="store_true",
        help="动态往返：upgrade head → downgrade base → upgrade head（全链路）",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="覆盖数据库 URL；默认读取 TEST_DATABASE_URL 环境变量，再退化为 settings.DATABASE_URL",
    )
    args = parser.parse_args()

    if args.check_downgrade:
        return check_downgrade()

    if args.last:
        url = _resolve_database_url(args.database_url)
        return _run_round_trip(url, "-1")

    if args.full:
        url = _resolve_database_url(args.database_url)
        return _run_round_trip(url, "base")

    # 互斥组已保证唯一，理论上不会到达
    parser.error("未指定验证模式")


if __name__ == "__main__":
    raise SystemExit(main())
