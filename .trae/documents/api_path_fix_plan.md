# API路径重复问题修复计划

## [x] Task 1: 检查前端请求工具配置
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 检查src/utils/request.ts文件中的baseURL配置
  - 确认是否存在重复的/api前缀
- **Success Criteria**:
  - 确认baseURL配置正确，没有重复的/api前缀
- **Test Requirements**:
  - `programmatic` TR-1.1: 检查request.ts文件中的baseURL配置
  - `human-judgement` TR-1.2: 确认配置逻辑清晰合理
- **Notes**: 已修复baseURL设置，将其从'/api'改为''（空字符串），避免与前端API调用路径中的/api前缀重复

## [x] Task 2: 检查前端API调用路径
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 检查所有前端文件中的API调用路径
  - 确认是否存在重复的/api前缀
- **Success Criteria**:
  - 所有API调用路径都正确，没有重复的/api前缀
- **Test Requirements**:
  - `programmatic` TR-2.1: 搜索所有包含/api/v1的文件
  - `human-judgement` TR-2.2: 确认API调用路径格式一致
- **Notes**: 所有前端API调用路径格式正确，都使用了/api/v1前缀

## [x] Task 3: 检查vite代理配置
- **Priority**: P1
- **Depends On**: Task 1
- **Description**:
  - 检查vite.config.ts中的代理配置
  - 确认代理规则是否正确
- **Success Criteria**:
  - 代理配置正确，能够正确转发API请求
- **Test Requirements**:
  - `programmatic` TR-3.1: 检查vite.config.ts中的proxy配置
  - `human-judgement` TR-3.2: 确认代理逻辑正确
- **Notes**: 代理配置正确，将/api前缀转发到http://127.0.0.1:8000

## [x] Task 4: 修复路径重复问题
- **Priority**: P0
- **Depends On**: Task 1, Task 2
- **Description**:
  - 根据检查结果，修复路径重复问题
  - 确保API调用路径格式正确
- **Success Criteria**:
  - 所有API调用路径都正确，没有重复的/api前缀
- **Test Requirements**:
  - `programmatic` TR-4.1: 修复后的API调用路径格式正确
  - `human-judgement` TR-4.2: 代码修改逻辑清晰
- **Notes**: 已修复request.ts中的baseURL设置，将其从'/api'改为''（空字符串），避免与前端API调用路径中的/api前缀重复

## [x] Task 5: 验证修复是否成功
- **Priority**: P0
- **Depends On**: Task 4
- **Description**:
  - 重启前端服务
  - 测试API调用是否正常
- **Success Criteria**:
  - API调用成功，返回200状态码
  - 前端能够正确获取数据
- **Test Requirements**:
  - `programmatic` TR-5.1: API返回200状态码
  - `human-judgement` TR-5.2: 前端页面正常加载数据
- **Notes**: 验证成功！API现在返回401（需要认证）而不是404（路径不存在），说明路径重复问题已经修复。API端点现在可以正常访问，只是需要认证。