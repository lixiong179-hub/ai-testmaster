# AI分析流程优化 - 实现计划

## 任务分解与优先级

### [x] 任务1: 创建测试点提取页面
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 创建新的测试点提取页面 `src/views/case/test-point-extract.vue`
  - 实现根据需求文档自动提取测试点的功能
  - 支持测试点的编辑和管理
- **Success Criteria**:
  - 页面能够成功加载并显示
  - 能够根据上传的需求文档提取测试点
  - 支持测试点的增删改查
- **Test Requirements**:
  - `programmatic` TR-1.1: 页面能够正常加载，无404错误
  - `programmatic` TR-1.2: 能够成功调用API提取测试点
  - `human-judgment` TR-1.3: 界面布局合理，操作流畅

### [x] 任务2: 修改AI分析按钮跳转逻辑
- **Priority**: P0
- **Depends On**: 任务1
- **Description**:
  - 修改 `src/views/requirement/index.vue` 中的 `handleAnalyze` 函数
  - 将跳转目标从 `ai-generate` 改为新的测试点提取页面
  - 确保正确传递文件信息
- **Success Criteria**:
  - 点击AI分析按钮后跳转到测试点提取页面
  - 页面能够接收到正确的文件信息
- **Test Requirements**:
  - `programmatic` TR-2.1: 点击AI分析按钮后正确跳转到测试点提取页面
  - `programmatic` TR-2.2: 测试点提取页面能够接收到文件ID和项目ID

### [x] 任务3: 实现测试点提取API
- **Priority**: P0
- **Depends On**: 任务1
- **Description**:
  - 在后端添加测试点提取API端点
  - 实现根据需求文档内容提取测试点的逻辑
  - 返回结构化的测试点数据
- **Success Criteria**:
  - API能够成功接收文件ID并返回提取的测试点
  - 提取的测试点符合测试工程师的专业标准
- **Test Requirements**:
  - `programmatic` TR-3.1: API能够正常响应，返回200状态码
  - `human-judgment` TR-3.2: 提取的测试点质量高，覆盖全面

### [x] 任务4: 修改AI用例生成页面
- **Priority**: P1
- **Depends On**: 任务1, 任务2, 任务3
- **Description**:
  - 修改 `src/views/case/ai-generate.vue`
  - 支持从测试点提取页面接收测试点信息
  - 根据测试点生成测试用例
- **Success Criteria**:
  - 页面能够接收并显示测试点信息
  - 能够根据测试点生成测试用例
- **Test Requirements**:
  - `programmatic` TR-4.1: 能够接收到测试点信息
  - `programmatic` TR-4.2: 能够根据测试点生成测试用例

### [x] 任务5: 测试完整流程
- **Priority**: P1
- **Depends On**: 任务1, 任务2, 任务3, 任务4
- **Description**:
  - 测试完整的AI分析流程
  - 从需求文档上传到测试点提取，再到测试用例生成
  - 确保各环节之间的衔接顺畅
- **Success Criteria**:
  - 完整流程能够顺利执行
  - 生成的测试用例质量高
- **Test Requirements**:
  - `programmatic` TR-5.1: 完整流程无错误
  - `human-judgment` TR-5.2: 生成的测试用例符合专业标准

## 实现步骤

1. 创建测试点提取页面
2. 实现测试点提取API
3. 修改AI分析按钮跳转逻辑
4. 修改AI用例生成页面
5. 测试完整流程

## 技术要点

- 前端：Vue 3 + Element Plus
- 后端：FastAPI + SQLAlchemy
- AI集成：调用大模型API进行测试点提取和用例生成
- 数据流：需求文档 → 测试点提取 → 测试用例生成

## 预期效果

通过优化AI分析流程，使整个测试用例生成过程更加符合测试工程师的专业工作流程，提高生成的测试用例质量和覆盖率。