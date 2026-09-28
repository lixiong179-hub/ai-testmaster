"""自愈体系单元测试包。

覆盖：
    - failure_analyzer: 失败类型分类与策略映射
    - audit_service: 审计写入、回滚、分页查询
    - token_budget: 单次/日预算双控、Redis 降级
    - config_service: 项目级自愈配置 CRUD
    - metrics: Prometheus 指标埋点
"""
