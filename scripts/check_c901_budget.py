"""C901 复杂度棘轮门禁（G-8 治理的卡口）。

背景：`C901` 在 `ruff.toml` 的 `[lint] ignore` 中长期全局豁免（与 B-05 之前的
`ruff check app` 同性质：规则开着但没人看）。G-8 立项时实测 **150 处 / 129 文件**
（≥20：18 / 16–19：28 / 11–15：104，max 39），策略与批次见
`docs/architecture/G-8-C901治理策略.md`。

棘轮规则（三条，缺一即失败）：

1. **总量只减不增**：`ruff check app --select C901` 的处数 ≤ `TOTAL_BUDGET`；
   每次结批下调到新总量（在台账 §3.3 登记）；
2. **豁免有帽**：`WHITELIST` 长度 ≤ `MAX_EXEMPTIONS`（目标 ≤5），且每条须满足策略页
   §4 的三条标准；`WHITELIST` 只允许是「本质状态机」类，不得用于掩盖业务规则复杂度；
3. **豁免须实存**：`WHITELIST` 里已被拆分掉的条目会告警，须销账（避免白名单变成垃圾桶）。

完成判据（策略页 §9）：总量 = 白名单数（即待治理 0 处），`TOTAL_BUDGET` 同步降到该值。

计数以 `ruff check app --select C901` 为唯一来源（不自行实现 mccabe）；ruff 版本已在
`ci.yml` 钉 `0.15.17`，保证 CI 与本地口径一致。

用法：
    python scripts/check_c901_budget.py            # 门禁模式（CI 用）
    python scripts/check_c901_budget.py --report   # 仅打印分布与分桶
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = "app"

# 总量预算：只减不增。每次结项（单处或整批）下调到实测总量，并在台账 §3.3 同步登记。
# 150（2026-11-18 立项基线）→ 149（B1 拆 _parse_case_response）→ 147（formatter 两处）
# → 146（build_ui_spec_description）→ 145（_repair_truncated_json）
# → 144（B1 结批：extract_json_objects_fallback 34 拆分，非豁免）
TOTAL_BUDGET = 144

# 豁免数量上限（策略页 §4：仅「本质状态机」可豁免）。
MAX_EXEMPTIONS = 5

# 已登记豁免：函数全限定名 → 豁免理由（须满足策略页 §4 三条标准）。
# 目标 ≤5 项；全部拆完则为空 dict。
WHITELIST: dict[str, str] = {}

# ruff 的 concise 输出：`app/services/x.py:12:5: C901 `func` is too complex (39 > 10)`
_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+C901\s+`(?P<func>[^`]+)`\s+is too complex\s+\((?P<complexity>\d+)\s*>\s*\d+\)\s*$"
)

_EXIT_ENV_ERROR = 2


class Finding:
    """单条 C901：文件（posix 相对路径）+ 函数名 + 复杂度。"""

    __slots__ = ("path", "line", "func", "complexity")

    def __init__(self, path: str, line: int, func: str, complexity: int) -> None:
        self.path = path
        self.line = line
        self.func = func
        self.complexity = complexity

    @property
    def qualname(self) -> str:
        return f"{self.path}::{self.func}"

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.func} ({self.complexity} > 10)"


def collect() -> list[Finding]:
    """调用 ruff 取当前 C901 清单；ruff 缺失或输出无法解析时抛 SystemExit(2)。"""
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        APP,
        "--select",
        "C901",
        "--output-format",
        "concise",
        "--no-cache",
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:  # pragma: no cover - 环境缺失 ruff
        print("[FAIL] 未找到 ruff，无法统计 C901。请先 `pip install ruff==0.15.17`。")
        raise SystemExit(_EXIT_ENV_ERROR) from None

    # ruff 发现违规时退出码为 1（正常），0 表示已清零；其余为真正的执行错误。
    if proc.returncode not in (0, 1):
        print("[FAIL] ruff 执行失败：")
        print(proc.stdout.strip())
        print(proc.stderr.strip())
        raise SystemExit(_EXIT_ENV_ERROR)

    findings: list[Finding] = []
    unparsed: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or "C901" not in line:
            continue
        match = _LINE_RE.match(line)
        if match is None:
            unparsed.append(line)
            continue
        findings.append(
            Finding(
                path=match.group("path").replace("\\", "/"),
                line=int(match.group("line")),
                func=match.group("func"),
                complexity=int(match.group("complexity")),
            )
        )

    if unparsed:
        print("[FAIL] ruff 输出无法解析，可能格式已变更（检查本脚本的 _LINE_RE）：")
        for item in unparsed[:5]:
            print(f"  {item}")
        raise SystemExit(_EXIT_ENV_ERROR)
    if proc.returncode == 1 and not findings:
        print("[FAIL] ruff 报告了 C901 但未解析出任何条目，疑似输出格式变更。")
        raise SystemExit(_EXIT_ENV_ERROR)

    return findings


def bucket_label(complexity: int) -> str:
    if complexity >= 20:
        return "≥20（必拆）"
    if complexity >= 16:
        return "16–19"
    return "11–15"


def report(findings: list[Finding]) -> None:
    exempt = [f for f in findings if f.qualname in WHITELIST]
    pending = [f for f in findings if f.qualname not in WHITELIST]
    by_file = Counter(f.path for f in pending)
    dist = Counter(bucket_label(f.complexity) for f in pending)

    print(
        f"[C901] 合计 {len(findings)} 处 / {len({f.path for f in findings})} 文件"
        f"（预算 {TOTAL_BUDGET}；待治理 {len(pending)}；已豁免 {len(exempt)}/{MAX_EXEMPTIONS}）"
    )
    if dist:
        print("  待治理分桶：" + " ／ ".join(f"{k} {v}" for k, v in sorted(dist.items())))
    print("  热点文件（待治理）：")
    for path, n in by_file.most_common(10):
        print(f"    {n:4d}  {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="C901 复杂度棘轮门禁")
    parser.add_argument("--report", action="store_true", help="仅打印分布，不做校验")
    args = parser.parse_args()

    findings = collect()
    report(findings)
    if args.report:
        return 0

    total = len(findings)
    pending = [f for f in findings if f.qualname not in WHITELIST]
    violations: list[str] = []

    if total > TOTAL_BUDGET:
        violations.append(f"总量超出预算（{total} > {TOTAL_BUDGET}）")
    if len(WHITELIST) > MAX_EXEMPTIONS:
        violations.append(f"豁免条目超上限（{len(WHITELIST)} > {MAX_EXEMPTIONS}）")
    if len(WHITELIST) > TOTAL_BUDGET:
        violations.append(
            f"豁免数超过预算（{len(WHITELIST)} > {TOTAL_BUDGET}），完成判据不可达——请下调预算或减少豁免条目"
        )

    stale = [name for name in WHITELIST if not any(f.qualname == name for f in findings)]
    if stale:
        print("\n[WARN] 以下豁免已不存在（可能已被拆分），请从 WHITELIST 移除并在台账 §3.3 销账：")
        for name in stale:
            print(f"  - {name}")

    if violations:
        print("\n[FAIL] C901 棘轮门禁未通过：")
        for item in violations:
            print(f"  - {item}")
        print("\n复杂度最高的待治理项：")
        for item in sorted(pending, key=lambda f: -f.complexity)[:10]:
            print(f"  - {item}")
        print(
            "\n处理方式：按 `docs/architecture/G-8-C901治理策略.md` 分层处置"
            "（≥20 必拆 / 16–19 与 11–15 拆三段 / 状态机类登记豁免）。"
            "**禁止**上调 `max-complexity` 或全仓 `noqa` 绕过；确需豁免须满足策略页 §4 "
            "三条标准，并在 `WHITELIST` + 台账 §3.3 登记。"
        )
        return 1

    print("\n[OK] C901 棘轮门禁通过（未超预算，豁免未超帽，无未登记新增）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
