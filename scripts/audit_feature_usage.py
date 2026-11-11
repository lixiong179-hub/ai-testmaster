"""R4-3 功能使用率审计脚本。

目的：找出「建了不用」的能力（零引用服务模块、无前端调用者的端点），
产出一份可复现的审计报告 `docs/review-history/功能使用率审计报告.md`。

扫描方法（报告中原样引用，保证可复现）：
    1. 后端模块引用数：遍历 `app/services/**/*.py`，以模块全限定名
       （如 `app.services.foo.bar`）在 `app/` + `tests/` 的 `.py` 源码中
       统计 `from <模块> import` 与 `<模块>.` 形态的命中数（排除定义文件自身）。
    2. 端点 → 前端调用：从 `app/main.py` 的 `include_router` 解析已挂载 router，
       用 AST 提取 `@router.<verb>("...")` 的路径，取首个非参数段作为资源名，
       在 `src/api/*.ts` 中统计命中；0 命中即「端点无前端调用者」。
    3. 输出三张表：模块→引用数 / 端点→前端调用数 / 零引用清单+处置建议。

用法：
    venv/Scripts/python.exe scripts/audit_feature_usage.py
    venv/Scripts/python.exe scripts/audit_feature_usage.py --out <path>
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
TESTS_DIR = ROOT / "tests"
SRC_API_DIR = ROOT / "src" / "api"
MAIN_PY = APP_DIR / "main.py"
DEFAULT_OUT = ROOT / "docs" / "review-history" / "功能使用率审计报告.md"


def _iter_py(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _corpus(root: Path) -> dict[Path, str]:
    return {path: _read(path) for path in _iter_py(root)}


def _count_refs(module: str, self_path: Path, corpus: dict[Path, str]) -> int:
    """统计模块全限定名在语料中的引用次数（排除定义文件自身）。"""
    pattern = re.compile(re.escape(module) + r"(?![0-9A-Za-z_])")
    return sum(len(pattern.findall(text)) for path, text in corpus.items() if path != self_path)


def _service_modules():
    """返回 [(模块名, 文件路径)]，覆盖 app/services 下全部 .py。"""
    result = []
    for path in _iter_py(APP_DIR / "services"):
        result.append((_module_name(path), path))
    return result


def _router_alias_map() -> dict[str, str]:
    """解析 main.py 中 `from app.api.v1.endpoints import x [as alias]` 的别名映射。"""
    mapping: dict[str, str] = {}
    for line in _read(MAIN_PY).splitlines():
        line = line.strip()
        if not line.startswith("from app.api.v1.endpoints import "):
            continue
        imports = line.split(" import ", 1)[1]
        for item in imports.split(","):
            item = item.strip()
            if not item:
                continue
            if " as " in item:
                name, alias = (part.strip() for part in item.split(" as ", 1))
                mapping[alias] = f"app.api.v1.endpoints.{name}"
            else:
                mapping[item] = f"app.api.v1.endpoints.{item}"
    return mapping


def _mounted_routers() -> list[str]:
    """从 main.py 的 include_router 调用解析已挂载的 router 模块全限定名。"""
    text = _read(MAIN_PY)
    aliases = _router_alias_map()
    found = re.findall(r"app\.include_router\(\s*([A-Za-z_][\w.]*)\.router", text)
    modules = set()
    for alias in found:
        root_alias = alias.split(".")[0]
        modules.add(aliases.get(root_alias, root_alias))
    return sorted(modules)


def _router_module_files(module: str) -> list[Path]:
    """定位 router 模块涉及的全部源文件。

    端点既可能是单文件（`endpoints/foo.py`），也可能是包
    （`endpoints/foo/__init__.py` + 子模块），后者需递归收集。
    """
    base = ROOT / module.replace(".", "/")
    if base.is_dir():
        return [p for p in sorted(base.rglob("*.py")) if "__pycache__" not in p.parts]
    single = base.with_suffix(".py")
    return [single] if single.exists() else []


_VERBS = {"get", "post", "put", "delete", "patch", "options", "head"}


def _paths_from_tree(tree: ast.AST) -> list[str]:
    """提取单棵 AST 中 `@router.<verb>("<path>")` 的路径。"""
    paths: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr not in _VERBS:
                continue
            if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "router":
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                paths.append(decorator.args[0].value)
    return paths


def _router_reexports(tree: ast.AST) -> list[str]:
    """提取 `from <模块> import router [as router]` 形式的重导出目标模块。"""
    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
            continue
        if any(alias.name in ("router", "api_router") for alias in node.names):
            modules.append(node.module)
    return modules


def _router_paths(module: str) -> list[str]:
    """用 AST 提取 router 全部路径。

    端点模块常见两种形态：① 单文件内直接 `@router.get`；② 聚合 shim
    （如 `endpoints/auth.py` 仅 `from ...auth_endpoints import router`）。
    后者需沿重导出链继续追溯，因此这里做有界广度优先遍历。
    """
    queue = [module]
    visited: set[str] = set()
    paths: list[str] = []
    while queue:
        current = queue.pop(0)
        if current in visited or len(visited) > 40:
            continue
        visited.add(current)
        for path in _router_module_files(current):
            try:
                tree = ast.parse(_read(path))
            except SyntaxError:
                continue
            paths.extend(_paths_from_tree(tree))
            queue.extend(_router_reexports(tree))
    # 去重且保持顺序
    return list(dict.fromkeys(paths))


def _resource_segment(route: str) -> str | None:
    """取路由的首个非参数路径段（如 `/test-case/{id}` → `test-case`）。"""
    for segment in route.strip("/").split("/"):
        if not segment or segment.startswith("{") or segment.startswith(":"):
            continue
        return segment
    return None


def _frontend_corpus() -> str:
    if not SRC_API_DIR.exists():
        return ""
    return "\n".join(_read(path) for path in sorted(SRC_API_DIR.rglob("*.ts")))


def _suggest(module: str, app_refs: int, test_refs: int) -> str:
    """按「是否被生产代码/测试引用」给出处置建议。"""
    if app_refs == 0 and test_refs == 0:
        return "删除"
    if app_refs == 0:
        return "冻结"
    return "保留"


def build_report() -> str:
    service_modules = _service_modules()
    app_corpus = _corpus(APP_DIR)
    test_corpus = _corpus(TESTS_DIR)

    rows = []
    for module, path in service_modules:
        app_refs = _count_refs(module, path, app_corpus)
        test_refs = _count_refs(module, path, test_corpus)
        rows.append({
            "module": module,
            "path": path.relative_to(ROOT).as_posix(),
            "app_refs": app_refs,
            "test_refs": test_refs,
            "total": app_refs + test_refs,
        })
    rows.sort(key=lambda r: (-r["total"], r["module"]))

    routers = _mounted_routers()
    frontend = _frontend_corpus()
    endpoint_rows = []
    for module in routers:
        paths = _router_paths(module)
        segments = sorted({s for s in (_resource_segment(p) for p in paths) if s})
        hits = {seg: frontend.count(seg) for seg in segments}
        endpoint_rows.append({
            "module": module,
            "route_count": len(paths),
            "segments": segments,
            "hits": hits,
            "total_hits": sum(hits.values()),
        })
    endpoint_rows.sort(key=lambda r: (r["total_hits"], r["module"]))

    zero_rows = [r for r in rows if r["app_refs"] == 0]
    zero_endpoints = [r for r in endpoint_rows if r["route_count"] > 0 and r["total_hits"] == 0]
    unparsed = [r for r in endpoint_rows if r["route_count"] == 0]

    lines: list[str] = []
    lines.append("# 功能使用率审计报告（R4-3）")
    lines.append("")
    lines.append(f"- **扫描对象**：`app/services/**/*.py` **{len(rows)}** 个模块；"
                 f"`app/main.py` 已挂载 router **{len(routers)}** 个；`src/api/**/*.ts` 前端 API 文件")
    lines.append(f"- **模块零生产引用**：{len(zero_rows)} 个（其中完全零引用 "
                 f"{sum(1 for r in zero_rows if r['test_refs'] == 0)} 个）")
    lines.append(f"- **无前端调用者的 router**：{len(zero_endpoints)} / {len(routers)}"
                 f"（另有 {len(unparsed)} 个 router 未解析出路由，需人工复核）")
    lines.append("- **生成方式**：`venv/Scripts/python.exe scripts/audit_feature_usage.py`（可复现）")
    lines.append("")
    lines.append("## 扫描方法")
    lines.append("")
    lines.append("1. **后端模块引用数**：以模块全限定名（如 `app.services.foo.bar`）在 `app/` + `tests/` 的 `.py` 源码中"
                 "统计命中次数（`from <模块> import` 与 `<模块>.` 两种形态都计入），排除定义文件自身。")
    lines.append("2. **端点 → 前端调用**：从 `app/main.py` 的 `include_router` 解析已挂载 router，用 AST 提取"
                 "`@router.<verb>(\"...\")` 路径，取首个非参数段作为资源名，在 `src/api/**/*.ts` 中统计命中数；"
                 "命中 0 即「该 router 无前端调用者」。")
    lines.append("3. **覆盖口径**：表 ① 覆盖 `app/services/` 下 **全部** `.py` 模块，不做抽样。")
    lines.append("")
    lines.append("## 表 ① 服务模块引用数")
    lines.append("")
    lines.append(f"共 **{len(rows)}** 个模块（按合计引用数降序）。`app` = 生产代码引用，`tests` = 测试代码引用。")
    lines.append("")
    lines.append("| # | 模块 | app | tests | 合计 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for idx, row in enumerate(rows, 1):
        lines.append(f"| {idx} | `{row['module']}` | {row['app_refs']} | {row['test_refs']} | {row['total']} |")
    lines.append("")
    lines.append("## 表 ② 端点 → 前端调用数")
    lines.append("")
    lines.append(f"共 **{len(routers)}** 个已挂载 router（按前端命中数升序）。")
    lines.append("")
    lines.append("| # | router 模块 | 路由数 | 资源段 | 前端命中 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for idx, row in enumerate(endpoint_rows, 1):
        segments = ", ".join(row["segments"][:6]) or "-"
        lines.append(f"| {idx} | `{row['module']}` | {row['route_count']} | {segments} | {row['total_hits']} |")
    lines.append("")
    lines.append("## 表 ③ 零引用清单与处置建议")
    lines.append("")
    lines.append("### ③-1 零生产引用（`app` 引用数 = 0）")
    lines.append("")
    if zero_rows:
        lines.append("| # | 模块 | app | tests | 处置建议 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for idx, row in enumerate(zero_rows, 1):
            lines.append(f"| {idx} | `{row['module']}` | 0 | {row['test_refs']} | "
                         f"**{_suggest(row['module'], row['app_refs'], row['test_refs'])}** |")
    else:
        lines.append("无：所有服务模块均被生产代码引用。")
    lines.append("")
    lines.append("### ③-2 无前端调用者的 router")
    lines.append("")
    if zero_endpoints:
        lines.append("| # | router 模块 | 路由数 | 前端命中 | 处置建议 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for idx, row in enumerate(zero_endpoints, 1):
            lines.append(f"| {idx} | `{row['module']}` | {row['route_count']} | 0 | **冻结**（无前端调用，"
                         "保留接口供外部/脚本调用前需先确认） |")
    else:
        lines.append("无：所有 router 均有前端调用者。")
    lines.append("")
    lines.append("### ③-3 未解析出路由的 router（需人工复核）")
    lines.append("")
    if unparsed:
        lines.append("| # | router 模块 | 说明 |")
        lines.append("| --- | --- | --- |")
        for idx, row in enumerate(unparsed, 1):
            lines.append(f"| {idx} | `{row['module']}` | AST 未发现 `@router.<verb>` 装饰器，"
                         "可能通过 `add_api_route` 或聚合 router 动态挂载，**不计入零调用结论** |")
    else:
        lines.append("无：所有 router 均解析出至少一条路由。")
    lines.append("")
    lines.append("## 结论与新增任务项")
    lines.append("")
    deletable = [r["module"] for r in zero_rows if r["test_refs"] == 0]
    frozen = [r["module"] for r in zero_rows if r["test_refs"] > 0]
    lines.append(f"1. `app/services/` **{len(rows)}** 个模块中，**{len(zero_rows)}** 个无生产代码引用，"
                 f"其中 **{len(deletable)}** 个连测试也不引用（真死代码）、**{len(frozen)}** 个仅被测试引用（疑似已废弃或待接线）。")
    lines.append(f"2. 已挂载 **{len(routers)}** 个 router 中，**{len(zero_endpoints)}** 个在 `src/api/**/*.ts` 中无任何调用命中；"
                 f"**{len(unparsed)}** 个未能解析路由，需人工复核后并入统计。")
    lines.append("3. 与既有登记互相印证：")
    if any(r["module"].endswith("audit_chain_service") for r in zero_rows):
        lines.append("   - `app.services.audit_chain_service` 生产引用数为 0 → 印证 **G-1 / O-16**「审计哈希链缺生产调用点」；")
    security_routers = [r["module"].rsplit(".", 1)[-1] for r in zero_endpoints
                        if r["module"].rsplit(".", 1)[-1] in ("mfa_endpoints", "oidc_endpoints", "saml_endpoints")]
    if security_routers:
        lines.append(f"   - `{'`、`'.join(security_routers)}` 无前端调用 → 三类安全能力（MFA/OIDC/SAML）"
                     "缺前端入口，属「建了不用」典型；")
    if frozen:
        lines.append(f"   - 仅被测试引用的 {len(frozen)} 个模块（如 `{'`、`'.join(frozen[:3])}`）"
                     "在修复测试时容易被误认为「已接线」，实际生产路径未调用。")
    lines.append("")
    lines.append("### 新增任务项（写入清单 §13）")
    lines.append("")
    lines.append(f"- **R4-5 清扫零引用服务模块（S）**：对 ③-1 中「删除」类（{len(deletable)} 个，"
                 f"如 `{'`、`'.join(deletable[:3]) or '无'}`）执行删除或接线；判据：`app/services/` 生产零引用模块数 = 0，"
                 "且全量 `pytest tests -q` 相对基线（23 failed）无新增失败。")
    lines.append(f"- **R4-6 端点冻结/接线决策（M）**：对 ③-2 的 {len(zero_endpoints)} 个无前端调用 router 逐个标注"
                 "「冻结 / 删除 / 接线」"
                 + (f"，优先处理 `{'`、`'.join(security_routers)}`（安全能力缺前端入口）" if security_routers else "")
                 + "；判据：每个 router 均有决策记录，冻结项在代码注释标注。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="R4-3 功能使用率审计")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="报告输出路径")
    args = parser.parse_args()

    report = build_report()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"报告已生成: {out_path}（{len(report.splitlines())} 行）")


if __name__ == "__main__":
    main()
