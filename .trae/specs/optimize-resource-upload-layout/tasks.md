# Tasks

- [x] Task 1: 移除顶部筛选区域的上传按钮
  - [x] SubTask 1.1: 删除顶部 el-form 中的"上传文件"按钮代码
  - [x] SubTask 1.2: 调整顶部筛选区域的布局，移除 margin-left: auto 的样式

- [x] Task 2: 在资源列表区域添加上传按钮
  - [x] SubTask 2.1: 在 resource-header 区域添加"上传文件"按钮
  - [x] SubTask 2.2: 根据当前选中的迭代动态显示/隐藏上传按钮（在"全部"、具体迭代、"未分类"下都显示）
  - [x] SubTask 2.3: 调整 resource-header 样式，使标题和按钮布局美观

- [x] Task 3: 优化迭代卡片列表样式
  - [x] SubTask 3.1: 调整 iteration-card 的 padding、margin 和边框样式
  - [x] SubTask 3.2: 优化迭代名称、版本标签、状态标签的排列方式
  - [x] SubTask 3.3: 优化选中状态的视觉表现（背景色、边框颜色）
  - [x] SubTask 3.4: 调整"全部"和"未分类"卡片的样式，使其与迭代卡片保持一致

- [x] Task 4: 优化迭代面板头部样式
  - [x] SubTask 4.1: 调整 iteration-panel-header 的布局和对齐方式
  - [x] SubTask 4.2: 优化"新建迭代"按钮的样式和位置

- [x] Task 5: 调整上传弹窗的迭代选择逻辑
  - [x] SubTask 5.1: 在"全部"视图下显示迭代选择器
  - [x] SubTask 5.2: 在具体迭代视图下隐藏迭代选择器，自动关联当前迭代
  - [x] SubTask 5.3: 在"未分类"视图下隐藏迭代选择器，自动设置为不归属任何迭代

- [x] Task 6: 优化资源列表空状态显示
  - [x] SubTask 6.1: 当迭代下无资源时，显示友好的空状态提示
  - [x] SubTask 6.2: 空状态下提供快捷上传入口

- [x] Task 7: 整体布局微调
  - [x] SubTask 7.1: 调整 iteration-panel 和 resource-area 的间距和比例
  - [x] SubTask 7.2: 优化卡片阴影、圆角等视觉细节

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 5] depends on [Task 2]
- [Task 6] depends on [Task 2]
- [Task 7] depends on [Task 2, Task 3, Task 4]
