# AI 生成成本基线报告

> 采集时间：2026-05-01 16:24:23

## 无数据

> 当前数据库中未找到任何 AI 调用日志。
> 请先运行至少一次 Pipeline（场景 1 或 2），再重新执行本脚本。

---

## 指标说明

| 指标 | 计算方式 | 数据来源 |
|------|----------|----------|
| 平均输入 Token | `AVG(prompt_tokens) WHERE status='success'` | ai_call_log |
| 平均输出 Token | `AVG(completion_tokens) WHERE status='success'` | ai_call_log |
| 平均延迟 | `AVG(latency_ms) WHERE status='success'` | ai_call_log |
| P50/P95 延迟 | 成功调用的 latency_ms 百分位数 | ai_call_log |
| 成功率 | `success / total * 100` | ai_call_log.status |
| 平均成本 | `AVG(cost_usd) WHERE status='success'` | ai_call_log |
