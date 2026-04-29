# UI原型图版本选择优化 - The Implementation Plan (Decomposed and Prioritized Task List)

## [x] Task 1: 创建 UI 原型图相关的前端 API 接口
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 在 src/api/ 目录下创建 uiPrototype.ts 文件
  - 定义相关的 TypeScript 类型
  - 封装获取原型项目列表、获取屏幕列表等 API 调用
- **Acceptance Criteria Addressed**: [AC-1, AC-2]
- **Test Requirements**:
  - `programmatic` TR-1.1: API 类型定义完整且正确
  - `programmatic` TR-1.2: API 调用方法可以正常导出和使用
- **Notes**: 参考 file.ts 的结构

## [x] Task 2: 修改 ai-generate.vue，添加 UI 原型项目（版本）选择功能
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 引入新创建的 UI 原型图 API
  - 添加原型项目（版本）下拉选择框
  - 选择项目后加载对应的原型项目列表
- **Acceptance Criteria Addressed**: [AC-1]
- **Test Requirements**:
  - `programmatic` TR-2.1: 选择项目后原型项目下拉框正确填充
  - `programmatic` TR-2.2: 可以选择不同的原型项目
- **Notes**: 保持与需求文档选择框样式一致

## [x] Task 3: 实现选择版本后展示屏幕列表预览
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 选择原型项目后，调用 API 获取该项目下的屏幕列表
  - 展示屏幕列表预览区域
  - 未选择原型项目时不显示预览区域
- **Acceptance Criteria Addressed**: [AC-2]
- **Test Requirements**:
  - `programmatic` TR-3.1: 选择原型项目后屏幕列表正确加载
  - `programmatic` TR-3.2: 未选择原型项目时预览区域隐藏
- **Notes**: 预览区域设计美观，显示缩略图和基本信息

## [ ] Task 4: 实现屏幕列表可拖拽排序功能
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 
  - 使用原生 HTML5 拖拽 API 或合适的拖拽库
  - 实现拖拽时的视觉反馈
  - 拖拽结束后更新屏幕顺序
  - 添加保存排序按钮
- **Acceptance Criteria Addressed**: [AC-3]
- **Test Requirements**:
  - `programmatic` TR-4.1: 拖拽操作流畅，有视觉反馈
  - `programmatic` TR-4.2: 拖拽后顺序正确更新
- **Notes**: 参考现有的拖拽实现代码

## [ ] Task 5: 实现点击预览图片功能
- **Priority**: P1
- **Depends On**: Task 3
- **Description**: 
  - 点击屏幕项的图片时，弹出大图预览对话框
  - 预览对话框支持关闭
  - 支持在多张图片之间导航（可选）
- **Acceptance Criteria Addressed**: [AC-4]
- **Test Requirements**:
  - `human-judgement` TR-5.1: 点击图片弹出预览对话框
  - `human-judgement` TR-5.2: 预览对话框可以正常关闭
- **Notes**: 使用 Element Plus 的 ElDialog 或 ElImage 预览组件

## [ ] Task 6: 优化页面 UI 布局
- **Priority**: P1
- **Depends On**: Task 2, Task 3, Task 4, Task 5
- **Description**: 
  - 优化各区域间距和布局
  - 统一视觉风格
  - 改进用户交互体验
- **Acceptance Criteria Addressed**: [AC-5]
- **Test Requirements**:
  - `human-judgement` TR-6.1: 页面布局美观，间距合理
  - `human-judgement` TR-6.2: 视觉层次清晰
- **Notes**: 保持与现有页面风格一致

## [x] Task 7: 完整功能测试
- **Priority**: P0
- **Depends On**: Task 1, Task 2, Task 3, Task 4, Task 5, Task 6
- **Description**: 
  - 测试所有功能是否正常工作
  - 验证用户体验
  - 修复发现的问题
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4, AC-5]
- **Test Requirements**:
  - `programmatic` TR-7.1: 所有功能正常工作
  - `human-judgement` TR-7.2: 用户体验良好
- **Notes**: 进行完整的端到端测试
