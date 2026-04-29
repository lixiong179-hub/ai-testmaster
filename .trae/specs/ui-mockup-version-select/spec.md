# UI原型图版本选择优化 - Product Requirement Document

## Overview
- **Summary**: 优化 AI 生成测试用例页面中的 UI 原型图选择功能，添加版本下拉选择框，选择后展示可拖拽排序的预览列表，支持点击预览图片，并优化页面 UI 布局。
- **Purpose**: 提升用户体验，让用户可以更方便地选择和管理不同版本的 UI 原型图，直观地预览和调整图片顺序。
- **Target Users**: 测试工程师、产品经理

## Goals
- 添加 UI 原型图版本下拉选择框
- 选择版本后展示排序预览区域
- 实现可拖拽排序功能
- 支持点击预览图片
- 优化页面 UI 布局，提升美观度

## Non-Goals (Out of Scope)
- 不涉及后端 API 的修改（已有的 API 已满足需求）
- 不修改其他页面的功能

## Background & Context
- 后端已有 UIPrototypeProject 和 UIPrototypeScreen 模型，支持原型项目（版本）和屏幕管理
- 前端已有基础的 UI 原型图选择功能，但缺少版本选择和更好的预览体验
- 使用 Vue 3 + Element Plus 技术栈

## Functional Requirements
- **FR-1**: 添加 UI 原型图版本下拉选择框，类似于需求文档选择
- **FR-2**: 选择版本后，下方才展示排序预览区域
- **FR-3**: 排序预览区域支持拖拽排序
- **FR-4**: 支持点击图片进行预览
- **FR-5**: 优化页面 UI 布局，使其更美观

## Non-Functional Requirements
- **NFR-1**: 页面响应流畅，拖拽操作无明显卡顿
- **NFR-2**: 图片预览加载快速
- **NFR-3**: 保持与现有页面风格一致

## Constraints
- **Technical**: 使用 Vue 3 + Element Plus 技术栈
- **Business**: 必须与现有功能兼容
- **Dependencies**: 后端 API 已存在（/api/v1/ui-prototype/project/list, /api/v1/ui-prototype/screens）

## Assumptions
- 后端 API 接口工作正常
- 已有 UI 原型图数据可供测试
- 用户已选择项目

## Acceptance Criteria

### AC-1: UI 原型图版本下拉选择框
- **Given**: 用户已选择项目且该项目有 UI 原型图版本
- **When**: 用户进入 AI 生成测试用例页面
- **Then**: 显示 UI 原型图版本下拉选择框，可选择不同的原型项目（版本）
- **Verification**: `programmatic`
- **Notes**: 下拉框样式与需求文档选择框保持一致

### AC-2: 选择版本后展示排序预览
- **Given**: 用户已选择项目
- **When**: 用户选择一个 UI 原型图版本
- **Then**: 下方展示该版本下所有屏幕的排序预览
- **Verification**: `programmatic`
- **Notes**: 未选择版本时不显示预览区域

### AC-3: 可拖拽排序
- **Given**: 排序预览区域已展示
- **When**: 用户拖拽某个屏幕项到新位置
- **Then**: 屏幕项顺序更新，并可以保存新的排序
- **Verification**: `programmatic`
- **Notes**: 拖拽交互流畅，有视觉反馈

### AC-4: 点击预览图片
- **Given**: 排序预览区域已展示
- **When**: 用户点击某个屏幕项的预览图片
- **Then**: 弹出大图预览对话框，展示完整图片
- **Verification**: `human-judgment`
- **Notes**: 预览对话框支持关闭和导航

### AC-5: UI 布局优化
- **Given**: AI 生成测试用例页面
- **When**: 用户查看页面
- **Then**: 页面布局美观，各区域间距合理，视觉层次清晰
- **Verification**: `human-judgment`
- **Notes**: 保持与现有设计风格一致

## Open Questions
- [ ] 无
