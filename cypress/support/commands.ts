// 登录命令
Cypress.Commands.add('login', (username = 'admin', password = 'password123') => {
  cy.visit('/')
  cy.wait(1000)
  // 点击账号登录tab
  cy.get('.el-tabs__item').contains('账号登录').click()
  cy.wait(500)

  cy.get('input[placeholder*="账号"]').should('be.visible').type(username)
  cy.get('input[placeholder*="密码"]').should('be.visible').type(password)
  cy.get('input[placeholder*="验证码"]').should('be.visible').then(() => {
    const code = localStorage.getItem('captcha') || '1234'
    cy.get('input[placeholder*="验证码"]').type(code)
  })
  cy.get('button').contains('登录').click()
  // 等待登录成功后跳转到首页
  cy.url().should('include', '/home', { timeout: 10000 })
})

// 导航到测试用例管理页面
Cypress.Commands.add('navigateToCaseManagement', () => {
  cy.get('.el-menu-item').contains('测试用例管理').click()
  cy.url().should('include', '/case')
  cy.wait(1000)
})

// 导航到AI生成用例页面
Cypress.Commands.add('navigateToAIGenerate', () => {
  cy.get('.el-menu-item').contains('测试用例管理').click()
  cy.url().should('include', '/case')
  cy.wait(500)
  cy.get('button').contains('AI生成').click()
  cy.url().should('include', '/ai-generate')
  cy.wait(1000)
})

// 导入 cypress-file-upload
import 'cypress-file-upload'
