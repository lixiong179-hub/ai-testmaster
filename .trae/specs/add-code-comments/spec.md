# 代码注释添加规范 Spec

## Why
项目代码缺乏系统性的注释，影响团队协作效率和后续功能开发。需要为项目核心代码添加结构化、详细的中文注释，帮助开发者快速理解代码逻辑、业务意图和设计决策。

## What Changes
- 为后端 Python 代码（app/ 目录）添加模块级、类级、方法级注释
- 为前端 TypeScript/Vue 代码（src/ 目录）添加模块级、函数级、组件级注释
- 注释遵循项目现有风格，使用中文编写
- 按项目架构分层，从底层到上层逐模块推进

## Impact
- Affected specs: 无破坏性变更，纯注释添加
- Affected code: app/ 和 src/ 下所有核心业务代码文件

## ADDED Requirements

### Requirement: 模块级注释
每个 Python 模块和 TypeScript/Vue 文件顶部 SHALL 添加模块级文档字符串，说明：
- 模块用途与职责
- 核心类/函数概览
- 与其他模块的依赖关系

### Requirement: 类级注释
每个类 SHALL 添加类文档字符串，说明：
- 类的职责和设计意图
- 关键属性说明
- 使用场景

### Requirement: 方法/函数级注释
公开方法 SHALL 添加文档字符串，包含：
- 功能描述（业务意图，而非代码翻译）
- Args/Returns/Raises 说明（Python 使用 Google 风格）
- 边界条件与特殊逻辑说明

### Requirement: 行内注释
复杂逻辑 SHALL 添加行内注释，说明：
- 业务原因（Why），而非代码行为（What）
- 算法思路与关键决策点
- 魔法数字的含义

### Requirement: 注释风格一致性
- Python: 使用三引号文档字符串（Google 风格），行内注释用 `#`
- TypeScript/Vue: 使用 JSDoc `/** */` 风格，行内注释用 `//`
- 所有注释使用中文

### Requirement: 按模块分批推进
按照项目架构分层，从底层到上层逐模块推进注释添加，每完成一个模块在 tasks.md 中标记完成。

## 模块划分（按项目流程从底层到上层）

### 第一层：核心基础设施 (app/core/)
- config.py - 全局配置
- constants.py - 常量枚举定义
- db_helper.py - 数据库工具
- exception.py - 异常处理
- permissions.py - 权限控制
- rate_limit.py - 限流中间件
- websocket.py - WebSocket管理

### 第二层：数据库层 (app/db/)
- database.py - 数据库连接与会话管理
- init_data.py - 初始数据
- init_simple.py - 简易初始化
- smart_sync.py - 数据库智能同步

### 第三层：数据模型层 (app/models/)
- 所有 SQLAlchemy 模型文件

### 第四层：数据模式层 (app/schemas/)
- 所有 Pydantic Schema 文件

### 第五层：数据访问层 (app/crud/)
- 所有 CRUD 操作文件

### 第六层：工具层 (app/utils/)
- AI客户端、加密、JWT、文件工具等

### 第七层：业务服务层 (app/services/)
- 核心业务逻辑服务（最大模块，需分子任务）

### 第八层：API接口层 (app/api/v1/endpoints/)
- 所有 API 端点文件

### 第九层：前端API与类型 (src/api/, src/types/)
- API 客户端模块与类型定义

### 第十层：前端状态与工具 (src/store/, src/utils/, src/composables/)
- Pinia Store、工具函数、组合式函数

### 第十一层：前端页面与组件 (src/views/, src/components/, src/layouts/)
- Vue 页面组件、布局、路由
