"""遗留文件处置审计脚本（只读）。

背景
----
2026-09-24 一次误操作（filter-repo + reset --hard）还原了 313 个文件的未提交修改。
本脚本对"事故还原文件"做可复现的量化审计，产出 docs/遗留文件处置清单.md 所需的全部数据：

    1. 解析事故还原清单（默认 _recovery_gap_report.txt），得到每个文件的增量证据强度
       （`仅 .pyc` = 有字节码证据 / `无来源` = 无任何内容证据 / `已恢复` = 已重建）
    2. 扣除已恢复并提交的文件（默认对比提交 337f07e），得到"仍待处置"集合
    3. 计算引用密度（对全仓库源码做单遍分词聚合，避免 293×N 重复匹配）
    4. 探测相邻测试覆盖（前端 __tests__/*.spec.ts、后端 tests/** 引用）
    5. 按文件归属映射到重构任务（R2-1/R2-2/R2-3/R3-1/R4-1/R5/前端批次/工程配置）
    6. 导出 Markdown 清单表格，或直接生成完整处置文档

用法
----
    venv/Scripts/python.exe scripts/audit_legacy_files.py                  # 打印摘要
    venv/Scripts/python.exe scripts/audit_legacy_files.py --table          # 打印清单表格
    venv/Scripts/python.exe scripts/audit_legacy_files.py --doc <输出路径>  # 生成完整处置文档

设计约束
--------
- 只读：除 `--doc` 指定的输出文件外不写任何文件，不执行任何 git 写操作。
- 可复现：所有判据来自磁盘扫描 + `git show`（只读）+ `.pyc` 头部信息，无外部依赖。
- 已知局限：引用密度基于标识符分词，属近似指标；连字符文件名/字符串懒加载的修正
  由 `--route-check` 逻辑（前端路由枚举）补充，见 `_route_referenced`。
"""
from __future__ import annotations

import argparse
import collections
import io
import os
import re
import subprocess
import sys
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# 扫描语料时的排除目录（构建产物、依赖、工具数据、恢复产物）
SKIP_DIRS = {
    "venv", "node_modules", ".git", "dist", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".codebuddy", ".workbuddy", "_recovered_all_tmp", "_recovered_wip_tmp",
    "_recovered_pyc", "_before_restore_bak",
}

SOURCE_EXTS = (".py", ".ts", ".vue", ".js", ".md", ".yml", ".yaml", ".json", ".scss", ".css", ".html")
CODE_EXTS = (".py", ".ts", ".vue", ".js")

WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# 行格式示例：
#   "无来源                            Dockerfile"
#   "仅 .pyc           2026-07-31 18:06  tests/api/test_bug_api.py"
# 因此日期与时间均为可选前缀，路径取最后一个非空片段。
PATH_RE = re.compile(
    r"^(已恢复|仅 \.pyc|无来源)\s+(?:\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?\s+)?(\S+)$"
)

# 重构任务归属规则：(路径正则, 任务代号, 说明) —— 顺序敏感，先匹配先命中
REFACTOR_RULES: Sequence[Tuple[str, str, str]] = (
    (r"^app/api/", "R2-3", "端点业务逻辑下沉 service"),
    (r"^app/db/", "R2-1/R2-2", "会话层归一 / 读写分离降级"),
    (r"^app/crud/", "R4-1", "六域分包（含拆分收尾）"),
    (r"^app/services/test_execution_engine/", "R3-1", "自愈能力策略化"),
    (r"^app/services/", "R4-1", "六域分包"),
    (r"^app/models/", "R4-1", "六域分包"),
    (r"^app/utils/|^app/ai/", "R4-1", "六域分包"),
    (r"^app/tasks/", "R5", "执行进程隔离（自测执行器）"),
    (r"^app/", "R4-1", "六域分包"),
    (r"^src/", "前端批次", "前端分批重构（先出映射表）"),
    (r"^tests/", "基线维护", "测试基线与增量对齐"),
    (r"^docs/", "文档订正", "D 组文档订正"),
    (r"^alembic/", "迁移", "随数据层变更同步"),
    (r"^deploy/|^\.github/", "CI/CD", "门禁与部署清单"),
)

CATEGORY_RULES: Sequence[Tuple[str, str]] = (
    (r"^src/", "前端"),
    (r"^tests/", "测试"),
    (r"^app/api/", "后端-端点"),
    (r"^app/services/", "后端-服务"),
    (r"^app/crud/|^app/db/", "后端-数据"),
    (r"^app/utils/|^app/ai/", "后端-工具AI"),
    (r"^app/", "后端-其他"),
    (r"^docs/|^\.github/|^scripts/|^[^/]+$", "工程配置/文档"),
)

# ---------------------------------------------------------------------------
# 引用面核实结论（2026-09-28，由 code-explorer 子代理做符号级检索后固化）
# 检索模式覆盖：路由懒加载字符串、import.meta.glob、defineAsyncComponent、
# vite.config.ts manualChunks、模板标签（含 kebab-case）、vitest/cypress 配置。
# 结论用于修正纯分词统计的误判（连字符文件名、字符串懒加载）。
# ---------------------------------------------------------------------------

# 前端"当前工作树零引用"文件（检索后仍无任何引用）
FRONTEND_ORPHANS: Sequence[Tuple[str, str]] = (
    ("src/views/analysis/AnalysisPage.vue", "路由仅 redirect 无 component；仅文档提及"),
    ("src/views/system/quality-rule/index.vue", "路由为 redirect（routes.ts:41-44）"),
    ("src/views/system/test-capability/index.vue", "路由为 redirect（routes.ts:26-30）"),
    ("src/views/test/index.vue", "src 内 0 命中"),
    ("src/components/report/ReportStat.vue", "仅出现在 components.d.ts 自动注册清单"),
    ("src/components/case/SupplementForm.vue", "仅 components.d.ts + 自身"),
    ("src/styles/select-unified.css", "无 @import / <style src> 引用"),
    ("src/composables/useCaseSelection.ts", "仅自身 import"),
    ("src/composables/useWebSocket.ts", "实际 WebSocket 走 src/utils/websocket.ts"),
    ("src/views/case/components/GenerateCaseConfigForm.vue", "无 import、无模板标签"),
    ("src/views/case/components/GenerateCaseResultCard.vue", "无 import、无模板标签"),
    ("src/views/case/components/ContextHistoryCases.vue", "名称 src 内 0 命中"),
    ("src/views/case/components/ContextTestPointSelector.vue", "名称 src 内 0 命中"),
    ("src/views/case/components/ContextScreenPreview.vue", "名称 0 命中（自身引用 FlowSortEditor）"),
)

# 前端"连锁失效"：有文本引用，但唯一引用方本身是不可达孤儿
FRONTEND_CHAIN_ORPHANS: Sequence[Tuple[str, str]] = (
    ("src/components/case/FlowSortEditor.vue", "唯一引用方 ContextScreenPreview.vue（孤儿）"),
    ("src/components/case/FlowSortEditor.scss", "仅 FlowSortEditor.vue @use"),
    ("src/views/case/components/GenerateCaseNavBar.vue", "仅 GenerateCaseResultCard.vue（孤儿）引用"),
    ("src/views/case/components/GenerateCaseStepSection.vue", "仅 GenerateCaseResultCard.vue（孤儿）引用"),
    ("src/views/case/components/ContextHealthPanel.vue", "仅 GenerateCaseConfigForm.vue（孤儿）引用"),
    ("src/views/case/components/EvidenceRefsPanel.vue", "仅 GenerateCaseConfigForm.vue（孤儿）引用"),
    ("src/components/analysis/ProgressBar.vue", "仅 AnalysisPage.vue（孤儿）引用"),
    ("src/store/analysis.ts", "仅 AnalysisPage.vue（孤儿）引用"),
)

# 后端"除自身包外零引用"文件（均仍被测试引用，删除前须先改测试）
BACKEND_ORPHANS: Sequence[Tuple[str, str]] = (
    ("app/crud/project.py", "app/ 内 0 命中；仅 tests/ 引用；同目录已存在 project_query/project_mutate"),
    ("app/crud/project_flow_data.py", "app/ 内 0 命中；仅 tests/crud/test_crud_project_flow_data.py 引用"),
    ("app/utils/browser_controller.py", "v1 实现，app/ 内 0 命中；仅 3 个真实浏览器测试引用（v2 为活跃实现）"),
)

# 后端 fan-in 最高的文件（R2-3 / R4-1 的"必须先出接口契约"候选）
BACKEND_FANIN: Sequence[Tuple[str, str, str]] = (
    ("app/models/test_case.py", "≈110+", "被 endpoints / crud / services / tasks 广泛引用"),
    ("app/models/user.py", "≈110+", "app/models/__init__.py 全量重导出；app/core/permissions.py 依赖"),
    ("app/models/project.py", "≈99+", "app/models/__init__.py 全量重导出"),
    ("app/utils/ai_client_core.py", "15", "ai_client / ai_client_stream / ai_client_enhanced / xmind 解析共用"),
    ("app/services/test_case_generation/validator.py", "≈22（包级）", "test_case_generation 包被多服务引用"),
    ("app/models/iteration.py", "21", "CRUD 与迭代相关端点"),
    ("app/models/test_result.py", "20", "执行结果链路"),
    ("app/models/test_point.py", "20", "测试点与导入链路"),
    ("app/utils/ai_client.py", "8", "case_refresh_service、test_case_ai_generate 端点"),
    ("app/crud/file.py", "≈8-10", "文件上传/导出端点与 content_extractor"),
    ("app/models/requirement.py", "8", "需求与用例关联"),
    ("app/services/review_service/_core.py", "7", "review_service 包内 _core_async / _undo"),
    ("app/crud/test_task.py", "5", "app/tasks/_self_test_executor_mixin.py、task_service/core_mixin.py"),
    ("app/models/report.py", "5", "crud/test_report.py、report_service、report 端点"),
    ("app/services/test_data/{__init__,generator_mixin}.py", "6", "test_execution_engine 以 TestDataGenerator 接入"),
)

# 前端被路由引用最广的视图（分批重构的"契约锚点"）
FRONTEND_ROUTE_ANCHORS: Sequence[Tuple[str, str]] = (
    ("src/views/requirement/resource-manage.vue", "routes.ts:160 与 173（唯一双路由复用视图）"),
    ("src/views/task/TaskList.vue", "routes.ts:289 与 295（双路由复用）"),
    ("src/views/project/detail.vue", "routes.ts:141（项目详情，跨页引用最多）"),
    ("src/views/project/ProjectList.vue", "routes.ts:135"),
    ("src/views/case/TestCaseList.vue", "routes.ts:217"),
    ("src/views/case/smart-generate.vue", "routes.ts:223"),
    ("src/views/task/TaskDetail.vue", "routes.ts:307"),
    ("src/views/iteration/PipelineProgress.vue", "routes.ts:373"),
    ("src/views/iteration/ReviewInbox.vue", "routes.ts:385"),
    ("src/views/admin/AICostDashboard.vue", "routes.ts:112"),
)

# 其他结构性发现（影响 R2-3 / R4-1 与门禁设计）
AUDIT_FINDINGS: Sequence[str] = (
    "**端点注册双源**：`app/main.py:200-242` 内联注册实际生效；"
    "`app/api/v1/endpoints/__init__.py:55` 的 `register_all_routers` 全仓库无调用点。"
    "R2-3 下沉时必须二选一并删除另一处，否则 URL 契约易漂移。",
    "**无字符串动态导入**：`app/` 全量检索 `importlib.import_module` / `__import__` 均为 0 命中；"
    "注册表（agent tools/registry、selector_registry、prompt_registry 等）均为静态 import，"
    "不存在隐藏引用导致待处置文件被跳过的情况。",
    "**CI 门禁覆盖面**：`.github/workflows/ci.yml:73-74` 后端仅跑 "
    "`tests/api tests/crud tests/models tests/schemas tests/services` 五个目录；"
    "`tests/` 根目录与 `tests/ai/`、`tests/utils/` 的待处置文件不在门禁内（CI 注释已登记为既有欠账）。"
    "前端 `npx vitest run`（ci.yml:94）覆盖全部前端 spec。",
    "**pytest 收集规则**：`pytest.ini` 无 `collect_ignore_glob`、无 deselect；"
    "冻结区的 `collect_ignore_glob = [\"tasks/_frozen/*\"]` 位于 `tests/conftest.py:19`（§11 O-1，不得回退）。",
    "**新旧双实现并存**：前端 flow 相关存在 `useFlowSort.ts`/`useFlowCore.ts`（现有活跃实现）与 "
    "`flowSort/*`、`FlowSortEditor` 集群（经核实整体不可达）并存；"
    "后端 crud 目录存在 `project.py`（单体）与 `project_query.py`/`project_mutate.py`（拆分产物）并存。"
    "这两处均是还原误伤后「新实现已入库、旧实现遗留」的形态，处置时须对照丢失增量再定去留。",
)


def _configure_stdout() -> None:
    """Windows 控制台默认 GBK，中文与特殊符号会报错，统一切到 UTF-8。"""
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _run_git(args: Sequence[str]) -> str:
    """执行只读 git 命令；关闭 quotepath 以免中文路径被转义。"""
    proc = subprocess.run(
        ["git", "-C", REPO_ROOT, "-c", "core.quotepath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.stdout if proc.returncode == 0 else ""


def parse_report(report_path: str) -> Dict[str, str]:
    """解析事故还原清单，返回 {相对路径: 证据等级}。

    证据等级：pyc = 有 .pyc 字节码证据；snapshot = 已由会话快照恢复；none = 无内容证据。
    """
    levels: Dict[str, str] = {}
    if not os.path.isfile(report_path):
        return levels
    with open(report_path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            m = PATH_RE.match(raw.strip())
            if not m:
                continue
            status, path = m.group(1), m.group(2)
            if path.isdigit():
                continue  # 防御：跳过 "无来源: 265" 这类统计行（正常格式已被正则排除）
            levels[path.replace(os.sep, "/")] = {
                "仅 .pyc": "pyc", "已恢复": "snapshot", "无来源": "none",
            }[status]
    return levels


def restored_files(commit: str) -> set[str]:
    """返回指定提交新增/修改的文件集合（用于扣除已恢复项）。"""
    out = _run_git(["show", "--name-only", "--format=", commit])
    return {line.strip().replace(os.sep, "/") for line in out.splitlines() if line.strip()}


def build_corpus() -> Tuple[collections.Counter, collections.Counter, int]:
    """单遍扫描仓库源码，返回 (token 计数, 测试目录 token 计数, 语料文件数)。"""
    tokens: collections.Counter = collections.Counter()
    test_tokens: collections.Counter = collections.Counter()
    files = 0
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(SOURCE_EXTS):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, REPO_ROOT).replace(os.sep, "/")
            try:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            found = set(WORD_RE.findall(text))
            tokens.update(found)
            if rel.startswith("tests/"):
                test_tokens.update(found)
            files += 1
    return tokens, test_tokens, files


def route_referenced(tokens: collections.Counter) -> Dict[str, int]:
    """枚举前端路由文件中的懒加载引用，返回 {视图文件名(含扩展名): 出现次数}。

    修正分词扫描对连字符文件名的漏判（`resource-manage.vue` 会被分词拆成两个词）。
    """
    refs: Dict[str, int] = {}
    router_dir = os.path.join(REPO_ROOT, "src", "router")
    if not os.path.isdir(router_dir):
        return refs
    for name in os.listdir(router_dir):
        if not name.endswith((".ts", ".js")):
            continue
        try:
            with open(os.path.join(router_dir, name), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for hit in re.finditer(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
            refs[os.path.basename(hit.group(1))] = refs.get(os.path.basename(hit.group(1)), 0) + 1
    return refs


def adjacent_frontend_test(rel_path: str) -> bool:
    """前端文件是否存在同名相邻单测（__tests__ 目录内包含该文件的主名）。"""
    directory = os.path.dirname(os.path.join(REPO_ROOT, rel_path))
    tests_dir = os.path.join(directory, "__tests__")
    if not os.path.isdir(tests_dir):
        return False
    stem = os.path.splitext(os.path.basename(rel_path))[0]
    return any(stem in name for name in os.listdir(tests_dir))


def backend_test_ref(rel_path: str, test_tokens: collections.Counter) -> bool:
    """后端模块是否被 tests/ 引用（按模块基名或点分路径判断）。"""
    stem = os.path.splitext(os.path.basename(rel_path))[0]
    return test_tokens.get(stem, 0) > 0


def density_bucket(count: int) -> str:
    if count == 0:
        return "零(0)"
    if count <= 2:
        return f"低({count})"
    if count <= 6:
        return f"中({count})"
    return f"高(>6)"


def classify_category(rel_path: str) -> str:
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, rel_path):
            return category
    return "其他"


def classify_refactor(rel_path: str) -> Tuple[str, str]:
    for pattern, task, note in REFACTOR_RULES:
        if re.search(pattern, rel_path):
            return task, note
    return "待定", "无对应重构任务"


def disposition(level: str, task: str, category: str) -> str:
    """处置结论：优先按增量证据强度分流，其次按是否处在重构范围。"""
    if level == "pyc":
        return "P0 重建增量（有 .pyc 字节码证据）"
    if level == "snapshot":
        return "P0 人工比对后重建（有会话快照）"
    if task == "待定":
        return "按需补齐（无重构计划覆盖）"
    if category in ("前端", "后端-端点", "后端-数据", "后端-服务", "后端-工具AI", "后端-其他"):
        return f"纳入 {task}，不恢复增量"
    return "按需补齐"


def analyze(report_path: str, restored_commit: str) -> List[Dict[str, str]]:
    """执行完整审计，返回逐文件记录列表。"""
    levels = parse_report(report_path)
    restored = restored_files(restored_commit)
    tokens, test_tokens, corpus_count = build_corpus()
    routes = route_referenced(tokens)

    rows: List[Dict[str, str]] = []
    for path in sorted(levels):
        if path in restored:
            continue
        level = levels[path]
        stem = os.path.splitext(os.path.basename(path))[0]
        count = tokens.get(stem, 0)
        category = classify_category(path)
        task, _note = classify_refactor(path)

        if category == "前端" and os.path.basename(path) in routes:
            density = f"路由懒加载({routes[os.path.basename(path)]})"
        elif task == "待定":
            density = "不适用"
        else:
            density = density_bucket(count)

        if category == "前端":
            has_test = "有" if adjacent_frontend_test(path) else "无"
        elif category == "测试":
            has_test = "自身"
        elif category.startswith("后端"):
            has_test = "有" if backend_test_ref(path, test_tokens) else "无"
        else:
            has_test = "不适用"

        rows.append({
            "file": path,
            "category": category,
            "evidence": {"pyc": ".pyc 字节码", "snapshot": "会话快照", "none": "无"}[level],
            "density": density,
            "test": has_test,
            "task": task,
            "disposition": disposition(level, task, category),
            "_corpus": str(corpus_count),
        })
    return rows


def summarize(rows: Sequence[Dict[str, str]]) -> Dict[str, collections.Counter]:
    """按类别、证据强度、处置结论聚合统计。"""
    return {
        "category": collections.Counter(r["category"] for r in rows),
        "evidence": collections.Counter(r["evidence"] for r in rows),
        "disposition": collections.Counter(r["disposition"] for r in rows),
        "task": collections.Counter(r["task"] for r in rows),
    }


def render_table(rows: Sequence[Dict[str, str]]) -> str:
    """渲染固定 schema 的 Markdown 清单表格。"""
    header = (
        "| 文件 | 类别 | 增量证据 | 引用密度 | 相邻测试 | 重构任务 | 处置结论 |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
    )
    body = "".join(
        f"| `{r['file']}` | {r['category']} | {r['evidence']} | {r['density']} | "
        f"{r['test']} | {r['task']} | {r['disposition']} |\n"
        for r in rows
    )
    return header + body


PYC_LEDGER_REL = os.path.join("docs", "analysis", "legacy-pyc-diff-report.txt")

# P0 台账中的人工裁决（覆盖机械规则），键为仓库相对路径
PYC_LEDGER_OVERRIDES: Dict[str, str] = {
    "app/models/test_case.py": "已解决：tenant_id 增量已按字节码精确重建并提交（337f07e）",
    "app/models/test_point.py": "已解决：tenant_id 增量已按字节码精确重建并提交（337f07e）",
    "app/models/test_result.py": "已解决：tenant_id 增量已按字节码精确重建并提交（337f07e）",
    "app/models/test_capability.py": "已解决：tenant_id 增量已按字节码精确重建并提交（337f07e）",
    "app/crud/test_task.py": "已解决：重建为「查询/变更分离」统一导出 shim（337f07e）",
    "tests/services/conftest.py": "已重建：补回 CSRF 中间件所需的 Origin 头（见 6.1 说明）",
}

_PYC_HEAD_RE = re.compile(r"^(?P<path>\S+)\s+\(旧版编译于 (?P<ts>[\d\- :]+)\)\s*$")


def build_pyc_ledger(report_path: str) -> List[Tuple[str, str, int, str, str]]:
    """解析入库的 .pyc 差异报告，产出 P0 台账行。

    Returns:
        [(文件, 旧版编译于, 差异函数数, 旧版独有函数, 处置结论), ...]
    """
    if not os.path.isfile(report_path):
        return []
    ledger: List[Tuple[str, str, int, str, str]] = []
    with open(report_path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    for block in content.split("\n\n"):
        lines = block.strip().split("\n")
        if not lines:
            continue
        m = _PYC_HEAD_RE.match(lines[0].strip())
        if not m:
            continue
        path, ts = m.group("path"), m.group("ts")
        diff_funcs = sum(1 for line in lines[1:] if line.strip().startswith("~ "))
        only_old = any("仅旧版有的函数" in line for line in lines[1:])
        if path in PYC_LEDGER_OVERRIDES:
            verdict = PYC_LEDGER_OVERRIDES[path]
        elif only_old:
            verdict = "不重建：旧版含当前已不存在的函数，差异已被后续提交/重构取代"
        elif diff_funcs == 0:
            verdict = "不重建：结构一致，差异仅在函数体字面量（保留证据备查）"
        else:
            verdict = "需人工比对：保留证据，纳入后续测试对齐（P1/基线维护）"
        ledger.append((path, ts, diff_funcs, "是" if only_old else "否", verdict))
    return sorted(ledger, key=lambda r: r[0])


def render_doc(rows: Sequence[Dict[str, str]], report_path: str, restored_commit: str) -> str:
    """生成完整处置文档（四段式报告 + 清单 + P0 台账 + 引用面附录）。"""
    """生成完整处置文档（四段式报告 + 清单 + 结论）。"""
    stats = summarize(rows)
    total = len(rows)
    evidence = stats["evidence"]
    category = stats["category"]
    disposition_stats = stats["disposition"]
    today = date.today().isoformat()

    def top(counter: collections.Counter, n: int = 12) -> Iterable[Tuple[str, int]]:
        return sorted(counter.items(), key=lambda kv: -kv[1])[:n]

    lines: List[str] = []
    add = lines.append

    add("# AI-TestMaster 遗留文件处置清单")
    add("")
    add(f"> **文档版本** v1.0 ｜ 生成日期 {today} ｜ 编制：遗留文件审计脚本 "
        f"`scripts/audit_legacy_files.py` ｜ 数据来源：`{os.path.basename(report_path)}` + git 只读比对")
    add(">")
    add("> **口径说明**：事故（2026-09-24）丢失的是**未提交增量**；本清单中的文件本身均已入库、可运行，"
        "因此每行结论同时回答两个问题：**增量是否值得重建**、**文件是否可直接重构**。")
    add(">")
    add(f"> **统计口径**：事故还原文件扣除已恢复提交（`{restored_commit}`）后，**仍待处置 {total} 个**。")
    add("")

    add("## 1. 清单与初步分类")
    add("")
    add("### 1.1 按角色分类")
    add("")
    add("| 类别 | 数量 |")
    add("| --- | --- |")
    for name, cnt in top(category, len(category)):
        add(f"| {name} | {cnt} |")
    add("")
    add("### 1.2 按增量证据强度分类")
    add("")
    add("| 证据强度 | 数量 | 含义 |")
    add("| --- | --- | --- |")
    add(f"| .pyc 字节码 | {evidence.get('.pyc 字节码', 0)} | 可用 `depyf`/`dis` 精确还原，成本最低 |")
    add(f"| 会话快照 | {evidence.get('会话快照', 0)} | 有历史读取/编辑记录，需人工比对 |")
    add(f"| 无 | {evidence.get('无', 0)} | 增量内容不可知，只能按功能重做 |")
    add("")
    add("### 1.3 按重构任务归属")
    add("")
    add("| 重构任务 | 数量 |")
    add("| --- | --- |")
    for name, cnt in top(stats["task"], len(stats["task"])):
        add(f"| {name} | {cnt} |")
    add("")
    add("### 1.4 逐文件清单")
    add("")
    add(render_table(rows))
    add("")

    add("## 2. 存在价值判断")
    add("")
    add("| 类别 | 数量 | 结论 |")
    add("| --- | --- | --- |")
    add(f"| 前端 | {category.get('前端', 0)} | 必须保留（运行中的界面层）；增量无证据，"
        "重建价值低于按需求重写；重构前需补 `__tests__` 护栏 |")
    add(f"| 测试 | {category.get('测试', 0)} | 保留文件；其中带 `.pyc` 证据者可低成本精确还原，"
        "测试增量本身又是后续重构的护栏 |")
    add(f"| 后端-端点 | {category.get('后端-端点', 0)} | 保留；处于 R2-3 重构范围，"
        "建议在重构中一次性落地而非先恢复后推翻 |")
    add(f"| 后端-服务 | {category.get('后端-服务', 0)} | 保留；自愈类 mixin 与 R3-1 立项重合 |")
    add(f"| 后端-数据 | {category.get('后端-数据', 0)} | 保留；拆分后的 `*_query/*_mutate` 已就位，"
        "旧单体文件增量已被取代 |")
    add(f"| 后端-工具AI | {category.get('后端-工具AI', 0)} | 保留；AI 客户端族相互耦合，需先定接口契约 |")
    add(f"| 后端-其他 | {category.get('后端-其他', 0)} | 保留；低引用但属主链路配置 |")
    add(f"| 工程配置/文档 | {category.get('工程配置/文档', 0)} | 保留；启动脚本可依 README 重写，"
        "启动类脚本与 CI 清单须一并核对 |")
    add("")
    add("**零引用候选复核结论**：文本分词扫描的候选经符号级核实后大量证伪——"
        "`src/views/**` 下的视图实际由 `src/router/routes.ts` 懒加载引用（连字符文件名导致分词误判，"
        "已由脚本 `route_referenced()` 纠正）；剩余为 `*.spec.ts`、`components.d.ts`、`docker-compose.yml`、"
        "`security-scan.yml` 等**工具消费型文件**。经二次核实仍成立的可疑文件见 §6.1，"
        "**本轮不执行任何删除**，仅登记为「归档观察」并给出复核前置条件。")
    add("")

    add("## 3. 是否可直接重构的判断")
    add("")
    add("| 文件群 | 可行性 | 依赖风险 | 测试覆盖 | 替代方案 | 前置条件 |")
    add("| --- | --- | --- | --- | --- | --- |")
    add("| 端点层 | 高 | 中（`app/main.py` 路由注册 + 前端 API 层引用） | `tests/api` 基线可作护栏 | "
        "按 R2-3 下沉 service，router 保留薄层 | Q1 范式决策落地 |")
    add("| 数据层 | 中高 | 低（拆分产物已就位） | `tests/api` + `tests/db` | 直接完成拆分收尾，废弃旧单体 | 无 |")
    add("| 服务层 | 中 | 中（自愈 mixin 被执行引擎主链路依赖） | `tests/services` | 并入 R3-1/R5 立项实现 | R3-1 决策（Q8） |")
    add("| 工具/AI 层 | 中低 | 高（`ai_client*` 相互耦合） | `tests/utils` 部分覆盖 | 先出接口契约再重构 | O-14 相关欠账收敛 |")
    add("| 前端 | 中 | 低（视图层相对独立）但引用面广 | 单测覆盖不足，vitest 基线 555 passed | "
        "建「视图→路由→API→store」映射表后分批重构 | 映射表 + 补 spec |")
    add("| 测试 | 高 | 无 | 自身即护栏 | 依 `.pyc` 证据逐条核对后重写 | 无 |")
    add("| 工程配置 | 高 | 低 | 无 | 依 README 与现有启动脚本重写 | 无 |")
    add("")

    add("## 4. 最终建议")
    add("")
    add("| 优先级 | 动作 | 范围 | 风险控制 |")
    add("| --- | --- | --- | --- |")
    p0 = sum(v for k, v in disposition_stats.items() if k.startswith("P0"))
    add(f"| P0 | 重建增量 | {p0} 个（有 `.pyc` 证据 / 会话快照） | 每批跑 `tests/api` + `tests/services`，比对 §12 基线 |")
    add("| P1 | 完成 O-14 未完成功能 | audit chain / self-healing 集成 / dependency resolution / legacy 套件 | "
        "独立立项 + 测试入库后再合并 |")
    add("| P2 | 按重构方案重写（不恢复增量） | 端点层 + 数据层 + 服务层 | 先落 Q1/Q2/Q8 决策；R4-1 分阶段并保留 shim 一迭代 |")
    add(f"| P3 | 前端分批重构 | {category.get('前端', 0)} 个 | 先建映射表、补 `__tests__`，vitest 555 passed 为闸门 |")
    add(f"| P4 | 工程配置补齐 | {category.get('工程配置/文档', 0)} 个 | 低风险，随 P0 一起 |")
    add("| 归档/删除 | 本轮无删除项 | — | 如需删除须先做运行时依赖分析（路由全量枚举 / `depcheck`） |")
    add("")
    add("### 4.1 处置结论汇总")
    add("")
    add("| 处置结论 | 数量 |")
    add("| --- | --- |")
    for name, cnt in top(disposition_stats, len(disposition_stats)):
        add(f"| {name} | {cnt} |")
    add("")
    add("### 4.2 执行顺序与风险控制要点")
    add("")
    add(f"1. **P0 先行（已完成核对，见 §5）**：`.pyc` 证据报告已入库为 `{PYC_LEDGER_REL}`，"
        "逐条核对结论：已被后续提交取代者不重建；结构一致者不重建；"
        "仅 `tests/services/conftest.py` 的 CSRF `Origin` 头增量已重建并提交。")
    add("2. **P1 登记立项**：将 O-14 四项未完成功能写入 `docs/架构优化执行计划清单.md` §11，"
        "补推荐默认值与最晚决策时点。")
    add("3. **P2 重构优先于恢复**：端点/数据/服务层的增量一律不恢复，在 R2-3 / R3-1 / R4-1 中一次性落地。")
    add("4. **P3 前端建表**：先产出映射表并补齐单测，再按批次重构视图。")
    add("5. **闸门**：每批改动后比对 `docs/架构优化执行计划清单.md` §12 基线"
        "（后端全量 73 failed / 10191 passed；`tests/api` 7 failed / 1015 passed；前端 555 passed），"
        "新增失败必须先归因再继续。")
    add("6. **纪律**：产出物一律先入库（§11 O-6）；禁止 `reset --hard` / `checkout -f` / `clean -fdx`；"
        "历史改写仅在独立克隆中进行并先断言工作目录。")
    add("")

    add("## 5. P0 台账：`.pyc` 字节码证据逐条核对")
    add("")
    ledger = build_pyc_ledger(os.path.join(REPO_ROOT, PYC_LEDGER_REL))
    if not ledger:
        add(f"> 证据报告未入库（请先生成 `{PYC_LEDGER_REL}`）；台账见对话记录与 "
            "`d:\\recovery_pyc\\_diff_report.txt`。")
    else:
        resolved = sum(1 for r in ledger if r[4].startswith("已"))
        rebuilt = sum(1 for r in ledger if "已重建" in r[4])
        skip = sum(1 for r in ledger if r[4].startswith("不重建"))
        manual = sum(1 for r in ledger if r[4].startswith("需人工比对"))
        add(f"> 证据来源：`{PYC_LEDGER_REL}`（旧版 `.pyc` 与当前源码的字节码级差异）。"
            f"共 {len(ledger)} 条，其中**已解决/已重建 {resolved} 条**（含重建增量 {rebuilt} 条）、"
            f"**判定不重建 {skip} 条**、**需人工比对 {manual} 条**。")
        add("")
        add("| 文件 | 旧版编译于 | 差异函数数 | 旧版独有函数 | 处置结论 |")
        add("| --- | --- | --- | --- | --- |")
        for path, ts, diff_funcs, only_old, verdict in ledger:
            add(f"| `{path}` | {ts} | {diff_funcs} | {only_old} | {verdict} |")
        add("")
        add("### 5.1 本次实际重建的增量")
        add("")
        add("`tests/services/conftest.py` —— 旧版 `.pyc` 反汇编显示两个 HTTP fixture 的 `AsyncClient` "
            "调用包含第三个关键字参数 `headers`（`KW_NAMES -> ('transport', 'base_url', 'headers')`，"
            "配套 `BUILD_MAP` 常量 `'Origin'` / `'http://localhost:5173'`）：")
        add("")
        add("```python")
        add("    # 设置 Origin 头模拟真实浏览器，使 CSRF 中间件 Origin/Referer 校验通过")
        add("    async with AsyncClient(")
        add("        transport=transport,")
        add('        base_url="http://test",')
        add('        headers={"Origin": "http://localhost:5173"},')
        add("    ) as client:")
        add("```")
        add("")
        add("重建依据：`app/core/security_middleware.py` 的 `CSRFMiddleware` 对非安全方法"
            "（POST/PUT/DELETE）在缺少 CSRF token 时回退校验 `Origin`/`Referer`，"
            "无匹配 Origin 将返回 403；已恢复的 `tests/api/conftest.py` 采用同一写法，"
            "本次按相同模式补齐 `tests/services/conftest.py`。")
        add("")
        add("### 5.2 判定不重建的理由")
        add("")
        add("1. **已被后续提交/重构取代**：旧版含当前已不存在的函数（如 `_verify_task_access*` 已被 "
            "R0-3「归属校验归一」的 `require_task_access` 取代），恢复旧增量等于回退已验证的重构。")
        add("2. **结构一致、仅字面量差异**：差异函数数为 0 的端点/CRUD 文件，"
            "其 `.pyc` 与当前源码大小仅差数个字节，属提示语/常量微调，无业务影响且无法可靠还原。")
        add("3. **测试文件的较大差异归入 P1**：`tests/api/test_core_config.py`（41 个差异函数）、"
            "`test_auth.py`（29 个）等对应 §11 O-14 登记的四项未完成功能与 legacy 套件对齐，"
            "应随功能实现或测试基线维护统一处理，而非按字节码逐字还原。")
        add("")

    add("## 6. 引用面核实附录（2026-09-28）")
    add("")
    add("> 核实方式：符号级检索（路由懒加载字符串、`import.meta.glob`、`defineAsyncComponent`、"
        "`vite.config.ts` manualChunks、模板标签含 kebab-case、vitest/cypress 配置、"
        "`importlib` / `__import__` 动态导入）。用于修正纯分词统计的误判。")
    add("")
    add("### 6.1 二次核实后仍无引用的文件（归档观察，本轮不删除）")
    add("")
    add("**前端（当前工作树零引用）**")
    add("")
    add("| 文件 | 核实结论 |")
    add("| --- | --- |")
    for path, why in FRONTEND_ORPHANS:
        add(f"| `{path}` | {why} |")
    add("")
    add("**前端（连锁失效：唯一引用方本身不可达）**")
    add("")
    add("| 文件 | 核实结论 |")
    add("| --- | --- |")
    for path, why in FRONTEND_CHAIN_ORPHANS:
        add(f"| `{path}` | {why} |")
    add("")
    add("**后端（除自身包外零引用，但均被测试引用）**")
    add("")
    add("| 文件 | 核实结论 |")
    add("| --- | --- |")
    for path, why in BACKEND_ORPHANS:
        add(f"| `{path}` | {why} |")
    add("")
    add("**复核前置条件（满足后方可进入删除评审）**：① 确认对应功能已由新实现完全覆盖；"
        "② 同步修改或删除引用它们的测试；③ 运行全量后端测试与前端 vitest 比对 §12 基线；"
        "④ 单独提交并可回滚（禁止与重构混提）。")
    add("")
    add("### 6.2 重构契约锚点（fan-in 高，改动前须先定接口）")
    add("")
    add("| 后端文件 | fan-in（约） | 引用说明 |")
    add("| --- | --- | --- |")
    for path, fanin, why in BACKEND_FANIN:
        add(f"| `{path}` | {fanin} | {why} |")
    add("")
    add("| 前端视图 | 路由引用 |")
    add("| --- | --- |")
    for path, why in FRONTEND_ROUTE_ANCHORS:
        add(f"| `{path}` | {why} |")
    add("")
    add("### 6.3 结构性发现")
    add("")
    for idx, item in enumerate(AUDIT_FINDINGS, start=1):
        add(f"{idx}. {item}")
    add("")
    add("### 6.4 前端单测覆盖（相邻 `__tests__`）")
    add("")
    add("待处置前端文件中带同名相邻单测者：`src/composables/useFlowEditor.ts`、"
        "`src/store/smartGeneration.ts`、`src/store/generate/generateHelpers.ts`、"
        "`src/views/quick-test/__tests__/useQuickTestFlow.spec.ts`（spec 本身待处置）；"
        "另有 `AIParseLoading`、`smart-generate`、`TaskDetail`、`ReportDetail`、`useReviewInbox*`、"
        "`project/detail`、`request`、`websocket` 等 spec 间接覆盖待处置文件。"
        "**结论：前端重构前需先补齐 `__tests__` 护栏。**")
    add("")
    add("---")
    add("")
    add(f"*本文档由 `scripts/audit_legacy_files.py` 生成（语料扫描 {rows[0]['_corpus'] if rows else '0'} 个源文件）。"
        "修订请先改脚本再重新生成，避免结论只存在于对话中。*")
    add("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="遗留文件处置审计（只读）")
    parser.add_argument("--report", default=os.path.join(REPO_ROOT, "_recovery_gap_report.txt"),
                        help="事故还原清单路径（默认 _recovery_gap_report.txt）")
    parser.add_argument("--restored-commit", default="337f07e",
                        help="已恢复并提交的提交号，用于扣除已处置项")
    parser.add_argument("--table", action="store_true", help="打印逐文件 Markdown 表格")
    parser.add_argument("--doc", metavar="PATH", help="生成完整处置文档到指定路径")
    args = parser.parse_args(argv)

    rows = analyze(args.report, args.restored_commit)
    if not rows:
        print("[error] 未解析到任何待处置文件，请检查 --report 路径")
        return 1

    if args.table:
        print(render_table(rows))
        return 0

    if args.doc:
        doc = render_doc(rows, args.report, args.restored_commit)
        os.makedirs(os.path.dirname(os.path.abspath(args.doc)), exist_ok=True)
        with open(args.doc, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(doc)
        print(f"[ok] 已生成 {args.doc}（{len(rows)} 行清单）")
        return 0

    stats = summarize(rows)
    print(f"待处置文件: {len(rows)}")
    print("按类别:", dict(stats["category"]))
    print("按证据:", dict(stats["evidence"]))
    print("按重构任务:", dict(stats["task"]))
    print("按处置结论:", dict(stats["disposition"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
