# 测试用例生成与执行系统 Spec

## Why
基于现有项目中的真实项目和需求文档，构建完整的测试用例自动生成和执行系统，实现从需求文档→测试点→测试用例→测试执行的完整自动化流程，期间不使用任何 Mock 数据，所有测试基于真实数据库和真实项目环境。

## What Changes
- **新增测试用例自动生成能力**：基于数据库中的项目、需求文档、测试点数据，自动调用 AI 生成可执行的测试用例
- **新增测试用例自动执行能力**：根据生成的测试用例，自动执行测试（包括前端 UI 测试和 API 接口测试）
- **新增前端页面测试验证**：测试前端页面展示、布局、请求参数等
- **新增问题自动修复机制**：测试过程中发现的问题自动记录并修复
- **新增测试报告生成**：生成详细的测试执行报告

## Impact
- **Affected specs**: 测试用例生成模块、测试执行引擎、前端页面
- **Affected code**: 
  - `app/services/case_generate_service.py` - 测试用例生成服务
  - `app/services/test_execution_engine_v2.py` - 测试执行引擎
  - `src/views/case/ai-generate.vue` - AI 生成测试用例前端页面
  - `src/views/test/index.vue` - 测试执行前端页面
  - `app/api/v1/endpoints/test_task.py` - 测试任务 API

## ADDED Requirements

### Requirement: 测试用例自动生成
The system SHALL provide 基于真实项目数据自动生成测试用例的能力

#### Scenario: 从需求文档生成测试用例
- **WHEN**: 用户选择包含需求文档和测试点的项目
- **THEN**: 系统自动调用 AI 为每个测试点生成详细的、可执行的测试用例
- **AND**: 生成的测试用例必须包含详细的前置条件、操作步骤、预期结果
- **AND**: 禁止使用 Mock 数据，所有数据来自真实数据库

#### Scenario: 测试用例质量验证
- **WHEN**: 测试用例生成完成后
- **THEN**: 系统自动验证测试用例的可执行性
- **AND**: 标记无法执行的测试用例并提示用户

### Requirement: 测试用例自动执行
The system SHALL provide 自动执行测试用例的能力

#### Scenario: 执行 UI 测试用例
- **WHEN**: 用户创建测试任务并选择 UI 测试用例
- **THEN**: 系统使用真实浏览器访问被测系统
- **AND**: 按照测试步骤执行操作
- **AND**: 记录执行结果和截图
- **AND**: 禁止使用 Mock 数据

#### Scenario: 执行 API 测试用例
- **WHEN**: 用户创建测试任务并选择 API 测试用例
- **THEN**: 系统发送真实 HTTP 请求到被测系统
- **AND**: 验证响应结果
- **AND**: 记录执行日志

### Requirement: 前端页面测试
The system SHALL provide 前端页面测试验证能力

#### Scenario: 页面布局测试
- **WHEN**: 测试用例执行时
- **THEN**: 验证页面元素布局正确
- **AND**: 验证页面元素可见性
- **AND**: 验证页面响应式布局

#### Scenario: 前端请求参数测试
- **WHEN**: 前端发起 API 请求时
- **THEN**: 验证请求参数格式正确
- **AND**: 验证请求头信息完整
- **AND**: 验证认证 token 有效

### Requirement: 问题自动修复
The system SHALL provide 测试问题自动修复能力

#### Scenario: 发现问题自动记录
- **WHEN**: 测试执行过程中发现错误
- **THEN**: 自动记录错误详情（截图、日志、堆栈信息）
- **AND**: 自动创建 Bug 记录
- **AND**: 关联到对应的测试用例

#### Scenario: 问题修复验证
- **WHEN**: Bug 修复完成后
- **THEN**: 自动重新执行失败的测试用例
- **AND**: 验证问题已修复
- **AND**: 更新测试报告

## MODIFIED Requirements

### Requirement: 测试用例生成服务
原需求：支持基于测试点生成测试用例

修改后：
- 必须使用真实数据库中的项目、需求文档、测试点数据
- 生成的测试用例必须可执行（包含详细步骤）
- 支持批量生成和保存
- 生成过程中自动验证用例质量

### Requirement: 测试执行引擎
原需求：执行测试用例并记录结果

修改后：
- 支持 UI 自动化测试（真实浏览器）
- 支持 API 接口测试（真实 HTTP 请求）
- 支持前端页面验证（布局、样式、交互）
- 支持测试数据参数化
- 执行失败时自动重试
- 自动生成详细执行报告

## REMOVED Requirements
无

## Technical Specifications

### 数据库配置
```
数据库：MySQL
地址：localhost:3306
数据库名：ai_testmaster
字符集：utf8mb4
```

### 测试环境配置
```
前端服务：http://localhost:3000
后端服务：http://localhost:8000
API 文档：http://localhost:8000/docs
```

### 测试原则（强制执行）
1. **严禁使用 Mock**：所有测试必须使用真实环境、真实数据
2. **真实执行优先**：禁止使用模拟数据和 Mock 对象
3. **覆盖率>=95%**：核心功能代码覆盖率必须达到 95% 以上
4. **数据库必须使用 MySQL**：禁止使用 SQLite 等内存数据库
5. **与公司配置保持一致**：测试环境必须与生产环境配置一致
6. **测试用例必须有价值**：测试目的是发现潜在问题

## Acceptance Criteria

### AC-1: 测试用例自动生成
- **Given**: 数据库中有包含需求文档和测试点的项目
- **When**: 用户选择项目并点击"生成测试用例"
- **Then**: 系统为每个测试点生成详细的、可执行的测试用例
- **And**: 生成的测试用例保存到数据库
- **Verification**: `programmatic`

### AC-2: 测试用例自动执行
- **Given**: 项目中有已生成的测试用例
- **When**: 用户创建测试任务并执行
- **Then**: 系统自动执行所有测试用例
- **And**: 记录详细的执行结果和截图
- **And**: 生成测试报告
- **Verification**: `programmatic`

### AC-3: 前端页面测试
- **Given**: 测试任务包含 UI 测试用例
- **When**: 执行测试用例
- **Then**: 验证前端页面布局正确
- **And**: 验证页面元素交互正常
- **And**: 验证前端请求参数正确
- **Verification**: `programmatic`

### AC-4: 问题自动修复
- **Given**: 测试执行过程中发现错误
- **When**: 错误被记录
- **Then**: 自动创建 Bug 记录
- **And**: Bug 修复后自动重新测试
- **And**: 验证问题已解决
- **Verification**: `programmatic`

### AC-5: 测试报告生成
- **Given**: 测试任务执行完成
- **When**: 用户查看测试报告
- **Then**: 显示详细的测试结果统计
- **And**: 显示每个用例的执行详情
- **And**: 显示发现的问题列表
- **Verification**: `programmatic`

### AC-6: 零 Mock 数据
- **Given**: 任何测试场景
- **When**: 执行测试
- **Then**: 不使用任何 Mock 数据或模拟对象
- **And**: 所有数据来自真实数据库和被测系统
- **Verification**: `human-judgment`
