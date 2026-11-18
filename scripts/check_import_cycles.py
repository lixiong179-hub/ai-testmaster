"""模块级循环依赖检测（R4-1 判据 3）。

构建 `app/` 包内模块的导入图（只看 `app.*` 内部导入，忽略第三方与标准库），
用 DFS 找出环路并按「环 → 文件路径」输出。存在环时退出码 1，可直接用作 CI 门禁。

局限（够用即可）：
    - 只解析 `import app.x`、`from app.x import y`、`from . import y` / `from .x import y`；
    - 函数内延迟导入同样计入（延迟导入恰恰是当前代码用来打断环的手段，需可见）；
    - 不解析 `importlib.import_module("app.x")` 动态导入。

用法：
    venv/Scripts/python.exe scripts/check_import_cycles.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def package_of(module: str, is_pkg: bool) -> str:
    if is_pkg:
        return module
    return module.rpartition(".")[0]


def collect_modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        modules[module_name(path)] = path
    return modules


def resolve(target: str, known: dict[str, Path]) -> str | None:
    """把导入目标解析为已知模块；支持「导入了子模块」与「导入了符号」两种形态。"""
    candidate = target
    while candidate:
        if candidate in known:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return None


def _is_type_only_test(test: ast.expr) -> bool:
    """识别 `if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` / `if False:`。"""
    if isinstance(test, ast.Name):
        return test.id in {"TYPE_CHECKING", "False"}
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    if isinstance(test, ast.Constant):
        return test.value is False
    return False


def imports_of(path: Path, module: str, known: dict[str, Path], include_lazy: bool = True) -> set[str]:
    is_pkg = path.name == "__init__.py"
    pkg = package_of(module, is_pkg)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    # 非运行期导入：① 函数体内（延迟导入）② `if TYPE_CHECKING:` / `if False:` 块
    # 二者在模块导入时都不执行，不构成运行时环；仅当 include_lazy 时计入。
    lazy_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    lazy_ids.add(id(sub))
        elif isinstance(node, ast.If) and _is_type_only_test(node.test):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    lazy_ids.add(id(sub))

    deps: set[str] = set()
    for node in ast.walk(tree):
        if not include_lazy and id(node) in lazy_ids:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app"):
                    hit = resolve(alias.name, known)
                    if hit:
                        deps.add(hit)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 相对导入
                base = pkg
                for _ in range(node.level - 1):
                    base = base.rpartition(".")[0]
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            if not target.startswith("app"):
                continue
            hit = resolve(target, known)
            if hit:
                deps.add(hit)
            for alias in node.names:  # from app.pkg import submodule
                sub = resolve(f"{target}.{alias.name}", known)
                if sub:
                    deps.add(sub)
    deps.discard(module)
    return deps


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    WHITE, GREY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        color[node] = GREY
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            if color.get(nxt, WHITE) == GREY:
                idx = stack.index(nxt)
                cycles.append(stack[idx:] + [nxt])
            elif color.get(nxt, WHITE) == WHITE:
                dfs(nxt)
        stack.pop()
        color[node] = BLACK

    for node in sorted(graph):
        if color[node] == WHITE:
            dfs(node)
    return cycles


def main() -> int:
    known = collect_modules()
    runtime = {m: imports_of(p, m, known, include_lazy=False) for m, p in known.items()}
    full = {m: imports_of(p, m, known, include_lazy=True) for m, p in known.items()}

    runtime_cycles = find_cycles(runtime)
    full_cycles = find_cycles(full)

    print(
        f"模块数: {len(runtime)}，模块级导入边: {sum(len(v) for v in runtime.values())}，"
        f"含延迟导入边: {sum(len(v) for v in full.values())}"
    )
    print(f"运行时环（模块级导入构成，门禁）: {len(runtime_cycles)}")
    print(f"含延迟导入的静态环（参考，非门禁）: {len(full_cycles)}")

    if runtime_cycles:
        for idx, cycle in enumerate(runtime_cycles, 1):
            print(f"  [R{idx}] " + " -> ".join(cycle))
        return 1

    if full_cycles:
        for idx, cycle in enumerate(full_cycles, 1):
            print(f"  [L{idx}] " + " -> ".join(cycle))

    print("运行时循环依赖: 0（判据满足）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
