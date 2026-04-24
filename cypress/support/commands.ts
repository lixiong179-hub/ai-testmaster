type Credentials = {
  username: string
  password: string
}

const getAdminCredentials = (
  username = Cypress.env('adminUsername') || 'admin',
  password = Cypress.env('adminPassword') || 'admin123'
): Credentials => ({
  username,
  password,
})

declare global {
  namespace Cypress {
    interface Chainable {
      login(username?: string, password?: string): Chainable<void>
      loginByApi(username?: string, password?: string): Chainable<void>
      navigateToCaseManagement(): Chainable<void>
      navigateToAIGenerate(): Chainable<void>
    }
  }
}

// 登录命令
Cypress.Commands.add('login', (username, password) => {
  const credentials = getAdminCredentials(username, password)
  return cy
    .visit('/')
    .wait(1000)
  // 点击账号登录tab
    .get('.el-tabs__item')
    .contains('账号登录')
    .click()
    .wait(500)
    .get('input[placeholder*="账号"]')
    .filter(':visible')
    .first()
    .type(credentials.username)
    .get('input[placeholder*="密码"]')
    .filter(':visible')
    .first()
    .type(credentials.password)
    .get('input[placeholder*="验证码"]')
    .filter(':visible')
    .first()
    .then(() => {
      const code = localStorage.getItem('captcha') || '1234'
      return cy.get('input[placeholder*="验证码"]').filter(':visible').first().type(code)
    })
    .get('button')
    .contains('登录')
    .click()
    // 等待登录成功后跳转到首页
    .url()
    .should('include', '/home', { timeout: 10000 })
})

// API登录命令，避免页面验证码流程影响回归稳定性
Cypress.Commands.add('loginByApi', (username, password) => {
  const credentials = getAdminCredentials(username, password)
  const apiUrl = Cypress.env('apiUrl') || 'http://127.0.0.1:8000'

  return cy.request({
    method: 'POST',
    url: `${apiUrl}/api/v1/auth/login`,
    body: credentials,
  }).then((loginResponse) => {
    expect(loginResponse.status).to.eq(200)
    const token = loginResponse.body.data.access_token

    cy.visit('/login')
    cy.window().then((win) => {
      win.localStorage.setItem('token', token)
    })
  })
})

// 导航到测试用例管理页面
Cypress.Commands.add('navigateToCaseManagement', () => {
  return cy.get('.el-menu-item').contains('测试用例管理').click().url().should('include', '/case').wait(1000)
})

// 导航到AI生成用例页面
Cypress.Commands.add('navigateToAIGenerate', () => {
  return cy
    .get('.el-menu-item')
    .contains('测试用例管理')
    .click()
    .url()
    .should('include', '/case')
    .wait(500)
    .get('button')
    .contains('AI生成')
    .click()
    .url()
    .should('include', '/ai-generate')
    .wait(1000)
})

// 导入 cypress-file-upload
import 'cypress-file-upload'
