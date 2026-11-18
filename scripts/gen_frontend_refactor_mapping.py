"""P3 阶段一：生成前端分批重构映射表 docs/architecture/frontend-refactor-mapping.md。

数据源：`docs/遗留文件处置清单.md` §1.4 逐文件清单中「类别 = 前端」的 172 个文件
（唯一事实来源，避免依赖已丢失的恢复报告）。

一行一文件：现有路径 → 层 → 领域 → 关联路由 → 外部引用数 → 测试覆盖 → 重构批次 → 建议动作。
未归类文件不做静默兜底：脚本打印清单并以退出码 1 结束。

用法：python scripts/gen_frontend_refactor_mapping.py [--out PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
LEGACY_DOC = ROOT / "docs" / "遗留文件处置清单.md"
ROUTES = SRC / "router" / "routes.ts"
DEFAULT_OUT = ROOT / "docs" / "architecture" / "frontend-refactor-mapping.md"

EXPECTED_TOTAL = 172
SOURCE_SUFFIXES = {".ts", ".vue", ".js", ".tsx", ".jsx"}
ASSET_SUFFIXES = {".scss", ".css"}

# 层：按 src/ 下第一段目录判定
LAYER_BY_SEGMENT = {
    "api": "API 层",
    "store": "Store 层",
    "views": "视图层",
    "components": "组件层",
    "composables": "Composable 层",
    "utils": "工具层",
    "types": "类型层",
    "router": "路由层",
    "layouts": "布局层",
    "constants": "常量层",
    "directives": "指令层",
    "styles": "样式层",
}
INFRA_LAYERS = {
    "应用入口层",
    "API 层",
    "Store 层",
    "工具层",
    "类型层",
    "路由层",
    "布局层",
    "常量层",
    "指令层",
    "样式层",
}

# 领域：按路径关键字判定，顺序敏感（先具体后宽泛）
DOMAIN_RULES = [
    ("app", r"^src/(app\.vue|main\.ts)$|^src/views/test/"),
    ("admin", r"(^|/)admin(/|$)|ai-cost|aicost"),
    ("analysis", r"(^|/)analysis(/|$)|analysispage"),
    (
        "execution",
        r"(execution|test-task|test_task|quick-test|quicktest|task-detail|taskdetail|batch|replay|playback|visual|mobile|(^|/)task(/|$))",
    ),
    ("report", r"(report|defect|bug)"),
    ("review", r"(review|quality|posterior|visibility)"),
    ("pipeline", r"(pipeline|iteration|smart-generat|smartgenerate)"),
    ("testpoint", r"(test-point|testpoint|test_point)"),
    ("case", r"(case|flow|prototype|xmind|requirement|resource|lineage|edge|generate|smart)"),
    ("project", r"(project)"),
    ("auth", r"(auth|login|user|role|permission|profile)"),
    ("system", r"(system|feature-flag|audit-log|prompt|monitor|setting|config)"),
]

DOMAIN_LABELS = {
    "app": "应用入口",
    "infra": "基础设施契约",
    "common": "公共组件与能力",
    "analysis": "AI 分析",
    "admin": "成本看板与管理",
    "case": "用例域",
    "testpoint": "测试点域",
    "execution": "执行域",
    "report": "报告域",
    "review": "评审域",
    "pipeline": "流水线域",
    "project": "项目域",
    "auth": "认证与用户",
    "system": "系统管理",
}

# 批次：契约层先行，其后按领域分组（每批独立 commit + 跑该域 spec）
BATCH_BY_DOMAIN = {
    "app": "B1",
    "infra": "B1",
    "common": "B5",
    "case": "B2",
    "testpoint": "B2",
    "execution": "B3",
    "report": "B4",
    "review": "B4",
    "pipeline": "B4",
    "analysis": "B4",
    "project": "B5",
    "auth": "B5",
    "system": "B5",
    "admin": "B5",
}

BATCH_LABELS = {
    "B1": "B1 基础设施契约（api/store/utils/types/router/constants）",
    "B2": "B2 用例域（含测试点、原型、思维导图、流程编排）",
    "B3": "B3 执行域（执行页、任务、快速验证、移动端）",
    "B4": "B4 报告与评审域（报告、缺陷、质量、流水线迭代）",
    "B5": "B5 项目与系统域（项目、认证、系统管理、公共组件）",
}

SPEC_PATTERN = re.compile(r"(^|/)__tests__/|\.spec\.(ts|js)$|\.test\.(ts|js)$")
IMPORT_PATTERN = re.compile(
    r"""(?:from|import|require|@use|@import|@forward)\s*\(?\s*['"]([^'"]+)['"]""",
)


def parse_legacy_frontend_files() -> list[str]:
    """从遗留清单 §1.4 提取「类别 = 前端」的文件路径（保持表内顺序）。"""
    if not LEGACY_DOC.exists():
        raise SystemExit(f"缺少数据源: {LEGACY_DOC}")

    files: list[str] = []
    for line in LEGACY_DOC.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 7 or cells[1] != "前端":
            continue
        files.append(cells[0].strip("`").replace("\\", "/"))
    return files


def load_sources() -> dict[Path, str]:
    """一次性载入 src 下全部前端源码/样式，供引用解析复用。"""
    sources: dict[Path, str] = {}
    for path in SRC.rglob("*"):
        if path.suffix not in SOURCE_SUFFIXES | ASSET_SUFFIXES:
            continue
        try:
            sources[path.resolve()] = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
    return sources


def resolve_spec(spec: str, importer: Path) -> Path | None:
    """把 import 说明符解析为绝对路径（不要求文件存在，交给调用方比对）。"""
    if spec.startswith("@/"):
        base = SRC / spec[2:]
    elif spec.startswith("."):
        base = importer.parent / spec
    else:
        return None
    try:
        return base.resolve()
    except OSError:
        return None


def candidate_targets(spec: str, importer: Path) -> set[Path]:
    """生成一个说明符可能指向的目标路径集合（含省略扩展名与 /index 形式）。"""
    base = resolve_spec(spec, importer)
    if base is None:
        return set()

    suffix = base.suffix
    if suffix:
        candidates = {base}
    else:
        candidates = {base.with_suffix(ext) for ext in SOURCE_SUFFIXES | ASSET_SUFFIXES}
        candidates |= {base / f"index{ext}" for ext in SOURCE_SUFFIXES}
        candidates.add(base)
    return candidates


def build_reference_index(sources: dict[Path, str]) -> dict[Path, set[Path]]:
    """目标文件 → 引用它的文件集合。"""
    index: dict[Path, set[Path]] = {}
    for importer, text in sources.items():
        for spec in IMPORT_PATTERN.findall(text):
            spec = spec[0] if isinstance(spec, tuple) else spec
            for target in candidate_targets(spec, importer):
                if target in sources and target != importer:
                    index.setdefault(target, set()).add(importer)
    return index


def parse_routes() -> dict[Path, set[str]]:
    """视图文件 → 路由 path 列表（按 routes.ts 中出现顺序取最近的 path:）。

    用全文位置排序而非逐行匹配，兼容 `component: () => import(\n  '...'\n)` 的跨行写法。
    """
    mapping: dict[Path, set[str]] = {}
    if not ROUTES.exists():
        return mapping

    text = ROUTES.read_text(encoding="utf-8")
    events: list[tuple[int, str, str]] = []
    for match in re.finditer(r"path:\s*['\"]([^'\"]*)['\"]", text):
        events.append((match.start(), "path", match.group(1)))
    for match in re.finditer(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
        events.append((match.start(), "import", match.group(1)))
    events.sort()

    last_path: str | None = None
    for _, kind, value in events:
        if kind == "path":
            last_path = value
            continue
        if last_path is None:
            continue
        for target in candidate_targets(value, ROUTES):
            if target.suffix in SOURCE_SUFFIXES:
                mapping.setdefault(target, set()).add(last_path)
    return mapping


def parse_redirect_paths() -> set[str]:
    """routes.ts 中被 `redirect:` 接管（不再加载 component）的 path 集合。"""
    if not ROUTES.exists():
        return set()

    text = ROUTES.read_text(encoding="utf-8")
    events: list[tuple[int, str, str]] = []
    for match in re.finditer(r"path:\s*['\"]([^'\"]*)['\"]", text):
        events.append((match.start(), "path", match.group(1)))
    for match in re.finditer(r"redirect:\s*['\"]([^'\"]+)['\"]", text):
        events.append((match.start(), "redirect", match.group(1)))
    events.sort()

    last_path: str | None = None
    redirected: set[str] = set()
    for _, kind, value in events:
        if kind == "path":
            last_path = value
        elif last_path is not None:
            redirected.add(last_path)
    return redirected


def classify_layer(rel: str) -> str:
    parts = rel.split("/")
    if parts[0] != "src":
        return ""
    if len(parts) == 2:  # src/App.vue、src/main.ts 等根级入口
        return "应用入口层"
    return LAYER_BY_SEGMENT.get(parts[1], "")


def classify_domain(rel: str, layer: str) -> str:
    lowered = rel.lower()
    for domain, pattern in DOMAIN_RULES:
        if re.search(pattern, lowered):
            return domain
    if layer in INFRA_LAYERS:
        return "infra"
    # 组件层/Composable 层未命中业务关键字的，归公共域（不掩盖视图层的未归类）
    if layer in {"组件层", "Composable 层"}:
        return "common"
    return ""


def classify_batch(domain: str) -> str:
    return BATCH_BY_DOMAIN.get(domain, "")


def build_rows(
    files: list[str],
    sources: dict[Path, str],
    ref_index: dict[Path, set[Path]],
    routes: dict[Path, set[str]],
    redirect_paths: set[str],
) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    unclassified: list[str] = []
    entry_files = {"src/main.ts", "src/App.vue", "src/router/index.ts"}

    for rel in files:
        abs_path = (ROOT / rel).resolve()
        layer = classify_layer(rel)
        domain = classify_domain(rel, layer)
        batch = classify_batch(domain)

        if not layer or not domain or not batch:
            unclassified.append(rel)
            layer = layer or "未识别"
            domain = domain or "未归类"
            batch = batch or "未定"

        referrers = ref_index.get(abs_path, set())
        spec_refs = {p for p in referrers if SPEC_PATTERN.search(p.as_posix())}
        prod_refs = referrers - spec_refs

        route_paths = sorted(routes.get(abs_path, set()))
        exists = abs_path.exists()
        is_spec_file = bool(SPEC_PATTERN.search(rel))
        segments = rel.split("/")
        dir_name = segments[-2] if len(segments) >= 2 else ""
        redirected = dir_name in redirect_paths and not route_paths

        if not exists:
            action = "文件已不存在（映射表待复核后删除该行）"
        elif is_spec_file:
            action = "测试护栏：随被测模块重构同步更新，禁止删除"
        elif prod_refs:
            action = "按域重构：保持对外导出契约，改前先补/加厚 spec"
        elif rel in entry_files:
            action = "应用入口：由 index.html / 框架加载，无引用属正常"
        elif route_paths:
            action = "路由可达但无代码引用：重构时保留路由入口"
        elif redirected:
            action = "路由已改为 redirect（旧 URL 指向新页面），死代码候选：本轮仅登记"
        elif spec_refs:
            action = "仅被 spec 引用：先确认是否为死代码，再决定重构或归档"
        else:
            action = "零引用候选：本轮仅登记，不删除（需运行时依赖分析后处理）"

        rows.append(
            {
                "path": rel,
                "layer": layer,
                "domain": domain,
                "domain_label": DOMAIN_LABELS.get(domain, domain),
                "batch": batch,
                "routes": route_paths,
                "prod_refs": len(prod_refs),
                "spec_refs": len(spec_refs),
                "covered": "✅" if spec_refs else "—",
                "exists": exists,
                "action": action,
            }
        )

    return rows, unclassified


def render(rows: list[dict[str, object]], unclassified: list[str]) -> str:
    layer_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    batch_counts: dict[str, int] = {}
    for row in rows:
        layer_counts[row["layer"]] = layer_counts.get(row["layer"], 0) + 1
        domain_counts[row["domain_label"]] = domain_counts.get(row["domain_label"], 0) + 1
        batch_counts[row["batch"]] = batch_counts.get(row["batch"], 0) + 1

    no_ref = sum(1 for r in rows if r["prod_refs"] == 0)
    no_spec = sum(1 for r in rows if not r["covered"] == "✅")
    missing = sum(1 for r in rows if not r["exists"])
    spec_files = sum(1 for r in rows if r["action"].startswith("测试护栏"))
    dead_code = sum(1 for r in rows if "死代码候选" in str(r["action"]))
    entry_files = sum(1 for r in rows if r["action"].startswith("应用入口"))

    lines: list[str] = []
    lines.append("# 前端分批重构映射表（P3 阶段一）")
    lines.append("")
    lines.append("> 生成方式：`python scripts/gen_frontend_refactor_mapping.py`（请勿手工编辑，改脚本后重跑）")
    lines.append("> 数据源：`docs/遗留文件处置清单.md` §1.4「类别 = 前端」逐文件清单")
    lines.append(
        "> 任务归属：**[分支] B-04**（P3 前端分批重构阶段一）——"
        "术语定义见《架构优化执行计划清单》§0：分支任务不计入主线进度"
    )
    lines.append("> 闸门：`npx vitest run` 全绿（历史基线 555 passed）；每批改动后必须复跑")
    lines.append("")
    lines.append("## 1. 覆盖与统计")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("| --- | --- |")
    lines.append(f"| 待处置前端文件总数 | **{len(rows)}** |")
    lines.append(f"| 未归类（须为 0） | **{len(unclassified)}** |")
    lines.append(f"| 工作区缺失文件 | {missing} |")
    lines.append(f"| 无生产代码引用 | {no_ref} |")
    lines.append(f"| 其中测试文件（护栏） | {spec_files} |")
    lines.append(f"| 其中应用入口文件 | {entry_files} |")
    lines.append(f"| 死代码候选（路由改 redirect） | {dead_code} |")
    lines.append(f"| 无 spec 直接覆盖 | {no_spec} |")
    lines.append("")
    lines.append("### 1.1 层分布")
    lines.append("")
    lines.append("| 层 | 文件数 |")
    lines.append("| --- | --- |")
    for layer, count in sorted(layer_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {layer} | {count} |")
    lines.append("")
    lines.append("### 1.2 领域分布")
    lines.append("")
    lines.append("| 领域 | 文件数 |")
    lines.append("| --- | --- |")
    for domain, count in sorted(domain_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {domain} | {count} |")
    lines.append("")
    lines.append("### 1.3 批次分布")
    lines.append("")
    lines.append("| 批次 | 说明 | 文件数 |")
    lines.append("| --- | --- | --- |")
    for batch in sorted(batch_counts):
        lines.append(f"| {batch} | {BATCH_LABELS.get(batch, '未定')} | {batch_counts[batch]} |")
    lines.append("")
    lines.append("## 2. 逐文件映射")
    lines.append("")
    lines.append("| # | 现有路径 | 层 | 领域 | 关联路由 | 生产引用 | spec | 批次 | 建议动作 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for idx, row in enumerate(rows, start=1):
        routes = " / ".join(f"`{p}`" for p in row["routes"]) if row["routes"] else "—"
        lines.append(
            "| {idx} | `{path}` | {layer} | {domain} | {routes} | {refs} | {spec} | {batch} | {action} |".format(
                idx=idx,
                path=row["path"],
                layer=row["layer"],
                domain=row["domain_label"],
                routes=routes,
                refs=row["prod_refs"],
                spec=row["covered"],
                batch=row["batch"],
                action=row["action"],
            )
        )
    lines.append("")
    lines.append("## 3. 批次执行约定")
    lines.append("")
    lines.append("1. 每批独立 commit；提交前 `npx vitest run` 必须全绿（0 failed，总数不下降）。")
    lines.append("2. 批次内先补 spec 再改实现；「无 spec 覆盖」文件在改动前必须先有护栏。")
    lines.append("3. 对外导出（`src/api`、`src/store`、`src/composables`）改签名须同步调用方，禁止留死路径。")
    lines.append("4. 零引用候选本轮只登记不删除；删除需先做路由全量枚举与 `depcheck` 依赖分析。")
    lines.append("")
    lines.append("## 4. 未归类清单")
    lines.append("")
    if unclassified:
        for rel in unclassified:
            lines.append(f"- `{rel}`")
    else:
        lines.append("无（172/172 全部归类）")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成前端分批重构映射表")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    files = parse_legacy_frontend_files()
    if len(files) != EXPECTED_TOTAL:
        print(f"[FAIL] 清单解析到 {len(files)} 条前端文件，期望 {EXPECTED_TOTAL} 条", file=sys.stderr)
        return 1

    sources = load_sources()
    ref_index = build_reference_index(sources)
    routes = parse_routes()
    redirect_paths = parse_redirect_paths()
    rows, unclassified = build_rows(files, sources, ref_index, routes, redirect_paths)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(rows, unclassified), encoding="utf-8")

    print(f"[OK] 已生成 {args.out}")
    print(f"     文件数={len(rows)} 未归类={len(unclassified)} 路由命中={sum(1 for r in rows if r['routes'])}")

    if unclassified:
        print("[FAIL] 存在未归类文件：", file=sys.stderr)
        for rel in unclassified:
            print(f"  - {rel}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
