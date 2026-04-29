# 测试用例双视图功能恢复 - The Implementation Plan (Decomposed and Prioritized Task List)

## [x] Task 1: 实现后端技术视图API路由
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 在 `app/api/v1/endpoints/test_case.py` 中添加 `/testCase/{test_case_id}/technical-view` 路由
  - 使用已有的 `TestCaseViewService.get_technical_view()` 方法
  - 正确处理响应格式，使用 `create_response()` 包装
- **Acceptance Criteria Addressed**: [AC-6]
- **Test Requirements**:
  - `programmatic` TR-1.1: GET /api/v1/testCase/{id}/technical-view 返回 200 状态码
  - `programmatic` TR-1.2: 响应包含 data.steps 数组
  - `programmatic` TR-1.3: 响应包含 data.locator_coverage 字段
  - `human-judgement` TR-1.4: 代码风格与现有路由一致
- **Notes**: 不需要修改 TestCaseViewService，直接使用现有方法
- **Status**: ✅ Completed

## [x] Task 2: 实现后端业务视图API路由
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 在 `app/api/v1/endpoints/test_case.py` 中添加 `/testCase/{test_case_id}/business-view` 路由
  - 使用已有的 `TestCaseViewService.get_business_view()` 方法
  - 正确处理响应格式，使用 `create_response()` 包装
- **Acceptance Criteria Addressed**: [AC-2]
- **Test Requirements**:
  - `programmatic` TR-2.1: GET /api/v1/testCase/{id}/business-view 返回 200 状态码
  - `programmatic` TR-2.2: 响应包含 data.steps 数组
  - `human-judgement` TR-2.3: 代码风格与现有路由一致
- **Notes**: 业务视图也可以通过现有的 getCase 接口获取，本任务是为了完整性
- **Status**: ✅ Completed

## [x] Task 3: 更新前端详情页面添加视图切换状态管理
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 在 `src/views/case/CaseDetail.vue` 中添加 `currentView` 状态，默认为 'business'
  - 导入 `testCaseViewApi` 用于调用后端API
  - 添加获取技术视图数据的函数 `fetchTechnicalView()`
  - 添加获取业务视图数据的函数 `fetchBusinessView()`
- **Acceptance Criteria Addressed**: [AC-1]
- **Test Requirements**:
  - `programmatic` TR-3.1: 组件有 `currentView` 状态变量
  - `programmatic` TR-3.2: 导入了 `testCaseViewApi`
  - `human-judgement` TR-3.3: 代码有清晰的注释说明状态用途
- **Status**: ✅ Completed

## [x] Task 4: 在前端详情页面添加视图切换UI
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 
  - 在页面顶部（标题右侧、编辑按钮左侧）添加视图切换按钮组
  - 使用 Element Plus 的 `el-radio-group` 或两个按钮组件
  - 视图切换按钮在编辑模式下隐藏（`v-if="!isEditing"`）
  - 添加样式，确保切换按钮美观且与现有布局协调
- **Acceptance Criteria Addressed**: [AC-1, AC-5]
- **Test Requirements**:
  - `human-judgement` TR-4.1: 页面顶部显示业务/技术视图切换按钮
  - `human-judgement` TR-4.2: 编辑模式下切换按钮隐藏
  - `human-judgement` TR-4.3: 按钮样式与现有设计风格一致
- **Status**: ✅ Completed

## [x] Task 5: 实现前端业务视图展示
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 
  - 业务视图使用现有的表格展示（已经在 `businessSteps` 中）
  - 确保步骤数据正确显示（操作、预期结果）
  - 保持现有表格的样式和功能
- **Acceptance Criteria Addressed**: [AC-2]
- **Test Requirements**:
  - `human-judgement` TR-5.1: 业务视图显示操作和预期结果两列
  - `human-judgement` TR-5.2: 步骤编号正确显示
  - `programmatic` TR-5.3: 空状态正确处理
- **Status**: ✅ Completed

## [x] Task 6: 实现前端技术视图展示
- **Priority**: P0
- **Depends On**: Task 1, Task 3
- **Description**: 
  - 创建技术视图的表格展示组件
  - 显示步骤、操作、预期结果、定位状态、CSS选择器、XPath等信息
  - 使用标签或颜色标识定位状态（pending/located/failed）
  - 在顶部显示定位覆盖率统计
  - 使用 `v-if="currentView === 'technical'"` 控制显示
- **Acceptance Criteria Addressed**: [AC-3, AC-4]
- **Test Requirements**:
  - `human-judgement` TR-6.1: 技术视图显示定位信息列
  - `human-judgement` TR-6.2: 定位状态有视觉标识（颜色/标签）
  - `human-judgement` TR-6.3: 顶部显示定位覆盖率
  - `programmatic` TR-6.4: 表格数据正确绑定
- **Status**: ✅ Completed

## [x] Task 7: 实现视图切换逻辑
- **Priority**: P0
- **Depends On**: Task 1, Task 3, Task 6
- **Description**: 
  - 绑定视图切换按钮到 `currentView` 状态
  - 切换时调用对应的API获取数据
  - 添加加载状态，切换时显示loading
  - 错误处理，API失败时显示错误提示
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4]
- **Test Requirements**:
  - `human-judgement` TR-7.1: 点击切换按钮视图正确切换
  - `human-judgement` TR-7.2: 切换时有加载状态提示
  - `programmatic` TR-7.3: 错误时显示友好提示
- **Status**: ✅ Completed

## [x] Task 8: 集成测试与验证
- **Priority**: P1
- **Depends On**: Task 1, Task 6, Task 7
- **Description**: 
  - 手动测试整个流程：进入详情页 → 切换视图 → 查看数据 → 进入编辑 → 返回查看
  - 验证所有功能正常工作
  - 检查代码诊断无错误
  - 运行项目确认可以正常启动
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
- **Test Requirements**:
  - `human-judgement` TR-8.1: 所有验收条件通过人工验证
  - `programmatic` TR-8.2: GetDiagnostics 无 TypeScript/ESLint 错误
  - `human-judgement` TR-8.3: 项目可以正常启动
- **Status**: ✅ Completed
