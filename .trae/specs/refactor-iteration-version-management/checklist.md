# Checklist

## 后端模型与数据库

* [x] Iteration 模型已创建，包含 id, project\_id, name, version, description, status, start\_date, end\_date, create\_time, update\_time 字段

* [x] ProjectFile 模型已新增 iteration\_id 外键（可空），与 Iteration 建立关联

* [x] UIPrototypeProject 模型已新增 iteration\_id 外键（可空），与 Iteration 建立关联

* [x] Project 模型已添加 iterations 关联关系

* [x] 数据库迁移成功执行，iterations 表和新增字段已创建

* [x] 旧数据 iteration\_id 为空时功能正常，不影响已有数据

## 后端 API

* [x] 迭代 CRUD API 已实现（POST /api/v1/iteration, GET /api/v1/iteration/list/{project\_id}, GET /api/v1/iteration/{id}, PUT /api/v1/iteration/{id}, DELETE /api/v1/iteration/{id}）

* [x] 迭代创建时校验同一项目下名称唯一

* [x] 删除迭代时级联删除关联的 ProjectFile 和 UIPrototypeProject 及物理文件

* [x] 文件上传接口（/api/v1/file/upload）支持可选参数 iteration\_id

* [x] 批量上传接口（/api/v1/file/batch-upload）支持可选参数 iteration\_id

* [x] 文件列表接口（/api/v1/file/list/{project\_id}）支持可选参数 iteration\_id 筛选

* [x] UI原型上传接口（/api/v1/ui-prototype/upload）支持可选参数 iteration\_id

* [x] UI原型项目列表接口（/api/v1/ui-prototype/project/list/{project\_id}）支持可选参数 iteration\_id 筛选

* [x] 迭代路由已在 API 路由中注册

## 前端 API 与类型

* [x] iteration.ts API 文件已创建，包含 createIteration, getIterations, updateIteration, deleteIteration 方法

* [x] file.ts 上传方法已支持 iteration\_id 参数

* [x] file.ts 文件列表方法已支持 iteration\_id 筛选

* [x] uiPrototype.ts 上传方法已支持 iteration\_id 参数

* [x] uiPrototype.ts 原型项目列表方法已支持 iteration\_id 筛选

## 前端页面

* [x] resource-manage.vue 已重构为左右布局：左侧迭代面板 + 右侧资源列表

* [x] 迭代面板正确展示迭代列表（名称、版本号、状态标签）

* [x] "未分类"选项展示 iteration\_id 为空的资源

* [x] 点击迭代切换时资源列表正确筛选

* [x] 新建迭代弹窗功能正常（名称、版本号、描述）

* [x] 编辑迭代功能正常

* [x] 删除迭代功能正常（含确认提示）

* [x] 上传文件时自动关联当前选中的迭代

* [x] 上传UI原型时自动关联当前选中的迭代

* [x] 页面布局美观，迭代面板与资源列表比例协调

## 兼容性与联调

* [x] 旧数据（无 iteration\_id）在"未分类"下正常展示

* [x] AI 分析跳转（test-point-extract）在迭代维度下正常工作

* [x] 项目详情页（project/detail.vue）文件列表不受影响

* [x] 测试用例生成页面（ai-generate.vue）UI 原型版本选择不受影响

* [x] UI 原型管理页面（ui-prototype.vue）追加上传携带 iteration\_id

* [x] 无冗余代码和重复功能实现

