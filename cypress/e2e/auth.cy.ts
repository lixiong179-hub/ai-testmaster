/**
 * 认证套件：覆盖 UI 登录、API 登录、错误分支
 * 合并来源：login.cy.ts + api-login-test.cy.ts
 */
describe('认证套件', () => {
  const API_BASE = 'http://127.0.0.1:8000'

  const prepareCaptcha = () => {
    cy.request('GET', `${API_BASE}/api/v1/auth/captcha/generate`).then(
      (captchaResponse) => {
        const captcha = captchaResponse.body.data || {}
        cy.intercept('GET', '**/api/v1/auth/captcha/generate', {
          statusCode: 200,
          body: {
            code: 200,
            data: {
              captcha_id: captcha.captcha_id,
              code: captcha.code,
            },
          },
        }).as('captchaForLogin')
        cy.reload()
        cy.wait('@captchaForLogin')
        cy.wrap(captcha.code).as('captchaCode')
      }
    )
  }

  beforeEach(() => {
    cy.visit('/')
    cy.wait(1000)
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
  })

  // ===== UI 登录测试 =====
  it('UI 正常登录', () => {
    cy.login()
    cy.url().should('include', '/home')
  })

  it('UI 错误密码登录', () => {
    prepareCaptcha()
    cy.intercept('POST', '**/api/v1/auth/login').as('loginRequest')
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
    cy.get('input[placeholder*="账号"]').first().type('admin')
    cy.get('input[placeholder*="密码"]').first().type('wrongpassword')
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        cy.get('@captchaCode').then((code) => {
          cy.get('input[placeholder*="验证码"]').first().type(String(code))
        })
      })
    cy.get('button').contains('登录').click()
    cy.wait('@loginRequest').its('response.statusCode').should('eq', 401)
    cy.get('.el-message__content', { timeout: 10000 }).should('be.visible')
  })

  it('UI 空用户名登录', () => {
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
    cy.get('input[placeholder*="密码"]').first().type('admin123')
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        const code = localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })
    cy.get('button').contains('登录').click()
    cy.contains('请输入账号').should('exist')
  })

  it('UI 空密码登录', () => {
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
    cy.get('input[placeholder*="账号"]').first().type('admin')
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        const code = localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })
    cy.get('button').contains('登录').click()
    cy.contains('请输入密码').should('exist')
  })

  // ===== API 登录测试 =====
  it('API 正常登录返回 token', () => {
    cy.request({
      method: 'POST',
      url: `${API_BASE}/api/v1/auth/login`,
      body: { username: 'admin', password: 'admin123' },
      headers: { 'Content-Type': 'application/json' },
    }).then((response) => {
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      expect(response.body.data).to.have.property('access_token')
      expect(response.body.data.access_token).to.not.be.empty
    })
  })

  it('API 错误密码返回 4xx', () => {
    cy.request({
      method: 'POST',
      url: `${API_BASE}/api/v1/auth/login`,
      body: { username: 'admin', password: 'wrongpassword' },
      headers: { 'Content-Type': 'application/json' },
      failOnStatusCode: false,
    }).then((response) => {
      expect(response.status).to.be.oneOf([400, 401])
    })
  })
})
