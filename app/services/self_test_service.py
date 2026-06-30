"""Self-test service - thin shim re-exporting from self_test subpackage.

本文件为薄重导出层，业务实现已拆分到 app.services.self_test 子包。
保留此文件以维持向后兼容的导入路径：
    from app.services.self_test_service import run_defect_discovery_self_test

以及测试 patch 路径兼容：
    @patch("app.services.self_test_service._step_*")
    @patch("app.services.self_test_service._notify_pipeline_summary")
    @patch("app.services.self_test_service._get_project_root")

编排器 (_orchestrator.run_defect_discovery_self_test) 通过
``from app.services import self_test_service as _stm`` 引用本 shim，
运行时 ``_stm._step_*`` 从本模块属性查找，使上述 patch 装饰器生效。
"""
from app.services.self_test._project_setup import (
    SELF_TEST_PROJECT_NAME,
    _get_project_root,
    _auto_import_requirement_doc,
    _get_self_test_env_configs,
    get_self_test_project,
    create_self_test_project,
)
from app.services.self_test._defect_bug import (
    _assess_defect_severity,
    _generate_bug_no,
    _auto_create_defect_bug,
    _notify_critical_defect_bug,
)
from app.services.self_test._defect_metrics import (
    calculate_defect_metrics,
    _is_implicit_defect,
    _collect_implicit_evidence,
)
from app.services.self_test._pipeline_steps_setup import (
    _build_step_result,
    _step_requirement_confirmation,
    _step_extract_test_points,
    _step_generate_cases,
    _step_review_and_save,
)
from app.services.self_test._pipeline_steps_run import (
    _step_create_task,
    _step_execute,
    _step_assess_severity,
    _step_generate_report,
    _step_cleanup,
)
from app.services.self_test._orchestrator import (
    run_defect_discovery_self_test,
    _notify_pipeline_summary,
)


__all__ = [
    "SELF_TEST_PROJECT_NAME",
    "_get_self_test_env_configs",
    "_get_project_root",
    "_auto_import_requirement_doc",
    "get_self_test_project",
    "create_self_test_project",
    "_assess_defect_severity",
    "_generate_bug_no",
    "_auto_create_defect_bug",
    "_notify_critical_defect_bug",
    "calculate_defect_metrics",
    "_is_implicit_defect",
    "_collect_implicit_evidence",
    "run_defect_discovery_self_test",
    "_notify_pipeline_summary",
    "_build_step_result",
    "_step_requirement_confirmation",
    "_step_extract_test_points",
    "_step_generate_cases",
    "_step_review_and_save",
    "_step_create_task",
    "_step_execute",
    "_step_assess_severity",
    "_step_generate_report",
    "_step_cleanup",
]
