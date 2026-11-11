# 六域映射表（R4-1 阶段一）

- **生成时间**：2026-11-10
- **扫描范围**：`app/services/**/*.py` + `app/api/v1/endpoints/**/*.py`
- **覆盖**：**553 / 553** 个文件；**未归类 0**
- **生成方式**：`venv/Scripts/python.exe scripts/gen_six_domain_mapping.py`（可复现；存在未归类则以退出码 1 结束）
- **shim 判定**：模块全限定名在 `app/`+`tests/` 中被引用（排除自身）→ 保留 re-export shim；否则直接物理移动

## 一、域分布

| 域 | 说明 | 文件数 |
| --- | --- | --- |
| `case` | 用例域 | 211 |
| `test_point` | 测试点域 | 8 |
| `execution` | 执行域 | 133 |
| `review` | 评审域 | 28 |
| `pipeline` | 流水线域 | 36 |
| `agent` | Agent 域 | 40 |
| `common` | 公共域（跨域基础设施，非业务能力） | 97 |
| **合计** | — | **553** |

**re-export shim**：需保留 **537** 个，可直接移动 **16** 个。

## 二、归类规则

### 2.1 目录级（最长前缀优先）

| 前缀 | 域 |
| --- | --- |
| `services/decision_application_service` | `execution` |
| `services/test_data_parameterizer` | `case` |
| `endpoints/test_case_ai_generate` | `case` |
| `services/test_execution_engine` | `execution` |
| `services/test_case_generation` | `case` |
| `endpoints/pipeline_dashboard` | `pipeline` |
| `services/ai_analysis_service` | `case` |
| `services/mobile_ai_executor` | `execution` |
| `services/lifecycle_service` | `case` |
| `services/visibility_config` | `review` |
| `services/xmind_case_parser` | `case` |
| `services/execution_replay` | `execution` |
| `services/pipeline_service` | `pipeline` |
| `endpoints/execution_core` | `execution` |
| `services/cost_statistics` | `execution` |
| `services/element_locator` | `execution` |
| `services/impact_analysis` | `case` |
| `services/xmind_ai_parser` | `case` |
| `services/case_migration` | `case` |
| `services/file_extractor` | `case` |
| `services/prompt_builder` | `common` |
| `services/review_service` | `review` |
| `services/test_case_view` | `case` |
| `services/ui_spec_parser` | `case` |
| `endpoints/review_inbox` | `review` |
| `endpoints/ui_prototype` | `case` |
| `services/batch_locator` | `execution` |
| `services/case_quality` | `case` |
| `services/link_fetcher` | `case` |
| `services/precondition` | `case` |
| `services/role_service` | `common` |
| `services/self_healing` | `execution` |
| `services/task_service` | `execution` |
| `services/user_service` | `common` |
| `services/xmind_parser` | `case` |
| `endpoints/test_point` | `test_point` |
| `services/recognizers` | `execution` |
| `endpoints/iteration` | `pipeline` |
| `services/url_driven` | `case` |
| `services/self_test` | `pipeline` |
| `services/test_data` | `case` |
| `services/visual_ai` | `execution` |
| `services/quality` | `case` |
| `services/storage` | `common` |
| `services/common` | `common` |
| `services/agent` | `agent` |
| `services/video` | `execution` |
| `services/saml` | `common` |

### 2.2 文件名级（按序匹配，首个命中生效）

| 规则 | 匹配 | 域 |
| --- | --- | --- |
| F01 | `^(agent|agents|mcp_server|mcp_)` | `agent` |
| F02 | `(test_point)` | `test_point` |
| F03 | `^(test_task|batch_locator|execution|execution_|_execution|quick_test|visual_ai|self_healing|ui_screens_batch)` | `execution` |
| F04 | `(locator|recognizer|replay|mobile_ai|self_test)` | `execution` |
| F05 | `(decision_application|cost_statistics|timeout|execution_control|execution_mode)` | `execution` |
| F06 | `^(review|_review|case_quality|_case_quality|quality_rule|visibility)` | `review` |
| F07 | `^bug` | `review` |
| F08 | `^(pipeline|_pipeline|iteration)` | `pipeline` |
| F09 | `^(report|_report)` | `pipeline` |
| F10 | `^(history_asset|_history_asset)` | `case` |
| F11 | `^(test_case|_test_case|case_|_case|generation_batch|_generation_batch)` | `case` |
| F12 | `^(test_data|_test_data)` | `case` |
| F13 | `(requirement_link|impact_analysis|xmind|ui_spec|ui_prototype|precondition|ab_test|case_number)` | `case` |
| F14 | `(prompt|ai_invocation|ai_analysis)` | `common` |
| F15 | `^(auth|user|_user|role|permission|project|_project|file)` | `common` |
| F16 | `^(oidc|saml|mfa|captcha|kms|session|config|feature_flag|audit)` | `common` |
| F17 | `^(test_capability|metrics|lineage|push|scheduler|ops|flow_validation|selector_registry|posterior|task_service)` | `common` |
| F18 | `^(websocket|health|static|admin|access_deps)` | `common` |
| F19 | `^link_fetcher` | `case` |
| F20 | `^test_execution_engine` | `execution` |
| F21 | `^__init__\.py$` | `common` |
| F22 | `^_deps\.py$` | `common` |

### 2.3 阶段二迁移顺序（按域，每域一个 commit）

① Agent 域 → ② 用例域 → ③ 测试点域 → ④ 执行域 → ⑤ 评审域 → ⑥ 流水线域；`common` 域最后一次性移动（被其他域依赖，先动会造成大范围 shim）。

## 三、`app/services/` 映射（逐文件）

| # | 现有路径 | 目标路径 | 归属域 | 依据 | 外部引用 | shim |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `app/services/_case_refresh_apply.py` | `app/services/case/_case_refresh_apply.py` | `case` | F11 | 1 | 是 |
| 2 | `app/services/_case_refresh_prompts.py` | `app/services/case/_case_refresh_prompts.py` | `case` | F11 | 0 | 否 |
| 3 | `app/services/_case_version_archive.py` | `app/services/case/_case_version_archive.py` | `case` | F11 | 1 | 是 |
| 4 | `app/services/_case_version_query.py` | `app/services/case/_case_version_query.py` | `case` | F11 | 1 | 是 |
| 5 | `app/services/_prompt_registry_async.py` | `app/services/common/_prompt_registry_async.py` | `common` | F14 | 1 | 是 |
| 6 | `app/services/_prompt_registry_helpers.py` | `app/services/common/_prompt_registry_helpers.py` | `common` | F14 | 3 | 是 |
| 7 | `app/services/_prompt_registry_sync.py` | `app/services/common/_prompt_registry_sync.py` | `common` | F14 | 1 | 是 |
| 8 | `app/services/_report_defect_builder.py` | `app/services/pipeline/_report_defect_builder.py` | `pipeline` | F09 | 2 | 是 |
| 9 | `app/services/ab_test_service.py` | `app/services/case/ab_test_service.py` | `case` | F13 | 4 | 是 |
| 10 | `app/services/agent/__init__.py` | `app/services/agent/__init__.py` | `agent` | DIR:agent | 152 | 是 |
| 11 | `app/services/agent/_registrations.py` | `app/services/agent/_registrations.py` | `agent` | DIR:agent | 2 | 是 |
| 12 | `app/services/agent/_rollback_handlers.py` | `app/services/agent/_rollback_handlers.py` | `agent` | DIR:agent | 2 | 是 |
| 13 | `app/services/agent/_tool_executor.py` | `app/services/agent/_tool_executor.py` | `agent` | DIR:agent | 1 | 是 |
| 14 | `app/services/agent/agents/__init__.py` | `app/services/agent/agents/__init__.py` | `agent` | DIR:agent | 13 | 是 |
| 15 | `app/services/agent/agents/_test_case_tools.py` | `app/services/agent/agents/_test_case_tools.py` | `agent` | DIR:agent | 5 | 是 |
| 16 | `app/services/agent/agents/failure_analysis_agent.py` | `app/services/agent/agents/failure_analysis_agent.py` | `agent` | DIR:agent | 2 | 是 |
| 17 | `app/services/agent/agents/locator_healing_agent.py` | `app/services/agent/agents/locator_healing_agent.py` | `agent` | DIR:agent | 2 | 是 |
| 18 | `app/services/agent/agents/test_execution_agent.py` | `app/services/agent/agents/test_execution_agent.py` | `agent` | DIR:agent | 2 | 是 |
| 19 | `app/services/agent/agents/test_generation_agent.py` | `app/services/agent/agents/test_generation_agent.py` | `agent` | DIR:agent | 3 | 是 |
| 20 | `app/services/agent/agents/visual_validation_agent.py` | `app/services/agent/agents/visual_validation_agent.py` | `agent` | DIR:agent | 3 | 是 |
| 21 | `app/services/agent/artifact_registry.py` | `app/services/agent/artifact_registry.py` | `agent` | DIR:agent | 3 | 是 |
| 22 | `app/services/agent/artifacts/__init__.py` | `app/services/agent/artifacts/__init__.py` | `agent` | DIR:agent | 27 | 是 |
| 23 | `app/services/agent/artifacts/application_state_artifact.py` | `app/services/agent/artifacts/application_state_artifact.py` | `agent` | DIR:agent | 1 | 是 |
| 24 | `app/services/agent/artifacts/base.py` | `app/services/agent/artifacts/base.py` | `agent` | DIR:agent | 19 | 是 |
| 25 | `app/services/agent/artifacts/execution_state_artifact.py` | `app/services/agent/artifacts/execution_state_artifact.py` | `agent` | DIR:agent | 1 | 是 |
| 26 | `app/services/agent/artifacts/failure_history_artifact.py` | `app/services/agent/artifacts/failure_history_artifact.py` | `agent` | DIR:agent | 1 | 是 |
| 27 | `app/services/agent/artifacts/project_context_artifact.py` | `app/services/agent/artifacts/project_context_artifact.py` | `agent` | DIR:agent | 3 | 是 |
| 28 | `app/services/agent/artifacts/test_case_artifact.py` | `app/services/agent/artifacts/test_case_artifact.py` | `agent` | DIR:agent | 1 | 是 |
| 29 | `app/services/agent/artifacts/user_intent_artifact.py` | `app/services/agent/artifacts/user_intent_artifact.py` | `agent` | DIR:agent | 3 | 是 |
| 30 | `app/services/agent/audit_service.py` | `app/services/agent/audit_service.py` | `agent` | DIR:agent | 5 | 是 |
| 31 | `app/services/agent/base.py` | `app/services/agent/base.py` | `agent` | DIR:agent | 11 | 是 |
| 32 | `app/services/agent/circuit_breaker.py` | `app/services/agent/circuit_breaker.py` | `agent` | DIR:agent | 7 | 是 |
| 33 | `app/services/agent/exceptions.py` | `app/services/agent/exceptions.py` | `agent` | DIR:agent | 15 | 是 |
| 34 | `app/services/agent/loop_detector.py` | `app/services/agent/loop_detector.py` | `agent` | DIR:agent | 2 | 是 |
| 35 | `app/services/agent/mcp_server.py` | `app/services/agent/mcp_server.py` | `agent` | DIR:agent | 3 | 是 |
| 36 | `app/services/agent/metrics.py` | `app/services/agent/metrics.py` | `agent` | DIR:agent | 5 | 是 |
| 37 | `app/services/agent/orchestrator.py` | `app/services/agent/orchestrator.py` | `agent` | DIR:agent | 3 | 是 |
| 38 | `app/services/agent/registry.py` | `app/services/agent/registry.py` | `agent` | DIR:agent | 7 | 是 |
| 39 | `app/services/agent/runtime.py` | `app/services/agent/runtime.py` | `agent` | DIR:agent | 12 | 是 |
| 40 | `app/services/agent/session_service.py` | `app/services/agent/session_service.py` | `agent` | DIR:agent | 7 | 是 |
| 41 | `app/services/agent/token_budget.py` | `app/services/agent/token_budget.py` | `agent` | DIR:agent | 2 | 是 |
| 42 | `app/services/agent/tools/__init__.py` | `app/services/agent/tools/__init__.py` | `agent` | DIR:agent | 20 | 是 |
| 43 | `app/services/agent/tools/base_tool.py` | `app/services/agent/tools/base_tool.py` | `agent` | DIR:agent | 13 | 是 |
| 44 | `app/services/agent/tools/client_tools.py` | `app/services/agent/tools/client_tools.py` | `agent` | DIR:agent | 2 | 是 |
| 45 | `app/services/agent/tools/external_tools.py` | `app/services/agent/tools/external_tools.py` | `agent` | DIR:agent | 1 | 是 |
| 46 | `app/services/agent/tools/registry.py` | `app/services/agent/tools/registry.py` | `agent` | DIR:agent | 4 | 是 |
| 47 | `app/services/agent/tools/server_tools.py` | `app/services/agent/tools/server_tools.py` | `agent` | DIR:agent | 3 | 是 |
| 48 | `app/services/ai_analysis_service/__init__.py` | `app/services/case/ai_analysis_service/__init__.py` | `case` | DIR:ai_analysis_service | 8 | 是 |
| 49 | `app/services/ai_analysis_service/_extract.py` | `app/services/case/ai_analysis_service/_extract.py` | `case` | DIR:ai_analysis_service | 3 | 是 |
| 50 | `app/services/ai_analysis_service/_service.py` | `app/services/case/ai_analysis_service/_service.py` | `case` | DIR:ai_analysis_service | 3 | 是 |
| 51 | `app/services/ai_analysis_utils.py` | `app/services/common/ai_analysis_utils.py` | `common` | F14 | 1 | 是 |
| 52 | `app/services/audit_chain_service.py` | `app/services/common/audit_chain_service.py` | `common` | F16 | 2 | 是 |
| 53 | `app/services/audit_service.py` | `app/services/common/audit_service.py` | `common` | F16 | 18 | 是 |
| 54 | `app/services/batch_locator/__init__.py` | `app/services/execution/batch_locator/__init__.py` | `execution` | DIR:batch_locator | 5 | 是 |
| 55 | `app/services/batch_locator/batch_executor_mixin.py` | `app/services/execution/batch_locator/batch_executor_mixin.py` | `execution` | DIR:batch_locator | 2 | 是 |
| 56 | `app/services/batch_locator/models.py` | `app/services/execution/batch_locator/models.py` | `execution` | DIR:batch_locator | 2 | 是 |
| 57 | `app/services/batch_locator/task_manager.py` | `app/services/execution/batch_locator/task_manager.py` | `execution` | DIR:batch_locator | 2 | 是 |
| 58 | `app/services/batch_locator_service.py` | `app/services/execution/batch_locator_service.py` | `execution` | F03 | 4 | 是 |
| 59 | `app/services/captcha_service.py` | `app/services/common/captcha_service.py` | `common` | F16 | 6 | 是 |
| 60 | `app/services/case_generation_prompt_builder.py` | `app/services/case/case_generation_prompt_builder.py` | `case` | F11 | 0 | 否 |
| 61 | `app/services/case_migration/__init__.py` | `app/services/case/case_migration/__init__.py` | `case` | DIR:case_migration | 10 | 是 |
| 62 | `app/services/case_migration/_ai_mixin.py` | `app/services/case/case_migration/_ai_mixin.py` | `case` | DIR:case_migration | 5 | 是 |
| 63 | `app/services/case_migration/_persistence_mixin.py` | `app/services/case/case_migration/_persistence_mixin.py` | `case` | DIR:case_migration | 1 | 是 |
| 64 | `app/services/case_migration/_preview_payload_mixin.py` | `app/services/case/case_migration/_preview_payload_mixin.py` | `case` | DIR:case_migration | 1 | 是 |
| 65 | `app/services/case_migration/migration_service.py` | `app/services/case/case_migration/migration_service.py` | `case` | DIR:case_migration | 1 | 是 |
| 66 | `app/services/case_number_service.py` | `app/services/case/case_number_service.py` | `case` | F11 | 10 | 是 |
| 67 | `app/services/case_quality/__init__.py` | `app/services/case/case_quality/__init__.py` | `case` | DIR:case_quality | 64 | 是 |
| 68 | `app/services/case_quality/analyzer_mixin/__init__.py` | `app/services/case/case_quality/analyzer_mixin/__init__.py` | `case` | DIR:case_quality | 3 | 是 |
| 69 | `app/services/case_quality/analyzer_mixin/_case_analyzer.py` | `app/services/case/case_quality/analyzer_mixin/_case_analyzer.py` | `case` | DIR:case_quality | 1 | 是 |
| 70 | `app/services/case_quality/analyzer_mixin/_project_analyzer.py` | `app/services/case/case_quality/analyzer_mixin/_project_analyzer.py` | `case` | DIR:case_quality | 1 | 是 |
| 71 | `app/services/case_quality/complexity_mixin.py` | `app/services/case/case_quality/complexity_mixin.py` | `case` | DIR:case_quality | 3 | 是 |
| 72 | `app/services/case_quality/coverage_mixin.py` | `app/services/case/case_quality/coverage_mixin.py` | `case` | DIR:case_quality | 4 | 是 |
| 73 | `app/services/case_quality/coverage_service.py` | `app/services/case/case_quality/coverage_service.py` | `case` | DIR:case_quality | 3 | 是 |
| 74 | `app/services/case_quality/history_cache.py` | `app/services/case/case_quality/history_cache.py` | `case` | DIR:case_quality | 2 | 是 |
| 75 | `app/services/case_quality/models.py` | `app/services/case/case_quality/models.py` | `case` | DIR:case_quality | 16 | 是 |
| 76 | `app/services/case_quality/quality_feedback_loop.py` | `app/services/case/case_quality/quality_feedback_loop.py` | `case` | DIR:case_quality | 6 | 是 |
| 77 | `app/services/case_quality/quality_scoring_constants.py` | `app/services/case/case_quality/quality_scoring_constants.py` | `case` | DIR:case_quality | 7 | 是 |
| 78 | `app/services/case_quality/quality_scoring_service.py` | `app/services/case/case_quality/quality_scoring_service.py` | `case` | DIR:case_quality | 7 | 是 |
| 79 | `app/services/case_quality/quality_signals.py` | `app/services/case/case_quality/quality_signals.py` | `case` | DIR:case_quality | 4 | 是 |
| 80 | `app/services/case_quality/redundancy_mixin.py` | `app/services/case/case_quality/redundancy_mixin.py` | `case` | DIR:case_quality | 1 | 是 |
| 81 | `app/services/case_quality/suggestion_mixin.py` | `app/services/case/case_quality/suggestion_mixin.py` | `case` | DIR:case_quality | 3 | 是 |
| 82 | `app/services/case_quality/tfidf_utils.py` | `app/services/case/case_quality/tfidf_utils.py` | `case` | DIR:case_quality | 4 | 是 |
| 83 | `app/services/case_quality_analyzer.py` | `app/services/review/case_quality_analyzer.py` | `review` | F06 | 2 | 是 |
| 84 | `app/services/case_refresh_service.py` | `app/services/case/case_refresh_service.py` | `case` | F11 | 8 | 是 |
| 85 | `app/services/case_version_service.py` | `app/services/case/case_version_service.py` | `case` | F11 | 6 | 是 |
| 86 | `app/services/common/__init__.py` | `app/services/common/__init__.py` | `common` | DIR:common | 6 | 是 |
| 87 | `app/services/common/token_budget.py` | `app/services/common/token_budget.py` | `common` | DIR:common | 7 | 是 |
| 88 | `app/services/config_service.py` | `app/services/common/config_service.py` | `common` | F16 | 12 | 是 |
| 89 | `app/services/cost_statistics/__init__.py` | `app/services/execution/cost_statistics/__init__.py` | `execution` | DIR:cost_statistics | 13 | 是 |
| 90 | `app/services/cost_statistics/models.py` | `app/services/execution/cost_statistics/models.py` | `execution` | DIR:cost_statistics | 8 | 是 |
| 91 | `app/services/cost_statistics/query_mixin.py` | `app/services/execution/cost_statistics/query_mixin.py` | `execution` | DIR:cost_statistics | 3 | 是 |
| 92 | `app/services/cost_statistics/report_mixin.py` | `app/services/execution/cost_statistics/report_mixin.py` | `execution` | DIR:cost_statistics | 2 | 是 |
| 93 | `app/services/cost_statistics_models.py` | `app/services/execution/cost_statistics_models.py` | `execution` | F05 | 1 | 是 |
| 94 | `app/services/cost_statistics_service.py` | `app/services/execution/cost_statistics_service.py` | `execution` | F05 | 5 | 是 |
| 95 | `app/services/decision_application_service/__init__.py` | `app/services/execution/decision_application_service/__init__.py` | `execution` | DIR:decision_application_service | 13 | 是 |
| 96 | `app/services/decision_application_service/_core.py` | `app/services/execution/decision_application_service/_core.py` | `execution` | DIR:decision_application_service | 4 | 是 |
| 97 | `app/services/decision_application_service/_handlers.py` | `app/services/execution/decision_application_service/_handlers.py` | `execution` | DIR:decision_application_service | 7 | 是 |
| 98 | `app/services/element_locator/__init__.py` | `app/services/execution/element_locator/__init__.py` | `execution` | DIR:element_locator | 3 | 是 |
| 99 | `app/services/element_locator/locator_query_mixin.py` | `app/services/execution/element_locator/locator_query_mixin.py` | `execution` | DIR:element_locator | 1 | 是 |
| 100 | `app/services/element_locator/locator_record_mixin.py` | `app/services/execution/element_locator/locator_record_mixin.py` | `execution` | DIR:element_locator | 1 | 是 |
| 101 | `app/services/element_locator/selector_generation_mixin.py` | `app/services/execution/element_locator/selector_generation_mixin.py` | `execution` | DIR:element_locator | 1 | 是 |
| 102 | `app/services/element_locator/smart_locate_mixin.py` | `app/services/execution/element_locator/smart_locate_mixin.py` | `execution` | DIR:element_locator | 1 | 是 |
| 103 | `app/services/element_locator_service.py` | `app/services/execution/element_locator_service.py` | `execution` | F04 | 14 | 是 |
| 104 | `app/services/execution_control_manager.py` | `app/services/execution/execution_control_manager.py` | `execution` | F03 | 3 | 是 |
| 105 | `app/services/execution_mode_selector.py` | `app/services/execution/execution_mode_selector.py` | `execution` | F03 | 3 | 是 |
| 106 | `app/services/execution_mode_types.py` | `app/services/execution/execution_mode_types.py` | `execution` | F03 | 5 | 是 |
| 107 | `app/services/execution_replay/__init__.py` | `app/services/execution/execution_replay/__init__.py` | `execution` | DIR:execution_replay | 26 | 是 |
| 108 | `app/services/execution_replay/legacy_models.py` | `app/services/execution/execution_replay/legacy_models.py` | `execution` | DIR:execution_replay | 4 | 是 |
| 109 | `app/services/execution_replay/legacy_playback_mixin.py` | `app/services/execution/execution_replay/legacy_playback_mixin.py` | `execution` | DIR:execution_replay | 1 | 是 |
| 110 | `app/services/execution_replay/legacy_query_mixin.py` | `app/services/execution/execution_replay/legacy_query_mixin.py` | `execution` | DIR:execution_replay | 1 | 是 |
| 111 | `app/services/execution_replay/legacy_service.py` | `app/services/execution/execution_replay/legacy_service.py` | `execution` | DIR:execution_replay | 8 | 是 |
| 112 | `app/services/execution_replay/legacy_session_mixin.py` | `app/services/execution/execution_replay/legacy_session_mixin.py` | `execution` | DIR:execution_replay | 1 | 是 |
| 113 | `app/services/execution_replay/models.py` | `app/services/execution/execution_replay/models.py` | `execution` | DIR:execution_replay | 8 | 是 |
| 114 | `app/services/execution_replay/playback_mixin.py` | `app/services/execution/execution_replay/playback_mixin.py` | `execution` | DIR:execution_replay | 2 | 是 |
| 115 | `app/services/execution_replay/query_mixin.py` | `app/services/execution/execution_replay/query_mixin.py` | `execution` | DIR:execution_replay | 1 | 是 |
| 116 | `app/services/execution_replay/session_manager_mixin.py` | `app/services/execution/execution_replay/session_manager_mixin.py` | `execution` | DIR:execution_replay | 1 | 是 |
| 117 | `app/services/execution_replay/timeline_mixin.py` | `app/services/execution/execution_replay/timeline_mixin.py` | `execution` | DIR:execution_replay | 2 | 是 |
| 118 | `app/services/feature_flag_service.py` | `app/services/common/feature_flag_service.py` | `common` | F16 | 2 | 是 |
| 119 | `app/services/file_content_extractor.py` | `app/services/common/file_content_extractor.py` | `common` | F15 | 5 | 是 |
| 120 | `app/services/file_extractor/extractors.py` | `app/services/case/file_extractor/extractors.py` | `case` | DIR:file_extractor | 2 | 是 |
| 121 | `app/services/file_parser.py` | `app/services/common/file_parser.py` | `common` | F15 | 0 | 否 |
| 122 | `app/services/flow_validation.py` | `app/services/common/flow_validation.py` | `common` | F17 | 4 | 是 |
| 123 | `app/services/history_asset_classification.py` | `app/services/case/history_asset_classification.py` | `case` | F10 | 1 | 是 |
| 124 | `app/services/history_asset_parsing.py` | `app/services/case/history_asset_parsing.py` | `case` | F10 | 1 | 是 |
| 125 | `app/services/impact_analysis/__init__.py` | `app/services/case/impact_analysis/__init__.py` | `case` | DIR:impact_analysis | 24 | 是 |
| 126 | `app/services/impact_analysis/change_analyzer.py` | `app/services/case/impact_analysis/change_analyzer.py` | `case` | DIR:impact_analysis | 4 | 是 |
| 127 | `app/services/impact_analysis/coverage_collector.py` | `app/services/case/impact_analysis/coverage_collector.py` | `case` | DIR:impact_analysis | 5 | 是 |
| 128 | `app/services/impact_analysis/impact_mapper.py` | `app/services/case/impact_analysis/impact_mapper.py` | `case` | DIR:impact_analysis | 3 | 是 |
| 129 | `app/services/impact_analysis/integration_service.py` | `app/services/case/impact_analysis/integration_service.py` | `case` | DIR:impact_analysis | 3 | 是 |
| 130 | `app/services/impact_analysis/models.py` | `app/services/case/impact_analysis/models.py` | `case` | DIR:impact_analysis | 9 | 是 |
| 131 | `app/services/impact_analysis/scheduler.py` | `app/services/case/impact_analysis/scheduler.py` | `case` | DIR:impact_analysis | 5 | 是 |
| 132 | `app/services/iteration_async_mixin.py` | `app/services/pipeline/iteration_async_mixin.py` | `pipeline` | F08 | 1 | 是 |
| 133 | `app/services/iteration_service.py` | `app/services/pipeline/iteration_service.py` | `pipeline` | F08 | 8 | 是 |
| 134 | `app/services/iteration_types.py` | `app/services/pipeline/iteration_types.py` | `pipeline` | F08 | 3 | 是 |
| 135 | `app/services/kms_service.py` | `app/services/common/kms_service.py` | `common` | F16 | 1 | 是 |
| 136 | `app/services/lifecycle_service/__init__.py` | `app/services/case/lifecycle_service/__init__.py` | `case` | DIR:lifecycle_service | 17 | 是 |
| 137 | `app/services/lifecycle_service/_capability_rules.py` | `app/services/case/lifecycle_service/_capability_rules.py` | `case` | DIR:lifecycle_service | 2 | 是 |
| 138 | `app/services/lifecycle_service/_capability_service.py` | `app/services/case/lifecycle_service/_capability_service.py` | `case` | DIR:lifecycle_service | 1 | 是 |
| 139 | `app/services/lifecycle_service/_rules.py` | `app/services/case/lifecycle_service/_rules.py` | `case` | DIR:lifecycle_service | 2 | 是 |
| 140 | `app/services/lifecycle_service/_service.py` | `app/services/case/lifecycle_service/_service.py` | `case` | DIR:lifecycle_service | 2 | 是 |
| 141 | `app/services/lineage_service.py` | `app/services/common/lineage_service.py` | `common` | F17 | 5 | 是 |
| 142 | `app/services/link_fetcher/__init__.py` | `app/services/case/link_fetcher/__init__.py` | `case` | DIR:link_fetcher | 6 | 是 |
| 143 | `app/services/link_fetcher/content_mixin.py` | `app/services/case/link_fetcher/content_mixin.py` | `case` | DIR:link_fetcher | 2 | 是 |
| 144 | `app/services/link_fetcher/core_mixin.py` | `app/services/case/link_fetcher/core_mixin.py` | `case` | DIR:link_fetcher | 2 | 是 |
| 145 | `app/services/link_fetcher/ui_mixin.py` | `app/services/case/link_fetcher/ui_mixin.py` | `case` | DIR:link_fetcher | 2 | 是 |
| 146 | `app/services/link_fetcher_service.py` | `app/services/case/link_fetcher_service.py` | `case` | F19 | 2 | 是 |
| 147 | `app/services/metrics_service.py` | `app/services/common/metrics_service.py` | `common` | F17 | 18 | 是 |
| 148 | `app/services/mfa_service.py` | `app/services/common/mfa_service.py` | `common` | F16 | 2 | 是 |
| 149 | `app/services/mobile_ai_executor/__init__.py` | `app/services/execution/mobile_ai_executor/__init__.py` | `execution` | DIR:mobile_ai_executor | 10 | 是 |
| 150 | `app/services/mobile_ai_executor/action_executor_mixin.py` | `app/services/execution/mobile_ai_executor/action_executor_mixin.py` | `execution` | DIR:mobile_ai_executor | 1 | 是 |
| 151 | `app/services/mobile_ai_executor/action_parser_mixin.py` | `app/services/execution/mobile_ai_executor/action_parser_mixin.py` | `execution` | DIR:mobile_ai_executor | 1 | 是 |
| 152 | `app/services/mobile_ai_executor/recognition_mixin.py` | `app/services/execution/mobile_ai_executor/recognition_mixin.py` | `execution` | DIR:mobile_ai_executor | 1 | 是 |
| 153 | `app/services/mobile_ai_executor/types.py` | `app/services/execution/mobile_ai_executor/types.py` | `execution` | DIR:mobile_ai_executor | 5 | 是 |
| 154 | `app/services/mobile_ai_executor.py` | `app/services/execution/mobile_ai_executor.py` | `execution` | F04 | 13 | 是 |
| 155 | `app/services/mobile_ai_executor_types.py` | `app/services/execution/mobile_ai_executor_types.py` | `execution` | F04 | 0 | 否 |
| 156 | `app/services/oidc_exceptions.py` | `app/services/common/oidc_exceptions.py` | `common` | F16 | 4 | 是 |
| 157 | `app/services/oidc_service.py` | `app/services/common/oidc_service.py` | `common` | F16 | 6 | 是 |
| 158 | `app/services/oidc_token_mixin.py` | `app/services/common/oidc_token_mixin.py` | `common` | F16 | 2 | 是 |
| 159 | `app/services/oidc_user_mixin.py` | `app/services/common/oidc_user_mixin.py` | `common` | F16 | 4 | 是 |
| 160 | `app/services/ops_service.py` | `app/services/common/ops_service.py` | `common` | F17 | 9 | 是 |
| 161 | `app/services/permission_service.py` | `app/services/common/permission_service.py` | `common` | F15 | 11 | 是 |
| 162 | `app/services/permission_service_async_mixin.py` | `app/services/common/permission_service_async_mixin.py` | `common` | F15 | 1 | 是 |
| 163 | `app/services/pipeline_permission_service.py` | `app/services/pipeline/pipeline_permission_service.py` | `pipeline` | F08 | 5 | 是 |
| 164 | `app/services/pipeline_service/__init__.py` | `app/services/pipeline/pipeline_service/__init__.py` | `pipeline` | DIR:pipeline_service | 43 | 是 |
| 165 | `app/services/pipeline_service/_artifact.py` | `app/services/pipeline/pipeline_service/_artifact.py` | `pipeline` | DIR:pipeline_service | 1 | 是 |
| 166 | `app/services/pipeline_service/_errors.py` | `app/services/pipeline/pipeline_service/_errors.py` | `pipeline` | DIR:pipeline_service | 10 | 是 |
| 167 | `app/services/pipeline_service/_run.py` | `app/services/pipeline/pipeline_service/_run.py` | `pipeline` | DIR:pipeline_service | 6 | 是 |
| 168 | `app/services/pipeline_service/_step.py` | `app/services/pipeline/pipeline_service/_step.py` | `pipeline` | DIR:pipeline_service | 2 | 是 |
| 169 | `app/services/pipeline_timeout_service.py` | `app/services/execution/pipeline_timeout_service.py` | `execution` | F05 | 6 | 是 |
| 170 | `app/services/posterior_quality_service.py` | `app/services/common/posterior_quality_service.py` | `common` | F17 | 3 | 是 |
| 171 | `app/services/posterior_score_service.py` | `app/services/common/posterior_score_service.py` | `common` | F17 | 4 | 是 |
| 172 | `app/services/precondition/__init__.py` | `app/services/case/precondition/__init__.py` | `case` | DIR:precondition | 36 | 是 |
| 173 | `app/services/precondition/browser_mixin.py` | `app/services/case/precondition/browser_mixin.py` | `case` | DIR:precondition | 1 | 是 |
| 174 | `app/services/precondition/decorator.py` | `app/services/case/precondition/decorator.py` | `case` | DIR:precondition | 7 | 是 |
| 175 | `app/services/precondition/executor_mixin.py` | `app/services/case/precondition/executor_mixin.py` | `case` | DIR:precondition | 1 | 是 |
| 176 | `app/services/precondition/init_mixin.py` | `app/services/case/precondition/init_mixin.py` | `case` | DIR:precondition | 1 | 是 |
| 177 | `app/services/precondition/login_mixin.py` | `app/services/case/precondition/login_mixin.py` | `case` | DIR:precondition | 2 | 是 |
| 178 | `app/services/precondition/login_strategy_mixin.py` | `app/services/case/precondition/login_strategy_mixin.py` | `case` | DIR:precondition | 3 | 是 |
| 179 | `app/services/precondition/models.py` | `app/services/case/precondition/models.py` | `case` | DIR:precondition | 12 | 是 |
| 180 | `app/services/precondition/test_object_mixin.py` | `app/services/case/precondition/test_object_mixin.py` | `case` | DIR:precondition | 4 | 是 |
| 181 | `app/services/precondition/utils.py` | `app/services/case/precondition/utils.py` | `case` | DIR:precondition | 4 | 是 |
| 182 | `app/services/precondition_service.py` | `app/services/case/precondition_service.py` | `case` | F13 | 27 | 是 |
| 183 | `app/services/project_access_service.py` | `app/services/common/project_access_service.py` | `common` | F15 | 2 | 是 |
| 184 | `app/services/prompt_builder/__init__.py` | `app/services/common/prompt_builder/__init__.py` | `common` | DIR:prompt_builder | 79 | 是 |
| 185 | `app/services/prompt_builder/_extra_context_renderer.py` | `app/services/common/prompt_builder/_extra_context_renderer.py` | `common` | DIR:prompt_builder | 1 | 是 |
| 186 | `app/services/prompt_builder/builder.py` | `app/services/common/prompt_builder/builder.py` | `common` | DIR:prompt_builder | 2 | 是 |
| 187 | `app/services/prompt_builder/case_prompt/__init__.py` | `app/services/common/prompt_builder/case_prompt/__init__.py` | `common` | DIR:prompt_builder | 17 | 是 |
| 188 | `app/services/prompt_builder/case_prompt/_flow_builder.py` | `app/services/common/prompt_builder/case_prompt/_flow_builder.py` | `common` | DIR:prompt_builder | 1 | 是 |
| 189 | `app/services/prompt_builder/case_prompt/_graph_prompt.py` | `app/services/common/prompt_builder/case_prompt/_graph_prompt.py` | `common` | DIR:prompt_builder | 1 | 是 |
| 190 | `app/services/prompt_builder/case_prompt/_node_format.py` | `app/services/common/prompt_builder/case_prompt/_node_format.py` | `common` | DIR:prompt_builder | 3 | 是 |
| 191 | `app/services/prompt_builder/case_prompt/_rules.py` | `app/services/common/prompt_builder/case_prompt/_rules.py` | `common` | DIR:prompt_builder | 4 | 是 |
| 192 | `app/services/prompt_builder/comparison_examples.py` | `app/services/common/prompt_builder/comparison_examples.py` | `common` | DIR:prompt_builder | 6 | 是 |
| 193 | `app/services/prompt_builder/constants.py` | `app/services/common/prompt_builder/constants.py` | `common` | DIR:prompt_builder | 2 | 是 |
| 194 | `app/services/prompt_builder/data_prompt.py` | `app/services/common/prompt_builder/data_prompt.py` | `common` | DIR:prompt_builder | 1 | 是 |
| 195 | `app/services/prompt_builder/domain_examples.py` | `app/services/common/prompt_builder/domain_examples.py` | `common` | DIR:prompt_builder | 1 | 是 |
| 196 | `app/services/prompt_builder/flow_aware_history.py` | `app/services/common/prompt_builder/flow_aware_history.py` | `common` | DIR:prompt_builder | 3 | 是 |
| 197 | `app/services/prompt_builder/helpers.py` | `app/services/common/prompt_builder/helpers.py` | `common` | DIR:prompt_builder | 7 | 是 |
| 198 | `app/services/prompt_builder/linear_prompt.py` | `app/services/common/prompt_builder/linear_prompt.py` | `common` | DIR:prompt_builder | 4 | 是 |
| 199 | `app/services/prompt_builder/migration_prompt.py` | `app/services/common/prompt_builder/migration_prompt.py` | `common` | DIR:prompt_builder | 5 | 是 |
| 200 | `app/services/prompt_builder/self_test_prompt.py` | `app/services/common/prompt_builder/self_test_prompt.py` | `common` | DIR:prompt_builder | 8 | 是 |
| 201 | `app/services/prompt_builder/ui_spec_formatter.py` | `app/services/common/prompt_builder/ui_spec_formatter.py` | `common` | DIR:prompt_builder | 2 | 是 |
| 202 | `app/services/prompt_registry.py` | `app/services/common/prompt_registry.py` | `common` | F14 | 3 | 是 |
| 203 | `app/services/push_service.py` | `app/services/common/push_service.py` | `common` | F17 | 16 | 是 |
| 204 | `app/services/quality/__init__.py` | `app/services/case/quality/__init__.py` | `case` | DIR:quality | 31 | 是 |
| 205 | `app/services/quality/grade.py` | `app/services/case/quality/grade.py` | `case` | DIR:quality | 5 | 是 |
| 206 | `app/services/quality/quality_gate_service.py` | `app/services/case/quality/quality_gate_service.py` | `case` | DIR:quality | 2 | 是 |
| 207 | `app/services/quality/validators/__init__.py` | `app/services/case/quality/validators/__init__.py` | `case` | DIR:quality | 24 | 是 |
| 208 | `app/services/quality/validators/base.py` | `app/services/case/quality/validators/base.py` | `case` | DIR:quality | 12 | 是 |
| 209 | `app/services/quality/validators/case_validator.py` | `app/services/case/quality/validators/case_validator.py` | `case` | DIR:quality | 2 | 是 |
| 210 | `app/services/quality/validators/duplication_validator.py` | `app/services/case/quality/validators/duplication_validator.py` | `case` | DIR:quality | 2 | 是 |
| 211 | `app/services/quality/validators/import_result_validator.py` | `app/services/case/quality/validators/import_result_validator.py` | `case` | DIR:quality | 2 | 是 |
| 212 | `app/services/quality/validators/material_conflict_validator.py` | `app/services/case/quality/validators/material_conflict_validator.py` | `case` | DIR:quality | 2 | 是 |
| 213 | `app/services/quality/validators/ui_reference_validator.py` | `app/services/case/quality/validators/ui_reference_validator.py` | `case` | DIR:quality | 2 | 是 |
| 214 | `app/services/quality/validators/update_suggestion_validator.py` | `app/services/case/quality/validators/update_suggestion_validator.py` | `case` | DIR:quality | 2 | 是 |
| 215 | `app/services/recognizers/__init__.py` | `app/services/execution/recognizers/__init__.py` | `execution` | DIR:recognizers | 11 | 是 |
| 216 | `app/services/recognizers/mcp_recognizer.py` | `app/services/execution/recognizers/mcp_recognizer.py` | `execution` | DIR:recognizers | 8 | 是 |
| 217 | `app/services/recognizers/vision_recognizer.py` | `app/services/execution/recognizers/vision_recognizer.py` | `execution` | DIR:recognizers | 5 | 是 |
| 218 | `app/services/report_service.py` | `app/services/pipeline/report_service.py` | `pipeline` | F09 | 8 | 是 |
| 219 | `app/services/requirement_link_content_resolver.py` | `app/services/case/requirement_link_content_resolver.py` | `case` | F13 | 0 | 否 |
| 220 | `app/services/review_service/__init__.py` | `app/services/review/review_service/__init__.py` | `review` | DIR:review_service | 17 | 是 |
| 221 | `app/services/review_service/_core.py` | `app/services/review/review_service/_core.py` | `review` | DIR:review_service | 1 | 是 |
| 222 | `app/services/review_service/_core_async.py` | `app/services/review/review_service/_core_async.py` | `review` | DIR:review_service | 0 | 否 |
| 223 | `app/services/review_service/_errors.py` | `app/services/review/review_service/_errors.py` | `review` | DIR:review_service | 7 | 是 |
| 224 | `app/services/review_service/_lock.py` | `app/services/review/review_service/_lock.py` | `review` | DIR:review_service | 1 | 是 |
| 225 | `app/services/review_service/_undo.py` | `app/services/review/review_service/_undo.py` | `review` | DIR:review_service | 2 | 是 |
| 226 | `app/services/role_service/__init__.py` | `app/services/common/role_service/__init__.py` | `common` | DIR:role_service | 8 | 是 |
| 227 | `app/services/role_service/role_service.py` | `app/services/common/role_service/role_service.py` | `common` | DIR:role_service | 8 | 是 |
| 228 | `app/services/role_service/role_service_async_mixin.py` | `app/services/common/role_service/role_service_async_mixin.py` | `common` | DIR:role_service | 1 | 是 |
| 229 | `app/services/saml/__init__.py` | `app/services/common/saml/__init__.py` | `common` | DIR:saml | 10 | 是 |
| 230 | `app/services/saml/_protocol.py` | `app/services/common/saml/_protocol.py` | `common` | DIR:saml | 1 | 是 |
| 231 | `app/services/saml/_relay_state.py` | `app/services/common/saml/_relay_state.py` | `common` | DIR:saml | 4 | 是 |
| 232 | `app/services/saml/_settings_builder.py` | `app/services/common/saml/_settings_builder.py` | `common` | DIR:saml | 4 | 是 |
| 233 | `app/services/saml/_user_provisioning.py` | `app/services/common/saml/_user_provisioning.py` | `common` | DIR:saml | 2 | 是 |
| 234 | `app/services/saml_service.py` | `app/services/common/saml_service.py` | `common` | F16 | 23 | 是 |
| 235 | `app/services/scheduler_service.py` | `app/services/common/scheduler_service.py` | `common` | F17 | 7 | 是 |
| 236 | `app/services/selector_registry.py` | `app/services/common/selector_registry.py` | `common` | F17 | 4 | 是 |
| 237 | `app/services/self_healing/__init__.py` | `app/services/execution/self_healing/__init__.py` | `execution` | DIR:self_healing | 29 | 是 |
| 238 | `app/services/self_healing/audit_service.py` | `app/services/execution/self_healing/audit_service.py` | `execution` | DIR:self_healing | 2 | 是 |
| 239 | `app/services/self_healing/config_service.py` | `app/services/execution/self_healing/config_service.py` | `execution` | DIR:self_healing | 14 | 是 |
| 240 | `app/services/self_healing/failure_analyzer.py` | `app/services/execution/self_healing/failure_analyzer.py` | `execution` | DIR:self_healing | 2 | 是 |
| 241 | `app/services/self_healing/metrics.py` | `app/services/execution/self_healing/metrics.py` | `execution` | DIR:self_healing | 4 | 是 |
| 242 | `app/services/self_healing/models.py` | `app/services/execution/self_healing/models.py` | `execution` | DIR:self_healing | 5 | 是 |
| 243 | `app/services/self_healing/token_budget.py` | `app/services/execution/self_healing/token_budget.py` | `execution` | DIR:self_healing | 2 | 是 |
| 244 | `app/services/self_test/__init__.py` | `app/services/pipeline/self_test/__init__.py` | `pipeline` | DIR:self_test | 9 | 是 |
| 245 | `app/services/self_test/_defect_bug.py` | `app/services/pipeline/self_test/_defect_bug.py` | `pipeline` | DIR:self_test | 2 | 是 |
| 246 | `app/services/self_test/_defect_metrics.py` | `app/services/pipeline/self_test/_defect_metrics.py` | `pipeline` | DIR:self_test | 1 | 是 |
| 247 | `app/services/self_test/_orchestrator.py` | `app/services/pipeline/self_test/_orchestrator.py` | `pipeline` | DIR:self_test | 1 | 是 |
| 248 | `app/services/self_test/_pipeline_steps_run.py` | `app/services/pipeline/self_test/_pipeline_steps_run.py` | `pipeline` | DIR:self_test | 1 | 是 |
| 249 | `app/services/self_test/_pipeline_steps_setup.py` | `app/services/pipeline/self_test/_pipeline_steps_setup.py` | `pipeline` | DIR:self_test | 2 | 是 |
| 250 | `app/services/self_test/_project_setup.py` | `app/services/pipeline/self_test/_project_setup.py` | `pipeline` | DIR:self_test | 1 | 是 |
| 251 | `app/services/self_test_service.py` | `app/services/execution/self_test_service.py` | `execution` | F04 | 61 | 是 |
| 252 | `app/services/session_service.py` | `app/services/common/session_service.py` | `common` | F16 | 5 | 是 |
| 253 | `app/services/storage/__init__.py` | `app/services/common/storage/__init__.py` | `common` | DIR:storage | 20 | 是 |
| 254 | `app/services/storage/base.py` | `app/services/common/storage/base.py` | `common` | DIR:storage | 9 | 是 |
| 255 | `app/services/storage/factory.py` | `app/services/common/storage/factory.py` | `common` | DIR:storage | 9 | 是 |
| 256 | `app/services/storage/local.py` | `app/services/common/storage/local.py` | `common` | DIR:storage | 2 | 是 |
| 257 | `app/services/storage/s3.py` | `app/services/common/storage/s3.py` | `common` | DIR:storage | 2 | 是 |
| 258 | `app/services/task_service/__init__.py` | `app/services/execution/task_service/__init__.py` | `execution` | DIR:task_service | 10 | 是 |
| 259 | `app/services/task_service/core_mixin.py` | `app/services/execution/task_service/core_mixin.py` | `execution` | DIR:task_service | 3 | 是 |
| 260 | `app/services/task_service/execution_mixin.py` | `app/services/execution/task_service/execution_mixin.py` | `execution` | DIR:task_service | 2 | 是 |
| 261 | `app/services/task_service/push_mixin.py` | `app/services/execution/task_service/push_mixin.py` | `execution` | DIR:task_service | 3 | 是 |
| 262 | `app/services/task_timeout_monitor.py` | `app/services/execution/task_timeout_monitor.py` | `execution` | F05 | 0 | 否 |
| 263 | `app/services/test_capability_service.py` | `app/services/common/test_capability_service.py` | `common` | F17 | 4 | 是 |
| 264 | `app/services/test_case_generation/__init__.py` | `app/services/case/test_case_generation/__init__.py` | `case` | DIR:test_case_generation | 88 | 是 |
| 265 | `app/services/test_case_generation/_batch_orchestrator_coverage.py` | `app/services/case/test_case_generation/_batch_orchestrator_coverage.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 266 | `app/services/test_case_generation/_batch_orchestrator_failure_feedback.py` | `app/services/case/test_case_generation/_batch_orchestrator_failure_feedback.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 267 | `app/services/test_case_generation/_context_loaders_mixin.py` | `app/services/case/test_case_generation/_context_loaders_mixin.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 268 | `app/services/test_case_generation/_helpers_budget.py` | `app/services/case/test_case_generation/_helpers_budget.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 269 | `app/services/test_case_generation/_helpers_constants.py` | `app/services/case/test_case_generation/_helpers_constants.py` | `case` | DIR:test_case_generation | 4 | 是 |
| 270 | `app/services/test_case_generation/_helpers_refs.py` | `app/services/case/test_case_generation/_helpers_refs.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 271 | `app/services/test_case_generation/_helpers_sanitizer.py` | `app/services/case/test_case_generation/_helpers_sanitizer.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 272 | `app/services/test_case_generation/_helpers_test_point.py` | `app/services/case/test_case_generation/_helpers_test_point.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 273 | `app/services/test_case_generation/_helpers_text.py` | `app/services/case/test_case_generation/_helpers_text.py` | `case` | DIR:test_case_generation | 4 | 是 |
| 274 | `app/services/test_case_generation/_history_scoring_mixin.py` | `app/services/case/test_case_generation/_history_scoring_mixin.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 275 | `app/services/test_case_generation/_quality_field_validators.py` | `app/services/case/test_case_generation/_quality_field_validators.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 276 | `app/services/test_case_generation/_quality_step_validators.py` | `app/services/case/test_case_generation/_quality_step_validators.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 277 | `app/services/test_case_generation/_requirement_ui_loaders_mixin.py` | `app/services/case/test_case_generation/_requirement_ui_loaders_mixin.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 278 | `app/services/test_case_generation/_validator_quality_gate.py` | `app/services/case/test_case_generation/_validator_quality_gate.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 279 | `app/services/test_case_generation/_validator_ui_elements.py` | `app/services/case/test_case_generation/_validator_ui_elements.py` | `case` | DIR:test_case_generation | 1 | 是 |
| 280 | `app/services/test_case_generation/ai_generator.py` | `app/services/case/test_case_generation/ai_generator.py` | `case` | DIR:test_case_generation | 10 | 是 |
| 281 | `app/services/test_case_generation/ai_response_parser.py` | `app/services/case/test_case_generation/ai_response_parser.py` | `case` | DIR:test_case_generation | 2 | 是 |
| 282 | `app/services/test_case_generation/batch_orchestrator.py` | `app/services/case/test_case_generation/batch_orchestrator.py` | `case` | DIR:test_case_generation | 2 | 是 |
| 283 | `app/services/test_case_generation/context_builder.py` | `app/services/case/test_case_generation/context_builder.py` | `case` | DIR:test_case_generation | 5 | 是 |
| 284 | `app/services/test_case_generation/continuous_scorer.py` | `app/services/case/test_case_generation/continuous_scorer.py` | `case` | DIR:test_case_generation | 2 | 是 |
| 285 | `app/services/test_case_generation/helpers.py` | `app/services/case/test_case_generation/helpers.py` | `case` | DIR:test_case_generation | 10 | 是 |
| 286 | `app/services/test_case_generation/quality_validator.py` | `app/services/case/test_case_generation/quality_validator.py` | `case` | DIR:test_case_generation | 8 | 是 |
| 287 | `app/services/test_case_generation/validator.py` | `app/services/case/test_case_generation/validator.py` | `case` | DIR:test_case_generation | 9 | 是 |
| 288 | `app/services/test_case_generation_service.py` | `app/services/case/test_case_generation_service.py` | `case` | F11 | 1 | 是 |
| 289 | `app/services/test_case_view/__init__.py` | `app/services/case/test_case_view/__init__.py` | `case` | DIR:test_case_view | 13 | 是 |
| 290 | `app/services/test_case_view/async_mixin.py` | `app/services/case/test_case_view/async_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 291 | `app/services/test_case_view/business_view_mixin.py` | `app/services/case/test_case_view/business_view_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 292 | `app/services/test_case_view/excel_export_mixin.py` | `app/services/case/test_case_view/excel_export_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 293 | `app/services/test_case_view/excel_import_mixin.py` | `app/services/case/test_case_view/excel_import_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 294 | `app/services/test_case_view/excel_mixin.py` | `app/services/case/test_case_view/excel_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 295 | `app/services/test_case_view/excel_normalize_mixin.py` | `app/services/case/test_case_view/excel_normalize_mixin.py` | `case` | DIR:test_case_view | 4 | 是 |
| 296 | `app/services/test_case_view/excel_validate_mixin.py` | `app/services/case/test_case_view/excel_validate_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 297 | `app/services/test_case_view/models.py` | `app/services/case/test_case_view/models.py` | `case` | DIR:test_case_view | 4 | 是 |
| 298 | `app/services/test_case_view/technical_view_mixin.py` | `app/services/case/test_case_view/technical_view_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 299 | `app/services/test_case_view/view_config_mixin.py` | `app/services/case/test_case_view/view_config_mixin.py` | `case` | DIR:test_case_view | 1 | 是 |
| 300 | `app/services/test_case_view_service.py` | `app/services/case/test_case_view_service.py` | `case` | F11 | 17 | 是 |
| 301 | `app/services/test_data/__init__.py` | `app/services/case/test_data/__init__.py` | `case` | DIR:test_data | 14 | 是 |
| 302 | `app/services/test_data/constants.py` | `app/services/case/test_data/constants.py` | `case` | DIR:test_data | 2 | 是 |
| 303 | `app/services/test_data/crud_mixin.py` | `app/services/case/test_data/crud_mixin.py` | `case` | DIR:test_data | 2 | 是 |
| 304 | `app/services/test_data/generator_mixin.py` | `app/services/case/test_data/generator_mixin.py` | `case` | DIR:test_data | 2 | 是 |
| 305 | `app/services/test_data/parameterizer_mixin.py` | `app/services/case/test_data/parameterizer_mixin.py` | `case` | DIR:test_data | 3 | 是 |
| 306 | `app/services/test_data/prompt_builder.py` | `app/services/case/test_data/prompt_builder.py` | `case` | DIR:test_data | 0 | 否 |
| 307 | `app/services/test_data/response_handler.py` | `app/services/case/test_data/response_handler.py` | `case` | DIR:test_data | 3 | 是 |
| 308 | `app/services/test_data/service_mixin.py` | `app/services/case/test_data/service_mixin.py` | `case` | DIR:test_data | 3 | 是 |
| 309 | `app/services/test_data_async_mixin.py` | `app/services/case/test_data_async_mixin.py` | `case` | F12 | 1 | 是 |
| 310 | `app/services/test_data_crud_mixin.py` | `app/services/case/test_data_crud_mixin.py` | `case` | F12 | 1 | 是 |
| 311 | `app/services/test_data_gen_constants.py` | `app/services/case/test_data_gen_constants.py` | `case` | F12 | 2 | 是 |
| 312 | `app/services/test_data_gen_service_mixin.py` | `app/services/case/test_data_gen_service_mixin.py` | `case` | F12 | 1 | 是 |
| 313 | `app/services/test_data_generator.py` | `app/services/case/test_data_generator.py` | `case` | F12 | 8 | 是 |
| 314 | `app/services/test_data_parameterizer/__init__.py` | `app/services/case/test_data_parameterizer/__init__.py` | `case` | DIR:test_data_parameterizer | 7 | 是 |
| 315 | `app/services/test_data_parameterizer/context.py` | `app/services/case/test_data_parameterizer/context.py` | `case` | DIR:test_data_parameterizer | 1 | 是 |
| 316 | `app/services/test_data_parameterizer/handlers.py` | `app/services/case/test_data_parameterizer/handlers.py` | `case` | DIR:test_data_parameterizer | 1 | 是 |
| 317 | `app/services/test_data_service.py` | `app/services/case/test_data_service.py` | `case` | F12 | 6 | 是 |
| 318 | `app/services/test_execution_engine/__init__.py` | `app/services/execution/test_execution_engine/__init__.py` | `execution` | DIR:test_execution_engine | 106 | 是 |
| 319 | `app/services/test_execution_engine/_basic_assertion_mixin.py` | `app/services/execution/test_execution_engine/_basic_assertion_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 320 | `app/services/test_execution_engine/_extended_assertion_mixin.py` | `app/services/execution/test_execution_engine/_extended_assertion_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 321 | `app/services/test_execution_engine/_step_defect_capture_mixin.py` | `app/services/execution/test_execution_engine/_step_defect_capture_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 322 | `app/services/test_execution_engine/_step_helpers_mixin.py` | `app/services/execution/test_execution_engine/_step_helpers_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 323 | `app/services/test_execution_engine/action_executor_basic_mixin.py` | `app/services/execution/test_execution_engine/action_executor_basic_mixin.py` | `execution` | DIR:test_execution_engine | 5 | 是 |
| 324 | `app/services/test_execution_engine/action_executor_complex_mixin.py` | `app/services/execution/test_execution_engine/action_executor_complex_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 325 | `app/services/test_execution_engine/action_executor_hover_select_mixin.py` | `app/services/execution/test_execution_engine/action_executor_hover_select_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 326 | `app/services/test_execution_engine/action_executor_input_click_mixin.py` | `app/services/execution/test_execution_engine/action_executor_input_click_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 327 | `app/services/test_execution_engine/action_executor_mixin.py` | `app/services/execution/test_execution_engine/action_executor_mixin.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 328 | `app/services/test_execution_engine/action_executor_verify_captcha_mixin.py` | `app/services/execution/test_execution_engine/action_executor_verify_captcha_mixin.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 329 | `app/services/test_execution_engine/ai_recognition_mixin.py` | `app/services/execution/test_execution_engine/ai_recognition_mixin.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 330 | `app/services/test_execution_engine/api_setup_mixin/__init__.py` | `app/services/execution/test_execution_engine/api_setup_mixin/__init__.py` | `execution` | DIR:test_execution_engine | 9 | 是 |
| 331 | `app/services/test_execution_engine/api_setup_mixin/_executor.py` | `app/services/execution/test_execution_engine/api_setup_mixin/_executor.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 332 | `app/services/test_execution_engine/api_setup_mixin/_helpers.py` | `app/services/execution/test_execution_engine/api_setup_mixin/_helpers.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 333 | `app/services/test_execution_engine/dependency_resolution_mixin/__init__.py` | `app/services/execution/test_execution_engine/dependency_resolution_mixin/__init__.py` | `execution` | DIR:test_execution_engine | 9 | 是 |
| 334 | `app/services/test_execution_engine/dependency_resolution_mixin/_graph.py` | `app/services/execution/test_execution_engine/dependency_resolution_mixin/_graph.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 335 | `app/services/test_execution_engine/dependency_resolution_mixin/_navigation.py` | `app/services/execution/test_execution_engine/dependency_resolution_mixin/_navigation.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 336 | `app/services/test_execution_engine/dependency_resolution_mixin/_orchestration.py` | `app/services/execution/test_execution_engine/dependency_resolution_mixin/_orchestration.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 337 | `app/services/test_execution_engine/dependency_resolution_mixin/_snapshot.py` | `app/services/execution/test_execution_engine/dependency_resolution_mixin/_snapshot.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 338 | `app/services/test_execution_engine/models/__init__.py` | `app/services/execution/test_execution_engine/models/__init__.py` | `execution` | DIR:test_execution_engine | 40 | 是 |
| 339 | `app/services/test_execution_engine/models/_enums.py` | `app/services/execution/test_execution_engine/models/_enums.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 340 | `app/services/test_execution_engine/models/_models.py` | `app/services/execution/test_execution_engine/models/_models.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 341 | `app/services/test_execution_engine/precondition_mixin.py` | `app/services/execution/test_execution_engine/precondition_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 342 | `app/services/test_execution_engine/self_healing_execute_helpers.py` | `app/services/execution/test_execution_engine/self_healing_execute_helpers.py` | `execution` | DIR:test_execution_engine | 0 | 否 |
| 343 | `app/services/test_execution_engine/self_healing_execute_mixin.py` | `app/services/execution/test_execution_engine/self_healing_execute_mixin.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 344 | `app/services/test_execution_engine/self_healing_mixin.py` | `app/services/execution/test_execution_engine/self_healing_mixin.py` | `execution` | DIR:test_execution_engine | 0 | 否 |
| 345 | `app/services/test_execution_engine/self_healing_stagehand_mixin.py` | `app/services/execution/test_execution_engine/self_healing_stagehand_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 346 | `app/services/test_execution_engine/self_healing_strategy_helpers.py` | `app/services/execution/test_execution_engine/self_healing_strategy_helpers.py` | `execution` | DIR:test_execution_engine | 0 | 否 |
| 347 | `app/services/test_execution_engine/self_healing_strategy_mixin.py` | `app/services/execution/test_execution_engine/self_healing_strategy_mixin.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 348 | `app/services/test_execution_engine/self_healing_utils_mixin.py` | `app/services/execution/test_execution_engine/self_healing_utils_mixin.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 349 | `app/services/test_execution_engine/step_executor_mixin.py` | `app/services/execution/test_execution_engine/step_executor_mixin.py` | `execution` | DIR:test_execution_engine | 9 | 是 |
| 350 | `app/services/test_execution_engine/structured_assertion_mixin.py` | `app/services/execution/test_execution_engine/structured_assertion_mixin.py` | `execution` | DIR:test_execution_engine | 3 | 是 |
| 351 | `app/services/test_execution_engine/task_batch_executor_mixin/__init__.py` | `app/services/execution/test_execution_engine/task_batch_executor_mixin/__init__.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 352 | `app/services/test_execution_engine/task_batch_executor_mixin/_executor.py` | `app/services/execution/test_execution_engine/task_batch_executor_mixin/_executor.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 353 | `app/services/test_execution_engine/task_batch_executor_mixin/_helpers.py` | `app/services/execution/test_execution_engine/task_batch_executor_mixin/_helpers.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 354 | `app/services/test_execution_engine/task_executor_mixin/__init__.py` | `app/services/execution/test_execution_engine/task_executor_mixin/__init__.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 355 | `app/services/test_execution_engine/task_executor_mixin/_executor.py` | `app/services/execution/test_execution_engine/task_executor_mixin/_executor.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 356 | `app/services/test_execution_engine/task_executor_mixin/_helpers.py` | `app/services/execution/test_execution_engine/task_executor_mixin/_helpers.py` | `execution` | DIR:test_execution_engine | 2 | 是 |
| 357 | `app/services/test_execution_engine/test_data_mixin.py` | `app/services/execution/test_execution_engine/test_data_mixin.py` | `execution` | DIR:test_execution_engine | 1 | 是 |
| 358 | `app/services/test_execution_engine_v2.py` | `app/services/execution/test_execution_engine_v2.py` | `execution` | F20 | 12 | 是 |
| 359 | `app/services/ui_prototype_flow.py` | `app/services/case/ui_prototype_flow.py` | `case` | F13 | 3 | 是 |
| 360 | `app/services/ui_spec_ocr.py` | `app/services/case/ui_spec_ocr.py` | `case` | F13 | 0 | 否 |
| 361 | `app/services/ui_spec_parse_pipeline.py` | `app/services/case/ui_spec_parse_pipeline.py` | `case` | F13 | 3 | 是 |
| 362 | `app/services/ui_spec_parser/__init__.py` | `app/services/case/ui_spec_parser/__init__.py` | `case` | DIR:ui_spec_parser | 13 | 是 |
| 363 | `app/services/ui_spec_parser/core_mixin.py` | `app/services/case/ui_spec_parser/core_mixin.py` | `case` | DIR:ui_spec_parser | 3 | 是 |
| 364 | `app/services/ui_spec_parser/flow_mixin.py` | `app/services/case/ui_spec_parser/flow_mixin.py` | `case` | DIR:ui_spec_parser | 2 | 是 |
| 365 | `app/services/ui_spec_parser/ocr_mixin.py` | `app/services/case/ui_spec_parser/ocr_mixin.py` | `case` | DIR:ui_spec_parser | 2 | 是 |
| 366 | `app/services/ui_spec_parser/pipeline_mixin.py` | `app/services/case/ui_spec_parser/pipeline_mixin.py` | `case` | DIR:ui_spec_parser | 2 | 是 |
| 367 | `app/services/ui_spec_parser/pipeline_upload_mixin.py` | `app/services/case/ui_spec_parser/pipeline_upload_mixin.py` | `case` | DIR:ui_spec_parser | 2 | 是 |
| 368 | `app/services/ui_spec_parser.py` | `app/services/case/ui_spec_parser.py` | `case` | F13 | 15 | 是 |
| 369 | `app/services/ui_spec_prompts.py` | `app/services/case/ui_spec_prompts.py` | `case` | F13 | 0 | 否 |
| 370 | `app/services/url_driven/__init__.py` | `app/services/case/url_driven/__init__.py` | `case` | DIR:url_driven | 40 | 是 |
| 371 | `app/services/url_driven/_crawl_mixin.py` | `app/services/case/url_driven/_crawl_mixin.py` | `case` | DIR:url_driven | 4 | 是 |
| 372 | `app/services/url_driven/_login_mixin.py` | `app/services/case/url_driven/_login_mixin.py` | `case` | DIR:url_driven | 2 | 是 |
| 373 | `app/services/url_driven/_prompt_mixin.py` | `app/services/case/url_driven/_prompt_mixin.py` | `case` | DIR:url_driven | 2 | 是 |
| 374 | `app/services/url_driven/_snapshot_mixin.py` | `app/services/case/url_driven/_snapshot_mixin.py` | `case` | DIR:url_driven | 2 | 是 |
| 375 | `app/services/url_driven/_task_assembler_async.py` | `app/services/case/url_driven/_task_assembler_async.py` | `case` | DIR:url_driven | 1 | 是 |
| 376 | `app/services/url_driven/_test_point_mixin.py` | `app/services/case/url_driven/_test_point_mixin.py` | `case` | DIR:url_driven | 1 | 是 |
| 377 | `app/services/url_driven/_validation_mixin.py` | `app/services/case/url_driven/_validation_mixin.py` | `case` | DIR:url_driven | 1 | 是 |
| 378 | `app/services/url_driven/auto_case_generator.py` | `app/services/case/url_driven/auto_case_generator.py` | `case` | DIR:url_driven | 5 | 是 |
| 379 | `app/services/url_driven/auto_project_builder.py` | `app/services/case/url_driven/auto_project_builder.py` | `case` | DIR:url_driven | 3 | 是 |
| 380 | `app/services/url_driven/quick_launcher.py` | `app/services/case/url_driven/quick_launcher.py` | `case` | DIR:url_driven | 3 | 是 |
| 381 | `app/services/url_driven/site_explorer.py` | `app/services/case/url_driven/site_explorer.py` | `case` | DIR:url_driven | 17 | 是 |
| 382 | `app/services/url_driven/task_assembler.py` | `app/services/case/url_driven/task_assembler.py` | `case` | DIR:url_driven | 4 | 是 |
| 383 | `app/services/user_role_service_async_mixin.py` | `app/services/common/user_role_service_async_mixin.py` | `common` | F15 | 1 | 是 |
| 384 | `app/services/user_service/__init__.py` | `app/services/common/user_service/__init__.py` | `common` | DIR:user_service | 16 | 是 |
| 385 | `app/services/user_service/user_service.py` | `app/services/common/user_service/user_service.py` | `common` | DIR:user_service | 8 | 是 |
| 386 | `app/services/user_service/user_service_async_mixin.py` | `app/services/common/user_service/user_service_async_mixin.py` | `common` | DIR:user_service | 1 | 是 |
| 387 | `app/services/video/__init__.py` | `app/services/execution/video/__init__.py` | `execution` | DIR:video | 18 | 是 |
| 388 | `app/services/video/cleanup_mixin.py` | `app/services/execution/video/cleanup_mixin.py` | `execution` | DIR:video | 2 | 是 |
| 389 | `app/services/video/crud_mixin.py` | `app/services/execution/video/crud_mixin.py` | `execution` | DIR:video | 2 | 是 |
| 390 | `app/services/video/ffmpeg_mixin.py` | `app/services/execution/video/ffmpeg_mixin.py` | `execution` | DIR:video | 2 | 是 |
| 391 | `app/services/video/models.py` | `app/services/execution/video/models.py` | `execution` | DIR:video | 7 | 是 |
| 392 | `app/services/video/path_utils_mixin.py` | `app/services/execution/video/path_utils_mixin.py` | `execution` | DIR:video | 2 | 是 |
| 393 | `app/services/visibility_config/__init__.py` | `app/services/review/visibility_config/__init__.py` | `review` | DIR:visibility_config | 39 | 是 |
| 394 | `app/services/visibility_config/core_mixin.py` | `app/services/review/visibility_config/core_mixin.py` | `review` | DIR:visibility_config | 4 | 是 |
| 395 | `app/services/visibility_config/env_loader.py` | `app/services/review/visibility_config/env_loader.py` | `review` | DIR:visibility_config | 6 | 是 |
| 396 | `app/services/visibility_config/merger.py` | `app/services/review/visibility_config/merger.py` | `review` | DIR:visibility_config | 6 | 是 |
| 397 | `app/services/visibility_config/models.py` | `app/services/review/visibility_config/models.py` | `review` | DIR:visibility_config | 13 | 是 |
| 398 | `app/services/visibility_config/permission_mixin.py` | `app/services/review/visibility_config/permission_mixin.py` | `review` | DIR:visibility_config | 2 | 是 |
| 399 | `app/services/visibility_config/validator.py` | `app/services/review/visibility_config/validator.py` | `review` | DIR:visibility_config | 4 | 是 |
| 400 | `app/services/visibility_config_service.py` | `app/services/review/visibility_config_service.py` | `review` | F06 | 8 | 是 |
| 401 | `app/services/visual_ai/__init__.py` | `app/services/execution/visual_ai/__init__.py` | `execution` | DIR:visual_ai | 17 | 是 |
| 402 | `app/services/visual_ai/_sdk_check_mixin.py` | `app/services/execution/visual_ai/_sdk_check_mixin.py` | `execution` | DIR:visual_ai | 1 | 是 |
| 403 | `app/services/visual_ai/_sdk_helpers.py` | `app/services/execution/visual_ai/_sdk_helpers.py` | `execution` | DIR:visual_ai | 1 | 是 |
| 404 | `app/services/visual_ai/baseline_service.py` | `app/services/execution/visual_ai/baseline_service.py` | `execution` | DIR:visual_ai | 3 | 是 |
| 405 | `app/services/visual_ai/comparison_engine.py` | `app/services/execution/visual_ai/comparison_engine.py` | `execution` | DIR:visual_ai | 6 | 是 |
| 406 | `app/services/visual_ai/dom_serializer.py` | `app/services/execution/visual_ai/dom_serializer.py` | `execution` | DIR:visual_ai | 2 | 是 |
| 407 | `app/services/visual_ai/match_level.py` | `app/services/execution/visual_ai/match_level.py` | `execution` | DIR:visual_ai | 3 | 是 |
| 408 | `app/services/visual_ai/sdk.py` | `app/services/execution/visual_ai/sdk.py` | `execution` | DIR:visual_ai | 2 | 是 |
| 409 | `app/services/visual_ai/token_estimator.py` | `app/services/execution/visual_ai/token_estimator.py` | `execution` | DIR:visual_ai | 4 | 是 |
| 410 | `app/services/xmind_ai_parser/__init__.py` | `app/services/case/xmind_ai_parser/__init__.py` | `case` | DIR:xmind_ai_parser | 5 | 是 |
| 411 | `app/services/xmind_ai_parser/_parser.py` | `app/services/case/xmind_ai_parser/_parser.py` | `case` | DIR:xmind_ai_parser | 1 | 是 |
| 412 | `app/services/xmind_ai_parser/_parsing.py` | `app/services/case/xmind_ai_parser/_parsing.py` | `case` | DIR:xmind_ai_parser | 3 | 是 |
| 413 | `app/services/xmind_ai_parser/_prompts.py` | `app/services/case/xmind_ai_parser/_prompts.py` | `case` | DIR:xmind_ai_parser | 2 | 是 |
| 414 | `app/services/xmind_case_parser/__init__.py` | `app/services/case/xmind_case_parser/__init__.py` | `case` | DIR:xmind_case_parser | 9 | 是 |
| 415 | `app/services/xmind_case_parser/_classify.py` | `app/services/case/xmind_case_parser/_classify.py` | `case` | DIR:xmind_case_parser | 4 | 是 |
| 416 | `app/services/xmind_case_parser/_parse.py` | `app/services/case/xmind_case_parser/_parse.py` | `case` | DIR:xmind_case_parser | 3 | 是 |
| 417 | `app/services/xmind_case_parser/_util.py` | `app/services/case/xmind_case_parser/_util.py` | `case` | DIR:xmind_case_parser | 3 | 是 |
| 418 | `app/services/xmind_import_service.py` | `app/services/case/xmind_import_service.py` | `case` | F13 | 3 | 是 |
| 419 | `app/services/xmind_parser/__init__.py` | `app/services/case/xmind_parser/__init__.py` | `case` | DIR:xmind_parser | 14 | 是 |
| 420 | `app/services/xmind_parser/_parse.py` | `app/services/case/xmind_parser/_parse.py` | `case` | DIR:xmind_parser | 3 | 是 |
| 421 | `app/services/xmind_parser/_util.py` | `app/services/case/xmind_parser/_util.py` | `case` | DIR:xmind_parser | 4 | 是 |

## 四、`app/api/v1/endpoints/` 映射（逐文件）

| # | 现有路径 | 目标路径 | 归属域 | 依据 | 外部引用 | shim |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `app/api/v1/endpoints/__init__.py` | `app/api/v1/endpoints/common/__init__.py` | `common` | F21 | 388 | 是 |
| 2 | `app/api/v1/endpoints/_case_quality_cost_routes.py` | `app/api/v1/endpoints/review/_case_quality_cost_routes.py` | `review` | F06 | 1 | 是 |
| 3 | `app/api/v1/endpoints/_case_quality_schemas.py` | `app/api/v1/endpoints/review/_case_quality_schemas.py` | `review` | F06 | 0 | 否 |
| 4 | `app/api/v1/endpoints/_deps.py` | `app/api/v1/endpoints/common/_deps.py` | `common` | F22 | 4 | 是 |
| 5 | `app/api/v1/endpoints/_generation_batch_helpers.py` | `app/api/v1/endpoints/case/_generation_batch_helpers.py` | `case` | F11 | 3 | 是 |
| 6 | `app/api/v1/endpoints/_generation_batch_routes.py` | `app/api/v1/endpoints/case/_generation_batch_routes.py` | `case` | F11 | 1 | 是 |
| 7 | `app/api/v1/endpoints/_generation_batch_save.py` | `app/api/v1/endpoints/case/_generation_batch_save.py` | `case` | F11 | 1 | 是 |
| 8 | `app/api/v1/endpoints/_history_asset_helpers.py` | `app/api/v1/endpoints/case/_history_asset_helpers.py` | `case` | F10 | 1 | 是 |
| 9 | `app/api/v1/endpoints/_pipeline_artifacts_helpers.py` | `app/api/v1/endpoints/pipeline/_pipeline_artifacts_helpers.py` | `pipeline` | F08 | 3 | 是 |
| 10 | `app/api/v1/endpoints/_pipeline_artifacts_mutations.py` | `app/api/v1/endpoints/pipeline/_pipeline_artifacts_mutations.py` | `pipeline` | F08 | 1 | 是 |
| 11 | `app/api/v1/endpoints/_pipeline_artifacts_routes.py` | `app/api/v1/endpoints/pipeline/_pipeline_artifacts_routes.py` | `pipeline` | F08 | 1 | 是 |
| 12 | `app/api/v1/endpoints/_test_case_crud_helpers.py` | `app/api/v1/endpoints/case/_test_case_crud_helpers.py` | `case` | F11 | 2 | 是 |
| 13 | `app/api/v1/endpoints/_test_case_crud_mutations.py` | `app/api/v1/endpoints/case/_test_case_crud_mutations.py` | `case` | F11 | 1 | 是 |
| 14 | `app/api/v1/endpoints/_test_case_crud_routes.py` | `app/api/v1/endpoints/case/_test_case_crud_routes.py` | `case` | F11 | 1 | 是 |
| 15 | `app/api/v1/endpoints/_user_perm_routes.py` | `app/api/v1/endpoints/common/_user_perm_routes.py` | `common` | F15 | 1 | 是 |
| 16 | `app/api/v1/endpoints/_user_role_routes.py` | `app/api/v1/endpoints/common/_user_role_routes.py` | `common` | F15 | 1 | 是 |
| 17 | `app/api/v1/endpoints/ab_test.py` | `app/api/v1/endpoints/case/ab_test.py` | `case` | F13 | 1 | 是 |
| 18 | `app/api/v1/endpoints/access_deps.py` | `app/api/v1/endpoints/common/access_deps.py` | `common` | F18 | 3 | 是 |
| 19 | `app/api/v1/endpoints/agents.py` | `app/api/v1/endpoints/agent/agents.py` | `agent` | F01 | 9 | 是 |
| 20 | `app/api/v1/endpoints/ai_invocation.py` | `app/api/v1/endpoints/common/ai_invocation.py` | `common` | F14 | 1 | 是 |
| 21 | `app/api/v1/endpoints/audit_log.py` | `app/api/v1/endpoints/common/audit_log.py` | `common` | F16 | 1 | 是 |
| 22 | `app/api/v1/endpoints/auth.py` | `app/api/v1/endpoints/common/auth.py` | `common` | F15 | 88 | 是 |
| 23 | `app/api/v1/endpoints/auth_deps.py` | `app/api/v1/endpoints/common/auth_deps.py` | `common` | F15 | 10 | 是 |
| 24 | `app/api/v1/endpoints/auth_endpoints.py` | `app/api/v1/endpoints/common/auth_endpoints.py` | `common` | F15 | 1 | 是 |
| 25 | `app/api/v1/endpoints/batch_locator.py` | `app/api/v1/endpoints/execution/batch_locator.py` | `execution` | F03 | 3 | 是 |
| 26 | `app/api/v1/endpoints/batch_locator_tasks.py` | `app/api/v1/endpoints/execution/batch_locator_tasks.py` | `execution` | F03 | 1 | 是 |
| 27 | `app/api/v1/endpoints/bug.py` | `app/api/v1/endpoints/review/bug.py` | `review` | F07 | 1 | 是 |
| 28 | `app/api/v1/endpoints/case_migration.py` | `app/api/v1/endpoints/case/case_migration.py` | `case` | F11 | 2 | 是 |
| 29 | `app/api/v1/endpoints/case_quality.py` | `app/api/v1/endpoints/review/case_quality.py` | `review` | F06 | 1 | 是 |
| 30 | `app/api/v1/endpoints/case_quality_check.py` | `app/api/v1/endpoints/review/case_quality_check.py` | `review` | F06 | 2 | 是 |
| 31 | `app/api/v1/endpoints/case_quality_posterior.py` | `app/api/v1/endpoints/review/case_quality_posterior.py` | `review` | F06 | 1 | 是 |
| 32 | `app/api/v1/endpoints/case_quality_report.py` | `app/api/v1/endpoints/review/case_quality_report.py` | `review` | F06 | 1 | 是 |
| 33 | `app/api/v1/endpoints/case_refresh.py` | `app/api/v1/endpoints/case/case_refresh.py` | `case` | F11 | 1 | 是 |
| 34 | `app/api/v1/endpoints/execution.py` | `app/api/v1/endpoints/execution/execution.py` | `execution` | F03 | 1 | 是 |
| 35 | `app/api/v1/endpoints/execution_core/__init__.py` | `app/api/v1/endpoints/execution/execution_core/__init__.py` | `execution` | DIR:execution_core | 7 | 是 |
| 36 | `app/api/v1/endpoints/execution_core/_analysis.py` | `app/api/v1/endpoints/execution/execution_core/_analysis.py` | `execution` | DIR:execution_core | 4 | 是 |
| 37 | `app/api/v1/endpoints/execution_core/_execution.py` | `app/api/v1/endpoints/execution/execution_core/_execution.py` | `execution` | DIR:execution_core | 1 | 是 |
| 38 | `app/api/v1/endpoints/execution_core/_helpers.py` | `app/api/v1/endpoints/execution/execution_core/_helpers.py` | `execution` | DIR:execution_core | 4 | 是 |
| 39 | `app/api/v1/endpoints/execution_management.py` | `app/api/v1/endpoints/execution/execution_management.py` | `execution` | F03 | 1 | 是 |
| 40 | `app/api/v1/endpoints/execution_vis_config.py` | `app/api/v1/endpoints/execution/execution_vis_config.py` | `execution` | F03 | 1 | 是 |
| 41 | `app/api/v1/endpoints/execution_vis_schemas.py` | `app/api/v1/endpoints/execution/execution_vis_schemas.py` | `execution` | F03 | 2 | 是 |
| 42 | `app/api/v1/endpoints/execution_vis_video_replay.py` | `app/api/v1/endpoints/execution/execution_vis_video_replay.py` | `execution` | F03 | 1 | 是 |
| 43 | `app/api/v1/endpoints/execution_visualization.py` | `app/api/v1/endpoints/execution/execution_visualization.py` | `execution` | F03 | 1 | 是 |
| 44 | `app/api/v1/endpoints/feature_flag.py` | `app/api/v1/endpoints/common/feature_flag.py` | `common` | F16 | 1 | 是 |
| 45 | `app/api/v1/endpoints/file.py` | `app/api/v1/endpoints/common/file.py` | `common` | F15 | 1 | 是 |
| 46 | `app/api/v1/endpoints/file_batch_upload.py` | `app/api/v1/endpoints/common/file_batch_upload.py` | `common` | F15 | 1 | 是 |
| 47 | `app/api/v1/endpoints/file_export.py` | `app/api/v1/endpoints/common/file_export.py` | `common` | F15 | 4 | 是 |
| 48 | `app/api/v1/endpoints/file_management.py` | `app/api/v1/endpoints/common/file_management.py` | `common` | F15 | 1 | 是 |
| 49 | `app/api/v1/endpoints/file_upload.py` | `app/api/v1/endpoints/common/file_upload.py` | `common` | F15 | 6 | 是 |
| 50 | `app/api/v1/endpoints/generation_batch.py` | `app/api/v1/endpoints/case/generation_batch.py` | `case` | F11 | 1 | 是 |
| 51 | `app/api/v1/endpoints/history_asset.py` | `app/api/v1/endpoints/case/history_asset.py` | `case` | F10 | 1 | 是 |
| 52 | `app/api/v1/endpoints/impact_analysis.py` | `app/api/v1/endpoints/case/impact_analysis.py` | `case` | F13 | 1 | 是 |
| 53 | `app/api/v1/endpoints/iteration/__init__.py` | `app/api/v1/endpoints/pipeline/iteration/__init__.py` | `pipeline` | DIR:iteration | 4 | 是 |
| 54 | `app/api/v1/endpoints/iteration/_helpers.py` | `app/api/v1/endpoints/pipeline/iteration/_helpers.py` | `pipeline` | DIR:iteration | 2 | 是 |
| 55 | `app/api/v1/endpoints/iteration/_routes.py` | `app/api/v1/endpoints/pipeline/iteration/_routes.py` | `pipeline` | DIR:iteration | 1 | 是 |
| 56 | `app/api/v1/endpoints/mcp_server.py` | `app/api/v1/endpoints/agent/mcp_server.py` | `agent` | F01 | 1 | 是 |
| 57 | `app/api/v1/endpoints/mfa_endpoints.py` | `app/api/v1/endpoints/common/mfa_endpoints.py` | `common` | F16 | 1 | 是 |
| 58 | `app/api/v1/endpoints/oidc_endpoints.py` | `app/api/v1/endpoints/common/oidc_endpoints.py` | `common` | F16 | 1 | 是 |
| 59 | `app/api/v1/endpoints/pipeline.py` | `app/api/v1/endpoints/pipeline/pipeline.py` | `pipeline` | F08 | 14 | 是 |
| 60 | `app/api/v1/endpoints/pipeline_artifacts.py` | `app/api/v1/endpoints/pipeline/pipeline_artifacts.py` | `pipeline` | F08 | 9 | 是 |
| 61 | `app/api/v1/endpoints/pipeline_dashboard/__init__.py` | `app/api/v1/endpoints/pipeline/pipeline_dashboard/__init__.py` | `pipeline` | DIR:pipeline_dashboard | 18 | 是 |
| 62 | `app/api/v1/endpoints/pipeline_dashboard/_overview.py` | `app/api/v1/endpoints/pipeline/pipeline_dashboard/_overview.py` | `pipeline` | DIR:pipeline_dashboard | 1 | 是 |
| 63 | `app/api/v1/endpoints/pipeline_dashboard/_trends.py` | `app/api/v1/endpoints/pipeline/pipeline_dashboard/_trends.py` | `pipeline` | DIR:pipeline_dashboard | 2 | 是 |
| 64 | `app/api/v1/endpoints/pipeline_dashboard/_utils.py` | `app/api/v1/endpoints/pipeline/pipeline_dashboard/_utils.py` | `pipeline` | DIR:pipeline_dashboard | 2 | 是 |
| 65 | `app/api/v1/endpoints/pipeline_deps.py` | `app/api/v1/endpoints/pipeline/pipeline_deps.py` | `pipeline` | F08 | 4 | 是 |
| 66 | `app/api/v1/endpoints/pipeline_metrics.py` | `app/api/v1/endpoints/pipeline/pipeline_metrics.py` | `pipeline` | F08 | 1 | 是 |
| 67 | `app/api/v1/endpoints/pipeline_precheck.py` | `app/api/v1/endpoints/pipeline/pipeline_precheck.py` | `pipeline` | F08 | 2 | 是 |
| 68 | `app/api/v1/endpoints/pipeline_resume.py` | `app/api/v1/endpoints/pipeline/pipeline_resume.py` | `pipeline` | F08 | 7 | 是 |
| 69 | `app/api/v1/endpoints/pipeline_schemas.py` | `app/api/v1/endpoints/pipeline/pipeline_schemas.py` | `pipeline` | F08 | 4 | 是 |
| 70 | `app/api/v1/endpoints/project.py` | `app/api/v1/endpoints/common/project.py` | `common` | F15 | 1 | 是 |
| 71 | `app/api/v1/endpoints/project_config.py` | `app/api/v1/endpoints/common/project_config.py` | `common` | F15 | 2 | 是 |
| 72 | `app/api/v1/endpoints/project_core.py` | `app/api/v1/endpoints/common/project_core.py` | `common` | F15 | 11 | 是 |
| 73 | `app/api/v1/endpoints/project_members.py` | `app/api/v1/endpoints/common/project_members.py` | `common` | F15 | 1 | 是 |
| 74 | `app/api/v1/endpoints/prompt_template.py` | `app/api/v1/endpoints/common/prompt_template.py` | `common` | F14 | 1 | 是 |
| 75 | `app/api/v1/endpoints/quality_rule.py` | `app/api/v1/endpoints/review/quality_rule.py` | `review` | F06 | 1 | 是 |
| 76 | `app/api/v1/endpoints/quick_test.py` | `app/api/v1/endpoints/execution/quick_test.py` | `execution` | F03 | 3 | 是 |
| 77 | `app/api/v1/endpoints/report.py` | `app/api/v1/endpoints/pipeline/report.py` | `pipeline` | F09 | 1 | 是 |
| 78 | `app/api/v1/endpoints/requirement_link.py` | `app/api/v1/endpoints/case/requirement_link.py` | `case` | F13 | 1 | 是 |
| 79 | `app/api/v1/endpoints/requirement_link_crud.py` | `app/api/v1/endpoints/case/requirement_link_crud.py` | `case` | F13 | 2 | 是 |
| 80 | `app/api/v1/endpoints/requirement_link_fetch.py` | `app/api/v1/endpoints/case/requirement_link_fetch.py` | `case` | F13 | 1 | 是 |
| 81 | `app/api/v1/endpoints/review_inbox/__init__.py` | `app/api/v1/endpoints/review/review_inbox/__init__.py` | `review` | DIR:review_inbox | 3 | 是 |
| 82 | `app/api/v1/endpoints/review_inbox/_mutations.py` | `app/api/v1/endpoints/review/review_inbox/_mutations.py` | `review` | DIR:review_inbox | 1 | 是 |
| 83 | `app/api/v1/endpoints/review_inbox/_queries.py` | `app/api/v1/endpoints/review/review_inbox/_queries.py` | `review` | DIR:review_inbox | 1 | 是 |
| 84 | `app/api/v1/endpoints/review_inbox/_schemas.py` | `app/api/v1/endpoints/review/review_inbox/_schemas.py` | `review` | DIR:review_inbox | 3 | 是 |
| 85 | `app/api/v1/endpoints/saml_endpoints.py` | `app/api/v1/endpoints/common/saml_endpoints.py` | `common` | F16 | 1 | 是 |
| 86 | `app/api/v1/endpoints/self_healing.py` | `app/api/v1/endpoints/execution/self_healing.py` | `execution` | F03 | 1 | 是 |
| 87 | `app/api/v1/endpoints/test_capability.py` | `app/api/v1/endpoints/common/test_capability.py` | `common` | F17 | 1 | 是 |
| 88 | `app/api/v1/endpoints/test_case.py` | `app/api/v1/endpoints/case/test_case.py` | `case` | F11 | 1 | 是 |
| 89 | `app/api/v1/endpoints/test_case_ai.py` | `app/api/v1/endpoints/case/test_case_ai.py` | `case` | F11 | 4 | 是 |
| 90 | `app/api/v1/endpoints/test_case_ai_generate/__init__.py` | `app/api/v1/endpoints/case/test_case_ai_generate/__init__.py` | `case` | DIR:test_case_ai_generate | 21 | 是 |
| 91 | `app/api/v1/endpoints/test_case_ai_generate/_context.py` | `app/api/v1/endpoints/case/test_case_ai_generate/_context.py` | `case` | DIR:test_case_ai_generate | 10 | 是 |
| 92 | `app/api/v1/endpoints/test_case_ai_generate/_generate.py` | `app/api/v1/endpoints/case/test_case_ai_generate/_generate.py` | `case` | DIR:test_case_ai_generate | 11 | 是 |
| 93 | `app/api/v1/endpoints/test_case_ai_generate/_precondition.py` | `app/api/v1/endpoints/case/test_case_ai_generate/_precondition.py` | `case` | DIR:test_case_ai_generate | 2 | 是 |
| 94 | `app/api/v1/endpoints/test_case_ai_helpers.py` | `app/api/v1/endpoints/case/test_case_ai_helpers.py` | `case` | F11 | 2 | 是 |
| 95 | `app/api/v1/endpoints/test_case_ai_preview.py` | `app/api/v1/endpoints/case/test_case_ai_preview.py` | `case` | F11 | 2 | 是 |
| 96 | `app/api/v1/endpoints/test_case_ai_schemas.py` | `app/api/v1/endpoints/case/test_case_ai_schemas.py` | `case` | F11 | 10 | 是 |
| 97 | `app/api/v1/endpoints/test_case_ai_stream.py` | `app/api/v1/endpoints/case/test_case_ai_stream.py` | `case` | F11 | 20 | 是 |
| 98 | `app/api/v1/endpoints/test_case_crud.py` | `app/api/v1/endpoints/case/test_case_crud.py` | `case` | F11 | 3 | 是 |
| 99 | `app/api/v1/endpoints/test_case_crud_batch.py` | `app/api/v1/endpoints/case/test_case_crud_batch.py` | `case` | F11 | 1 | 是 |
| 100 | `app/api/v1/endpoints/test_case_export.py` | `app/api/v1/endpoints/case/test_case_export.py` | `case` | F11 | 1 | 是 |
| 101 | `app/api/v1/endpoints/test_case_lineage.py` | `app/api/v1/endpoints/case/test_case_lineage.py` | `case` | F11 | 1 | 是 |
| 102 | `app/api/v1/endpoints/test_case_status.py` | `app/api/v1/endpoints/case/test_case_status.py` | `case` | F11 | 1 | 是 |
| 103 | `app/api/v1/endpoints/test_case_version.py` | `app/api/v1/endpoints/case/test_case_version.py` | `case` | F11 | 1 | 是 |
| 104 | `app/api/v1/endpoints/test_case_workflow.py` | `app/api/v1/endpoints/case/test_case_workflow.py` | `case` | F11 | 1 | 是 |
| 105 | `app/api/v1/endpoints/test_data.py` | `app/api/v1/endpoints/case/test_data.py` | `case` | F12 | 1 | 是 |
| 106 | `app/api/v1/endpoints/test_point/__init__.py` | `app/api/v1/endpoints/test_point/__init__.py` | `test_point` | DIR:test_point | 6 | 是 |
| 107 | `app/api/v1/endpoints/test_point/_helpers.py` | `app/api/v1/endpoints/test_point/_helpers.py` | `test_point` | DIR:test_point | 6 | 是 |
| 108 | `app/api/v1/endpoints/test_point/_management.py` | `app/api/v1/endpoints/test_point/_management.py` | `test_point` | DIR:test_point | 1 | 是 |
| 109 | `app/api/v1/endpoints/test_point/_mutations.py` | `app/api/v1/endpoints/test_point/_mutations.py` | `test_point` | DIR:test_point | 1 | 是 |
| 110 | `app/api/v1/endpoints/test_point/_queries.py` | `app/api/v1/endpoints/test_point/_queries.py` | `test_point` | DIR:test_point | 1 | 是 |
| 111 | `app/api/v1/endpoints/test_point_extract.py` | `app/api/v1/endpoints/test_point/test_point_extract.py` | `test_point` | F02 | 1 | 是 |
| 112 | `app/api/v1/endpoints/test_point_import.py` | `app/api/v1/endpoints/test_point/test_point_import.py` | `test_point` | F02 | 5 | 是 |
| 113 | `app/api/v1/endpoints/test_point_import_stream.py` | `app/api/v1/endpoints/test_point/test_point_import_stream.py` | `test_point` | F02 | 2 | 是 |
| 114 | `app/api/v1/endpoints/test_task.py` | `app/api/v1/endpoints/execution/test_task.py` | `execution` | F03 | 2 | 是 |
| 115 | `app/api/v1/endpoints/test_task_exec.py` | `app/api/v1/endpoints/execution/test_task_exec.py` | `execution` | F03 | 1 | 是 |
| 116 | `app/api/v1/endpoints/test_task_helpers.py` | `app/api/v1/endpoints/execution/test_task_helpers.py` | `execution` | F03 | 1 | 是 |
| 117 | `app/api/v1/endpoints/ui_prototype/__init__.py` | `app/api/v1/endpoints/case/ui_prototype/__init__.py` | `case` | DIR:ui_prototype | 14 | 是 |
| 118 | `app/api/v1/endpoints/ui_prototype/_parse_helpers.py` | `app/api/v1/endpoints/case/ui_prototype/_parse_helpers.py` | `case` | DIR:ui_prototype | 0 | 否 |
| 119 | `app/api/v1/endpoints/ui_prototype/_project_endpoints_flow.py` | `app/api/v1/endpoints/case/ui_prototype/_project_endpoints_flow.py` | `case` | DIR:ui_prototype | 1 | 是 |
| 120 | `app/api/v1/endpoints/ui_prototype/_project_endpoints_routes.py` | `app/api/v1/endpoints/case/ui_prototype/_project_endpoints_routes.py` | `case` | DIR:ui_prototype | 1 | 是 |
| 121 | `app/api/v1/endpoints/ui_prototype/_upload_helpers.py` | `app/api/v1/endpoints/case/ui_prototype/_upload_helpers.py` | `case` | DIR:ui_prototype | 0 | 否 |
| 122 | `app/api/v1/endpoints/ui_prototype/helpers.py` | `app/api/v1/endpoints/case/ui_prototype/helpers.py` | `case` | DIR:ui_prototype | 7 | 是 |
| 123 | `app/api/v1/endpoints/ui_prototype/parse_endpoints.py` | `app/api/v1/endpoints/case/ui_prototype/parse_endpoints.py` | `case` | DIR:ui_prototype | 3 | 是 |
| 124 | `app/api/v1/endpoints/ui_prototype/project_endpoints.py` | `app/api/v1/endpoints/case/ui_prototype/project_endpoints.py` | `case` | DIR:ui_prototype | 3 | 是 |
| 125 | `app/api/v1/endpoints/ui_prototype/screen_endpoints.py` | `app/api/v1/endpoints/case/ui_prototype/screen_endpoints.py` | `case` | DIR:ui_prototype | 1 | 是 |
| 126 | `app/api/v1/endpoints/ui_prototype/screen_endpoints_manage.py` | `app/api/v1/endpoints/case/ui_prototype/screen_endpoints_manage.py` | `case` | DIR:ui_prototype | 1 | 是 |
| 127 | `app/api/v1/endpoints/ui_prototype.py` | `app/api/v1/endpoints/case/ui_prototype.py` | `case` | F13 | 18 | 是 |
| 128 | `app/api/v1/endpoints/ui_screens_batch.py` | `app/api/v1/endpoints/execution/ui_screens_batch.py` | `execution` | F03 | 2 | 是 |
| 129 | `app/api/v1/endpoints/user.py` | `app/api/v1/endpoints/common/user.py` | `common` | F15 | 6 | 是 |
| 130 | `app/api/v1/endpoints/visibility.py` | `app/api/v1/endpoints/review/visibility.py` | `review` | F06 | 1 | 是 |
| 131 | `app/api/v1/endpoints/visual_ai.py` | `app/api/v1/endpoints/execution/visual_ai.py` | `execution` | F03 | 1 | 是 |
| 132 | `app/api/v1/endpoints/websocket.py` | `app/api/v1/endpoints/common/websocket.py` | `common` | F18 | 1 | 是 |

## 五、边界判定说明（评审重点）

| 对象 | 归属 | 理由 |
| --- | --- | --- |
| `services/self_healing`、`services/decision_application_service` | execution | 自愈发生在执行期，决策应用对象是执行结果 |
| `services/cost_statistics` | execution | 统计对象是视觉 AI 调用成本（执行期产生） |
| `services/self_test` | pipeline | 全链路 9 步自测，属流水线编排能力 |
| `services/url_driven` | case | 站点探索 → 自动建项 → 用例生成，主产出是用例 |
| `services/lifecycle_service` | case | 状态机服务对象为用例/任务生命周期 |
| `services/prompt_builder` | common | 同时服务用例生成 / 测试数据 / UI 解析，跨域共享 |
| `services/saml`、`services/role_service`、`services/user_service`、`services/storage` | common | 认证与基础设施，不属于任何业务域 |
| `services/visibility_config`、`endpoints/visibility` | review | 可见范围用于评审可见性控制 |
| `endpoints/iteration`、`endpoints/pipeline_dashboard` | pipeline | 迭代与流水线看板同属交付流程运营 |
| `endpoints/bug` | review | 缺陷由评审/质检环节产生并闭环 |

## 六、阶段一验收

- [x] 覆盖 **553/553**，未归类 **0**（判据：零未归类）
- [x] 每行含「现有路径 → 目标路径 → 归属域 → 是否保留 shim」四要素
- [ ] 评审通过后进入阶段二（按域 6 批物理移动 + shim 保留一个迭代）
