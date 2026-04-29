# 迭代管理功能Bug修复与完善 Spec

## Why
当前需求管理已重构为迭代管理模式（resource-manage.vue），后端迭代CRUD、文件/UI原型上传接口均已支持iteration_id参数，但实际使用中存在大量bug导致功能无法正常使用。需要系统性排查并修复所有遗留问题，确保迭代管理的完整可用性。

## What Changes
**核心问题诊断与修复范围：**

### 一、前端页面问题
- **BUG-1**: resource-manage.vue 使用前端假分页（全量加载后slice），大数据量下性能差且total计算不准确
- **BUG-2**: 迭代筛选逻辑混乱 - selectedIterationId=null表示"全部"、=-1表示"未分类"、>0表示具体迭代，容易出错
- **BUG-3**: 上传文件弹窗缺少迭代选择器（当用户在"全部"或"未分类"视图下上传时，无法明确指定归属迭代）
- **BUG-4**: upload.vue 独立页面未适配迭代管理，仍使用旧的上传流程
- **BUG-5**: UI原型管理页面（ui-prototype.vue）迭代信息展示和传递不完整
- **BUG-6**: 资源列表的AI分析跳转未携带iteration_id参数
- **BUG-7**: 删除/编辑操作的错误处理不够友好
- **BUG-8**: 页面初始化时项目自动选中逻辑可能导致迭代加载失败

### 二、后端API问题
- **BUG-9**: 文件列表API的iteration_id筛选参数可能未被正确使用（前端传了但后端未用）
- **BUG-10**: 批量上传文件的iteration_id传递链路断裂
- **BUG-11**: 删除迭代的级联删除逻辑可能遗漏某些关联资源
- **BUG-12**: 迭代名称唯一性校验在前端重复提交时可能出现竞态条件

### 三、数据一致性问题
- **BUG-13**: 旧数据（无iteration_id）在切换迭代时的显示逻辑可能有误
- **BUG-14**: 编辑资源时修改iteration_id的功能缺失
- **BUG-15**: 资源在不同迭代间移动的功能缺失

### 四、用户体验问题
- **BUG-16**: 迭代面板缺少空状态提示（无迭代时）
- **BUG-17**: 操作成功/失败的反馈不够明确
- **BUG-18**: 缺少批量操作功能（批量移动到其他迭代）
- **BUG-19**: 迭代卡片缺少资源统计数量显示

## Impact
- Affected specs: refactor-iteration-version-management（基于此规格进行修复）
- Affected code:
  - 前端: `src/views/requirement/resource-manage.vue`（主修复目标）、`src/views/requirement/upload.vue`、`src/views/requirement/ui-prototype.vue`、`src/api/file.ts`、`src/api/uiPrototype.ts`
  - 后端: `app/api/v1/endpoints/file.py`（检查iteration_id筛选）、`app/crud/file.py`（确认筛选逻辑）

## ADDED Requirements

### Requirement: 前端分页优化与迭代筛选修复
系统 SHALL 将resource-manage.vue的前端假分页改为后端真分页，并简化迭代筛选逻辑。

#### Scenario: 后端真分页
- **WHEN** 用户查看某个迭代下的资源列表
- **THEN** 请求应携带page、page_size、iteration_id参数到后端，由后端返回分页数据

#### Scenario: 简化迭代筛选状态
- **WHEN** 用户点击迭代列表中的选项
- **THEN** 统一使用三种状态：null=全部、0=未分类、正数=具体迭代ID（移除-1的混淆用法）

### Requirement: 上传流程迭代绑定增强
系统 SHALL 在所有上传入口明确支持迭代绑定，包括新建上传弹窗、upload.vue独立页面。

#### Scenario: 上传弹窗显示迭代选择器
- **WHEN** 用户点击"上传文件"按钮打开上传弹窗
- **THEN** 弹窗中应显示迭代下拉选择框（预填当前选中的迭代，允许修改），且在"全部"或"未分类"视图下必选

#### Scenario: upload.vue页面适配迭代
- **WHEN** 用户通过导航进入upload.vue页面
- **THEN** 页面应支持从URL参数接收iteration_id，并在上传表单中显示迭代选择器

### Requirement: 资源操作完整性
系统 SHALL 确保资源的查看、编辑、删除、AI分析等操作均正确携带和处理迭代信息。

#### Scenario: AI分析携带迭代信息
- **WHEN** 用户对某资源点击"AI分析"
- **THEN** 跳转到test-point-extract页面时应携带完整的项目ID、文件ID、迭代ID、来源类型等参数

#### Scenario: 编辑资源可修改迭代归属
- **WHEN** 用户编辑某个非UI原型类型的资源
- **THEN** 编辑弹窗应允许修改该资源所属的迭代（通过迭代下拉选择框）

### Requirement: 迭代管理体验优化
系统 SHALL 提供更好的迭代管理用户体验，包括统计信息、空状态提示、操作反馈等。

#### Scenario: 迭代卡片显示资源统计
- **WHEN** 迭代列表加载完成
- **THEN** 每个迭代卡片应显示该迭代下的资源数量（如"3个文档, 5个原型"）

#### Scenario: 无迭代时的空状态
- **WHEN** 项目下没有任何迭代
- **THEN** 迭代面板应显示友好的空状态提示和引导用户创建迭代的按钮

#### Scenario: 操作结果明确反馈
- **WHEN** 用户执行任何操作（创建/编辑/删除迭代、上传/删除资源等）
- **THEN** 系统应给出明确的成功或失败提示，包含具体的错误信息

## MODIFIED Requirements

### Requirement: 文件列表API正确使用iteration_id筛选
原有 `/api/v1/file/list/{project_id}` 接口必须正确接收和使用iteration_id查询参数进行数据库筛选，而非返回全量数据让前端过滤。

### Requirement: UI原型项目列表API正确使用iteration_id筛选
原有 `/api/v1/ui-prototype/project/list/{project_id}` 接口必须正确接收和使用iteration_id查询参数进行数据库筛选。

### Requirement: 删除迭代级联完整性
删除迭代时的级联删除逻辑必须覆盖所有关联资源类型（ProjectFile、UIPrototypeProject、UIScreen、UIScreenTestCaseLink），并确保物理文件也被清理。

## REMOVED Requirements
无移除的需求。所有原有功能保持兼容，重点修复bug和提升可用性。
