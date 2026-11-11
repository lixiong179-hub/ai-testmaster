"""API 延迟基线压测脚本（R5-1 阶段一）。

用途：为「执行进程隔离」改造提供可复现的延迟基线。默认打轻量存活探针
`/live`（不查 DB/Redis），采集 P50/P95/P99，并把结果以 markdown 行追加到
基线报告，供阶段三复测对比（验收阈值：P95 ≤ 基线 × 1.2）。

示例：
    # 空闲基线
    python scripts/bench_api_latency.py --base-url http://127.0.0.1:8000 --label idle

    # 长任务同期执行（用 /health 的 DB+Redis 访问造 IO 竞争）
    python scripts/bench_api_latency.py --base-url http://127.0.0.1:8000 \
        --label busy --noise-path /health --noise-concurrency 10

    # 阶段三复测（同一脚本、同一参数）
    python scripts/bench_api_latency.py --label post-isolation \
        --report docs/baseline/execution_isolation_baseline.md

退出码：0 = 全部请求成功（或允许错误）；1 = 存在失败请求且未加 `--allow-errors`。
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import httpx

_DEFAULT_REPORT = "docs/baseline/execution_isolation_baseline.md"


def _percentile(sorted_values: list[float], percentile: float) -> float:
    """线性插值计算百分位（p ∈ [0, 100]）。

    Args:
        sorted_values: 已升序排序的样本。
        percentile: 目标百分位。

    Returns:
        float: 对应百分位延迟（毫秒）；样本为空时返回 0.0。
    """
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (percentile / 100) * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * weight


async def _request_once(
    client: httpx.AsyncClient, url: str
) -> tuple[float, int | None]:
    """发起单次请求，返回 (毫秒, 状态码)；异常时状态码为 None。"""
    started = time.perf_counter()
    try:
        response = await client.get(url)
        status_code = response.status_code
    except Exception:
        status_code = None
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms, status_code


async def _load(
    client: httpx.AsyncClient,
    url: str,
    *,
    requests: int,
    concurrency: int,
) -> list[tuple[float, int | None]]:
    """按并发上限施压，返回全部 (毫秒, 状态码)。"""
    semaphore = asyncio.Semaphore(max(concurrency, 1))

    async def _worker() -> tuple[float, int | None]:
        async with semaphore:
            return await _request_once(client, url)

    return await asyncio.gather(*[_worker() for _ in range(requests)])


def _summarize(label: str, samples: Iterable[tuple[float, int | None]]) -> dict[str, Any]:
    """汇总延迟统计。"""
    rows = list(samples)
    latencies = sorted(row[0] for row in rows)
    errors = sum(1 for row in rows if row[1] != 200)
    total_seconds = sum(latencies) / 1000 if latencies else 0.0
    return {
        "label": label,
        "samples": len(rows),
        "errors": errors,
        "min_ms": round(latencies[0], 2) if latencies else 0.0,
        "p50_ms": round(_percentile(latencies, 50), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "p99_ms": round(_percentile(latencies, 99), 2),
        "max_ms": round(latencies[-1], 2) if latencies else 0.0,
        "mean_ms": round(statistics.fmean(latencies), 2) if latencies else 0.0,
        "throughput_rps": round(len(rows) / total_seconds, 2) if total_seconds else 0.0,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _format_row(summary: dict[str, Any], args: argparse.Namespace) -> str:
    """格式化为 markdown 表格行。"""
    noise = (
        f"{args.noise_path}×{args.noise_concurrency}"
        if args.noise_path
        else "—"
    )
    return (
        f"| {summary['label']} | {summary['collected_at']} | {args.path} | "
        f"{summary['samples']} | {args.concurrency} | {noise} | "
        f"{summary['p50_ms']} | {summary['p95_ms']} | {summary['p99_ms']} | "
        f"{summary['mean_ms']} | {summary['throughput_rps']} | {summary['errors']} |"
    )


def _write_report(report_path: Path, summary: dict[str, Any], args: argparse.Namespace) -> None:
    """把本次结果追加到 markdown 基线报告（表头不存在时先写入）。"""
    header = (
        "# 执行进程隔离 · API 延迟基线（R5-1 阶段一）\n\n"
        "> 采集工具：`scripts/bench_api_latency.py`（httpx 并发，线性插值百分位）。\n"
        "> 口径：`p95 ≤ 基线 × 1.2` 为阶段三验收阈值；`busy` 组用 `--noise-path` 造\n"
        "> 同期 DB/Redis 访问竞争（合成负载），真实长任务复采命令见文末。\n\n"
        "| 组 | 采集时间 | 探针 | 样本 | 并发 | 噪声负载 | P50(ms) | P95(ms) | P99(ms) | 均值(ms) | RPS | 错误 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not report_path.exists():
        report_path.write_text(header, encoding="utf-8")

    with report_path.open("a", encoding="utf-8") as fp:
        fp.write(_format_row(summary, args) + "\n")


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    """执行一轮压测。"""
    base = args.base_url.rstrip("/")
    target_url = f"{base}{args.path}"
    timeout = httpx.Timeout(args.timeout)
    limits = httpx.Limits(max_connections=max(args.concurrency * 2, 10))

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        if args.warmup > 0:
            await _load(
                client, target_url, requests=args.warmup, concurrency=args.concurrency
            )

        noise_task: asyncio.Task | None = None
        if args.noise_path:
            noise_url = f"{base}{args.noise_path}"
            noise_task = asyncio.create_task(
                _load(
                    client,
                    noise_url,
                    requests=max(args.requests * 2, 50),
                    concurrency=args.noise_concurrency,
                )
            )

        started = time.perf_counter()
        samples = await _load(
            client,
            target_url,
            requests=args.requests,
            concurrency=args.concurrency,
        )
        wall_ms = (time.perf_counter() - started) * 1000

        if noise_task is not None:
            try:
                await noise_task
            except Exception:  # 噪声负载失败不影响主测量
                pass

    summary = _summarize(args.label, samples)
    summary["wall_ms"] = round(wall_ms, 2)
    summary["base_url"] = base
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API 延迟基线压测（R5-1）")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/live", help="被测轻量端点")
    parser.add_argument("--requests", type=int, default=200, help="采样请求数")
    parser.add_argument("--concurrency", type=int, default=20, help="并发上限")
    parser.add_argument("--warmup", type=int, default=20, help="预热请求数（不计入统计）")
    parser.add_argument("--timeout", type=float, default=10.0, help="单请求超时（秒）")
    parser.add_argument("--label", default="idle", help="组标签（idle/busy/post-isolation）")
    parser.add_argument(
        "--noise-path",
        default=None,
        help="同期噪声负载探针（如 /health）；设置后本组标记为竞争条件",
    )
    parser.add_argument("--noise-concurrency", type=int, default=10)
    parser.add_argument("--report", default=None, help=f"markdown 报告路径（默认 {_DEFAULT_REPORT}）")
    parser.add_argument("--no-report", action="store_true", help="只打印，不写报告")
    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="存在失败请求时仍返回退出码 0",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = asyncio.run(_run(args))

    print(
        f"[{summary['label']}] samples={summary['samples']} "
        f"p50={summary['p50_ms']}ms p95={summary['p95_ms']}ms "
        f"p99={summary['p99_ms']}ms errors={summary['errors']} "
        f"rps={summary['throughput_rps']}"
    )

    if not args.no_report:
        report_path = Path(args.report or _DEFAULT_REPORT)
        _write_report(report_path, summary, args)
        print(f"报告已追加: {report_path}")

    if summary["errors"] > 0 and not args.allow_errors:
        print(
            f"[FAIL] 存在 {summary['errors']} 个失败请求（非 200 或连接异常）",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
