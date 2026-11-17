"""AsyncSession 收敛门禁（R2-1 阶段三 → 阶段四入口判据）。

背景：R2-1 阶段三把端点依赖从异步会话（`async_get_db`）收敛为同步 `get_db`。
收敛过程逐批推进并在台账登记；本脚本把「当前残余」固化为**只减不增**的棘轮：

- `ALLOWLIST`：允许继续持有 `async_get_db` 的文件及其处数上限（引擎定义 / B-14
  真异步子系统 / 认证 SSO 链路，全部台账在案）；
- 白名单外任何文件出现 `async_get_db` → 失败（防止新代码回潮）；
- 白名单文件超过上限 → 失败（防止在例外文件里继续堆异步依赖）；
- 总量超过 `TOTAL_BUDGET` → 失败。

阶段四（会话层收尾）完成后，`app/db/database/` 两项应从白名单删除，
最终目标是白名单与预算同时清零。

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
    # 引擎/依赖定义本身（阶段四删除 async_get_db 时一并清理）
    "app/db/database/_session.py": 5,
    "app/db/database/__init__.py": 4,
    # B-14：Agent / 视觉 / 定位 / AI 流式（内部为真异步内核）
    "app/api/v1/endpoints/agents.py": 10,
    "app/api/v1/endpoints/visual_ai.py": 9,
    "app/api/v1/endpoints/ab_test.py": 4,
    "app/api/v1/endpoints/batch_locator_tasks.py": 4,
    "app/api/v1/endpoints/batch_locator.py": 3,
    "app/api/v1/endpoints/test_case_ai_stream.py": 3,
    "app/api/v1/endpoints/mcp_server.py": 2,
    # 认证 SSO：handle_callback / handle_acs 为 httpx 真异步链路
    "app/api/v1/endpoints/oidc_endpoints.py": 2,
    "app/api/v1/endpoints/saml_endpoints.py": 2,
}

# 总量预算：只允许下降。调整预算必须在台账「R2-1 收敛计数」中同步登记。
TOTAL_BUDGET = 48


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
            "\n处理方式：把端点/服务迁移到同步 `get_db`（参照台账 W2-x 记录）；"
            "确需保留的例外，先在 `docs/全量结项攻坚台账.md` 登记理由，再更新本白名单。"
        )
        return 1

    print("\n[OK] AsyncSession 收敛门禁通过（无白名单外新增，未超预算）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
