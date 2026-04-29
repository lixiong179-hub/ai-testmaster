# UI原型图资源管理集成 - 实施计划

## [ ] Task 1: 研究现有UI原型管理模块
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 阅读完整的 ui_prototype.py 模型和接口代码
  - 检查 ui_prototype API 的 schema 文件
  - 理解 UISpecParsePipeline 和相关服务
  - 确认数据库表结构完整可用
- **Acceptance Criteria Addressed**: [AC-1, AC-4]
- **Test Requirements**:
  - `programmatic` TR-1.1: UIPrototypeProject 和 UIPrototypeScreen 模型完整可用
  - `programmatic` TR-1.2: /api/v1/ui-prototype/screens/{project_id} 接口能正常返回
  - `human-judgement` TR-1.3: 代码库中有完整的 UI 原型上传、解析、管理功能

## [ ] Task 2: 开发 UI 原型 API 的前端调用层
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 在 src/api 目录下完善 uiPrototype.ts API 调用封装
  - 新增获取原型项目列表、获取屏幕列表等接口方法
  - 新增类型定义（UIPrototypeProject、UIScreen 等）
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-5]
- **Test Requirements**:
  - `programmatic` TR-2.1: uiPrototype.ts 文件有完整的类型定义
  - `programmatic` TR-2.2: API 方法覆盖了获取原型项目列表、屏幕列表等需求
  - `programmatic` TR-2.3: 前端编译通过无类型错误

## [ ] Task 3: 改造 resource-manage.vue 列表展示逻辑
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 修改 getResources 函数，当资源类型为 ui_mockup 或 "全部" 时，同时获取 ProjectFile 和 UIPrototypeProject 数据
  - 将两种数据源合并为统一的列表格式
  - UI原型项目显示为单一资源项，含原型名称、屏幕数量等信息
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-5]
- **Test Requirements**:
  - `programmatic` TR-3.1: 列表同时展示 ProjectFile 和 UIPrototypeProject
  - `programmatic` TR-3.2: UI原型项目列表项有正确的类型标签和屏幕数量
  - `programmatic` TR-3.3: 资源类型筛选对 UI 原型项目有效
  - `human-judgement` TR-3.4: UI原型项目与其他资源混排时布局美观

## [ ] Task 4: 改造批量上传逻辑为UI原型上传
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 修改 resource-manage.vue 中的批量上传逻辑
  - 当资源类型为 UI 原型图时，调用 UI 原型上传接口而非 ProjectFile 批量上传
  - 保持现有单文件上传（非UI原型）逻辑不变
- **Acceptance Criteria Addressed**: [AC-4]
- **Test Requirements**:
  - `programmatic` TR-4.1: 批量上传 UI 原型时调用 UI 原型上传接口
  - `programmatic` TR-4.2: 批量上传成功后创建 UIPrototypeProject 和 UIPrototypeScreen 记录
  - `programmatic` TR-4.3: 其他资源类型仍使用原有上传逻辑
  - `human-judgement` TR-4.4: 上传前后端交互正常，错误提示友好

## [ ] Task 5: 实现编辑跳转和UI原型管理页面
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 
  - 在路由配置中增加 UI 原型管理页面路由
  - 创建 UI 原型管理页面（或复用现有界面）
  - 修改 resource-manage.vue 中的编辑按钮逻辑：UI原型项目跳转到 UI 原型管理
- **Acceptance Criteria Addressed**: [AC-3]
- **Test Requirements**:
  - `programmatic` TR-5.1: 路由配置新增 UI 原型管理页面
  - `programmatic` TR-5.2: 点击 UI 原型项目的编辑按钮正确跳转
  - `human-judgement` TR-5.3: UI 原型管理页面完整展示该项目的所有屏幕/图片
  - `human-judgement` TR-5.4: UI 原型管理页面功能可用

## [ ] Task 6: 集成测试与验证
- **Priority**: P0
- **Depends On**: [Task 3, Task 4, Task 5]
- **Description**: 
  - 端到端测试整个流程：上传、列表、编辑、查看
  - 验证资源类型筛选功能
  - 验证其他资源类型功能不受影响
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4, AC-5]
- **Test Requirements**:
  - `programmatic` TR-6.1: 完整流程测试通过
  - `programmatic` TR-6.2: 边缘场景测试通过（如无原型项目、混合资源等）
  - `human-judgement` TR-6.3: 用户体验顺畅，无明显卡顿
  - `human-judgement` TR-6.4: UI布局美观，功能完整
