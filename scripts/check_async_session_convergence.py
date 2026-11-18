"""AsyncSession 收敛门禁（R2-1 阶段四收口后的硬校验）。

背景：R2-1 阶段三把端点依赖从异步会话（`async_get_db`）收敛为同步 `get_db`，
批次记录见 `docs/全量结项攻坚台账.md` §3.1。**2026-11-17 阶段四收口后**：

- 使用面已归零：端点 / 业务服务里 `async_get_db` 引用 **0 处**；
- 仅剩 `app/db/database/` 两处**定义与再导出**（`_session.py` 定义 4 个异步
  依赖 + 1 处文档引用，`__init__.py` 4 处再导出），供遗留 `AsyncSession`
  （后台任务 / SSE 流式上下文 / 测试壳）与 `db_async_compat` 共存期使用；
- 异步引擎与 `AsyncPrimarySessionLocal` **保留**：51 处后台任务/流式上下文仍
  依赖，属会话层「双轨」而非待删除物（推翻原判据「4→2 / 8→4」的删除设想）。

本脚本把该状态固化为棘轮：`ALLOWLIST` 之外任何文件出现 `async_get_db` 即失败，
防止新代码把异步依赖带回端点层。等后台任务也切同步后，两处定义再随
`db_async_compat` 一并清理。

用法：
    python scripts/check_async_session_convergence.py            # 门禁模式
    python scripts/check_async_session_convergence.py --report   # 仅打印分布
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
TOKEN = "async_get_db"

# 白名单：文件相对路径（posix 风格） → 允许的最大出现次数
ALLOWLIST: dict[str, int] = {
    # 唯一保留项：异步依赖的定义与再导出（非使用面）
    "app/db/database/_session.py": 5,
    "app/db/database/__init__.py": 4,
}

# 总量预算：只允许下降（= 仅剩定义/导出）。调整预算须在台账 §3.1 同步登记。
TOTAL_BUDGET = 9


def scan() -> dict[str, int]:
    """返回 `{相对路径: 出现次数}`，仅包含出现的文件。"""
    counts: dict[str, int] = {}
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        n = text.count(TOKEN)
        if n:
            counts[path.relative_to(ROOT).as_posix()] = n
    return counts


def report(counts: dict[str, int]) -> None:
    total = sum(counts.values())
    print(f"[{TOKEN}] 合计 {total} 处 / {len(counts)} 文件（预算 {TOTAL_BUDGET}）")
    for path, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        cap = ALLOWLIST.get(path)
        mark = "" if cap is not None and n <= cap else "  <-- 超白名单/超上限"
        print(f"  {n:4d}  {path}{mark}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AsyncSession 收敛门禁")
    parser.add_argument("--report", action="store_true", help="仅打印分布，不做校验")
    args = parser.parse_args()

    counts = scan()
    report(counts)
    if args.report:
        return 0

    violations: list[str] = []

    for path, n in counts.items():
        cap = ALLOWLIST.get(path)
        if cap is None:
            violations.append(f"白名单外出现 {n} 处：{path}")
        elif n > cap:
            violations.append(f"超出上限（{n} > {cap}）：{path}")

    total = sum(counts.values())
    if total > TOTAL_BUDGET:
        violations.append(f"总量超出预算（{total} > {TOTAL_BUDGET}）")

    if violations:
        print("\n[FAIL] AsyncSession 收敛门禁未通过：")
        for item in violations:
            print(f"  - {item}")
        print(
            "\n处理方式：端点/服务一律用同步 `get_db`，DB 调用经 "
            "`app/services/db_async_compat`（execute/get/flush/commit/refresh/delete）"
            "执行；确需新增例外，先在 `docs/全量结项攻坚台账.md` §3.1 登记理由，"
            "再更新本白名单与 `TOTAL_BUDGET`。"
        )
        return 1

    print("\n[OK] AsyncSession 收敛门禁通过（无白名单外新增，未超预算）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
