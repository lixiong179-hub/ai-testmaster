# 测试用例双视图功能恢复 - Product Requirement Document

## Overview
- **Summary**: 恢复测试用例详情页面的业务视图和技术视图切换功能，这是之前被意外移除的核心特性。业务视图面向产品经理和第三方验收，以自然语言描述；技术视图面向测试工程师，包含结构化操作和元素定位信息。
- **Purpose**: 解决当前详情页面缺少双视图切换的问题，恢复完整的测试用例查看和编辑体验。
- **Target Users**: 产品经理、测试工程师、自动化测试开发人员、第三方验收人员

## Goals
- 恢复业务视图和技术视图的切换按钮
- 实现业务视图数据的获取和展示（自然语言描述）
- 实现技术视图数据的获取和展示（结构化操作+定位信息）
- 保持现有页面的编辑、复制等功能
- 提供定位覆盖率统计信息展示

## Non-Goals (Out of Scope)
- 不实现新的视图类型（除了业务和技术视图）
- 不修改测试用例创建流程
- 不实现视图导出功能（Excel/Markdown等，可后续迭代）
- 不实现视图配置批量更新功能（可后续迭代）

## Background & Context
- 原项目已经有完整的 `test_case_view_service.py` 双视图服务实现
- 前端API `testCaseView.ts` 已经定义了完整的接口类型
- 之前的详情页面 `detail.vue` 有双视图功能，但在优化时被意外移除
- 当前详情页面 `CaseDetail.vue` 只有单一视图，缺少切换功能
- 后端API路由缺少 `/testCase/{id}/technical-view` 等接口

## Functional Requirements
- **FR-1**: 在详情页面顶部显示业务视图/技术视图切换按钮
- **FR-2**: 业务视图显示：自然语言描述的测试步骤（面向产品/验收）
- **FR-3**: 技术视图显示：结构化操作步骤 + 元素定位信息（CSS/XPath/AI坐标）
- **FR-4**: 在技术视图中显示定位覆盖率统计
- **FR-5**: 切换视图时保持页面其他功能（编辑、复制、返回）正常工作

## Non-Functional Requirements
- **NFR-1**: 视图切换响应时间 < 200ms
- **NFR-2**: 在编辑模式下隐藏视图切换按钮
- **NFR-3**: 技术视图中定位信息显示清晰，有视觉标识
- **NFR-4**: 保持代码的可维护性和可扩展性

## Constraints
- **Technical**: 前端使用 Vue3 + TypeScript + Element Plus；后端使用 FastAPI + SQLAlchemy
- **Business**: 必须保持与现有代码风格一致
- **Dependencies**: 依赖已有的 `test_case_view_service.py` 服务和 `testCaseView.ts` 前端API

## Assumptions
- 后端已有 `TestCaseViewService` 服务实现可以直接使用
- 前端已有 `testCaseViewApi` 可以直接引入使用
- 测试步骤数据存储在 `TestStep` 表中，并有 `is_business_view` 和 `is_technical_view` 字段
- 元素定位信息存储在 `ElementLocator` 表中

## Acceptance Criteria

### AC-1: 视图切换按钮可见
- **Given**: 用户进入测试用例详情页面且不在编辑模式
- **When**: 页面加载完成
- **Then**: 页面顶部显示"业务视图"和"技术视图"两个按钮，默认为业务视图
- **Verification**: `human-judgment`

### AC-2: 业务视图显示正确
- **Given**: 用户选择业务视图
- **When**: 页面渲染
- **Then**: 显示自然语言描述的测试步骤（操作、预期结果）
- **Verification**: `programmatic` + `human-judgment`

### AC-3: 技术视图显示正确
- **Given**: 用户选择技术视图
- **When**: 页面渲染
- **Then**: 显示结构化步骤，包含元素定位信息（CSS选择器、XPath、AI坐标等）
- **Verification**: `programmatic` + `human-judgment`

### AC-4: 定位覆盖率显示
- **Given**: 用户选择技术视图
- **When**: 页面渲染
- **Then**: 顶部显示定位覆盖率统计（已定位步骤数/总步骤数）
- **Verification**: `programmatic`

### AC-5: 编辑模式不显示切换按钮
- **Given**: 用户点击"编辑"进入编辑模式
- **When**: 页面切换到编辑模式
- **Then**: 视图切换按钮隐藏
- **Verification**: `human-judgment`

### AC-6: 后端API可用
- **Given**: 系统运行中
- **When**: 调用 GET /api/v1/testCase/{id}/technical-view
- **Then**: 返回技术视图数据，包含 steps 数组和 locator_coverage
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要在技术视图中显示元素定位状态（pending/located/failed）的视觉标识？
- [ ] 是否需要在两个视图中都可以编辑，还是仅在业务视图可编辑？
- [ ] 是否需要实现视图配置（哪些步骤在哪个视图显示）的功能？
