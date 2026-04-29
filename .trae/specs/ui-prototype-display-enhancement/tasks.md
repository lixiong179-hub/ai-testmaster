# Tasks

## 任务列表

- [ ] Task 1: 重构预览弹窗布局 — 将弹窗改为左右分栏布局（左侧图片60%，右侧信息40%）
  - [ ] SubTask 1.1: 修改el-dialog布局结构
  - [ ] SubTask 1.2: 添加CSS实现左右分栏
  - [ ] SubTask 1.3: 调整基础信息展示位置

- [ ] Task 2: 增强基础信息展示 — 添加元素/按钮/输入框的图标装饰，优化AI摘要展示
  - [ ] SubTask 2.1: 添加el-descriptions-item的图标装饰
  - [ ] SubTask 2.2: 优化summary字段的展示样式（卡片+阴影）
  - [ ] SubTask 2.3: 添加类型标签颜色映射

- [ ] Task 3: 添加元素详情折叠面板 — 展示elements数组数据
  - [ ] SubTask 3.1: 添加el-collapse折叠面板组件
  - [ ] SubTask 3.2: 实现elements列表渲染（按位置排序）
  - [ ] SubTask 3.3: 添加类型标签颜色和图标
  - [ ] SubTask 3.4: 处理空数据提示

- [ ] Task 4: 添加跳转流程区域 — 展示flows和navigation数据
  - [ ] SubTask 4.1: 添加跳转流程卡片
  - [ ] SubTask 4.2: 展示预期跳转页面列表
  - [ ] SubTask 4.3: 展示触发动作列表
  - [ ] SubTask 4.4: 展示返回按钮/Tab栏信息

- [ ] Task 5: 添加布局约束和视觉风格展示
  - [ ] SubTask 5.1: 添加layout_constraints列表展示
  - [ ] SubTask 5.2: 添加visual_style卡片展示
  - [ ] SubTask 5.3: 添加优先级标签（high/medium/low）

- [ ] Task 6: 添加warnings警告展示
  - [ ] SubTask 6.1: 添加warnings提示区域
  - [ ] SubTask 6.2: 使用el-alert组件展示警告信息

## 任务依赖关系

- Task 1 是其他任务的基础（布局结构）
- Task 2、3、4、5、6 可并行开发（各自独立的展示区块）
