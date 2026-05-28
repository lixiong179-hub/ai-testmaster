describe('手动登录测试', () => {
  it('手动登录并访问首页', () => {
    // 直接调用登录API
    cy.request({
      method: 'POST',
      url: 'http://127.0.0.1:8000/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'admin123',
      },
      headers: {
        'Content-Type': 'application/json',
      },
    }).then((response) => {
      cy.log('登录API响应状态码:', response.status)
      cy.log('登录API响应数据:', response.body)

      // 验证登录成功
      expect(response.status).to.eq(200)
      expect(response.body).to.have.property('code')
      expect(response.body.code).to.eq(200)
      expect(response.body).to.have.property('data')
      expect(response.body.data).to.have.property('access_token')

      // 设置token到localStorage
      const token = response.body.data.access_token
      cy.window().then((win) => {
        win.localStorage.setItem('token', token)
        cy.log('设置的token:', win.localStorage.getItem('token'))
      })
    })

    // 访问首页
    cy.visit('/home')
    cy.wait(2000)

    // 检查当前URL
    cy.url().then((url) => {
      cy.log('当前URL:', url)
    })

    // 验证登录成功后跳转到首页
    cy.url().should('include', '/home')
    cy.contains('仪表盘')
  })
})
