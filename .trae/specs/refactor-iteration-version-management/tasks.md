# Tasks

- [x] Task 1: 后端 - 新增 Iteration 模型与数据库迁移
  - [x] SubTask 1.1: 在 `app/models/` 下新增 `iteration.py`，定义 Iteration 模型（id, project_id, name, version, description, status, start_date, end_date, create_time, update_time），建立与 Project 的关联关系
  - [x] SubTask 1.2: 修改 `app/models/project.py` 的 Project 模型，添加 iterations 关联关系
  - [x] SubTask 1.3: 修改 `app/models/project.py` 的 ProjectFile 模型，新增 `iteration_id` 外键（可空，ForeignKey -> iterations.id）和 iteration 关联关系
  - [x] SubTask 1.4: 修改 `app/models/ui_prototype.py` 的 UIPrototypeProject 模型，新增 `iteration_id` 外键（可空）和 iteration 关联关系
  - [x] SubTask 1.5: 更新 `app/models/__init__.py`，导入 Iteration 模型
  - [x] SubTask 1.6: 执行数据库迁移，确保新表和新字段正确创建

- [x] Task 2: 后端 - 新增迭代 CRUD 与 Schema
  - [x] SubTask 2.1: 在 `app/schemas/` 下新增 `iteration.py`，定义 IterationCreate, IterationUpdate, IterationResponse 等 Schema
  - [x] SubTask 2.2: 在 `app/crud/` 下新增 `iteration.py`，实现迭代的 CRUD 操作（create, get, list, update, delete）
  - [x] SubTask 2.3: 修改 `app/crud/file.py`，新增按 iteration_id 筛选文件的方法，修改 create_project_file 支持 iteration_id
  - [x] SubTask 2.4: 修改 `app/crud/ui_prototype.py`，新增按 iteration_id 筛选 UI 原型项目的方法，修改 create_ui_prototype_project 支持 iteration_id

- [x] Task 3: 后端 - 新增迭代 API 端点与修改现有接口
  - [x] SubTask 3.1: 在 `app/api/v1/endpoints/` 下新增 `iteration.py`，实现迭代 CRUD API（POST创建、GET列表、GET详情、PUT更新、DELETE删除）
  - [x] SubTask 3.2: 修改 `app/api/v1/endpoints/file.py` 的 upload_file 和 batch_upload_files 接口，新增可选参数 iteration_id
  - [x] SubTask 3.3: 修改 `app/api/v1/endpoints/file.py` 的 get_file_list 接口，新增可选参数 iteration_id 筛选
  - [x] SubTask 3.4: 修改 `app/api/v1/endpoints/ui_prototype.py` 的 upload_ui_screens 接口，新增可选参数 iteration_id
  - [x] SubTask 3.5: 修改 `app/api/v1/endpoints/ui_prototype.py` 的 get_prototype_projects 接口，新增可选参数 iteration_id 筛选
  - [x] SubTask 3.6: 在 `app/api/v1/__init__.py` 中注册迭代路由

- [x] Task 4: 前端 - 新增迭代 API 与类型定义
  - [x] SubTask 4.1: 在 `src/api/` 下新增 `iteration.ts`，定义 Iteration 相关类型和 API 方法（createIteration, getIterations, updateIteration, deleteIteration）
  - [x] SubTask 4.2: 修改 `src/api/file.ts`，上传接口新增 iteration_id 参数，文件列表接口新增 iteration_id 筛选参数
  - [x] SubTask 4.3: 修改 `src/api/uiPrototype.ts`，上传接口新增 iteration_id 参数，原型项目列表接口新增 iteration_id 筛选参数

- [x] Task 5: 前端 - 重构需求管理页面（resource-manage.vue）
  - [x] SubTask 5.1: 重构页面布局，左侧增加迭代列表面板（展示迭代卡片列表 + "未分类"选项），右侧为资源列表
  - [x] SubTask 5.2: 实现迭代列表的加载、选中切换、资源联动筛选
  - [x] SubTask 5.3: 实现迭代管理操作（新建迭代弹窗、编辑迭代、删除迭代、状态标签展示）
  - [x] SubTask 5.4: 修改上传文件弹窗，当处于某迭代下时自动关联 iteration_id
  - [x] SubTask 5.5: 优化页面整体布局美观度（迭代面板与资源列表的比例、间距、颜色风格）

- [x] Task 6: 前端 - 修改 UI 原型管理页面（ui-prototype.vue）
  - [x] SubTask 6.1: 页面头部展示当前所属迭代信息
  - [x] SubTask 6.2: 追加上传时携带 iteration_id 参数

- [x] Task 7: 前端 - 修改路由与导航
  - [x] SubTask 7.1: 检查路由配置，确保迭代相关页面跳转正常
  - [x] SubTask 7.2: 确认侧边栏菜单无需修改（迭代管理在需求管理页面内完成）

- [x] Task 8: 联调验证与兼容性测试
  - [x] SubTask 8.1: 验证旧数据（iteration_id 为空的资源）在"未分类"下正常展示
  - [x] SubTask 8.2: 验证 AI 分析跳转（test-point-extract）在迭代维度下正常工作
  - [x] SubTask 8.3: 验证项目详情页（project/detail.vue）文件列表不受影响
  - [x] SubTask 8.4: 验证测试用例生成页面（ai-generate.vue）中 UI 原型版本选择不受影响
  - [x] SubTask 8.5: 验证删除迭代时级联删除资源和物理文件

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 2]
- [Task 4] depends on [Task 3]
- [Task 5] depends on [Task 4]
- [Task 6] depends on [Task 4]
- [Task 7] depends on [Task 5]
- [Task 8] depends on [Task 5, Task 6, Task 7]
