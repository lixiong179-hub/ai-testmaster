describe('登录功能测试', () => {
  it('测试登录API并访问首页', () => {
    // 直接调用登录API
    cy.request({
      method: 'POST',
      url: 'http://localhost:8000/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'password123',
      },
      headers: {
        'Content-Type': 'application/json',
      },
    }).then((response) => {
      cy.log('登录API响应:', response)
      cy.log('响应状态码:', response.status)
      cy.log('响应数据:', response.body)

      // 验证登录成功
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      expect(response.body.data).to.have.property('access_token')

      // 设置token到localStorage
      const token = response.body.data.access_token
      cy.window().then((win) => {
        win.localStorage.setItem('token', token)
        cy.log('设置的token:', win.localStorage.getItem('token'))
      })
    })

    // 访问首页
    cy.visit('http://localhost:3000/home')
    cy.wait(2000)

    // 检查当前URL
    cy.url().then((url) => {
      cy.log('当前URL:', url)
    })

    // 检查页面内容
    cy.get('body').then((body) => {
      cy.log('页面内容:', body.text())
    })

    // 验证登录成功后跳转到首页
    cy.url().should('include', '/home')
    cy.contains('仪表盘')
  })
})
