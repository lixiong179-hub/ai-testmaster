# Cypress UI自动化测试指南

## 环境配置

### 安装依赖
```bash
# 安装Cypress（如果尚未安装）
npm install cypress --save-dev

# 验证安装
npx cypress --version
```

### 配置文件
- `cypress.config.ts` - Cypress配置文件
- `cypress/support/commands.ts` - 自定义命令
- `cypress/support/e2e.ts` - 测试支持文件

## 测试用例

### 1. 登录功能测试 (`cypress/e2e/login.cy.ts`)
- 正常登录
- 错误密码登录
- 空用户名登录
- 空密码登录

### 2. 测试用例管理功能测试 (`cypress/e2e/case-management.cy.ts`)
- 查看用例列表
- 搜索用例
- 筛选用例类型
- 分页功能
- 批量删除用例

### 3. AI生成用例功能测试 (`cypress/e2e/ai-generate.cy.ts`)
- 查看AI生成用例页面
- 生成测试用例
- 取消生成
- 保存生成的用例

## 运行测试

### 1. 打开Cypress测试运行器
```bash
npm run cypress:open
```

这将打开Cypress的图形化界面，你可以选择要运行的测试文件。

### 2. 运行所有测试
```bash
npm run cypress:run
```

这将在无头浏览器中运行所有测试，并生成测试报告。

### 3. 运行特定测试文件
```bash
npx cypress run --spec "cypress/e2e/login.cy.ts"
```

## 测试注意事项

1. **确保服务运行**：测试前确保后端服务和前端服务都已启动
   - 后端：`http://localhost:8000`
   - 前端：`http://localhost:3001`

2. **测试数据**：测试会创建和删除测试数据，请确保测试环境中没有重要数据

3. **网络环境**：AI生成测试需要网络连接，确保可以访问DeepSeek API

4. **测试时间**：AI生成测试可能需要较长时间，请耐心等待

## 测试结果

测试结果会输出到控制台，并在以下位置生成：
- `cypress/videos/` - 测试视频（如果启用）
- `cypress/screenshots/` - 测试截图（失败时）
- `cypress/results/` - 测试报告（如果配置）

## 扩展测试

如果需要添加新的测试用例：
1. 在 `cypress/e2e/` 目录下创建新的测试文件
2. 使用 `describe` 和 `it` 函数编写测试用例
3. 使用 Cypress 命令进行页面操作和断言
4. 运行测试验证功能

## 常见问题

### 1. 测试失败：无法找到元素
- 检查元素选择器是否正确
- 增加等待时间 `cy.wait()`
- 使用 `cy.get().should('be.visible')` 确保元素可见

### 2. 测试失败：网络请求失败
- 确保后端服务正在运行
- 检查API路径是否正确
- 验证认证Token是否有效

### 3. 测试失败：AI生成超时
- 增加等待时间
- 检查网络连接
- 验证DeepSeek API配置是否正确

## 示例测试执行

### 运行登录测试
```bash
npm run cypress:run -- --spec "cypress/e2e/login.cy.ts"
```

### 运行所有测试
```bash
npm run cypress:run
```
