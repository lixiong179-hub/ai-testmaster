"""
现有用例质量基线采集脚本

采集现有用例的质量基线数据，作为引入 Pipeline 之前的效果度量参照。

使用方式：
    python -m scripts.collect_quality_baseline --project-id 1
    python -m scripts.collect_quality_baseline --all-projects

输出：
    docs/baseline/quality_baseline.md

依赖关系：
    - app.db.database : SecondarySessionLocal
"""
import argparse
import difflib
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "baseline",
)
SIMILARITY_THRESHOLD = 0.85


def _get_col(record: Any, key: str, sentinel: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, sentinel)
    return getattr(record, key, sentinel)


def _collect_project(db: Session, pid: int, pname: str) -> Dict[str, Any]:
    cases = db.execute(
        text(
            "SELECT id, module, title, steps_json, review_status, "
            "create_time, update_time "
            "FROM test_cases "
            "WHERE project_id = :pid AND is_deleted = 0"
        ),
        {"pid": pid},
    ).mappings().all()

    total_cases = len(cases)
    if total_cases == 0:
        return {
            "project_id": pid,
            "project_name": pname,
            "total_cases": 0,
            "modules": [],
        }

    reviewed = sum(1 for c in cases if _get_col(c, "review_status") != "pending")
    approved = sum(1 for c in cases if _get_col(c, "review_status") == "approved")
    review_pass_rate = (approved / reviewed * 100) if reviewed > 0 else None

    exec_row = db.execute(
        text(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed "
            "FROM test_case_executions e "
            "JOIN test_cases tc ON e.test_case_id = tc.id "
            "WHERE tc.project_id = :pid AND tc.is_deleted = 0"
        ),
        {"pid": pid},
    ).mappings().one()
    total_execs = exec_row["total"] or 0
    passed_execs = exec_row["passed"] or 0
    execution_pass_rate = (passed_execs / total_execs * 100) if total_execs > 0 else None

    total_steps = 0
    cases_with_steps = 0
    for c in cases:
        steps = _get_col(c, "steps_json")
        if steps is not None:
            try:
                if isinstance(steps, str):
                    steps = json.loads(steps)
                if isinstance(steps, list):
                    total_steps += len(steps)
                    cases_with_steps += 1
            except (json.JSONDecodeError, TypeError):
                case_id = _get_col(c, "id", "?")
                logger.warning("用例 %s 的 steps_json 解析失败，已跳过", case_id)
    avg_steps = round(total_steps / cases_with_steps, 2) if cases_with_steps > 0 else 0.0

    modified = sum(
        1 for c in cases
        if _get_col(c, "update_time") is not None
        and _get_col(c, "create_time") is not None
        and _get_col(c, "update_time") > _get_col(c, "create_time")
    )
    modification_rate = (modified / total_cases * 100) if total_cases > 0 else 0.0

    similar_pairs = _compute_similarity(cases)

    code_reviews = _fetch_code_review_count(db, pid)

    module_groups = defaultdict(int)
    for c in cases:
        module_groups[_get_col(c, "module") or "未分类"] += 1

    modules = [
        {"module": m, "count": cnt}
        for m, cnt in sorted(module_groups.items(), key=lambda x: -x[1])
    ]

    return {
        "project_id": pid,
        "project_name": pname,
        "total_cases": total_cases,
        "reviewed_cases": reviewed,
        "approved_cases": approved,
        "review_pass_rate_pct": round(review_pass_rate, 1) if review_pass_rate is not None else None,
        "total_executions": total_execs,
        "passed_executions": passed_execs,
        "execution_pass_rate_pct": round(execution_pass_rate, 1) if execution_pass_rate is not None else None,
        "avg_steps_per_case": avg_steps,
        "modified_cases": modified,
        "modification_rate_pct": round(modification_rate, 1),
        "similar_pair_count": len(similar_pairs),
        "similar_case_ratio_pct": round(len(similar_pairs) / total_cases * 100, 1) if total_cases > 0 else 0.0,
        "code_review_count": code_reviews,
        "modules": modules,
    }


def _fetch_code_review_count(db, pid: int) -> int:
    try:
        row = db.execute(
            text("SELECT COUNT(*) AS cnt FROM code_reviews WHERE project_id = :pid"),
            {"pid": pid},
        ).mappings().one()
        return row["cnt"]
    except Exception:
        logger.warning("查询 code_reviews 表失败，返回 0（可能表不存在）")
        return 0


def _compute_similarity(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    titles = [
        (_get_col(c, "id"), _get_col(c, "title") or "")
        for c in cases
    ]
    pairs = []
    n = len(titles)
    for i in range(n):
        for j in range(i + 1, n):
            ratio = difflib.SequenceMatcher(None, titles[i][1], titles[j][1]).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                pairs.append({
                    "case_a": titles[i][0],
                    "case_b": titles[j][0],
                    "similarity": round(ratio, 4),
                })
    return pairs


def _generate_report(all_stats: List[Dict[str, Any]], output_path: str) -> None:
    lines = []
    lines.append("# 现有用例质量基线报告")
    lines.append("")
    lines.append(f"> 采集时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 相似度阈值：{SIMILARITY_THRESHOLD}（基于标题文本的 SequenceMatcher 相似度）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|----|")

    total_all = sum(s["total_cases"] for s in all_stats)
    total_approved = sum(s["approved_cases"] for s in all_stats)
    total_reviewed = sum(s["reviewed_cases"] for s in all_stats)
    total_execs = sum(s["total_executions"] for s in all_stats)
    total_passed = sum(s["passed_executions"] for s in all_stats)
    total_modified = sum(s["modified_cases"] for s in all_stats)
    total_similar = sum(s["similar_pair_count"] for s in all_stats)

    review_rate = (total_approved / total_reviewed * 100) if total_reviewed > 0 else None
    exec_rate = (total_passed / total_execs * 100) if total_execs > 0 else None
    mod_rate = (total_modified / total_all * 100) if total_all > 0 else 0.0
    sim_ratio = (total_similar / total_all * 100) if total_all > 0 else 0.0

    weighted_steps = (
        sum(s["avg_steps_per_case"] * s["total_cases"] for s in all_stats) / total_all
    ) if total_all > 0 else 0.0

    lines.append(f"| 项目数 | {len(all_stats)} |")
    lines.append(f"| 用例总数 | {total_all} |")
    if review_rate is not None:
        lines.append(f"| 人工评审通过率 | {review_rate:.1f}% |")
    else:
        lines.append("| 人工评审通过率 | N/A（无评审记录） |")
    if exec_rate is not None:
        lines.append(f"| 执行通过率 | {exec_rate:.1f}% |")
    else:
        lines.append("| 执行通过率 | N/A（无执行记录） |")
    lines.append(f"| 平均步骤数 | {weighted_steps:.2f} |")
    lines.append(f"| 用例修改率 | {mod_rate:.1f}% |")
    lines.append(f"| 相似用例比率 | {sim_ratio:.1f}% |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 按项目明细")
    lines.append("")

    for s in all_stats:
        lines.append(f"### {s['project_name']}（ID={s['project_id']}）")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        lines.append(f"| 用例总数 | {s['total_cases']} |")
        rpr = f"{s['review_pass_rate_pct']:.1f}%" if s['review_pass_rate_pct'] is not None else "N/A"
        lines.append(f"| 人工评审通过率 | {rpr}（已评审{s['reviewed_cases']}/{s['total_cases']}） |")
        epr = f"{s['execution_pass_rate_pct']:.1f}%" if s['execution_pass_rate_pct'] is not None else "N/A"
        lines.append(f"| 执行通过率 | {epr}（已执行{s['total_executions']}次） |")
        lines.append(f"| 平均步骤数 | {s['avg_steps_per_case']} |")
        lines.append(f"| 用例修改率 | {s['modification_rate_pct']:.1f}% |")
        lines.append(f"| 相似用例对数 | {s['similar_pair_count']}（占{s['similar_case_ratio_pct']}%） |")
        lines.append(f"| CodeReview 记录数 | {s.get('code_review_count', 0)} |")
        lines.append("")
        lines.append("**模块分布**：")
        modules_str = "、".join(f"{m['module']}({m['count']})" for m in s["modules"][:10])
        if len(s["modules"]) > 10:
            modules_str += f" ... 共{len(s['modules'])}个模块"
        lines.append(f"> {modules_str}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 指标说明")
    lines.append("")
    lines.append("| 指标 | 计算方式 | 数据来源 |")
    lines.append("|------|----------|----------|")
    lines.append("| 用例总数 | `COUNT(*) WHERE project_id = ? AND is_deleted = 0` | test_cases |")
    lines.append("| 人工评审通过率 | `approved / (approved + rejected + needs_optimization) * 100` | test_cases.review_status |")
    lines.append("| 执行通过率 | `passed / total * 100` | test_case_executions.status |")
    lines.append("| 平均步骤数 | `AVG(LEN(steps_json))` | test_cases.steps_json |")
    lines.append("| 用例修改率 | `(update_time > create_time) / total * 100` | test_cases |")
    lines.append("| 相似用例比率 | 标题 SequenceMatcher >= 0.85 / total * 100 | test_cases.title |")

    content = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("报告已写入: %s", output_path)


def collect_quality_baseline(
    project_id: Optional[int] = None,
    all_projects: bool = False,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    from app.db.database import SecondarySessionLocal as SessionLocal

    output_path = output_path or os.path.join(OUTPUT_DIR, "quality_baseline.md")

    with SessionLocal() as db:
        if all_projects:
            project_rows = db.execute(
                text("SELECT id, name FROM projects WHERE status = 1")
            ).mappings().all()
        elif project_id is not None:
            project_rows = db.execute(
                text("SELECT id, name FROM projects WHERE id = :pid AND status = 1"),
                {"pid": project_id},
            ).mappings().all()
        else:
            project_rows = db.execute(
                text("SELECT id, name FROM projects WHERE status = 1 LIMIT 1")
            ).mappings().all()

        if not project_rows:
            logger.error("未找到活跃项目，请先创建项目")
            sys.exit(1)

        logger.info("找到 %d 个项目", len(project_rows))
        all_stats = []

        for row in project_rows:
            pid, pname = row["id"], row["name"]
            logger.info("正在采集项目: %s (ID=%d)", pname, pid)
            stats = _collect_project(db, pid, pname)
            all_stats.append(stats)

    _generate_report(all_stats, output_path)

    summary = {
        "projects_collected": len(all_stats),
        "total_cases": sum(s["total_cases"] for s in all_stats),
        "output": output_path,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="现有用例质量基线采集")
    parser.add_argument("--project-id", type=int, default=None, help="指定项目 ID")
    parser.add_argument("--all-projects", action="store_true", default=True, help="采集所有活跃项目")
    parser.add_argument("--output", type=str, default=None, help="输出路径")

    args = parser.parse_args()

    summary = collect_quality_baseline(
        project_id=args.project_id,
        all_projects=args.all_projects,
        output_path=args.output,
    )
    logger.info("采集完成: %s", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
