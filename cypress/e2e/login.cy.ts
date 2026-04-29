describe('登录功能测试', () => {
  beforeEach(() => {
    cy.visit('/')
    cy.wait(1000)
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
  })

  it('正常登录', () => {
    cy.login()
    cy.url().should('include', '/home')
  })

  it('错误密码登录', () => {
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
    cy.get('input[placeholder*="账号"]').first().type('admin')
    cy.get('input[placeholder*="密码"]').first().type('wrongpassword')
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        const code = localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })
    cy.get('button').contains('登录').click()
    cy.contains('登录失败', { timeout: 10000 }).should('exist')
  })

  it('空用户名登录', () => {
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
    cy.get('input[placeholder*="密码"]').first().type('password123')
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        const code = localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })
    cy.get('button').contains('登录').click()
    cy.contains('请输入账号').should('exist')
  })

  it('空密码登录', () => {
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
})
