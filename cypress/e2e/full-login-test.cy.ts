describe('完整登录流程测试', () => {
  beforeEach(() => {
    // 访问登录页面
    cy.visit('/login')
    cy.wait(1000)
  })

  it('测试完整登录流程', () => {
    // 点击账号登录tab
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)

    // 输入账号密码
    cy.get('input[placeholder*="账号"]').first().type('admin')
    cy.get('input[placeholder*="密码"]').first().type('password123')

    // 输入验证码
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        // 从localStorage获取验证码
        cy.window().then((win) => {
          const code = win.localStorage.getItem('captcha') || '1234'
          cy.log('从localStorage获取的验证码:', code)
          cy.get('input[placeholder*="验证码"]').first().type(code)
        })
      })

    // 检查登录按钮是否存在且可点击
    cy.get('button').contains('登录').should('exist').should('be.visible')

    // 监听登录请求
    cy.intercept('POST', '**/v1/auth/login').as('loginRequest')

    // 点击登录按钮
    cy.get('button').contains('登录').click()

    // 检查是否有错误提示
    cy.get('body').then((body) => {
      const errorMessage = body.find('.el-message__content').text()
      if (errorMessage) {
        cy.log('错误提示:', errorMessage)
      }
    })

    // 等待登录请求完成
    cy.wait('@loginRequest', { timeout: 10000 }).then((interception) => {
      cy.log('登录请求URL:', interception.request.url)
      cy.log('登录请求数据:', interception.request.body)
      cy.log('登录响应状态码:', interception.response?.statusCode)
      cy.log('登录响应数据:', interception.response?.body)

      // 检查响应结构
      if (interception.response) {
        expect(interception.response.statusCode).to.eq(200)
        expect(interception.response.body).to.have.property('code')
        expect(interception.response.body.code).to.eq(200)
        expect(interception.response.body).to.have.property('data')
        expect(interception.response.body.data).to.have.property('access_token')
      } else {
        cy.log('没有收到登录响应')
      }
    })

    // 等待登录完成和页面跳转
    cy.wait(5000)

    // 检查localStorage中的token
    cy.window().then((win) => {
      const token = win.localStorage.getItem('token')
      cy.log('LocalStorage中的token:', token)
      cy.log('LocalStorage中的所有数据:', win.localStorage)
      if (token === null) {
        cy.log('Token为null，检查页面是否有错误')
        cy.get('body').then((body) => {
          cy.log('页面HTML:', body.html())
        })
      }
      expect(token).to.not.be.null
      if (token) {
        expect(token).to.not.be.empty
      }
    })

    // 验证登录成功后跳转到首页
    cy.url().should('include', '/home')
    cy.contains('仪表盘')
  })
})
