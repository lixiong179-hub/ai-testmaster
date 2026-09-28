"""集中注册所有 API v1 端点路由。

将原本散落在 main.py 中的 40 处 app.include_router 调用收敛到此处，
main.py 只需调用 register_all_routers(app) 一次即可完成全部路由注册。

每个路由的 prefix 与原 main.py 中的注册保持完全一致，避免破坏现有 URL 契约。
模块注册顺序与原 main.py 一致，便于排查回归。
"""
from fastapi import FastAPI

from app.api.v1.endpoints import (
    ab_test,
    agents,
    ai_invocation,
    audit_log,
    auth,
    batch_locator,
    bug as bug_endpoint,
    case_migration,
    case_quality,
    case_refresh,
    execution,
    execution_visualization,
    feature_flag,
    file,
    generation_batch,
    history_asset,
    impact_analysis,
    iteration,
    mcp_server,
    pipeline,
    project,
    project_members,
    prompt_template,
    quality_rule,
    quick_test,
    report,
    requirement_link,
    review_inbox,
    self_healing,
    test_capability,
    test_case,
    test_data,
    test_point,
    test_task,
    ui_prototype,
    ui_screens_batch,
    user,
    visual_ai,
    visibility,
    websocket,
)


def register_all_routers(app: FastAPI) -> None:
    """将所有 v1 端点路由注册到 FastAPI 应用上。

    Args:
        app: FastAPI 应用实例。
    """
    # 所有模块均自带 prefix，此处统一添加 /api/v1 前缀
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(project.router, prefix="/api/v1")
    app.include_router(quality_rule.router, prefix="/api/v1/projects")
    app.include_router(test_point.router, prefix="/api/v1")
    app.include_router(file.router, prefix="/api/v1")
    app.include_router(test_task.router, prefix="/api/v1")
    app.include_router(user.router, prefix="/api/v1")
    app.include_router(websocket.router, prefix="/api/v1")
    app.include_router(test_case.router, prefix="/api/v1")
    app.include_router(requirement_link.router, prefix="/api/v1")
    app.include_router(batch_locator.router, prefix="/api/v1")
    app.include_router(test_data.router, prefix="/api/v1")
    app.include_router(execution_visualization.router, prefix="/api/v1")
    app.include_router(case_quality.router, prefix="/api/v1")
    app.include_router(execution.router, prefix="/api/v1")
    app.include_router(visibility.router, prefix="/api/v1")
    app.include_router(report.router, prefix="/api/v1")
    app.include_router(ui_prototype.router, prefix="/api/v1")
    app.include_router(ui_screens_batch.router, prefix="/api/v1")
    app.include_router(iteration.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    app.include_router(review_inbox.router, prefix="/api/v1")
    app.include_router(test_capability.router, prefix="/api/v1")
    app.include_router(audit_log.router, prefix="/api/v1")
    app.include_router(case_migration.router, prefix="/api/v1")
    app.include_router(case_refresh.router, prefix="/api/v1/case-refresh")
    app.include_router(ab_test.router, prefix="/api/v1/ab-test")
    app.include_router(generation_batch.router, prefix="/api/v1/generation-batches")
    app.include_router(history_asset.router, prefix="/api/v1/history-assets")
    app.include_router(feature_flag.router, prefix="/api/v1/feature-flags")
    app.include_router(ai_invocation.router, prefix="/api/v1/ai-invocation")
    app.include_router(prompt_template.router, prefix="/api/v1/prompt-templates")
    app.include_router(bug_endpoint.router, prefix="/api/v1/bugs")
    app.include_router(quick_test.router, prefix="/api/v1/quick-test")
    # 自愈管理：审计查询/回滚(/self-healing/*) + 项目级自愈配置(/projects/{id}/self-healing-config)
    app.include_router(self_healing.router, prefix="/api/v1")
    # Agent 会话与审计管理（路由器自带 prefix=/agents）
    app.include_router(agents.router, prefix="/api/v1")
    # MCP Server 工具与 SSE 端点（路由器自带 prefix=/mcp）
    app.include_router(mcp_server.router, prefix="/api/v1")
    app.include_router(project_members.router, prefix="/api/v1")
    # TIA 智能调度：调度计划生成 + 覆盖率映射管理（路由器自带 prefix=/projects/{id}/impact-analysis）
    app.include_router(impact_analysis.router, prefix="/api/v1")
    # Visual AI 视觉回归：基线管理 + 图像对比 + Diff 审批（Phase 2）
    app.include_router(visual_ai.router, prefix="/api/v1")


__all__ = ["register_all_routers"]
