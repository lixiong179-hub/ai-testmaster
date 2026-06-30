"""Self-test service subpackage.

业务实现拆分到以下子模块：
    _project_setup: 自测项目创建与需求文档导入
    _defect_bug: 缺陷严重度评估与 Bug 自动创建
    _defect_metrics: 缺陷发现率指标计算
    _pipeline_steps_setup: 流水线步骤 1-4（需求确认/测试点提取/用例生成/评审保存）
    _pipeline_steps_run: 流水线步骤 5-9（任务创建/执行/严重度评估/报告/清理）
    _orchestrator: 全链路编排器

外部导入仍应通过 app.services.self_test_service shim，以保持
@patch("app.services.self_test_service._step_*") 等测试 patch 路径兼容。
"""
