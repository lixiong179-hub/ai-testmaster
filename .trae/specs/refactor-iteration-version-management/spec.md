# 需求上传模块迭代版本管理重构 Spec

## Why
当前需求文档和UI原型图直接挂在项目下，缺乏迭代版本维度的组织管理。当项目经历多个迭代周期时，无法清晰区分不同迭代的需求和UI原型，导致资源混乱、追溯困难。引入迭代版本管理，让需求文档和UI原型图归属于具体迭代，实现项目资源的结构化管理。

## What Changes
- 新增 `Iteration` 迭代模型，作为项目与资源之间的中间层级
- 修改 `ProjectFile` 模型，新增 `iteration_id` 外键（可空，兼容旧数据）
- 修改 `UIPrototypeProject` 模型，新增 `iteration_id` 外键（可空，兼容旧数据）
- 新增迭代管理后端 API（CRUD + 列表查询）
- 修改文件上传接口，支持 `iteration_id` 参数
- 修改 UI 原型上传接口，支持 `iteration_id` 参数
- 重构前端需求管理页面，引入迭代维度切换
- 重构前端资源上传流程，绑定到具体迭代

## Impact
- Affected specs: 需求管理模块、UI原型管理模块、文件管理模块
- Affected code:
  - 后端: `app/models/` (新增 iteration, 修改 project/ui_prototype), `app/api/v1/endpoints/` (新增 iteration, 修改 file/ui_prototype), `app/crud/` (新增 iteration, 修改 file/ui_prototype), `app/schemas/` (新增 iteration, 修改 file/ui_prototype)
  - 前端: `src/views/requirement/` (重构 resource-manage.vue, ui-prototype.vue), `src/api/` (新增 iteration, 修改 file/uiPrototype), `src/router/` (修改路由)

## ADDED Requirements

### Requirement: 迭代模型与数据管理
系统 SHALL 提供 Iteration 迭代模型，包含以下字段：id, project_id, name, version, description, status(planning/active/completed/archived), start_date, end_date, create_time, update_time。一个项目下可以有多个迭代，迭代名称在项目内唯一。

#### Scenario: 创建迭代
- **WHEN** 用户在项目下创建迭代，填写名称、版本号、描述等信息
- **THEN** 系统创建迭代记录并返回迭代信息，迭代状态默认为 planning

#### Scenario: 迭代名称唯一性校验
- **WHEN** 用户创建的迭代名称在同一项目下已存在
- **THEN** 系统返回错误提示"迭代名称已存在"

#### Scenario: 删除迭代
- **WHEN** 用户删除一个迭代
- **THEN** 系统级联删除该迭代下的所有需求文档(ProjectFile)和UI原型项目(UIPrototypeProject)，同时删除物理文件

### Requirement: 资源归属迭代
系统 SHALL 支持将需求文档和UI原型图归属于具体迭代。ProjectFile 和 UIPrototypeProject 新增 iteration_id 外键（可空），未归属迭代的资源视为"未分类"资源。

#### Scenario: 上传需求文档到迭代
- **WHEN** 用户在指定迭代下上传需求文档
- **THEN** 文件记录的 iteration_id 关联到该迭代

#### Scenario: 上传UI原型到迭代
- **WHEN** 用户在指定迭代下上传UI原型图
- **THEN** UI原型项目记录的 iteration_id 关联到该迭代

#### Scenario: 兼容旧数据
- **WHEN** 已有资源的 iteration_id 为空
- **THEN** 这些资源在"未分类"分类下展示，不影响原有功能

### Requirement: 迭代维度资源管理前端
系统 SHALL 在需求管理页面提供迭代维度切换，用户可在不同迭代间切换查看资源，也可查看"未分类"资源。

#### Scenario: 迭代列表展示
- **WHEN** 用户进入需求管理页面并选择了项目
- **THEN** 页面左侧或顶部展示该项目的迭代列表，包含迭代名称、版本号、状态标签

#### Scenario: 切换迭代查看资源
- **WHEN** 用户点击某个迭代
- **THEN** 右侧资源列表仅展示该迭代下的需求文档和UI原型图

#### Scenario: 查看未分类资源
- **WHEN** 用户点击"未分类"选项
- **THEN** 资源列表展示 iteration_id 为空的所有资源

#### Scenario: 在迭代下上传资源
- **WHEN** 用户在某个迭代下点击上传
- **THEN** 上传的资源自动关联到当前选中的迭代

### Requirement: 迭代管理操作
系统 SHALL 提供迭代的增删改查操作，包括创建迭代、编辑迭代信息、修改迭代状态、删除迭代。

#### Scenario: 编辑迭代
- **WHEN** 用户修改迭代的名称、版本号、描述或状态
- **THEN** 系统更新迭代记录

#### Scenario: 迭代状态流转
- **WHEN** 用户修改迭代状态（如从 planning → active → completed → archived）
- **THEN** 系统更新状态，不限制状态流转顺序

## MODIFIED Requirements

### Requirement: 文件上传接口支持迭代
原有 `/api/v1/file/upload` 和 `/api/v1/file/batch-upload` 接口新增可选参数 `iteration_id`，上传时若指定迭代ID则关联到对应迭代。

### Requirement: UI原型上传接口支持迭代
原有 `/api/v1/ui-prototype/upload` 接口新增可选参数 `iteration_id`，上传时若指定迭代ID则关联到对应迭代。

### Requirement: 文件列表查询支持迭代筛选
原有 `/api/v1/file/list/{project_id}` 接口新增可选参数 `iteration_id`，支持按迭代筛选文件。

### Requirement: UI原型项目列表查询支持迭代筛选
原有 `/api/v1/ui-prototype/project/list/{project_id}` 接口新增可选参数 `iteration_id`，支持按迭代筛选UI原型项目。

## REMOVED Requirements
无移除的需求。所有原有功能保持兼容，迭代为可选维度。
