# 项目统计数据显示问题修复计划

## [x] Task 1: 分析前端项目详情页面代码
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 检查前端项目详情页面的代码，特别是显示测试用例、测试任务、测试报告和上传文件数量的部分
  - 确认前端如何获取和处理这些统计数据
  - 定位导致显示错误数据的原因
- **Success Criteria**:
  - 找到错误的数据源或处理逻辑
  - 确认正确的数据结构
- **Test Requirements**:
  - `programmatic` TR-1.1: 检查前端代码中的统计数据获取逻辑
  - `human-judgement` TR-1.2: 确认数据显示逻辑是否正确
- **Notes**: 找到问题了！前端代码中的getProjectStats函数使用了硬编码的模拟数据，而不是从后端获取实际数据

## [x] Task 2: 检查后端API返回的数据结构
- **Priority**: P1
- **Depends On**: Task 1
- **Description**:
  - 检查后端项目详情API的实现
  - 确认后端是否正确返回统计数据
  - 检查是否有默认数据或测试数据被返回
- **Success Criteria**:
  - 确认后端API返回的数据结构
  - 验证是否存在默认数据或测试数据
- **Test Requirements**:
  - `programmatic` TR-2.1: 检查后端API实现
  - `human-judgement` TR-2.2: 确认数据返回逻辑正确
- **Notes**: 后端项目详情API只返回了基本信息和文件列表，没有返回测试用例、测试任务和测试报告的统计数据

## [/] Task 3: 修复前端数据显示逻辑
- **Priority**: P0
- **Depends On**: Task 1, Task 2
- **Description**:
  - 根据后端返回的数据结构，修复前端数据显示逻辑
  - 确保前端只显示实际存在的数据
  - 修复任何硬编码或默认值的问题
- **Success Criteria**:
  - 前端能够正确显示实际的统计数据
  - 不再显示不存在的数据
- **Test Requirements**:
  - `programmatic` TR-3.1: 修复后前端能够正确显示统计数据
  - `human-judgement` TR-3.2: 新项目显示正确的空状态
- **Notes**: 确保修复不会影响其他功能

## [ ] Task 4: 验证修复是否成功
- **Priority**: P0
- **Depends On**: Task 3
- **Description**:
  - 刷新项目详情页面
  - 验证统计数据是否正确显示
  - 确认新项目不再显示不存在的数据
- **Success Criteria**:
  - 项目详情页面能够正确显示统计数据
  - 新项目显示空状态或正确的0值
  - 没有错误信息
- **Test Requirements**:
  - `programmatic` TR-4.1: 前端不再显示错误的统计数据
  - `human-judgement` TR-4.2: 项目详情页面显示完整且正确
- **Notes**: 验证修复后，确保没有引入新的问题