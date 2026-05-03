"""
AI 生成成本基线采集脚本

采集当前 AI 生成用例的 token 消耗、延迟、成本数据。

使用方式：
    python -m scripts.collect_ai_cost_baseline --sample-size 50
    python -m scripts.collect_ai_cost_baseline

输出：
    docs/baseline/ai_cost_baseline.md

依赖关系：
    - app.db.database : SecondarySessionLocal
"""
import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Optional

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


def _collect_ai_call_log(db: Session, min_sample_size: int) -> Dict[str, Any]:
    total = db.execute(text("SELECT COUNT(*) AS cnt FROM ai_call_log")).mappings().one()["cnt"]
    if total == 0:
        return {"total_calls": 0, "source": "ai_call_log"}

    limit = max(total, min_sample_size)
    logs = db.execute(
        text(
            "SELECT id, model, prompt_tokens, completion_tokens, "
            "cost_usd, latency_ms, status, step_name, created_at "
            "FROM ai_call_log ORDER BY created_at DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings().all()

    success_logs = [l for l in logs if l["status"] == "success"]
    failed_logs = [l for l in logs if l["status"] != "success"]

    calls = len(logs)
    success_count = len(success_logs)

    if success_logs:
        avg_prompt = round(sum(l["prompt_tokens"] for l in success_logs) / success_count, 1)
        avg_completion = round(sum(l["completion_tokens"] for l in success_logs) / success_count, 1)
        avg_latency = round(sum(l["latency_ms"] for l in success_logs) / success_count, 1)
        avg_cost = round(sum(float(l["cost_usd"]) for l in success_logs) / success_count, 6)

        latencies = sorted(l["latency_ms"] for l in success_logs)
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else latencies[-1]
    else:
        avg_prompt = avg_completion = avg_latency = 0.0
        avg_cost = 0.0
        p50 = p95 = 0

    total_cost = round(sum(float(l["cost_usd"]) for l in logs), 6)
    success_rate = round(success_count / calls * 100, 1) if calls > 0 else 0.0
    failure_rate = round(len(failed_logs) / calls * 100, 1) if calls > 0 else 0.0

    model_stats: Dict[str, Dict] = defaultdict(
        lambda: {"calls": 0, "avg_latency_ms": 0, "total_cost_usd": 0.0},
    )
    step_stats: Dict[str, Dict] = defaultdict(
        lambda: {"calls": 0, "avg_latency_ms": 0},
    )
    for l in success_logs:
        m = l["model"]
        model_stats[m]["calls"] += 1
        model_stats[m]["avg_latency_ms"] += l["latency_ms"]
        model_stats[m]["total_cost_usd"] += float(l["cost_usd"])

        sn = l["step_name"] or "unknown"
        step_stats[sn]["calls"] += 1
        step_stats[sn]["avg_latency_ms"] += l["latency_ms"]

    for m, s in model_stats.items():
        s["avg_latency_ms"] = round(s["avg_latency_ms"] / s["calls"], 1)
        s["total_cost_usd"] = round(s["total_cost_usd"], 6)
    for sn, s in step_stats.items():
        s["avg_latency_ms"] = round(s["avg_latency_ms"] / s["calls"], 1)

    return {
        "source": "ai_call_log",
        "total_calls": calls,
        "success_calls": success_count,
        "failed_calls": len(failed_logs),
        "avg_prompt_tokens": avg_prompt,
        "avg_completion_tokens": avg_completion,
        "avg_total_tokens": round(avg_prompt + avg_completion, 1),
        "avg_latency_ms": avg_latency,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "avg_cost_usd": avg_cost,
        "total_cost_usd": total_cost,
        "success_rate_pct": success_rate,
        "failure_rate_pct": failure_rate,
        "by_model": dict(model_stats),
        "by_step": dict(step_stats),
    }


def _collect_api_cost_log(db: Session, min_sample_size: int) -> Dict[str, Any]:
    total = db.execute(text("SELECT COUNT(*) AS cnt FROM api_cost_log")).mappings().one()["cnt"]
    if total == 0:
        return {"total_calls": 0, "source": "api_cost_log"}

    limit = max(total, min_sample_size)
    logs = db.execute(
        text(
            "SELECT id, model, input_tokens, output_tokens, "
            "cost, status, api_type, call_time "
            "FROM api_cost_log ORDER BY call_time DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings().all()

    success_logs = [l for l in logs if l["status"] == "success"]
    failed_logs = [l for l in logs if l["status"] != "success"]

    calls = len(logs)
    success_count = len(success_logs)

    if success_logs:
        avg_input = round(sum(l["input_tokens"] or 0 for l in success_logs) / success_count, 1)
        avg_output = round(sum(l["output_tokens"] or 0 for l in success_logs) / success_count, 1)
        avg_cost_cny = round(sum(float(l["cost"] or 0) for l in success_logs) / success_count, 6)
    else:
        avg_input = avg_output = 0.0
        avg_cost_cny = 0.0

    total_cost_cny = round(sum(float(l["cost"] or 0) for l in logs), 6)
    success_rate = round(success_count / calls * 100, 1) if calls > 0 else 0.0
    failure_rate = round(len(failed_logs) / calls * 100, 1) if calls > 0 else 0.0

    model_stats: Dict[str, Dict] = defaultdict(
        lambda: {"calls": 0, "total_cost_cny": 0.0},
    )
    type_stats: Dict[str, Dict] = defaultdict(lambda: {"calls": 0})
    for l in success_logs:
        m = l["model"]
        model_stats[m]["calls"] += 1
        model_stats[m]["total_cost_cny"] += float(l["cost"] or 0)
        type_stats[l["api_type"]]["calls"] += 1

    for m, s in model_stats.items():
        s["total_cost_cny"] = round(s["total_cost_cny"], 6)

    return {
        "source": "api_cost_log",
        "total_calls": calls,
        "success_calls": success_count,
        "failed_calls": len(failed_logs),
        "avg_input_tokens": avg_input,
        "avg_output_tokens": avg_output,
        "avg_total_tokens": round(avg_input + avg_output, 1),
        "avg_latency_ms": None,
        "avg_cost_cny": avg_cost_cny,
        "total_cost_cny": total_cost_cny,
        "success_rate_pct": success_rate,
        "failure_rate_pct": failure_rate,
        "by_model": dict(model_stats),
        "by_type": dict(type_stats),
    }


def _generate_report(data: Dict[str, Any], output_path: str) -> None:
    lines = []
    lines.append("# AI 生成成本基线报告")
    lines.append("")
    lines.append(f"> 采集时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    primary = data.get("ai_call_log", {})
    secondary = data.get("api_cost_log", {})

    if primary.get("total_calls", 0) > 0:
        lines.append("## 主要数据源：ai_call_log（Pipeline 框架级调用日志）")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        for key, label in [
            ("total_calls", "总调用次数"),
            ("success_calls", "成功次数"),
            ("failed_calls", "失败次数"),
            ("avg_prompt_tokens", "平均输入 Token 数"),
            ("avg_completion_tokens", "平均输出 Token 数"),
            ("avg_total_tokens", "平均总 Token 数"),
            ("avg_latency_ms", "平均延迟（ms）"),
            ("p50_latency_ms", "P50 延迟（ms）"),
            ("p95_latency_ms", "P95 延迟（ms）"),
            ("avg_cost_usd", "平均单次成本（USD）"),
            ("total_cost_usd", "总成本（USD）"),
            ("success_rate_pct", "成功率"),
            ("failure_rate_pct", "失败率"),
        ]:
            lines.append(f"| {label} | {primary.get(key, 'N/A')} |")
        lines.append("")

        if primary.get("by_model"):
            lines.append("### 按模型分布")
            lines.append("")
            lines.append("| 模型 | 调用次数 | 平均延迟（ms） | 总成本（USD） |")
            lines.append("|------|----------|----------------|---------------|")
            for model, stats in sorted(primary["by_model"].items()):
                lines.append(
                    f"| {model} | {stats['calls']} | {stats['avg_latency_ms']} | {stats['total_cost_usd']} |"
                )
            lines.append("")

        if primary.get("by_step"):
            lines.append("### 按 Step 分布")
            lines.append("")
            lines.append("| Step | 调用次数 | 平均延迟（ms） |")
            lines.append("|------|----------|----------------|")
            for step, stats in sorted(primary["by_step"].items()):
                lines.append(f"| {step} | {stats['calls']} | {stats['avg_latency_ms']} |")
            lines.append("")

    if secondary.get("total_calls", 0) > 0:
        lines.append("## 辅助数据源：api_cost_log（旧版成本日志）")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        for key, label in [
            ("total_calls", "总调用次数"),
            ("success_calls", "成功次数"),
            ("failed_calls", "失败次数"),
            ("avg_input_tokens", "平均输入 Token 数"),
            ("avg_output_tokens", "平均输出 Token 数"),
            ("avg_total_tokens", "平均总 Token 数"),
            ("avg_cost_cny", "平均单次成本（CNY）"),
            ("total_cost_cny", "总成本（CNY）"),
            ("success_rate_pct", "成功率"),
            ("failure_rate_pct", "失败率"),
        ]:
            lines.append(f"| {label} | {secondary.get(key, 'N/A')} |")
        lines.append("")

        if secondary.get("by_model"):
            lines.append("### 按模型分布")
            lines.append("")
            lines.append("| 模型 | 调用次数 | 总成本（CNY） |")
            lines.append("|------|----------|---------------|")
            for model, stats in sorted(secondary["by_model"].items()):
                lines.append(f"| {model} | {stats['calls']} | {stats['total_cost_cny']} |")
            lines.append("")

        if secondary.get("by_type"):
            lines.append("### 按 API 类型分布")
            lines.append("")
            lines.append("| API 类型 | 调用次数 |")
            lines.append("|----------|----------|")
            for atype, stats in sorted(secondary["by_type"].items()):
                lines.append(f"| {atype} | {stats['calls']} |")
            lines.append("")

    if primary.get("total_calls", 0) == 0 and secondary.get("total_calls", 0) == 0:
        lines.append("## 无数据")
        lines.append("")
        lines.append("> 当前数据库中未找到任何 AI 调用日志。")
        lines.append("> 请先运行至少一次 Pipeline（场景 1 或 2），再重新执行本脚本。")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 指标说明")
    lines.append("")
    lines.append("| 指标 | 计算方式 | 数据来源 |")
    lines.append("|------|----------|----------|")
    lines.append("| 平均输入 Token | `AVG(prompt_tokens) WHERE status='success'` | ai_call_log |")
    lines.append("| 平均输出 Token | `AVG(completion_tokens) WHERE status='success'` | ai_call_log |")
    lines.append("| 平均延迟 | `AVG(latency_ms) WHERE status='success'` | ai_call_log |")
    lines.append("| P50/P95 延迟 | 成功调用的 latency_ms 百分位数 | ai_call_log |")
    lines.append("| 成功率 | `success / total * 100` | ai_call_log.status |")
    lines.append("| 平均成本 | `AVG(cost_usd) WHERE status='success'` | ai_call_log |")

    content = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("报告已写入: %s", output_path)


def collect_ai_cost_baseline(
    min_sample_size: int = 50,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    from app.db.database import SecondarySessionLocal as SessionLocal

    output_path = output_path or os.path.join(OUTPUT_DIR, "ai_cost_baseline.md")

    with SessionLocal() as db:
        logger.info("正在采集 ai_call_log 数据...")
        primary = _collect_ai_call_log(db, min_sample_size)
        logger.info("ai_call_log: %d 条记录", primary.get("total_calls", 0))

        logger.info("正在采集 api_cost_log 数据...")
        secondary = _collect_api_cost_log(db, min_sample_size)
        logger.info("api_cost_log: %d 条记录", secondary.get("total_calls", 0))

    all_data = {"ai_call_log": primary, "api_cost_log": secondary}
    _generate_report(all_data, output_path)

    return {
        "total_calls": primary.get("total_calls", 0) + secondary.get("total_calls", 0),
        "ai_call_log_count": primary.get("total_calls", 0),
        "api_cost_log_count": secondary.get("total_calls", 0),
        "output": output_path,
    }


def main():
    parser = argparse.ArgumentParser(description="AI 生成成本基线采集")
    parser.add_argument("--sample-size", type=int, default=50, help="最少样本量（默认 50）")
    parser.add_argument("--output", type=str, default=None, help="输出路径")

    args = parser.parse_args()

    summary = collect_ai_cost_baseline(min_sample_size=args.sample_size, output_path=args.output)
    logger.info("采集完成: %s", json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
