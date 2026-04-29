# UI原型图资源管理集成 - Product Requirement Document

## Overview
- **Summary**: 在需求管理页面中，UI原型图以**作为单一资源展示，点击编辑可查看该原型项目下的所有屏幕/图片
- **Purpose**: 复用现有的批量上传功能目前将每张UI图片单独作为一个资源展示，导致列表冗余；需改为按照UI原型项目聚合展示，提升用户体验
- **Target Users**: 测试工程师、产品经理

## Goals
- 目标1：在需求管理资源列表中，UI原型图资源从 ProjectFile 迁移为 UIPrototypeProject 表读取
- 目标2：UI原型项目作为单一资源项展示在列表中，包含项目名称、屏幕总数等信息
- 目标3：点击编辑按钮后，打开专门的UI原型管理界面展示所有屏幕/图片

## Non-Goals (Out of Scope)
- 不修改现有 ProjectFile 表的结构
- 不修改其他资源类型（需求文档、API文档等）的展示方式
- 不重新开发UI原型管理功能（复用现有功能）

## Background & Context
- 现有代码库已有完整的UI原型管理系统（UIPrototypeProject + UIPrototypeScreen）
- UI原型上传功能已有完整实现（批量上传、ZIP解压、视觉解析等）
- 当前需求管理页面（resource-manage.vue）是所有资源的统一入口

## Functional Requirements
- **FR-1**: 需求管理资源列表展示UI原型项目（UIPrototypeProject）作为单一资源项
- **FR-2**: 列表展示的UI原型项包含：原型名称、屏幕数量、创建时间等信息
- **FR-3**: 点击编辑按钮时，跳转到UI原型管理界面
- **FR-4**: 批量上传UI图片时，调用UI原型上传接口而非ProjectFile上传接口
- **FR-5**: 资源类型筛选时，ui_mockup 类型展示UI原型项目而非ProjectFile的ui_mockup

## Non-Functional Requirements
- **NFR-1**: 保持当前需求管理页面的加载性能（<1秒）
- **NFR-2**: 复用现有代码，最小化改动范围
- **NFR-3**: 保持现有功能的完整性

## Constraints
- **Technical**: FastAPI + Vue3 + Element Plus + MySQL
- **Business**: 保持现有功能不变
- **Dependencies**: 现有UI原型管理模块（ui_prototype）

## Assumptions
- 现有UI原型管理接口已完善可用
- 用户理解UI原型与ProjectFile是两个独立的数据模型

## Acceptance Criteria

### AC-1: 资源列表展示UI原型项目
- **Given**: 用户已选择项目
- **When**: 用户进入需求管理页面
- **Then**: 列表中展示UI原型项目（UIPrototypeProject）作为单一资源项
- **Verification**: `programmatic`
- **Notes**: 列表项需包含：原型名称、屏幕数量、类型标签、创建时间

### AC-2: UI原型项目与其他资源类型共存展示
- **Given**: 项目中同时存在需求文档、UI原型等多种资源类型
- **When**: 用户查看资源列表
- **Then**: UI原型项目与ProjectFile资源类型正常混合展示在同一列表中
- **Verification**: `programmatic`

### AC-3: 点击编辑打开UI原型管理
- **Given**: 资源列表中有UI原型项目
- **When**: 用户点击UI原型项目的编辑按钮
- **Then**: 跳转到专门的UI原型管理页面，展示该原型下所有屏幕/图片
- **Verification**: `human-judgment`

### AC-4: 批量上传UI图片创建UI原型项目
- **Given**: 用户在需求管理页面选择资源类型为"UI原型图"并上传多张图片
- **When**: 用户填写资源名称并提交
- **Then**: 系统创建UIPrototypeProject和对应的UIPrototypeScreen记录
- **Verification**: `programmatic`

### AC-5: 资源类型筛选工作正常
- **Given**: 资源列表有UI原型项目
- **When**: 用户选择类型筛选为"UI原型图"
- **Then**: 只展示UI原型项目
- **Verification**: `programmatic`

## Open Questions
- [ ] UI原型管理页面是否需要新建，还是直接复用现有界面？
