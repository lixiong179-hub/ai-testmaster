# 测试用例类型可选功能 - 实现计划

## [x] Task 1: 修改前端用例类型字段为非必填
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改 src/views/case/ai-generate.vue 中的用例类型表单项，移除 required 属性
  - 更新占位文字，添加"不选择则由AI智能判断"的提示
- **Acceptance Criteria Addressed**: [AC-1]
- **Test Requirements**:
  - `programmatic` TR-1.1: 检查 el-form-item 的 required 属性已移除 ✅
  - `human-judgement` TR-1.2: 占位文字清晰提示用户可以不选择类型 ✅
- **Notes**: 第 323 行附近

## [x] Task 2: 移除前端用例类型默认值
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 修改 formData 的初始化，case_type 不再设置默认值
  - 修改 resetForm 函数，重置时 case_type 设为空或 undefined
- **Acceptance Criteria Addressed**: [AC-2]
- **Test Requirements**:
  - `programmatic` TR-2.1: 表单初始化时 formData.case_type 为空 ✅
  - `programmatic` TR-2.2: 点击重置按钮后 formData.case_type 为空 ✅
- **Notes**: 第 755 行和第 1566 行

## [x] Task 3: 修改后端 API 请求模型
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改 app/api/v1/endpoints/test_case.py 中的 AIGenerateEnhancedRequest 模型
  - 将 case_type 字段改为 Optional[str] 类型，不设置默认值
- **Acceptance Criteria Addressed**: [AC-3]
- **Test Requirements**:
  - `programmatic` TR-3.1: 检查 Pydantic 模型中 case_type 是 Optional 类型 ✅
  - `programmatic` TR-3.2: 发送不带 case_type 的请求，后端正常处理不报错 ✅
- **Notes**: 第 1332 行附近

## [x] Task 4: 修改后端生成服务，支持可选 case_type
- **Priority**: P0
- **Depends On**: Task 3
- **Description**: 
  - 修改 app/services/test_case_generation_service.py 中的生成逻辑
  - 当 case_type 未提供时，启用现有的智能判断逻辑
  - 当 case_type 提供时，覆盖智能判断结果，使用用户指定的类型
  - 修改 app/utils/ai_client.py 中的 generate_test_case_enhanced 函数
  - 修改 BatchGenerateRequest 和 SingleGenerateRequest 模型
- **Acceptance Criteria Addressed**: [AC-4, AC-5]
- **Test Requirements**:
  - `programmatic` TR-4.1: case_type 为空时，生成的用例类型由智能判断决定 ✅
  - `programmatic` TR-4.2: case_type 为 'api_automation' 时，所有用例类型都是 api_automation ✅
- **Notes**: 修改了3个文件：test_case_generation_service.py, ai_client.py, test_case.py

## [x] Task 5: 修改保存逻辑，移除默认类型覆盖
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改前端保存逻辑，当 AI 已生成 case_type 时，不使用默认值覆盖
  - 检查生成的用例是否已有 case_type，有则直接使用
- **Acceptance Criteria Addressed**: [AC-6]
- **Test Requirements**:
  - `programmatic` TR-5.1: 保存 AI 生成的用例时，用例类型与生成结果一致 ✅
  - `programmatic` TR-5.2: 只有当 AI 未返回 case_type 时，才使用默认值 ✅
- **Notes**: 修改了3处：第1430行、第1460行、第1506行
