# 测试用例类型可选功能 - 产品需求文档

## Overview
- **Summary**: 优化AI生成测试用例功能，使用户可以选择是否指定用例类型。如果不指定，由AI智能判断用例类型；如果指定，则生成对应类型的测试用例。
- **Purpose**: 解决当前用例类型强制默认"UI自动化"的问题，提供更灵活的生成方式，让AI能够根据测试点的实际性质自动识别合适的用例类型。
- **Target Users**: 测试工程师、QA人员、AI生成测试用例的使用者

## Goals
- 用例类型字段不再是必填项，用户可以自由选择是否指定
- 当用户不选用例类型时，由AI根据测试点和需求文档智能判断用例类型
- 当用户选择了用例类型时，按用户选择的类型生成对应的测试用例
- 保持向后兼容性，不破坏现有功能

## Non-Goals (Out of Scope)
- 不修改AI模型本身的生成逻辑
- 不修改测试用例类型的枚举值
- 不涉及测试用例执行功能的修改
- 不修改测试用例的存储结构

## Background & Context
当前系统在生成测试用例时，用例类型字段是必填的，且默认值为"UI自动化"。但从代码分析来看，后端的 `test_case_generation_service.py` 已经包含了根据UI描述智能判断用例类型的逻辑，前端和后端的默认值设置覆盖了这个智能判断能力。

## Functional Requirements
- **FR-1**: 前端用例类型选择框改为非必填
- **FR-2**: 前端表单初始化时不设置用例类型的默认值
- **FR-3**: 后端API接收请求时，支持 case_type 为可选参数
- **FR-4**: 当 case_type 未提供时，启用AI智能判断用例类型的逻辑
- **FR-5**: 当 case_type 提供时，按指定类型生成测试用例

## Non-Functional Requirements
- **NFR-1**: 保持用户体验流畅，不增加操作复杂度
- **NFR-2**: 不影响现有功能的正常使用
- **NFR-3**: 错误提示友好，明确告知用户发生了什么

## Constraints
- **Technical**: 必须使用现有的代码库架构，遵循现有代码规范
- **Business**: 必须在1个迭代内完成，不影响现有用户
- **Dependencies**: 依赖现有的AI生成测试用例服务

## Assumptions
- 后端现有的智能判断用例类型的逻辑是正确可用的
- 用户理解"不选择类型即由AI判断"的含义
- 现有测试用例类型枚举值能够满足AI自动分类的需求

## Acceptance Criteria

### AC-1: 前端用例类型字段非必填
- **Given**: 用户打开AI生成测试用例页面
- **When**: 用户查看用例类型选择框
- **Then**: 用例类型选择框没有红色星号（必填标记）
- **Verification**: `programmatic`
- **Notes**: 检查前端代码中 el-form-item 的 required 属性

### AC-2: 表单初始化无默认类型
- **Given**: 用户首次打开AI生成测试用例页面，或点击重置表单
- **When**: 查看用例类型选择框
- **Then**: 选择框显示占位文字"请选择用例类型"，没有预选项
- **Verification**: `programmatic`
- **Notes**: 检查前端 formData.case_type 初始值和重置逻辑

### AC-3: 后端支持可选 case_type
- **Given**: 前端发送AI生成测试用例请求
- **When**: 请求中不包含 case_type 字段，或 case_type 为空
- **Then**: 后端正常接收请求，不报错
- **Verification**: `programmatic`
- **Notes**: 检查后端 Pydantic 模型 AIGenerateEnhancedRequest 的 case_type 字段是否为 Optional

### AC-4: 未指定类型时AI智能判断
- **Given**: 用户未选用例类型，点击生成
- **When**: AI生成测试用例完成
- **Then**: 生成的测试用例类型由AI根据测试点和需求智能判断（可能包含UI自动化、手工测试、API自动化等多种类型）
- **Verification**: `programmatic`
- **Notes**: 检查后端 test_case_generation_service.py 中的智能判断逻辑是否被正确调用

### AC-5: 指定类型时生成对应类型
- **Given**: 用户选择了特定用例类型（如API自动化）
- **When**: AI生成测试用例完成
- **Then**: 所有生成的测试用例类型都是用户指定的类型
- **Verification**: `programmatic`
- **Notes**: 验证生成的用例 case_type 字段与用户选择一致

### AC-6: 保存用例时无默认类型覆盖
- **Given**: AI生成了测试用例，且用例类型由AI判断
- **When**: 用户保存测试用例
- **Then**: 保存的用例类型保持AI生成的类型，不被默认值覆盖
- **Verification**: `programmatic`
- **Notes**: 检查前端保存逻辑中是否有默认值覆盖

## Open Questions
- [ ] 是否需要在UI上明确提示"不选择则由AI智能判断"？
- [ ] 是否需要在生成结果中展示AI是如何判断用例类型的？
