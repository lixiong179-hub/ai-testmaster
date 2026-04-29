# 测试点提取页面优化 - 实现计划

## 任务分解与优先级

### [x] 任务1: 在侧边菜单中添加测试点提取菜单项
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 在 `MainLayout.vue` 的测试用例管理子菜单中添加测试点提取菜单项
  - 确保菜单项能够正确跳转到测试点提取页面
- **Success Criteria**:
  - 侧边菜单中显示测试点提取菜单项
  - 点击菜单项能够正确跳转到测试点提取页面
- **Test Requirements**:
  - `programmatic` TR-1.1: 侧边菜单中存在测试点提取菜单项
  - `programmatic` TR-1.2: 点击菜单项后URL正确跳转到 `/home/case/test-point-extract`
  - `human-judgment` TR-1.3: 菜单项显示位置合理，符合整体菜单结构

### [x] 任务2: 更新面包屑导航映射
- **Priority**: P0
- **Depends On**: 任务1
- **Description**:
  - 在 `MainLayout.vue` 的面包屑导航映射中添加测试点提取页面的路径
  - 确保面包屑导航能够正确显示测试点提取页面的路径
- **Success Criteria**:
  - 测试点提取页面的面包屑导航显示正确
  - 不再显示"未知页面"
- **Test Requirements**:
  - `programmatic` TR-2.1: 测试点提取页面的面包屑导航显示正确路径
  - `human-judgment` TR-2.2: 面包屑导航显示美观，符合整体设计风格

### [x] 任务3: 优化测试点提取页面，以项目维度隔离
- **Priority**: P1
- **Depends On**: 任务1, 任务2
- **Description**:
  - 修改测试点提取页面，添加项目选择功能
  - 确保测试点提取功能以项目维度隔离
  - 优化页面布局和用户体验
- **Success Criteria**:
  - 测试点提取页面能够选择项目
  - 提取的测试点与项目关联
  - 页面布局美观，用户体验良好
- **Test Requirements**:
  - `programmatic` TR-3.1: 页面能够选择项目并提取对应项目的测试点
  - `human-judgment` TR-3.2: 页面布局美观，操作流程清晰

## 实现步骤

1. 在侧边菜单中添加测试点提取菜单项
2. 更新面包屑导航映射
3. 优化测试点提取页面，以项目维度隔离
4. 测试完整流程

## 技术要点

- 前端：Vue 3 + Element Plus
- 后端：FastAPI + SQLAlchemy
- 数据流：项目选择 → 需求文件选择 → 测试点提取 → 测试用例生成

## 预期效果

通过优化，测试点提取页面将成为系统中的一个正式功能模块，具有良好的用户体验和清晰的项目维度隔离，使测试工程师能够更方便地进行测试点提取和管理。