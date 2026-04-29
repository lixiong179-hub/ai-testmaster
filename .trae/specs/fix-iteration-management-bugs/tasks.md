# Tasks

- [x] Task 1: 诊断并修复后端API的iteration_id筛选问题
  - [x] SubTask 1.1: 检查 `app/api/v1/endpoints/file.py` 的 `get_file_list` 接口，确认是否正确接收和使用 iteration_id 查询参数
  - [x] SubTask 1.2: 检查 `app/crud/file.py` 的文件查询方法，确认是否实现了按 iteration_id 筛选的逻辑
  - [x] SubTask 1.3: 检查 `app/api/v1/endpoints/ui_prototype.py` 的 `get_prototype_projects` 接口，确认 iteration_id 筛选是否生效
  - [x] SubTask 1.4: 检查 `app/crud/ui_prototype.py` 的UI原型项目查询方法，确认 iteration_id 筛选逻辑
  - [x] SubTask 1.5: 修复发现的筛选逻辑bug（如果后端未实现筛选，需要添加；如果已实现但前端传参方式不对，需调整）

- [x] Task 2: 重构前端 resource-manage.vue 的分页与迭代筛选逻辑
  - [x] SubTask 2.1: 将前端假分页改为后端真分页（修改 getResources 方法，让后端处理分页）
  - [x] SubTask 2.2: 简化迭代筛选状态管理（统一使用 null=全部、0=未分类、正数=具体迭代ID）
  - [x] SubTask 2.3: 修复 selectedIterationId 的初始值和切换逻辑
  - [x] SubTask 2.4: 修复"全部"、"未分类"、具体迭代的资源查询参数组装逻辑

- [x] Task 3: 增强上传流程的迭代绑定功能
  - [x] SubTask 3.1: 在上传文件弹窗中添加迭代选择器下拉框（预填当前选中迭代，允许修改）
  - [x] SubTask 3.2: 处理"全部"视图下的上传逻辑（必须选择具体迭代或明确标记为未分类）
  - [x] SubTask 3.3: 处理"未分类"视图下的上传逻辑（默认不关联迭代）
  - [x] SubTask 3.4: 确保 uploadFormData.iteration_id 在提交时正确传递到后端
  - [x] SubTask 3.5: 验证单文件上传和批量UI原型上传的 iteration_id 传递链路完整

- [x] Task 4: 适配 upload.vue 和 ui-prototype.vue 页面
  - [x] SubTask 4.1: 修改 `src/views/requirement/upload.vue`，添加迭代选择器支持从URL参数接收iteration_id
  - [x] SubTask 4.2: 修改 `src/views/requirement/ui-prototype.vue`，完善迭代信息的展示和传递
  - [x] SubTask 4.3: 确保从 resource-manage.vue 跳转到这两个页面时正确携带 iteration_id 参数

- [x] Task 5: 完善资源操作功能的迭代信息处理
  - [x] SubTask 5.1: 修复 AI 分析跳转（handleAnalyze），确保携带完整的 iteration_id 参数
  - [x] SubTask 5.2: 修改编辑资源的弹窗，添加迭代归属修改功能（针对非UI原型资源）
  - [x] SubTask 5.3: 优化删除操作的错误提示信息，包含更多上下文
  - [x] SubTask 5.4: 添加资源在迭代间移动的功能（可选，通过编辑实现）

- [x] Task 6: 优化迭代管理用户体验
  - [x] SubTask 6.1: 为迭代卡片添加资源统计数量显示（需调用统计API或在前端聚合计算）
  - [x] SubTask 6.2: 添加无迭代时的空状态提示和引导创建按钮
  - [x] SubTask 6.3: 优化所有操作的成功/失败反馈消息（更明确的提示内容）
  - [x] SubTask 6.4: 修复页面初始化时项目自动选中可能导致的问题（确保迭代列表正确加载）

- [x] Task 7: 全面测试与联调验证
  - [x] SubTask 7.1: 测试创建迭代 → 上传资源 → 查看资源列表的完整流程
  - [x] SubTask 7.2: 测试在不同迭代视图下上传资源的正确性
  - [x] SubTask 7.3: 测试切换迭代时资源列表的正确筛选
  - [x] SubTask 7.4: 测试编辑资源修改迭代归属的功能
  - [x] SubTask 7.5: 测试删除迭代时的级联删除和数据清理
  - [x] SubTask 7.6: 测试旧数据（无iteration_id）在"未分类"下的显示
  - [x] SubTask 7.7: 测试 AI 分析跳转在迭代维度下的正常工作
  - [x] SubTask 7.8: 测试边界情况（无迭代项目、大量资源分页、并发操作等）

# Task Dependencies
- [Task 2] depends on [Task 1] (先确保后端筛选正确，再重构前端)
- [Task 3] depends on [Task 2] (上传依赖正确的迭代状态管理)
- [Task 4] depends on [Task 3] (子页面适配依赖主页面逻辑稳定)
- [Task 5] depends on [Task 2, Task 3] (资源操作依赖筛选和上传逻辑)
- [Task 6] depends on [Task 2] (体验优化依赖核心逻辑修复)
- [Task 7] depends on [Task 1, Task 2, Task 3, Task 4, Task 5, Task 6] (最后全面验证)
