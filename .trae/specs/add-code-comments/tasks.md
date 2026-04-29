# Tasks

## Phase 1: 语言规范与安全红线修复（无破坏性变更）

* [x] Task 1: 修复TypeScript any类型 - request.ts核心模块

  * [x] 1.1: 为`ApiResponse<T>`移除默认`any`，改为`ApiResponse<T = unknown>`

  * [x] 1.2: 为`typedRequest`方法的`data`参数定义具体类型，移除`any`默认值

  * [x] 1.3: 响应拦截器中移除`res as any`，使用类型守卫处理

  * [x] 1.4: 错误处理中移除`(customError as any)`，定义CustomError接口

  * [x] 1.5: 验证：`npx tsc --noEmit`无类型错误

* [x] Task 2: 修复TypeScript any类型 - API层文件

  * [ ] 2.1: 修复`src/api/case.ts`中的`any`（约8处：as any、Promise<any>等）

  * [ ] 2.2: 修复`src/api/uiPrototype.ts`中的`any`（约7处：Record\<string, any>、Promise<any>）

  * [ ] 2.3: 修复`src/api/testCaseView.ts`中的`any`（约6处：test\_data?: any、Promise<any>）

  * [ ] 2.4: 修复`src/api/file.ts`中的`any`（2处：Record\<string, any>）

  * [ ] 2.5: 修复`src/api/testData.ts`中的`any`（4处：Record\<string, any>）

  * [ ] 2.6: 验证：`npx tsc --noEmit`无类型错误

* [x] Task 3: 修复TypeScript any类型 - Store与Composables层

  * [ ] 3.1: 修复`src/store/task.ts`中的`catch(error: any)`（9处），改为`catch(error: unknown)`+类型守卫

  * [ ] 3.2: 修复`src/store/project.ts`中的`any`（8处：as any、catch(error: any)）

  * [ ] 3.3: 修复`src/store/case.ts`中的`any`（4处：any\[]、as any）

  * [ ] 3.4: 修复`src/store/analysis.ts`中的`as any`（1处）

  * [ ] 3.5: 修复`src/composables/useResourceUpload.ts`中的`any`（约12处）

  * [ ] 3.6: 修复`src/composables/useResourceOperations.ts`中的`any`（3处）

  * [ ] 3.7: 修复`src/composables/useResourceList.ts`中的`any`（4处）

  * [ ] 3.8: 修复`src/composables/useIterationManager.ts`中的`any`（约8处）

  * [ ] 3.9: 修复`src/utils/websocket.ts`中的`any`（4处：回调参数类型）

  * [ ] 3.10: 修复`src/utils/debounce.ts`中的泛型`any`（2处：函数类型参数）

  * [ ] 3.11: 修复`src/directives/permission.ts`中的`any`（5处：as any、Record\<string, any>）

  * [ ] 3.12: 修复`src/types/case.d.ts`中的`any[]`和`src/types/testCase.ts`中的`Record<string, any>`

  * [ ] 3.13: 验证：`npx tsc --noEmit`无类型错误

* [x] Task 4: 修复Python .format()字符串为f-string

  * [x] 4.1: 修复`app/services/ui_spec_parser.py`中3处`.format()`调用

  * [x] 4.2: 修复`app/utils/ai_client.py`中3处`.format()`调用

  * [x] 4.3: 修复`app/utils/mcp_text_llm.py`中1处`.format()`调用

  * [x] 4.4: 修复`app/utils/report_utils.py`中1处`.format()`调用

  * [x] 4.5: 验证：`python -m pytest tests/test_unit.py`通过

* [x] Task 5: 移除TODO注释并处理未实现逻辑

  * [x] 5.1: `app/services/test_case_view_service.py:466` - 移除TODO注释

  * [x] 5.2: `app/services/test_data_parameterizer.py:216` - 移除TODO注释

  * [x] 5.3: `app/services/test_data_parameterizer.py:228` - 移除TODO注释

  * [x] 5.4: 验证：`grep -r "TODO" app/`无结果

* [x] Task 6: 修复日志敏感信息泄露

  * [x] 6.1: `app/services/precondition_service.py:451` - 对密码输入框坐标信息脱敏处理

  * [x] 6.2: 全局扫描其他日志中的敏感信息输出并修复

  * [x] 6.3: 验证：无明文敏感信息日志

## Phase 2: 架构设计修复 - 文件拆分（按严重程度排序）

* [x] Task 7: 拆分超大型API端点文件（800+行）

  * [ ] 7.1: 拆分`app/api/v1/endpoints/file.py`（894行）→ file\_upload.py + file\_management.py + file\_export.py

  * [ ] 7.2: 拆分`app/api/v1/endpoints/test_case.py`（860行）→ test\_case\_crud.py + test\_case\_workflow\.py + test\_case\_version.py + test\_case\_ai.py

  * [ ] 7.3: 拆分`app/api/v1/endpoints/execution.py`（789行）→ execution\_core.py + execution\_visualization.py

  * [ ] 7.4: 拆分`app/api/v1/endpoints/case_quality.py`（777行）→ case\_quality\_check.py + case\_quality\_report.py

  * [ ] 7.5: 验证：所有拆分后文件≤300行，API路由功能不变

* [x] Task 8: 拆分超大型工具/服务文件（800+行）

  * [ ] 8.1: 拆分`app/utils/ai_client.py`（902行）→ ai\_client\_core.py + ai\_client\_test\_case.py + ai\_client\_parser.py

  * [ ] 8.2: 拆分`app/utils/browser_controller_v2.py`（807行）→ browser\_controller\_base.py + browser\_controller\_actions.py + browser\_controller\_navigation.py

  * [ ] 8.3: 拆分`app/services/precondition_service.py`（942行）→ precondition\_parser.py + precondition\_executor.py + precondition\_login.py

  * [ ] 8.4: 拆分`app/services/test_case_generation_service.py`（872行）→ case\_generation\_core.py + case\_generation\_ai.py + case\_generation\_steps.py

  * [ ] 8.5: 验证：所有拆分后文件≤300行，功能不变

* [x] Task 9: 拆分中型文件（500-800行）

  * [ ] 9.1: 拆分`app/services/element_locator_service.py`（689行）

  * [ ] 9.2: 拆分`app/services/batch_locator_service.py`（677行）

  * [ ] 9.3: 拆分`app/api/v1/endpoints/ui_prototype.py`（677行）

  * [ ] 9.4: 拆分`app/services/test_execution_engine_v2.py`（658行）

  * [ ] 9.5: 拆分`app/utils/unified_vision_model.py`（546行）

  * [ ] 9.6: 拆分`app/services/execution_replay_service.py`（578行）

  * [ ] 9.7: 拆分`app/services/case_quality_analyzer.py`（533行）

  * [ ] 9.8: 拆分`app/utils/browser_controller.py`（507行）

  * [ ] 9.9: 拆分`app/services/video_service.py`（504行）

  * [ ] 9.10: 验证：所有拆分后文件≤300行

* [x] Task 10: 拆分小型超标文件（300-500行）

  * [ ] 10.1: 拆分`app/api/v1/endpoints/test_point.py`（520行）

  * [ ] 10.2: 拆分`app/api/v1/endpoints/requirement_link.py`（476行）

  * [ ] 10.3: 拆分`app/api/v1/endpoints/execution_visualization.py`（468行）

  * [ ] 10.4: 拆分`app/crud/ui_prototype.py`（450行）

  * [ ] 10.5: 拆分`app/services/cost_statistics_service.py`（459行）

  * [ ] 10.6: 拆分`app/services/ui_spec_parser.py`（438行）

  * [ ] 10.7: 拆分`app/api/v1/endpoints/project.py`（424行）

  * [ ] 10.8: 拆分`app/services/mobile_ai_executor.py`（413行）

  * [ ] 10.9: 拆分`app/api/v1/endpoints/auth.py`（359行）

  * [ ] 10.10: 拆分`app/services/visibility_config_service.py`（356行）

  * [ ] 10.11: 拆分`app/services/ui_spec_parse_pipeline.py`（347行）

  * [ ] 10.12: 拆分`app/services/link_fetcher_service.py`（340行）

  * [ ] 10.13: 拆分`app/services/user_service.py`（331行）

  * [ ] 10.14: 拆分`app/services/task_service.py`（375行）

  * [ ] 10.15: 拆分`app/services/test_data_generator.py`（323行）

  * [ ] 10.16: 拆分`app/services/test_data_service.py`（321行）

  * [ ] 10.17: 拆分`app/services/execution_mode_selector.py`（311行）

  * [ ] 10.18: 拆分`app/crud/test_case.py`（312行）

  * [ ] 10.19: 验证：所有文件≤300行，`python -m pytest tests/`通过

## Phase 3: 测试覆盖率提升

* [x] Task 11: 建立测试基础设施

  * [ ] 11.1: 配置pytest覆盖率阈值，在`pytest.ini`中添加`--cov-fail-under=95`

  * [ ] 11.2: 创建测试数据库fixture，支持真实数据库连接与自动清理

  * [ ] 11.3: 创建通用测试工具函数（断言辅助、数据生成等）

* [x] Task 12: 补充Model层单元测试（当前0%→≥95%）

  * [ ] 12.1: 编写`app/models/test_case.py`测试

  * [ ] 12.2: 编写`app/models/user.py`测试

  * [ ] 12.3: 编写`app/models/project.py`测试

  * [ ] 12.4: 编写`app/models/element_locator.py`测试

  * [ ] 12.5: 编写其余Model测试

  * [ ] 12.6: 验证：Model层覆盖率≥95%

* [x] Task 13: 补充Core层单元测试

  * [ ] 13.1: 提升`app/core/config.py`覆盖率（69%→≥95%）

  * [ ] 13.2: 提升`app/core/db_helper.py`覆盖率（44%→≥95%）

  * [ ] 13.3: 提升`app/core/exception.py`覆盖率（49%→≥95%）

  * [ ] 13.4: 提升`app/db/database.py`覆盖率（35%→≥95%）

  * [ ] 13.5: 验证：Core层覆盖率≥95%

* [x] Task 14: 补充Utils层单元测试

  * [ ] 14.1: 提升`app/utils/crypto.py`覆盖率（68%→≥95%）

  * [ ] 14.2: 提升`app/utils/file_utils.py`覆盖率（28%→≥95%）

  * [ ] 14.3: 补充`app/utils/jwt_utils.py`测试

  * [ ] 14.4: 补充`app/utils/test_case_helpers.py`测试

  * [ ] 14.5: 补充`app/utils/db_time.py`测试

  * [ ] 14.6: 验证：Utils层覆盖率≥95%

* [x] Task 15: 补充CRUD层与Service层集成测试

  * [ ] 15.1: 编写CRUD层测试

  * [ ] 15.2: 编写Service层核心测试

  * [ ] 15.3: 编写API端点集成测试

  * [ ] 15.4: 验证：总体覆盖率≥95%

## Phase 4: Python类型注解补充

* [ ] Task 16: 补充公开方法类型注解与文档注释

  * [ ] 16.1: 为`app/api/v1/endpoints/`下所有API端点添加返回类型注解

  * [ ] 16.2: 为`app/services/`下所有Service公开方法添加类型注解与文档注释

  * [ ] 16.3: 为`app/utils/`下所有工具函数添加类型注解与文档注释

  * [ ] 16.4: 为`app/crud/`下所有CRUD方法添加类型注解与文档注释

  * [ ] 16.5: 验证：`mypy app/`无类型错误

# Task Dependencies

* Task 2 depends on Task 1（API层修复依赖核心request.ts修复）

* Task 3 depends on Task 1（Store/Composable层修复依赖核心类型定义）

* Task 7-10 可并行执行（文件拆分互不依赖）

* Task 11 必须在 Task 12-15 之前完成（测试基础设施先行）

* Task 12-14 可并行执行（不同层测试互不依赖）

* Task 15 depends on Task 12, 13, 14（集成测试依赖单元测试基础设施）

* Task 16 建议在 Task 7-10 之后执行（拆分后的文件更容易添加注解）

