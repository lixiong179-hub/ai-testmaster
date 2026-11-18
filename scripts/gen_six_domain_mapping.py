"""R4-1 阶段一：生成六域映射表 docs/architecture/six-domain-mapping.md。

一行一文件：现有路径 → 目标路径 → 归属域 → 是否保留 re-export shim。
未归类文件不做静默兜底：脚本打印清单并以退出码 1 结束。

用法：venv/Scripts/python.exe scripts/gen_six_domain_mapping.py [--out PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "app" / "services"
ENDPOINTS = ROOT / "app" / "api" / "v1" / "endpoints"
DEFAULT_OUT = ROOT / "docs" / "architecture" / "six-domain-mapping.md"

DOMAINS = {
    "case": "用例域",
    "test_point": "测试点域",
    "execution": "执行域",
    "review": "评审域",
    "pipeline": "流水线域",
    "agent": "Agent 域",
    "common": "公共域（跨域基础设施，非业务能力）",
}

DIR_RULES = {
    "services/agent": "agent",
    "services/self_healing": "execution",
    "services/test_execution_engine": "execution",
    "services/execution_replay": "execution",
    "services/execution_core": "execution",
    "services/test_point": "test_point",
    "services/mobile_ai_executor": "execution",
    "services/visual_ai": "execution",
    "services/element_locator": "execution",
    "services/batch_locator": "execution",
    "services/recognizers": "execution",
    "services/decision_application_service": "execution",
    "services/cost_statistics": "execution",
    "services/video": "execution",
    "services/url_driven": "case",
    "services/precondition": "case",
    "services/test_case_generation": "case",
    "services/test_case_view": "case",
    "services/test_data": "case",
    "services/test_data_parameterizer": "case",
    "services/case_quality": "case",
    "services/case_migration": "case",
    "services/quality": "case",
    "services/lifecycle_service": "case",
    "services/link_fetcher": "case",
    "services/ai_analysis_service": "case",
    "services/impact_analysis": "case",
    "services/ui_spec_parser": "case",
    "services/xmind_parser": "case",
    "services/xmind_case_parser": "case",
    "services/xmind_ai_parser": "case",
    "services/file_extractor": "case",
    "services/review_service": "review",
    "services/visibility_config": "review",
    "services/pipeline_service": "pipeline",
    "services/self_test": "pipeline",
    "services/task_service": "execution",
    "services/prompt_builder": "common",
    "services/role_service": "common",
    "services/user_service": "common",
    "services/saml": "common",
    "services/storage": "common",
    "services/common": "common",
    "endpoints/execution_core": "execution",
    "endpoints/iteration": "pipeline",
    "endpoints/pipeline_dashboard": "pipeline",
    "endpoints/review_inbox": "review",
    "endpoints/test_case_ai_generate": "case",
    "endpoints/test_point": "test_point",
    "endpoints/ui_prototype": "case",
}

FILE_RULES = [
    ("F01", r"^(agent|agents|mcp_server|mcp_)", "agent"),
    ("F02", r"(test_point)", "test_point"),
    (
        "F03",
        r"^(test_task|batch_locator|execution|execution_|_execution|quick_test|visual_ai|self_healing|ui_screens_batch)",
        "execution",
    ),
    ("F04", r"(locator|recognizer|replay|mobile_ai|self_test)", "execution"),
    ("F05", r"(decision_application|cost_statistics|timeout|execution_control|execution_mode)", "execution"),
    ("F06", r"^(review|_review|case_quality|_case_quality|quality_rule|visibility)", "review"),
    ("F07", r"^bug", "review"),
    ("F08", r"^(pipeline|_pipeline|iteration)", "pipeline"),
    ("F09", r"^(report|_report)", "pipeline"),
    ("F10", r"^(history_asset|_history_asset)", "case"),
    ("F11", r"^(test_case|_test_case|case_|_case|generation_batch|_generation_batch)", "case"),
    ("F12", r"^(test_data|_test_data)", "case"),
    ("F13", r"(requirement_link|impact_analysis|xmind|ui_spec|ui_prototype|precondition|ab_test|case_number)", "case"),
    ("F14", r"(prompt|ai_invocation|ai_analysis)", "common"),
    ("F15", r"^(auth|user|_user|role|permission|project|_project|file)", "common"),
    ("F16", r"^(oidc|saml|mfa|captcha|kms|session|config|feature_flag|audit)", "common"),
    (
        "F17",
        r"^(test_capability|metrics|lineage|push|scheduler|ops|flow_validation|selector_registry|posterior|task_service)",
        "common",
    ),
    ("F18", r"^(websocket|health|static|admin|access_deps)", "common"),
    ("F19", r"^link_fetcher", "case"),
    ("F20", r"^test_execution_engine", "execution"),
    # 包级 __init__ 无业务语义，统一归公共域（仅兜底根目录未被子包规则命中的 __init__）
    ("F21", r"^__init__\.py$", "common"),
    ("F22", r"^_deps\.py$", "common"),
]


def iter_py(base: Path):
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


def rel_key(path: Path) -> str:
    for base, label in ((SERVICES, "services"), (ENDPOINTS, "endpoints")):
        if base in path.parents:
            return f"{label}/{path.relative_to(base).as_posix()}"
    return path.as_posix()


def dir_domain(key: str):
    for prefix in sorted(DIR_RULES, key=len, reverse=True):
        if key == prefix or key.startswith(prefix + "/"):
            return DIR_RULES[prefix], f"DIR:{prefix.rsplit('/', 1)[-1]}"
    return None


def file_domain(name: str):
    for rule_id, pattern, domain in FILE_RULES:
        if re.search(pattern, name.lower()):
            return domain, rule_id
    return None


def module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def corpus():
    items = []
    for base in (ROOT / "app", ROOT / "tests"):
        for path in base.rglob("*.py"):
            if "__pycache__" not in path.parts:
                items.append((path, read(path)))
    return items


def ref_count(module: str, self_path: Path, items) -> int:
    """统计模块的外部引用：全限定名引用 + `from <父包> import <叶子>` 形态。

    后者用于识别 `from app.api.v1.endpoints import bug as bug_endpoint`
    这类「包级导入」，否则会误判为「无外部引用」。
    """
    if not module:
        return 0
    pkg, _, leaf = module.rpartition(".")
    full = re.compile(re.escape(module) + r"(?![0-9A-Za-z_])")
    grouped = (
        re.compile(r"from\s+" + re.escape(pkg) + r"\s+import\s+[^\n]*?\b" + re.escape(leaf) + r"\b")
        if pkg and leaf
        else None
    )
    total = 0
    for path, text in items:
        if path == self_path:
            continue
        total += len(full.findall(text))
        if grouped is not None:
            total += len(grouped.findall(text))
    return total


def target_path(path: Path, domain: str) -> str:
    """目标路径：`<根>/<域>/<原相对路径>`；若原首段与域名同名则不重复拼接。"""
    if SERVICES in path.parents:
        root, rel = "app/services", path.relative_to(SERVICES)
    else:
        root, rel = "app/api/v1/endpoints", path.relative_to(ENDPOINTS)
    parts = list(rel.parts)
    if len(parts) > 1 and parts[0] == domain:
        parts = parts[1:]
    return f"{root}/{domain}/{'/'.join(parts)}"


def build() -> tuple[str, list[str]]:
    items = corpus()
    rows, unclassified = [], []
    for path in list(iter_py(SERVICES)) + list(iter_py(ENDPOINTS)):
        hit = dir_domain(rel_key(path)) or file_domain(path.name)
        if not hit:
            unclassified.append(path.relative_to(ROOT).as_posix())
            continue
        domain, basis = hit
        refs = ref_count(module_name(path), path, items)
        rows.append(
            {
                "from": path.relative_to(ROOT).as_posix(),
                "to": target_path(path, domain),
                "domain": domain,
                "basis": basis,
                "refs": refs,
                "shim": "是" if refs > 0 else "否",
            }
        )

    counts = {d: sum(1 for r in rows if r["domain"] == d) for d in DOMAINS}
    shim_yes = sum(1 for r in rows if r["shim"] == "是")
    total = len(rows) + len(unclassified)

    out = []
    out.append("# 六域映射表（R4-1 阶段一）")
    out.append("")
    out.append("- **生成时间**：2026-11-10")
    out.append("- **扫描范围**：`app/services/**/*.py` + `app/api/v1/endpoints/**/*.py`")
    out.append(f"- **覆盖**：**{len(rows)} / {total}** 个文件；**未归类 {len(unclassified)}**")
    out.append(
        "- **生成方式**：`venv/Scripts/python.exe scripts/gen_six_domain_mapping.py`（可复现；存在未归类则以退出码 1 结束）"
    )
    out.append(
        "- **shim 判定**：模块全限定名在 `app/`+`tests/` 中被引用（排除自身）→ 保留 re-export shim；否则直接物理移动"
    )
    out.append("")
    out.append("## 一、域分布")
    out.append("")
    out.append("| 域 | 说明 | 文件数 |")
    out.append("| --- | --- | --- |")
    for domain, label in DOMAINS.items():
        out.append(f"| `{domain}` | {label} | {counts[domain]} |")
    out.append(f"| **合计** | — | **{len(rows)}** |")
    out.append("")
    out.append(f"**re-export shim**：需保留 **{shim_yes}** 个，可直接移动 **{len(rows) - shim_yes}** 个。")
    out.append("")
    out.append("## 二、归类规则")
    out.append("")
    out.append("### 2.1 目录级（最长前缀优先）")
    out.append("")
    out.append("| 前缀 | 域 |")
    out.append("| --- | --- |")
    for prefix, domain in sorted(DIR_RULES.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        out.append(f"| `{prefix}` | `{domain}` |")
    out.append("")
    out.append("### 2.2 文件名级（按序匹配，首个命中生效）")
    out.append("")
    out.append("| 规则 | 匹配 | 域 |")
    out.append("| --- | --- | --- |")
    for rule_id, pattern, domain in FILE_RULES:
        out.append(f"| {rule_id} | `{pattern}` | `{domain}` |")
    out.append("")
    out.append("### 2.3 阶段二迁移顺序（按域，每域一个 commit）")
    out.append("")
    out.append(
        "① Agent 域 → ② 用例域 → ③ 测试点域 → ④ 执行域 → ⑤ 评审域 → ⑥ 流水线域；"
        "`common` 域最后一次性移动（被其他域依赖，先动会造成大范围 shim）。"
    )
    out.append("")
    out.append("## 三、`app/services/` 映射（逐文件）")
    out.append("")
    out.append("| # | 现有路径 | 目标路径 | 归属域 | 依据 | 外部引用 | shim |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    idx = 0
    for row in rows:
        if not row["from"].startswith("app/services/"):
            continue
        idx += 1
        out.append(
            f"| {idx} | `{row['from']}` | `{row['to']}` | `{row['domain']}` | {row['basis']} | {row['refs']} | {row['shim']} |"
        )
    out.append("")
    out.append("## 四、`app/api/v1/endpoints/` 映射（逐文件）")
    out.append("")
    out.append("| # | 现有路径 | 目标路径 | 归属域 | 依据 | 外部引用 | shim |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    idx = 0
    for row in rows:
        if not row["from"].startswith("app/api/v1/endpoints/"):
            continue
        idx += 1
        out.append(
            f"| {idx} | `{row['from']}` | `{row['to']}` | `{row['domain']}` | {row['basis']} | {row['refs']} | {row['shim']} |"
        )
    out.append("")
    out.append("## 五、边界判定说明（评审重点）")
    out.append("")
    out.append("| 对象 | 归属 | 理由 |")
    out.append("| --- | --- | --- |")
    out.append(
        "| `services/self_healing`、`services/decision_application_service` | execution | 自愈发生在执行期，决策应用对象是执行结果 |"
    )
    out.append("| `services/cost_statistics` | execution | 统计对象是视觉 AI 调用成本（执行期产生） |")
    out.append("| `services/self_test` | pipeline | 全链路 9 步自测，属流水线编排能力 |")
    out.append("| `services/url_driven` | case | 站点探索 → 自动建项 → 用例生成，主产出是用例 |")
    out.append("| `services/lifecycle_service` | case | 状态机服务对象为用例/任务生命周期 |")
    out.append("| `services/prompt_builder` | common | 同时服务用例生成 / 测试数据 / UI 解析，跨域共享 |")
    out.append(
        "| `services/saml`、`services/role_service`、`services/user_service`、`services/storage` | common | 认证与基础设施，不属于任何业务域 |"
    )
    out.append("| `services/visibility_config`、`endpoints/visibility` | review | 可见范围用于评审可见性控制 |")
    out.append(
        "| `endpoints/iteration`、`endpoints/pipeline_dashboard` | pipeline | 迭代与流水线看板同属交付流程运营 |"
    )
    out.append("| `endpoints/bug` | review | 缺陷由评审/质检环节产生并闭环 |")
    out.append("")
    out.append("## 六、阶段一验收")
    out.append("")
    out.append(f"- [x] 覆盖 **{len(rows)}/{total}**，未归类 **{len(unclassified)}**（判据：零未归类）")
    out.append("- [x] 每行含「现有路径 → 目标路径 → 归属域 → 是否保留 shim」四要素")
    out.append("- [ ] 评审通过后进入阶段二（按域 6 批物理移动 + shim 保留一个迭代）")
    out.append("")
    return "\n".join(out), unclassified


def main() -> int:
    parser = argparse.ArgumentParser(description="R4-1 阶段一：生成六域映射表")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    report, unclassified = build()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"映射表已生成: {out_path}（{len(report.splitlines())} 行）")
    if unclassified:
        print("未归类文件：")
        for item in unclassified:
            print(f"  - {item}")
        return 1
    print("未归类 0 个（判据满足）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
