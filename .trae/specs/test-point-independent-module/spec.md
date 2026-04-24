# 测试点独立管理模块 Spec

## Why

当前测试点功能存在以下关键问题：
1. **入口分散**：无独立菜单入口，仅在"需求分析"和"测试点提取"页面可见
2. **复用困难**：缺少统一检索与列表管理，跨需求文件复用成本高
3. **流程冗长**：查看/编辑/生成用例需要3~5步完成
4. **关系缺失**：TestPoint与TestCase无数据关联，无法溯源
5. **权限不清**：无独立权限配置，无法满足团队协作需求

## What Changes

### 架构变更
- 新增独立的测试点管理列表页
- 新增"测试点管理"一级菜单项
- TestPoint模型新增 `created_by` 字段
- TestCase模型新增 `test_point_id` 字段建立关联
- 保留原有 AnalysisPage 和 test-point-extract 页面（兼容）

### 功能新增
- 完整CRUD（新增、编辑、删除、详情）
- 多维度筛选（模块、优先级、创建人、创建时间、关联需求）
- 批量操作（删除、生成用例）
- 测试点→测试用例关联可视化
- 测试点独立权限控制

### 功能保留
- 保留原需求分析页面
- 保留原测试点提取页面
- 原AI生成用例流程不变

## Impact

- Affected specs: 无直接依赖
- Affected code:
  - **后端**:
    - `app/models/test_point.py` - 新增字段
    - `app/models/test_case.py` - 新增关联字段
    - `app/crud/test_point.py` - 完善查询能力
    - `app/api/v1/endpoints/test_point*.py` - 新增API
  - **前端**:
    - `src/views/test-point/` - 新建目录
    - `src/api/testPoint.ts` - 新增API方法
    - `src/store/testPoint.ts` - 新建状态管理
    - `src/router/index.ts` - 新增路由
    - `src/types/testPoint.ts` - 完善类型

---

## ADDED Requirements

### Requirement: 独立菜单入口
系统 SHALL 提供清晰的独立菜单入口：

#### Scenario: 菜单显示
- **WHEN** 用户登录系统
- **THEN** 左侧导航栏显示"测试点管理"菜单项

#### Scenario: 点击跳转
- **WHEN** 用户点击"测试点管理"菜单项
- **THEN** 跳转到独立的测试点列表页

### Requirement: 完整CRUD能力
系统 SHALL 提供完整的测试点CRUD能力：

#### Scenario: 新增测试点
- **WHEN** 用户点击"新增测试点"按钮
- **THEN** 显示弹窗表单，填写后保存到数据库

#### Scenario: 编辑测试点
- **WHEN** 用户点击测试点的"编辑"按钮
- **THEN** 显示弹窗表单，修改后更新

#### Scenario: 删除测试点
- **WHEN** 用户点击测试点的"删除"按钮
- **THEN** 弹出确认框，确认后删除

#### Scenario: 批量删除
- **WHEN** 用户选择多条测试点并点击"批量删除"
- **THEN** 弹出确认框，确认后批量删除

### Requirement: 多维度筛选排序
系统 SHALL 提供灵活的筛选与排序能力：

#### Scenario: 按模块筛选
- **WHEN** 用户选择模块筛选条件
- **THEN** 列表只显示该模块的测试点

#### Scenario: 按优先级筛选
- **WHEN** 用户选择优先级筛选条件
- **THEN** 列表只显示该优先级的测试点

#### Scenario: 按创建时间筛选
- **WHEN** 用户选择创建时间范围
- **THEN** 列表只显示该时间范围内的测试点

#### Scenario: 排序
- **WHEN** 用户点击表头排序
- **THEN** 列表按对应字段升序/降序排列

### Requirement: 直接生成测试用例
系统 SHALL 支持从列表直接触发AI生成测试用例：

#### Scenario: 单条生成
- **WHEN** 用户点击单条测试点的"生成用例"按钮
- **THEN** 触发AI生成，显示进度，生成完成后展示关联关系

#### Scenario: 批量生成
- **WHEN** 用户选择多条测试点并点击"批量生成用例"
- **THEN** 批量触发AI生成，显示进度，生成完成后展示关联关系

### Requirement: 关系可视化
系统 SHALL 直观展示测试点与测试用例的关联：

#### Scenario: 查看关联用例
- **WHEN** 用户点击测试点的"查看用例"按钮
- **THEN** 弹窗展示该测试点生成的所有用例列表，支持跳转详情

#### Scenario: 关联关系展示
- **WHEN** 用户查看测试点列表
- **THEN** 列表显示"已生成用例数"列，点击可查看详情

### Requirement: 权限管控
系统 SHALL 实现测试点独立的权限配置：

#### Scenario: 查看权限
- **WHEN** 用户无 test_point:read 权限
- **THEN** 菜单项隐藏/置灰，无法访问列表页

#### Scenario: 编辑权限
- **WHEN** 用户无 test_point:update 权限
- **THEN** "编辑"按钮隐藏/置灰

#### Scenario: 删除权限
- **WHEN** 用户无 test_point:delete 权限
- **THEN** "删除"按钮隐藏/置灰

---

## MODIFIED Requirements

### Requirement: 兼容现有页面
系统 SHALL 保留原有功能逻辑，确保存量用户无感知：

#### Scenario: 需求分析页面保留
- **WHEN** 用户访问原需求分析页面
- **THEN** 功能完全正常，可新增快捷跳转"跳转到测试点列表"

#### Scenario: 测试点提取页面保留
- **WHEN** 用户访问原测试点提取页面
- **THEN** 功能完全正常，可新增快捷跳转"跳转到测试点列表"

### Requirement: 数据模型改造
系统 SHALL 在不破坏现有数据的前提下进行模型改造：

#### Scenario: 新增字段
- **WHEN** 执行数据库迁移
- **THEN** TestPoint 新增 created_by 字段，TestCase 新增 test_point_id 字段，均为可空，确保兼容

#### Scenario: 历史数据处理
- **WHEN** 迁移历史数据
- **THEN** 历史数据保留，新生成的用例才建立关联关系

---

## 技术约束
- 必须遵循现有项目的代码规范（变量命名、缩进、注释等）
- 必须遵循现有架构设计原则（低耦合、依赖注入）
- 必须遵循测试规范（覆盖率≥95%，真实环境测试）
- 不新增任何第三方依赖
