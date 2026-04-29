# 测试用例生成模块重构 - 实现计划

## [ ] Task 1: 重构AI生成测试用例前端页面
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 重写 ai-generate.vue 页面
  - 添加项目选择、需求文件选择、测试点选择的完整流程UI
  - 实现测试用例预览和编辑功能
  - 实现批量生成和批量保存按钮
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-6]
- **Test Requirements**:
  - `programmatic` TR-1.1: 页面加载后显示三个选择步骤（项目、需求文件、测试点）
  - `programmatic` TR-1.2: 选择项目后能够加载该项目的需求文件
  - `programmatic` TR-1.3: 选择需求文件后能够显示测试点列表
  - `programmatic` TR-1.4: 测试用例生成后能够预览并编辑任意用例
  - `human-judgement` TR-1.5: UI布局清晰，流程引导明确
- **Notes**: 参考现有 test-point-extract.vue 的代码风格和组件使用方式

## [ ] Task 2: 改进后端测试用例生成API
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 在 test_case.py 中添加支持批量生成测试用例的新API端点
  - 新API应支持接收项目ID、需求文件ID、测试点列表作为参数
  - 为每个测试点调用AI生成对应的测试用例
  - 支持批量创建测试用例到数据库
- **Acceptance Criteria Addressed**: [AC-4, AC-7]
- **Test Requirements**:
  - `programmatic` TR-2.1: 新增API端点能够接收项目、文件、测试点参数
  - `programmatic` TR-2.2: API能够为多个测试点生成对应的测试用例
  - `programmatic` TR-2.3: API能够批量保存测试用例到数据库
  - `programmatic` TR-2.4: API返回生成的测试用例列表
- **Notes**: 保持向后兼容，保留现有的 ai-generate 端点

## [ ] Task 3: 优化AI提示词，生成更具体可执行的测试用例
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改 ai_client.py 中的提示词模板
  - 提示词要求生成包含更详细操作步骤的测试用例
  - 步骤应包含具体的操作描述、元素定位提示、预期结果验证方法
  - 确保生成的测试用例能够支持手工测试执行
- **Acceptance Criteria Addressed**: [AC-5]
- **Test Requirements**:
  - `human-judgement` TR-3.1: 生成的测试用例包含详细的前置条件
  - `human-judgement` TR-3.2: 每个测试步骤包含具体的操作描述
  - `human-judgement` TR-3.3: 每个步骤有明确的预期结果
  - `human-judgement` TR-3.4: 测试用例可以手工执行
- **Notes**: 可以参考手工测试用例的标准格式

## [ ] Task 4: 实现批量生成和批量保存功能
- **Priority**: P1
- **Depends On**: [Task 1, Task 2]
- **Description**: 
  - 前端实现测试点多选功能
  - 前端显示批量生成进度
  - 前端处理部分失败的情况
  - 前端实现批量保存功能，支持选择要保存的用例
- **Acceptance Criteria Addressed**: [AC-4, AC-7]
- **Test Requirements**:
  - `programmatic` TR-4.1: 支持多选测试点
  - `programmatic` TR-4.2: 显示批量生成进度条
  - `programmatic` TR-4.3: 批量保存时支持选择用例
  - `programmatic` TR-4.4: 部分失败时有错误提示和重试选项
- **Notes**: 考虑大数量测试点的性能问题

## [ ] Task 5: 测试并验证完整流程
- **Priority**: P0
- **Depends On**: [Task 1, Task 2, Task 3, Task 4]
- **Description**: 
  - 端到端测试完整流程
  - 测试需求文档上传 → 测试点提取 → 测试用例生成 → 保存用例 → 查看用例列表
  - 验证生成的测试用例质量
  - 编写单元测试
- **Acceptance Criteria Addressed**: [AC-8]
- **Test Requirements**:
  - `programmatic` TR-5.1: 完整流程可以顺利执行
  - `programmatic` TR-5.2: 保存的测试用例在项目用例列表中可见
  - `programmatic` TR-5.3: 核心功能单元测试覆盖率≥90%
  - `human-judgement` TR-5.4: 测试用例质量符合预期，可以手工执行
- **Notes**: 遵循项目规则，使用真实MySQL数据库，不使用Mock
