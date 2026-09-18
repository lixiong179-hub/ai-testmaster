"""app.tasks 包初始化。

本包当前仅保留「自测（缺陷发现）定时调度」能力：

    - self_test_scheduler: APScheduler 驱动的自测计划调度（被
      app/api/v1/endpoints/project_core.py 与 tests/services/ 多个测试引用）
    - _self_test_executor_mixin: 自测执行期辅助方法（缺陷通知等）

原「分布式测试执行引擎」的 Celery 基础设施（celery_app / base / worker /
scheduler / _async_bridge / test_execution）已于 2026-09-18 冻结，
代码移至 app/tasks/_frozen/，冻结原因与恢复方法见该目录的 README.md。

注意：冻结前本模块会导出 get_celery_app / create_celery_app / BaseTask /
task_state_callback / async_task。这些导出现已移除；如需恢复，请先按
app/tasks/_frozen/README.md 的说明还原文件与依赖。
"""
